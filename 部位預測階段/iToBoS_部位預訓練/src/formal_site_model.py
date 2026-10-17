from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch import nn
from torch.utils.data import Dataset
from torchvision import transforms
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny


def map_body_part(raw: str) -> str | None:
    value = raw.strip().lower()
    if value == "torso":
        return "torso"
    for side in ("left", "right"):
        if value.startswith(f"{side} arm"):
            return f"{side}_arm"
        if value.startswith(f"{side} leg"):
            return f"{side}_leg"
    return None


def swap_left_right(label: str) -> str:
    swaps = {
        "left_arm": "right_arm",
        "right_arm": "left_arm",
        "left_leg": "right_leg",
        "right_leg": "left_leg",
    }
    return swaps.get(label, label)


def stratified_split(rows, validation_fraction: float, seed: int):
    groups = defaultdict(list)
    for row in rows:
        groups[row["site"]].append(row)
    rng = random.Random(seed)
    training, validation = [], []
    for site in sorted(groups):
        group = sorted(groups[site], key=lambda item: item["image_id"])
        rng.shuffle(group)
        count = max(1, round(len(group) * validation_fraction))
        validation.extend(group[:count])
        training.extend(group[count:])
    rng.shuffle(training)
    validation.sort(key=lambda item: item["image_id"])
    return training, validation


def shuffled_labels(rows, seed: int):
    copied = [dict(row) for row in rows]
    labels = [row["site"] for row in copied]
    random.Random(seed + 100_003).shuffle(labels)
    for row, label in zip(copied, labels):
        row["site"] = label
    return copied


def build_transform(config: dict, training: bool):
    size = int(config["image_size"])
    if training:
        operations = [
            transforms.RandomRotation(float(config["rotation_degrees"])),
            transforms.RandomResizedCrop(
                size,
                scale=tuple(config["random_resized_crop_scale"]),
                ratio=(0.9, 1.1),
            ),
            transforms.ColorJitter(
                brightness=config["color_jitter"],
                contrast=config["color_jitter"],
                saturation=config["color_jitter"],
            ),
        ]
    else:
        operations = [transforms.Resize((size, size))]
    operations.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(
                [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
            ),
        ]
    )
    return transforms.Compose(operations)


class SiteDataset(Dataset):
    def __init__(self, rows, images_dir: Path, site_classes, transform, training, flip_probability):
        self.rows = rows
        self.images_dir = Path(images_dir)
        self.site_to_target = {name: index for index, name in enumerate(site_classes)}
        self.transform = transform
        self.training = training
        self.flip_probability = float(flip_probability)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        label = row["site"]
        with Image.open(self.images_dir / f"{row['image_id']}.png") as source:
            image = source.convert("RGB")
        if self.training and random.random() < self.flip_probability:
            image = ImageOps.mirror(image)
            label = swap_left_right(label)
        return self.transform(image), self.site_to_target[label], row["image_id"]


def build_model(num_classes: int, pretrained: bool = True):
    weights = ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
    model = convnext_tiny(weights=weights)
    model.classifier[2] = nn.Linear(model.classifier[2].in_features, num_classes)
    return model


def parameter_groups_with_layer_decay(model, base_lr: float, weight_decay: float, decay: float):
    max_depth = 9
    groups = {}
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if name.startswith("features."):
            try:
                depth = int(name.split(".")[1]) + 1
            except (ValueError, IndexError):
                depth = 1
        else:
            depth = max_depth
        learning_rate = base_lr * (decay ** (max_depth - depth))
        no_decay = parameter.ndim == 1 or name.endswith(".bias")
        key = (depth, no_decay)
        groups.setdefault(
            key,
            {
                "params": [],
                "lr": learning_rate,
                "weight_decay": 0.0 if no_decay else weight_decay,
            },
        )["params"].append(parameter)
    return list(groups.values())


def weighted_cross_entropy(rows, site_classes, device):
    counts = Counter(row["site"] for row in rows)
    reference = max(counts.values())
    values = [math.sqrt(reference / counts[name]) for name in site_classes]
    mean = sum(values) / len(values)
    values = [value / mean for value in values]
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(values, dtype=torch.float32, device=device)
    )
    return criterion, counts, values


def classification_metrics(targets, predictions, site_classes):
    targets = np.asarray(targets)
    predictions = np.asarray(predictions)
    recalls, f1_values, per_class = [], [], {}
    matrix = np.zeros((len(site_classes), len(site_classes)), dtype=int)
    for target, prediction in zip(targets, predictions):
        matrix[target, prediction] += 1
    for index, name in enumerate(site_classes):
        true_positive = int(matrix[index, index])
        false_negative = int(matrix[index, :].sum() - true_positive)
        false_positive = int(matrix[:, index].sum() - true_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        precision = true_positive / max(1, true_positive + false_positive)
        f1 = 2 * precision * recall / max(1e-12, precision + recall)
        recalls.append(recall)
        f1_values.append(f1)
        per_class[name] = {
            "recall": recall,
            "precision": precision,
            "f1": f1,
            "support": int(matrix[index, :].sum()),
        }
    return {
        "accuracy": float((targets == predictions).mean()),
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1_values)),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }


def seed_worker(_worker_id):
    worker_seed = torch.initial_seed() % (2**32)
    np.random.seed(worker_seed)
    random.seed(worker_seed)


def count_parameters(model):
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)

