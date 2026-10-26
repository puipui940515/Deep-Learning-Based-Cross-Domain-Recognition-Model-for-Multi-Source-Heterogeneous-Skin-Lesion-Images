from __future__ import annotations

import torch
from torch import nn


class MLPBaseline(nn.Module):
    def __init__(self, image_size: int = 64, num_classes: int = 7) -> None:
        super().__init__()
        input_dim = image_size * image_size * 3
        self.network = nn.Sequential(
            nn.Flatten(),
            nn.Linear(input_dim, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(inplace=True),
            nn.Linear(256, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class SmallCNN(nn.Module):
    def __init__(self, num_classes: int = 7) -> None:
        super().__init__()
        channels = [3, 32, 64, 128, 256]
        self.features = nn.Sequential(
            *(ConvBlock(channels[i], channels[i + 1]) for i in range(4))
        )
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(256, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.pool(x).flatten(1)
        return self.classifier(x)


def build_model(name: str, image_size: int, num_classes: int = 7) -> nn.Module:
    if name == "mlp":
        return MLPBaseline(image_size=image_size, num_classes=num_classes)
    if name == "small_cnn":
        return SmallCNN(num_classes=num_classes)
    raise ValueError(f"不支援的模型：{name}")


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

