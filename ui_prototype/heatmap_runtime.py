from __future__ import annotations

import base64
import io
from typing import Any

import numpy as np
from PIL import Image


def _spatial_layers(model, definition: dict) -> list[tuple[str, Any]]:
    wrapper = definition.get("wrapper", "standard")
    architecture = definition.get("architecture", "")
    if wrapper == "parallel":
        return [
            ("疾病影像分支", model.student.features[-1]),
            ("凍結教師分支", model.teacher.features[-1]),
        ]
    backbone = model.backbone if wrapper == "noisefilter" else model
    if architecture == "convnext_tiny":
        return [("ConvNeXt 最後卷積階段", backbone.features[-1])]
    if architecture == "resnet18":
        return [("ResNet18 第四殘差階段", backbone.layer4)]
    return []


def gradcam_prediction(model, tensor, definition: dict):
    """回傳 logits、0..1 Grad-CAM、使用層名稱與不可用原因。"""
    import torch
    import torch.nn.functional as functional

    layers = _spatial_layers(model, definition)
    if not layers:
        with torch.inference_mode():
            logits = model(tensor)
        return logits, None, [], "此模型沒有可對應空間位置的卷積特徵圖。"

    activations: dict[str, Any] = {}
    gradients: dict[str, Any] = {}
    handles = []

    def capture(name: str):
        def hook(_module, _inputs, output):
            activations[name] = output
            output.register_hook(lambda gradient: gradients.__setitem__(name, gradient))
        return hook

    try:
        for name, layer in layers:
            handles.append(layer.register_forward_hook(capture(name)))
        model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            grad_tensor = tensor.detach().requires_grad_(True)
            logits = model(grad_tensor)
            target_index = int(logits.argmax(dim=1)[0].item())
            logits[0, target_index].backward()

        maps = []
        used_layers = []
        for name, _layer in layers:
            activation = activations.get(name)
            gradient = gradients.get(name)
            if activation is None or gradient is None or activation.ndim != 4:
                continue
            weights = gradient.mean(dim=(2, 3), keepdim=True)
            cam = torch.relu((weights * activation).sum(dim=1, keepdim=True))
            cam = functional.interpolate(
                cam,
                size=tensor.shape[-2:],
                mode="bilinear",
                align_corners=False,
            )[0, 0]
            minimum, maximum = cam.min(), cam.max()
            if float((maximum - minimum).detach()) <= 1e-12:
                continue
            maps.append(((cam - minimum) / (maximum - minimum)).detach())
            used_layers.append(name)
        if not maps:
            return logits.detach(), None, [], "梯度圖為常數，無法建立有意義的熱力圖。"
        combined = torch.stack(maps).mean(dim=0)
        combined -= combined.min()
        combined /= combined.max().clamp_min(1e-12)
        return logits.detach(), combined.float().cpu().numpy(), used_layers, ""
    finally:
        for handle in handles:
            handle.remove()
        model.zero_grad(set_to_none=True)


def _turbo_like(values: np.ndarray) -> np.ndarray:
    """無額外繪圖依賴的藍→青→黃→紅色盤。"""
    values = np.clip(values, 0.0, 1.0)
    red = np.clip(1.5 - np.abs(4.0 * values - 3.0), 0.0, 1.0)
    green = np.clip(1.5 - np.abs(4.0 * values - 2.0), 0.0, 1.0)
    blue = np.clip(1.5 - np.abs(4.0 * values - 1.0), 0.0, 1.0)
    return np.stack([red, green, blue], axis=-1)


def overlay_data_url(image: Image.Image, heatmap: np.ndarray, alpha: float = 0.44) -> str:
    base = image.convert("RGB").copy()
    base.thumbnail((720, 720), Image.Resampling.LANCZOS)
    map_image = Image.fromarray(np.uint8(np.clip(heatmap, 0.0, 1.0) * 255), mode="L")
    map_image = map_image.resize(base.size, Image.Resampling.BILINEAR)
    colored = Image.fromarray(
        np.uint8(_turbo_like(np.asarray(map_image, dtype=np.float32) / 255.0) * 255.0)
    )
    colored = colored.convert("RGB")
    overlay = Image.blend(base, colored, alpha)
    output = io.BytesIO()
    overlay.save(output, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
