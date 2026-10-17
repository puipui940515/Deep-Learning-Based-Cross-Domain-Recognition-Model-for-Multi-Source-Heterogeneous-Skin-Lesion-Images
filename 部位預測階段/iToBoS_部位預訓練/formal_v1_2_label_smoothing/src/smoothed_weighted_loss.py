from __future__ import annotations

import math
from collections import Counter

import torch
from torch import nn


def weighted_cross_entropy(rows, site_classes, device, label_smoothing: float = 0.05):
    counts = Counter(row["site"] for row in rows)
    reference = max(counts.values())
    values = [math.sqrt(reference / counts[name]) for name in site_classes]
    mean = sum(values) / len(values)
    values = [value / mean for value in values]
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(values, dtype=torch.float32, device=device),
        label_smoothing=label_smoothing,
    )
    return criterion, counts, values


def build_loss(config: dict):
    smoothing = float(config["label_smoothing"])
    if not 0.0 <= smoothing < 1.0:
        raise ValueError("label_smoothing 必須介於 0（含）與 1（不含）")

    def factory(rows, site_classes, device):
        return weighted_cross_entropy(
            rows,
            site_classes,
            device,
            label_smoothing=smoothing,
        )

    return factory

