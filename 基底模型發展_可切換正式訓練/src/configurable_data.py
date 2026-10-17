from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms
from torchvision.transforms import functional as TF


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
AUDIT_ONLY_FEATURE_NAMES = {
    "laplacian_variance", "dark_fraction", "bright_fraction", "dark_border_fraction",
    "dark_corner_fraction", "aspect_ratio", "log_pixel_count",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class AspectResizePad:
    def __init__(self, size: int, padding_mode: str = "edge"):
        self.size = int(size)
        self.padding_mode = padding_mode

    def __call__(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        scale = self.size / max(width, height)
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        image = TF.resize(image, [resized_height, resized_width], antialias=True)
        left = (self.size - resized_width) // 2
        right = self.size - resized_width - left
        top = (self.size - resized_height) // 2
        bottom = self.size - resized_height - top
        return TF.pad(image, [left, top, right, bottom], padding_mode=self.padding_mode)


class AddGaussianNoise:
    def __init__(self, probability: float, standard_deviation: float):
        self.probability = float(probability)
        self.standard_deviation = float(standard_deviation)

    def __call__(self, tensor: torch.Tensor) -> torch.Tensor:
        if random.random() >= self.probability:
            return tensor
        return tensor + torch.randn_like(tensor) * self.standard_deviation


def build_transform(config: dict, train: bool):
    image_size = int(config["input"]["image_size"])
    input_config = config["input"]
    augmentation = config["augmentation"]
    if input_config["normalization"] != "imagenet":
        raise ValueError("目前正式流程只支援 imagenet normalization")
    resize = (
        AspectResizePad(image_size, input_config["pad_mode"])
        if input_config["preserve_aspect_ratio"]
        else transforms.Resize((image_size, image_size))
    )
    operations: list = [resize]
    if train:
        if augmentation["horizontal_flip"]:
            operations.append(transforms.RandomHorizontalFlip())
        if augmentation["vertical_flip"]:
            operations.append(transforms.RandomVerticalFlip())
        if float(augmentation["rotation_degrees"]) > 0 or float(augmentation["translation_fraction"]) > 0:
            operations.append(transforms.RandomAffine(
                degrees=float(augmentation["rotation_degrees"]),
                translate=[float(augmentation["translation_fraction"])] * 2,
                scale=tuple(float(value) for value in augmentation["scale_range"]),
            ))
        if augmentation["color_jitter"]:
            operations.append(transforms.RandomApply([transforms.ColorJitter(
                brightness=float(augmentation["brightness"]),
                contrast=float(augmentation["contrast"]),
                saturation=float(augmentation["saturation"]),
                hue=float(augmentation["hue"]),
            )], p=0.80))
        if augmentation["gaussian_blur"]:
            operations.append(transforms.RandomApply(
                [transforms.GaussianBlur(3, sigma=(0.1, 1.5))],
                p=float(augmentation["gaussian_blur_probability"]),
            ))
        gray_probability = float(augmentation["grayscale_probability"])
        if gray_probability > 0:
            operations.append(transforms.RandomGrayscale(p=gray_probability))
        contrast_probability = float(augmentation["autocontrast_probability"])
        if contrast_probability > 0:
            operations.append(transforms.RandomAutocontrast(p=contrast_probability))
    operations.extend([transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)])
    if train and augmentation["gaussian_noise"]:
        operations.append(AddGaussianNoise(
            augmentation["gaussian_noise_probability"], augmentation["gaussian_noise_std"]
        ))
    if train and augmentation["random_erasing"]:
        operations.append(transforms.RandomErasing(
            p=float(augmentation["random_erasing_probability"]),
            scale=tuple(float(value) for value in augmentation["random_erasing_scale"]),
            ratio=(0.3, 3.3), value="random",
        ))
    return transforms.Compose(operations)


def load_feature_cache(path: Path) -> tuple[dict[str, dict[str, str]], tuple[str, ...]]:
    rows = read_csv(path)
    if not rows:
        raise RuntimeError(f"顯式特徵快取為空：{path}")
    metadata = {"record_id", "source", "split", "label", "feature_version"}
    feature_names = tuple(
        name for name in rows[0]
        if name not in metadata and name not in AUDIT_ONLY_FEATURE_NAMES
    )
    cache = {row["record_id"]: row for row in rows}
    return cache, feature_names


def fit_feature_standardizer(
    rows: list[dict[str, str]], cache: dict[str, dict[str, str]], feature_names: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray([
        [float(cache[row["record_id"]][name]) for name in feature_names]
        for row in rows
    ], dtype=np.float32)
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std = np.where(std < 1e-6, 1.0, std)
    return mean.astype(np.float32), std.astype(np.float32)


class ConfigurableDataset(Dataset):
    def __init__(
        self,
        project: Path,
        rows: list[dict[str, str]],
        config: dict,
        train: bool,
        feature_cache: dict[str, dict[str, str]] | None,
        feature_names: tuple[str, ...],
        feature_mean: np.ndarray,
        feature_std: np.ndarray,
    ):
        self.project = project
        self.rows = rows
        self.config = config
        self.transform = build_transform(config, train)
        self.feature_cache = feature_cache
        self.feature_names = feature_names
        self.feature_mean = feature_mean
        self.feature_std = feature_std
        site_classes = config["model"]["site_auxiliary"]["classes"]
        source_classes = config["model"]["source_adversarial"]["classes"]
        self.site_to_id = {name: index for index, name in enumerate(site_classes)}
        self.source_to_id = {name: index for index, name in enumerate(source_classes)}

    def __len__(self):
        return len(self.rows)

    def _roi(self, image: Image.Image, row: dict[str, str]) -> Image.Image:
        roi = self.config["data"]["roi"]
        if not roi["enabled"]:
            return image
        if roi["mode"] != "manifest_bbox":
            raise ValueError(f"不支援的 ROI mode：{roi['mode']}")
        columns = roi["columns"]
        if any(not row.get(column) for column in columns):
            raise RuntimeError(f"已啟用 ROI，但 {row['record_id']} 缺少 bbox")
        xmin, ymin, xmax, ymax = [float(row[column]) for column in columns]
        if roi["coordinate_format"] == "normalized_xyxy":
            width, height = image.size
            xmin, xmax = xmin * width, xmax * width
            ymin, ymax = ymin * height, ymax * height
        if not (xmax > xmin and ymax > ymin):
            raise RuntimeError(f"無效 bbox：{row['record_id']}")
        return image.crop((round(xmin), round(ymin), round(xmax), round(ymax)))

    def __getitem__(self, index: int):
        row = self.rows[index]
        with Image.open(self.project / row["image_path"]) as opened:
            image = self._roi(opened.convert("RGB"), row)
            image_tensor = self.transform(image)
        if self.feature_cache is None:
            explicit = torch.empty(0, dtype=torch.float32)
        else:
            cached = self.feature_cache[row["record_id"]]
            values = np.asarray([float(cached[name]) for name in self.feature_names], dtype=np.float32)
            explicit = torch.from_numpy((values - self.feature_mean) / self.feature_std)
        site = self.site_to_id.get(row.get("anatomical_site_canonical_code", ""), -100)
        source = self.source_to_id[row["source"]]
        return image_tensor, explicit, int(row["label"]), site, source, row["record_id"], row["source"]

