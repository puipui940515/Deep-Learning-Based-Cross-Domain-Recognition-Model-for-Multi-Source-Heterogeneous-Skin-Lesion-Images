from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image
import torch
from torch.utils.data import Dataset, WeightedRandomSampler
from torchvision import transforms

from .site_labels import build_within_diagnosis_site_weights


def build_transform(image_size: int, train: bool):
    if train:
        ops = [
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomChoice([transforms.RandomRotation((x, x)) for x in (0, 90, 180, 270)]),
            transforms.RandomResizedCrop(image_size, scale=(0.8, 1.0), ratio=(0.9, 1.1)),
        ]
    else:
        ops = [transforms.Resize((image_size, image_size))]
    ops += [transforms.ToTensor(), transforms.Normalize([0.5] * 3, [0.5] * 3)]
    return transforms.Compose(ops)


class V10NullControlDataset(Dataset):
    """四分支接收相同 RGB tensor；每筆另外攜帶部位標籤。"""

    def __init__(self, manifest_path, dataset_root, split: str, transform):
        if split == "test":
            raise ValueError("v14 前禁止讀取 test split")
        self.dataset_root = Path(dataset_root)
        self.transform = transform
        with Path(manifest_path).open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [row for row in csv.DictReader(handle) if row["split"] == split]
        if not self.rows:
            raise ValueError(f"manifest 中沒有 split={split}")
        required = {"site_group", "site_label", "site_known"}
        missing = required.difference(self.rows[0])
        if missing:
            raise ValueError(f"manifest 缺少部位標籤欄位：{sorted(missing)}")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(self.dataset_root / row["image_path"]) as image:
            rgb = self.transform(image.convert("RGB"))
        return (rgb, rgb, rgb, rgb), int(row["label"]), row["isic_id"], int(row["site_label"])


def build_site_sampler(dataset, config, generator):
    if not config.get("enabled", False):
        return None, {"enabled": False, "reason": "preserve_version_control"}
    weights, audit = build_within_diagnosis_site_weights(
        dataset.rows,
        power=float(config.get("power", 0.5)),
        max_weight=float(config.get("max_weight", 4.0)),
        min_group_count=int(config.get("min_group_count", 10)),
    )
    sampler = WeightedRandomSampler(
        torch.as_tensor(weights, dtype=torch.double),
        num_samples=len(dataset),
        replacement=True,
        generator=generator,
    )
    return sampler, {"enabled": True, **audit}
