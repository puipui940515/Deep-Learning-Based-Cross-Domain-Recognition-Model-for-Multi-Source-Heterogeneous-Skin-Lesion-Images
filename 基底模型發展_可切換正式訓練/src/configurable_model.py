from __future__ import annotations

import torch
from torch import nn
from torchvision.models import (
    ConvNeXt_Tiny_Weights,
    ResNet18_Weights,
    convnext_tiny,
    resnet18,
)


class _GradientReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx, values: torch.Tensor, strength: float) -> torch.Tensor:
        ctx.strength = float(strength)
        return values.view_as(values)

    @staticmethod
    def backward(ctx, gradient: torch.Tensor):
        return -ctx.strength * gradient, None


def gradient_reverse(values: torch.Tensor, strength: float) -> torch.Tensor:
    return _GradientReverse.apply(values, strength)


class ConfigurableDiseaseModel(nn.Module):
    def __init__(self, config: dict, explicit_feature_count: int):
        super().__init__()
        model_config = config["model"]
        architecture = model_config["architecture"]
        pretrained = bool(model_config["imagenet_pretrained"])
        if architecture == "resnet18":
            weights = ResNet18_Weights.DEFAULT if pretrained else None
            self.backbone = resnet18(weights=weights)
            feature_dim = self.backbone.fc.in_features
            self.backbone.fc = nn.Identity()
            self.spatial_layer = self.backbone.layer4
        elif architecture == "convnext_tiny":
            weights = ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
            self.backbone = convnext_tiny(weights=weights)
            feature_dim = self.backbone.classifier[2].in_features
            self.backbone.classifier[2] = nn.Identity()
            self.spatial_layer = self.backbone.features[-1]
        else:
            raise ValueError(f"不支援的 architecture：{architecture}")

        explicit_config = model_config["explicit_features"]
        self.explicit_enabled = bool(explicit_config["enabled"])
        self.explicit_dropout_probability = float(explicit_config["whole_branch_dropout_probability"])
        if self.explicit_enabled:
            hidden = int(explicit_config["hidden_dim"])
            self.explicit_branch = nn.Sequential(
                nn.LayerNorm(explicit_feature_count),
                nn.Linear(explicit_feature_count, 64),
                nn.GELU(),
                nn.Dropout(float(explicit_config["dropout"])),
                nn.Linear(64, hidden),
                nn.GELU(),
            )
        else:
            hidden = 0
            self.explicit_branch = None

        disease_input = feature_dim + hidden
        self.disease_head = nn.Sequential(
            nn.LayerNorm(disease_input),
            nn.Dropout(float(model_config["dropout"])),
            nn.Linear(disease_input, int(model_config["num_disease_classes"])),
        )

        site_config = model_config["site_auxiliary"]
        self.site_enabled = bool(site_config["enabled"])
        self.site_head = nn.Linear(feature_dim, len(site_config["classes"])) if self.site_enabled else None

        source_config = model_config["source_adversarial"]
        self.source_enabled = bool(source_config["enabled"])
        self.source_strength = float(source_config["gradient_reversal_strength"])
        self.source_head = nn.Sequential(
            nn.Linear(feature_dim, 128), nn.GELU(), nn.Dropout(0.20),
            nn.Linear(128, len(source_config["classes"])),
        ) if self.source_enabled else None

    def forward(self, images: torch.Tensor, explicit_features: torch.Tensor | None = None) -> dict[str, torch.Tensor | None]:
        image_features = self.backbone(images)
        disease_features = image_features
        if self.explicit_enabled:
            if explicit_features is None:
                raise ValueError("已啟用顯式特徵，但 forward 沒有收到 explicit_features")
            side = self.explicit_branch(explicit_features)
            if self.training and self.explicit_dropout_probability > 0:
                keep = (
                    torch.rand(side.shape[0], 1, device=side.device) >= self.explicit_dropout_probability
                ).to(side.dtype)
                side = side * keep
            disease_features = torch.cat([image_features, side], dim=1)
        disease = self.disease_head(disease_features)
        site = self.site_head(image_features) if self.site_head is not None else None
        source = None
        if self.source_head is not None:
            source = self.source_head(gradient_reverse(image_features, self.source_strength))
        return {"disease": disease, "site": site, "source": source}


def build_model(config: dict, explicit_feature_count: int) -> ConfigurableDiseaseModel:
    return ConfigurableDiseaseModel(config, explicit_feature_count)

