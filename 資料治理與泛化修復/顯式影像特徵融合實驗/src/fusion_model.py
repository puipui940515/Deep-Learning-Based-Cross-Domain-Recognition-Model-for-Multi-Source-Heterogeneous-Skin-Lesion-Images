from __future__ import annotations

import torch
from torch import nn
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny


class ExplicitFeatureMLP(nn.Module):
    def __init__(self, num_features: int, num_classes: int = 7):
        super().__init__()
        self.network = nn.Sequential(
            nn.LayerNorm(num_features),
            nn.Linear(num_features, 64),
            nn.GELU(),
            nn.Dropout(0.20),
            nn.Linear(64, 32),
            nn.GELU(),
            nn.Dropout(0.10),
            nn.Linear(32, num_classes),
        )

    def forward(self, _images: torch.Tensor, explicit_features: torch.Tensor) -> torch.Tensor:
        return self.network(explicit_features)


class ConvNeXtExplicitFusion(nn.Module):
    def __init__(self, num_features: int, num_classes: int = 7, pretrained: bool = True):
        super().__init__()
        weights = ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
        self.image_backbone = convnext_tiny(weights=weights)
        image_dim = self.image_backbone.classifier[2].in_features
        self.image_backbone.classifier[2] = nn.Identity()
        self.explicit_branch = nn.Sequential(
            nn.LayerNorm(num_features),
            nn.Linear(num_features, 64),
            nn.GELU(),
            nn.Dropout(0.20),
            nn.Linear(64, 32),
            nn.GELU(),
        )
        self.fusion_head = nn.Sequential(
            nn.LayerNorm(image_dim + 32),
            nn.Dropout(0.25),
            nn.Linear(image_dim + 32, num_classes),
        )

    def forward(self, images: torch.Tensor, explicit_features: torch.Tensor) -> torch.Tensor:
        image_features = self.image_backbone(images)
        side_features = self.explicit_branch(explicit_features)
        return self.fusion_head(torch.cat([image_features, side_features], dim=1))


def build_experiment_model(mode: str, num_features: int, num_classes: int, pretrained: bool):
    if mode == "feature_only":
        return ExplicitFeatureMLP(num_features, num_classes)
    if mode == "fusion":
        return ConvNeXtExplicitFusion(num_features, num_classes, pretrained)
    raise ValueError(f"未知模式：{mode}")

