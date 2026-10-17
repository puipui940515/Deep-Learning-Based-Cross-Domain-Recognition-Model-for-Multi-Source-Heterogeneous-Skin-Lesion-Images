"""把 FilterChainV2 掛到任何已正規化輸入的骨幹前面。

v1 的 NormalizedFilterModel 寫死 [-1,1]（mean=std=0.5）。現行主線
（資料治理 train_regularized.py、端到端規格 v2 §4）已改用 ImageNet 統計量；
若沿用 v1 wrapper，濾鏡會收到錯誤的像素值且不報錯。這裡把 mean／std 改為
**必填**，與規格「缺少即拒絕載入」一致。
"""

from __future__ import annotations

import torch
import torch.nn as nn

from .filters import FilterChainV2

__all__ = ["FilteredBackbone", "IMAGENET_MEAN", "IMAGENET_STD"]

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


class FilteredBackbone(nn.Module):
    def __init__(self, backbone: nn.Module, filter_chain: FilterChainV2, *, mean, std,
                 freeze_filter: bool = True):
        super().__init__()
        if mean is None or std is None:
            raise ValueError("mean／std 為必填，不提供預設值（見端到端規格 v2 §4）")
        self.backbone = backbone
        self.filter = filter_chain
        self.register_buffer("mean", torch.tensor(mean, dtype=torch.float32).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(std, dtype=torch.float32).view(1, 3, 1, 1))
        if freeze_filter:
            for p in self.filter.parameters():
                p.requires_grad_(False)

    def to_pixels(self, normalized):
        return (normalized * self.std.to(normalized) + self.mean.to(normalized)).clamp(0.0, 1.0)

    def to_normalized(self, pixels):
        return (pixels - self.mean.to(pixels)) / self.std.to(pixels)

    def filtered_normalized(self, normalized, alpha=None, skin_weight=None):
        with torch.autocast(device_type=normalized.device.type, enabled=False):
            px = self.to_pixels(normalized.float())
            out = self.filter(px, alpha=alpha, skin_weight=skin_weight)
            return self.to_normalized(out).to(normalized.dtype)

    def forward(self, normalized, alpha=None, skin_weight=None):
        return self.backbone(self.filtered_normalized(normalized, alpha, skin_weight))
