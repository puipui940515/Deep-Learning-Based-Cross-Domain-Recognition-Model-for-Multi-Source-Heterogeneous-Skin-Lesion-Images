from __future__ import annotations

from torch import nn
from torchvision.models import (
    ConvNeXt_Tiny_Weights, ResNet18_Weights, convnext_tiny, resnet18,
)


def build_model(name: str, pretrained: bool, num_classes: int = 7):
    if name == "resnet18":
        model = resnet18(weights=ResNet18_Weights.DEFAULT if pretrained else None)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        return model
    if name == "convnext_tiny":
        model = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None)
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, num_classes)
        return model
    raise ValueError(f"不支援模型：{name}")


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
        lr = base_lr * (decay ** (max_depth - depth))
        no_decay = parameter.ndim == 1 or name.endswith(".bias")
        key = (depth, no_decay)
        groups.setdefault(key, {"params": [], "lr": lr, "weight_decay": 0.0 if no_decay else weight_decay})["params"].append(parameter)
    return list(groups.values())


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

