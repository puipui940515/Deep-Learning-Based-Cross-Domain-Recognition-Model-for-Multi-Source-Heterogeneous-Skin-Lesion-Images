from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


def build_transform(image_size: int, train: bool):
    if train:
        operations = [
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(25),
            transforms.RandomResizedCrop(image_size, scale=(0.8, 1.0), ratio=(0.9, 1.1)),
            transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
        ]
    else:
        operations = [transforms.Resize((image_size, image_size))]
    operations.extend([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    return transforms.Compose(operations)


class SiteDataset(Dataset):
    def __init__(self, manifest_path, dataset_root, split: str, transform, known_sites) -> None:
        if split == "test":
            raise ValueError("test split 在正式最終評估前維持封存")
        self.dataset_root = Path(dataset_root)
        self.transform = transform
        self.site_to_target = {name: index for index, name in enumerate(known_sites)}
        with Path(manifest_path).open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [
                row for row in csv.DictReader(handle)
                if row["split"] == split and row["site_group"] in self.site_to_target
            ]
        if not self.rows:
            raise ValueError(f"manifest 中沒有可用的 split={split}")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(self.dataset_root / row["image_path"]) as image:
            image = image.convert("RGB")
        return (
            self.transform(image),
            self.site_to_target[row["site_group"]],
            row["isic_id"],
        )

    def class_counts(self):
        counts = Counter(self.site_to_target[row["site_group"]] for row in self.rows)
        return [counts[index] for index in range(len(self.site_to_target))]
