from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


def build_transform(image_size: int, train: bool):
    if train:
        ops = [
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomChoice([
                transforms.RandomRotation((0, 0)), transforms.RandomRotation((90, 90)),
                transforms.RandomRotation((180, 180)), transforms.RandomRotation((270, 270)),
            ]),
            transforms.RandomResizedCrop(image_size, scale=(0.8, 1.0), ratio=(0.9, 1.1)),
        ]
    else:
        ops = [transforms.Resize((image_size, image_size))]
    # 與第一階段目前實作一致，避免 v5 另引入 normalization 變因。
    ops.extend([transforms.ToTensor(), transforms.Normalize([0.5] * 3, [0.5] * 3)])
    return transforms.Compose(ops)


class ManifestDataset(Dataset):
    def __init__(self, manifest_path, dataset_root, split: str, transform) -> None:
        self.dataset_root = Path(dataset_root)
        self.transform = transform
        with Path(manifest_path).open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [r for r in csv.DictReader(handle) if r["split"] == split]
        if not self.rows:
            raise ValueError(f"manifest 中沒有 split={split}")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(self.dataset_root / row["image_path"]) as image:
            image = image.convert("RGB")
        return self.transform(image), int(row["label"]), row["isic_id"]

