from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms
from torchvision.transforms import functional as TF


class TranslatePixels:
    def __init__(self, pixels: int = 8) -> None:
        self.pixels = pixels

    def __call__(self, image):
        return TF.affine(image, angle=0, translate=[self.pixels, 0], scale=1.0, shear=[0.0, 0.0])


def build_transform(image_size: int, train: bool, augmentation: bool, translate_pixels: int = 0):
    operations = []
    if train and augmentation:
        operations.extend([
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomChoice([
                transforms.RandomRotation((0, 0)),
                transforms.RandomRotation((90, 90)),
                transforms.RandomRotation((180, 180)),
                transforms.RandomRotation((270, 270)),
            ]),
            transforms.RandomResizedCrop(image_size, scale=(0.8, 1.0), ratio=(0.9, 1.1)),
        ])
    else:
        operations.append(transforms.Resize((image_size, image_size)))
    if translate_pixels:
        operations.append(TranslatePixels(translate_pixels))
    operations.extend([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
    ])
    return transforms.Compose(operations)


class HAM10000ManifestDataset(Dataset):
    def __init__(self, manifest_path, dataset_root, split: str, transform) -> None:
        self.dataset_root = Path(dataset_root)
        self.transform = transform
        with Path(manifest_path).open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [row for row in csv.DictReader(handle) if row["split"] == split]
        if not self.rows:
            raise ValueError(f"manifest 中沒有 split={split} 的資料")

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        path = self.dataset_root / row["image_path"]
        with Image.open(path) as image:
            image = image.convert("RGB")
        return self.transform(image), int(row["label"]), row["isic_id"]

