from __future__ import annotations

import json
import sys
from pathlib import Path


def load_model_registry(library_dir: Path) -> dict:
    registry_path = library_dir / "model_registry.json"
    if not registry_path.is_file():
        return {"default_model": "demo", "models": []}
    payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    for item in payload.get("models", []):
        checkpoint = (library_dir / item["checkpoint"]).resolve()
        item["checkpoint_path"] = str(checkpoint)
        item["available"] = bool(item.get("available")) and bool(item.get("runtime_supported", True)) and checkpoint.is_file()
    return payload


def _base_model(architecture: str, image_size: int, project_root: Path):
    from torch import nn
    from torchvision.models import convnext_tiny, resnet18

    if architecture == "mlp":
        stage1_src = project_root / "第一階段" / "src"
        if str(stage1_src) not in sys.path:
            sys.path.insert(0, str(stage1_src))
        from stage1.models import build_model

        return build_model("mlp", image_size=image_size, num_classes=7)
    if architecture == "resnet18":
        model = resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, 7)
        return model
    if architecture == "convnext_tiny":
        model = convnext_tiny(weights=None)
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, 7)
        return model
    raise ValueError(f"不支援的疾病模型架構：{architecture}")


def _noisefilter_model(definition: dict, project_root: Path):
    from torch import nn

    vendor = (project_root / definition["vendor"]).resolve()
    if str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    from noisefilter import FilterChain

    class NormalizedFilterModel(nn.Module):
        def __init__(self, backbone, alpha):
            super().__init__()
            self.filter = FilterChain(alpha_init=alpha, learn_alpha=False)
            self.backbone = backbone

        def forward(self, normalized):
            pixels = ((normalized + 1.0) * 0.5).clamp(0.0, 1.0)
            filtered = self.filter(pixels)
            return self.backbone(filtered * 2.0 - 1.0)

    backbone = _base_model(definition["architecture"], definition["image_size"], project_root)
    return NormalizedFilterModel(backbone, definition["alpha"])


def _parallel_model(definition: dict):
    import torch
    from torch import nn
    from torchvision.models import convnext_tiny

    def feature_vector(model, images):
        values = model.features(images)
        values = model.avgpool(values)
        values = model.classifier[0](values)
        return model.classifier[1](values)

    class ParallelFrozenTeacher(nn.Module):
        def __init__(self, teacher_classes: int):
            super().__init__()
            self.student = convnext_tiny(weights=None)
            self.teacher = convnext_tiny(weights=None)
            if teacher_classes != 1000:
                self.teacher.classifier[2] = nn.Linear(self.teacher.classifier[2].in_features, teacher_classes)
            self.fusion_head = nn.Linear(768 * 2, 7)
            self.register_buffer("imagenet_mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
            self.register_buffer("imagenet_std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

        def forward(self, stage2_images):
            student_features = feature_vector(self.student, stage2_images)
            pixels_01 = stage2_images * 0.5 + 0.5
            teacher_images = (pixels_01 - self.imagenet_mean) / self.imagenet_std
            teacher_features = feature_vector(self.teacher, teacher_images)
            return self.fusion_head(torch.cat([student_features, teacher_features], dim=1))

    return ParallelFrozenTeacher(int(definition["teacher_classes"]))


def build_model_from_definition(definition: dict, project_root: Path):
    import torch
    from torchvision import transforms

    wrapper = definition.get("wrapper", "standard")
    if wrapper == "standard":
        model = _base_model(definition["architecture"], int(definition["image_size"]), project_root)
    elif wrapper == "noisefilter":
        model = _noisefilter_model(definition, project_root)
    elif wrapper == "parallel":
        model = _parallel_model(definition)
    else:
        raise ValueError(f"不支援的模型包裝器：{wrapper}")

    checkpoint = torch.load(definition["checkpoint_path"], map_location="cpu", weights_only=False)
    state_dict = checkpoint["model"] if isinstance(checkpoint, dict) and "model" in checkpoint else checkpoint
    model.load_state_dict(state_dict, strict=True)
    image_size = int(definition["image_size"])
    normalization = definition.get("normalization", {})
    mean = normalization.get("mean", [0.5, 0.5, 0.5])
    std = normalization.get("std", [0.5, 0.5, 0.5])
    transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    return model, transform
