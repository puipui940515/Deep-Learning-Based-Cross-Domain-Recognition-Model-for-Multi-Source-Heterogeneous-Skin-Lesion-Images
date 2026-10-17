from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms
from torchvision.models import convnext_tiny


STAGE = Path(__file__).resolve().parents[1]
PROJECT = STAGE.parent
RESULTS = STAGE / "results"
HEATMAPS = RESULTS / "heatmaps"
CLASS_NAMES = ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL"]
CLASS_NAMES_ZH = ["光化性角化症", "基底細胞癌", "良性角化病灶", "皮膚纖維瘤", "黑色素細胞痣", "血管性病灶", "黑色素瘤"]
SEED = 17
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "資料治理與泛化修復" / "顯式影像特徵融合實驗" / "src"))

from ui_prototype.model_runtime import build_model_from_definition, load_model_registry
from fusion_model import build_experiment_model


SAMPLE_PLAN = [
    ("HAM10000", "DF"),
    ("HAM10000", "VASC"),
    ("HAM10000", "NV"),
    ("HAM10000", "MEL"),
    ("BCN20000", "AKIEC"),
    ("BCN20000", "BKL"),
    ("BCN20000", "BCC"),
    ("PAD-UFES-20", "AKIEC"),
    ("PAD-UFES-20", "BCC"),
    ("PAD-UFES-20", "MEL"),
]


MODEL_CATEGORY = {
    "stage1_v1": "隨機初始化",
    "stage1_v1_noisefilter": "隨機初始化",
    "stage2_v5": "隨機初始化",
    "stage2_v6": "ImageNet",
    "stage2_v7": "ImageNet",
    "stage2_v8": "ImageNet",
    "stage2_v10": "隨機初始化",
    "stage2_v5_noisefilter": "隨機初始化",
    "frozen_imagenet": "ImageNet",
    "frozen_densepose_true": "部位預訓練",
    "frozen_densepose_shuffled": "部位亂標對照",
    "parallel_imagenet": "ImageNet",
    "parallel_densepose_true": "部位預訓練",
    "parallel_densepose_shuffled": "部位亂標對照",
    "finetune_imagenet": "ImageNet",
    "finetune_densepose_true": "部位預訓練",
    "mixed_v1": "ImageNet",
    "mixed_convnext": "ImageNet",
    "mixed_resnet18": "ImageNet",
    "regularized_v1": "ImageNet",
    "regularized_v2_long": "ImageNet",
    "regularized_v3a": "ImageNet",
    "explicit_fusion": "ImageNet＋顯式特徵",
    "explicit_only": "顯式特徵",
}


SHORT_NAMES = {
    "stage1_v1": "第一階段 MLP",
    "stage1_v1_noisefilter": "第一階段 MLP＋濾波",
    "stage2_v5": "ResNet18 零起點",
    "stage2_v6": "ResNet18 ImageNet",
    "stage2_v7": "ConvNeXt ImageNet 224",
    "stage2_v8": "ConvNeXt ImageNet 384",
    "stage2_v10": "ConvNeXt 零起點",
    "stage2_v5_noisefilter": "ResNet18＋濾波",
    "frozen_imagenet": "凍結 ImageNet",
    "frozen_densepose_true": "凍結部位預訓練",
    "frozen_densepose_shuffled": "凍結部位亂標",
    "parallel_imagenet": "並行 ImageNet",
    "parallel_densepose_true": "並行部位預訓練",
    "parallel_densepose_shuffled": "並行部位亂標",
    "finetune_imagenet": "完整微調 ImageNet",
    "finetune_densepose_true": "完整微調部位",
    "mixed_v1": "混合 V1 ConvNeXt",
    "mixed_convnext": "混合 V2 ConvNeXt",
    "mixed_resnet18": "混合 V2 ResNet18",
    "regularized_v1": "治理 V1 正則化",
    "regularized_v2_long": "治理 V2 長訓練",
    "regularized_v3a": "治理 V3A 覆蓋",
    "explicit_fusion": "ConvNeXt＋顯式特徵",
    "explicit_only": "純顯式特徵 MLP",
}


@dataclass
class Adapter:
    model_id: str
    name: str
    category: str
    model: torch.nn.Module
    image_size: int
    mean: tuple[float, float, float]
    std: tuple[float, float, float]
    layers: list[tuple[str, torch.nn.Module]]
    side_builder: Callable[[Image.Image, dict[str, str] | None], torch.Tensor | None]
    forward_fn: Callable[[torch.Tensor, torch.Tensor | None], torch.Tensor]

    def tensor(self, image: Image.Image) -> torch.Tensor:
        pipeline = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor(),
            transforms.Normalize(self.mean, self.std),
        ])
        return pipeline(image.convert("RGB")).unsqueeze(0).to(DEVICE)

    def side(self, image: Image.Image, sample: dict[str, str] | None = None) -> torch.Tensor | None:
        value = self.side_builder(image, sample)
        return None if value is None else value.to(DEVICE)

    def image_from_tensor(self, tensor: torch.Tensor) -> Image.Image:
        values = tensor.detach()[0].float().cpu().numpy().transpose(1, 2, 0)
        values = values * np.asarray(self.std)[None, None, :] + np.asarray(self.mean)[None, None, :]
        return Image.fromarray(np.uint8(np.clip(values, 0.0, 1.0) * 255.0), mode="RGB")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def choose_samples() -> list[dict[str, str]]:
    rows = read_csv(PROJECT / "資料治理與泛化修復" / "data" / "unified_manifest_v1.csv")
    eligible = [
        row for row in rows
        if row["split"] == "validation"
        and row["training_eligible"].lower() == "true"
        and (PROJECT / row["image_path"]).is_file()
    ]
    selected = []
    for source, label in SAMPLE_PLAN:
        candidates = [row for row in eligible if row["source"] == source and row["label_name"] == label]
        if not candidates:
            raise RuntimeError(f"找不到樣本：{source}/{label}")
        candidates.sort(key=lambda row: hashlib.sha256(f"{SEED}:{row['record_id']}".encode()).hexdigest())
        selected.append(dict(candidates[0]))
    for index, row in enumerate(selected, start=1):
        row["sample_id"] = f"S{index:02d}"
    STAGE.joinpath("data").mkdir(parents=True, exist_ok=True)
    fields = ["sample_id", "record_id", "source", "label", "label_name", "diagnosis_canonical_zh", "image_modality_zh", "image_path"]
    with (STAGE / "data" / "selected_samples.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selected)
    return selected


def registry_layers(model: torch.nn.Module, definition: dict[str, Any]) -> list[tuple[str, torch.nn.Module]]:
    wrapper = definition.get("wrapper", "standard")
    architecture = definition.get("architecture", "")
    if wrapper == "parallel":
        return [("疾病影像分支", model.student.features[-1]), ("凍結教師分支", model.teacher.features[-1])]
    backbone = model.backbone if wrapper == "noisefilter" else model
    if architecture == "convnext_tiny":
        return [("ConvNeXt 最後卷積階段", backbone.features[-1])]
    if architecture == "resnet18":
        return [("ResNet18 第四殘差階段", backbone.layer4)]
    return []


def registry_adapters() -> list[Adapter]:
    registry = load_model_registry(PROJECT / "模型資產庫")
    adapters = []
    for definition in registry.get("models", []):
        if not definition.get("available"):
            continue
        model, _unused = build_model_from_definition(definition, PROJECT)
        model = model.to(DEVICE).eval()
        model_id = definition["id"]
        adapters.append(Adapter(
            model_id=model_id,
            name=SHORT_NAMES.get(model_id, definition["name"]),
            category=MODEL_CATEGORY.get(model_id, "其他"),
            model=model,
            image_size=int(definition["image_size"]),
            mean=(0.5, 0.5, 0.5),
            std=(0.5, 0.5, 0.5),
            layers=registry_layers(model, definition),
            side_builder=lambda _image, _sample: None,
            forward_fn=lambda tensor, _side, current=model: current(tensor),
        ))
        yield adapters.pop()


def convnext_adapter(model_id: str, name: str, checkpoint_path: Path) -> Adapter:
    model = convnext_tiny(weights=None)
    model.classifier[2] = torch.nn.Linear(model.classifier[2].in_features, 7)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model"] if isinstance(checkpoint, dict) and "model" in checkpoint else checkpoint)
    model = model.to(DEVICE).eval()
    return Adapter(
        model_id=model_id,
        name=name,
        category=MODEL_CATEGORY[model_id],
        model=model,
        image_size=224,
        mean=(0.485, 0.456, 0.406),
        std=(0.229, 0.224, 0.225),
        layers=[("ConvNeXt 最後卷積階段", model.features[-1])],
        side_builder=lambda _image, _sample: None,
        forward_fn=lambda tensor, _side: model(tensor),
    )


def fusion_adapter(mode: str) -> Adapter:
    model_id = "explicit_fusion" if mode == "fusion" else "explicit_only"
    checkpoint_path = PROJECT / "資料治理與泛化修復" / "顯式影像特徵融合實驗" / "results" / f"{mode}_seed17" / "best.pt"
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = build_experiment_model(mode, len(checkpoint["feature_names"]), 7, pretrained=False)
    model.load_state_dict(checkpoint["model"])
    model = model.to(DEVICE).eval()
    mean = np.asarray(checkpoint["feature_mean"], dtype=np.float32)
    std = np.asarray(checkpoint["feature_std"], dtype=np.float32)
    names = tuple(checkpoint["feature_names"])
    feature_rows = {
        row["record_id"]: row
        for row in read_csv(PROJECT / "資料治理與泛化修復" / "顯式影像特徵融合實驗" / "data" / "explicit_features_v1.csv")
    }

    def side_builder(_image: Image.Image, sample: dict[str, str] | None) -> torch.Tensor:
        if sample is None or sample["record_id"] not in feature_rows:
            raise RuntimeError("顯式特徵模型需要已快取的 validation record_id")
        cached = feature_rows[sample["record_id"]]
        model_values = np.asarray([float(cached[name]) for name in names], dtype=np.float32)
        standardized = (model_values - mean) / std
        return torch.from_numpy(standardized).unsqueeze(0)

    if mode == "fusion":
        layers = [("ConvNeXt 最後卷積階段", model.image_backbone.features[-1])]
        forward_fn = lambda tensor, side: model(tensor, side)
    else:
        layers = []
        forward_fn = lambda tensor, side: model(tensor, side)
    return Adapter(
        model_id=model_id,
        name=SHORT_NAMES[model_id],
        category=MODEL_CATEGORY[model_id],
        model=model,
        image_size=224,
        mean=(0.485, 0.456, 0.406),
        std=(0.229, 0.224, 0.225),
        layers=layers,
        side_builder=side_builder,
        forward_fn=forward_fn,
    )


def formal_adapters() -> list[Adapter]:
    formal = PROJECT / "資料治理與泛化修復" / "results"
    specs = [
        ("regularized_v1", "治理 V1 正則化", formal / "formal_v1" / "regularized_seed17" / "best.pt"),
        ("regularized_v2_long", "治理 V2 長訓練", formal / "formal_v2_long" / "regularized_seed17" / "best.pt"),
        ("regularized_v3a", "治理 V3A 覆蓋", formal / "formal_v3a_coverage" / "regularized_seed17" / "best.pt"),
    ]
    for model_id, name, path in specs:
        if path.is_file():
            yield convnext_adapter(model_id, name, path)


def feature_adapters() -> list[Adapter]:
    for mode in ("fusion", "feature_only"):
        path = PROJECT / "資料治理與泛化修復" / "顯式影像特徵融合實驗" / "results" / f"{mode}_seed17" / "best.pt"
        if path.is_file():
            yield fusion_adapter(mode)


def gradcam(adapter: Adapter, tensor: torch.Tensor, side: torch.Tensor | None, target: int | None = None):
    activations: dict[str, torch.Tensor] = {}
    gradients: dict[str, torch.Tensor] = {}
    handles = []

    def capture(name: str):
        def hook(_module, _inputs, output):
            activations[name] = output
            output.register_hook(lambda grad: gradients.__setitem__(name, grad))
        return hook

    try:
        for name, layer in adapter.layers:
            handles.append(layer.register_forward_hook(capture(name)))
        adapter.model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            input_tensor = tensor.detach().requires_grad_(True)
            logits = adapter.forward_fn(input_tensor, side)
            chosen = int(logits.argmax(1)[0].item()) if target is None else int(target)
            logits[0, chosen].backward()
        maps = []
        for name, _layer in adapter.layers:
            activation, gradient = activations.get(name), gradients.get(name)
            if activation is None or gradient is None or activation.ndim != 4:
                continue
            weights = gradient.mean(dim=(2, 3), keepdim=True)
            cam = torch.relu((weights * activation).sum(dim=1, keepdim=True))
            cam = F.interpolate(cam, size=tensor.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
            spread = cam.max() - cam.min()
            if float(spread.detach()) <= 1e-12:
                continue
            maps.append((cam - cam.min()) / spread)
        if not maps:
            return logits.detach(), chosen, None
        combined = torch.stack(maps).mean(0)
        combined = (combined - combined.min()) / (combined.max() - combined.min()).clamp_min(1e-12)
        return logits.detach(), chosen, combined.detach()
    finally:
        for handle in handles:
            handle.remove()
        adapter.model.zero_grad(set_to_none=True)


def probabilities(adapter: Adapter, tensor: torch.Tensor, side: torch.Tensor | None) -> torch.Tensor:
    with torch.inference_mode():
        return torch.softmax(adapter.forward_fn(tensor, side), dim=1)[0]


def mask_by_quantile(tensor: torch.Tensor, cam: torch.Tensor, upper: bool) -> torch.Tensor:
    threshold = torch.quantile(cam.flatten(), 0.80 if upper else 0.20)
    mask = cam >= threshold if upper else cam <= threshold
    result = tensor.clone()
    result.masked_fill_(mask[None, None, :, :], 0.0)
    return result


def save_overlay(image: Image.Image, cam: torch.Tensor, output: Path, image_size: int) -> None:
    base = np.asarray(image.convert("RGB").resize((image_size, image_size), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    values = cam.float().cpu().numpy()
    red = np.clip(1.5 - np.abs(4.0 * values - 3.0), 0.0, 1.0)
    green = np.clip(1.5 - np.abs(4.0 * values - 2.0), 0.0, 1.0)
    blue = np.clip(1.5 - np.abs(4.0 * values - 1.0), 0.0, 1.0)
    color = np.stack([red, green, blue], axis=-1)
    overlay = np.uint8(np.clip(0.56 * base + 0.44 * color, 0.0, 1.0) * 255.0)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(overlay, mode="RGB").save(output, quality=88, optimize=True)


def ece(confidences: np.ndarray, correct: np.ndarray, bins: int = 5) -> float:
    total = len(confidences)
    score = 0.0
    for start, end in zip(np.linspace(0, 1, bins + 1)[:-1], np.linspace(0, 1, bins + 1)[1:]):
        chosen = (confidences >= start) & (confidences < end if end < 1 else confidences <= end)
        if chosen.any():
            score += chosen.mean() * abs(float(correct[chosen].mean()) - float(confidences[chosen].mean()))
    return float(score)


def aggregate(per_image: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    targets = per_image["target"].to_numpy(int)
    predictions = per_image["prediction"].to_numpy(int)
    recalls, f1s = [], []
    for label in sorted(set(targets.tolist())):
        tp = int(((targets == label) & (predictions == label)).sum())
        fn = int(((targets == label) & (predictions != label)).sum())
        fp = int(((targets != label) & (predictions == label)).sum())
        recall = tp / max(tp + fn, 1)
        precision = tp / max(tp + fp, 1)
        recalls.append(recall)
        f1s.append(2 * precision * recall / max(precision + recall, 1e-12))
    available = per_image[per_image["heatmap_available"] == True]
    result = dict(metadata)
    result.update({
        "samples": len(per_image),
        "accuracy": float((targets == predictions).mean()),
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1s)),
        "ece_5bin": ece(per_image["confidence"].to_numpy(float), (targets == predictions).astype(float)),
        "heatmap_available_rate": float(len(available) / len(per_image)),
        "top20_probability_drop": float(available["top20_probability_drop"].mean()) if len(available) else math.nan,
        "bottom20_probability_drop": float(available["bottom20_probability_drop"].mean()) if len(available) else math.nan,
        "faithfulness_margin": float(available["faithfulness_margin"].mean()) if len(available) else math.nan,
        "flip_top20_iou": float(available["flip_top20_iou"].mean()) if len(available) else math.nan,
        "flip_prediction_consistency": float(available["flip_prediction_same"].mean()) if len(available) else math.nan,
        "center60_energy_share": float(available["center60_energy_share"].mean()) if len(available) else math.nan,
        "normalized_cam_entropy": float(available["normalized_cam_entropy"].mean()) if len(available) else math.nan,
        "median_latency_ms": float(per_image["latency_ms"].median()),
        "error": "",
    })
    return result


def evaluate_adapter(adapter: Adapter, samples: list[dict[str, str]]) -> tuple[list[dict], dict]:
    rows = []
    for index, sample in enumerate(samples, start=1):
        image = Image.open(PROJECT / sample["image_path"]).convert("RGB")
        tensor = adapter.tensor(image)
        side = adapter.side(image, sample)
        started = time.perf_counter()
        if adapter.layers:
            logits, predicted, cam = gradcam(adapter, tensor, side)
            probs = torch.softmax(logits, dim=1)[0]
        else:
            probs = probabilities(adapter, tensor, side)
            predicted = int(probs.argmax().item())
            cam = None
        confidence = float(probs[predicted].item())
        row = {
            "model_id": adapter.model_id,
            "model_name": adapter.name,
            "category": adapter.category,
            "sample_id": sample["sample_id"],
            "record_id": sample["record_id"],
            "image_path": sample["image_path"],
            "source": sample["source"],
            "target": int(sample["label"]),
            "target_name": sample["label_name"],
            "prediction": predicted,
            "prediction_name": CLASS_NAMES[predicted],
            "correct": int(predicted == int(sample["label"])),
            "confidence": confidence,
            "heatmap_available": cam is not None,
            "top20_probability_drop": math.nan,
            "bottom20_probability_drop": math.nan,
            "faithfulness_margin": math.nan,
            "flip_top20_iou": math.nan,
            "flip_prediction_same": math.nan,
            "center60_energy_share": math.nan,
            "normalized_cam_entropy": math.nan,
            "overlay_path": "",
        }
        if cam is not None:
            top_tensor = mask_by_quantile(tensor, cam, True)
            bottom_tensor = mask_by_quantile(tensor, cam, False)
            # 固定顯式特徵，只量測 Grad-CAM 所解釋的影像分支。
            top_side = side
            bottom_side = side
            top_prob = float(probabilities(adapter, top_tensor, top_side)[predicted].item())
            bottom_prob = float(probabilities(adapter, bottom_tensor, bottom_side)[predicted].item())

            flipped_image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            flip_tensor, flip_side = adapter.tensor(flipped_image), side
            flip_logits, _same_target, flip_cam = gradcam(adapter, flip_tensor, flip_side, predicted)
            flip_prediction = int(flip_logits.argmax(1)[0].item())
            if flip_cam is not None:
                flip_cam = torch.flip(flip_cam, dims=[1])
                original_hot = cam >= torch.quantile(cam.flatten(), 0.80)
                flipped_hot = flip_cam >= torch.quantile(flip_cam.flatten(), 0.80)
                intersection = float((original_hot & flipped_hot).sum().item())
                union = float((original_hot | flipped_hot).sum().item())
                flip_iou = intersection / max(union, 1.0)
            else:
                flip_iou = math.nan
            height, width = cam.shape
            y0, y1 = int(height * 0.20), int(height * 0.80)
            x0, x1 = int(width * 0.20), int(width * 0.80)
            center_share = float(cam[y0:y1, x0:x1].sum().item() / max(cam.sum().item(), 1e-12))
            distribution = cam.flatten().clamp_min(0)
            distribution = distribution / distribution.sum().clamp_min(1e-12)
            entropy = float((-(distribution * distribution.clamp_min(1e-12).log()).sum() / math.log(distribution.numel())).item())
            overlay = HEATMAPS / adapter.model_id / f"{sample['sample_id']}.jpg"
            save_overlay(image, cam, overlay, adapter.image_size)
            row.update({
                "top20_probability_drop": confidence - top_prob,
                "bottom20_probability_drop": confidence - bottom_prob,
                "faithfulness_margin": (confidence - top_prob) - (confidence - bottom_prob),
                "flip_top20_iou": flip_iou,
                "flip_prediction_same": int(flip_prediction == predicted),
                "center60_energy_share": center_share,
                "normalized_cam_entropy": entropy,
                "overlay_path": str(overlay.relative_to(STAGE)).replace("\\", "/"),
            })
        row["latency_ms"] = (time.perf_counter() - started) * 1000.0
        rows.append(row)
        print(f"  {index:02d}/10 {sample['sample_id']} {sample['source']} {sample['label_name']} -> {row['prediction_name']}", flush=True)
    metadata = {
        "model_id": adapter.model_id,
        "model_name": adapter.name,
        "category": adapter.category,
        "parameters": sum(parameter.numel() for parameter in adapter.model.parameters()),
        "image_size": adapter.image_size,
    }
    return rows, aggregate(pd.DataFrame(rows), metadata)


def add_screening_score(summary: pd.DataFrame) -> pd.DataFrame:
    eligible = summary["heatmap_available_rate"] >= 0.999
    metrics = {
        "balanced_accuracy": 0.50,
        "accuracy": 0.20,
        "faithfulness_margin": 0.15,
        "flip_top20_iou": 0.10,
        "flip_prediction_consistency": 0.05,
    }
    summary["screening_score"] = np.nan
    score = pd.Series(0.0, index=summary.index)
    for column, weight in metrics.items():
        score += summary.loc[eligible, column].rank(method="average", pct=True) * weight
    summary.loc[eligible, "screening_score"] = score.loc[eligible] * 100.0
    return summary.sort_values(["screening_score", "balanced_accuracy"], ascending=False, na_position="last")


def main() -> None:
    parser = argparse.ArgumentParser(description="十張分類與 Grad-CAM 模型篩選")
    parser.add_argument("--scope", choices=["registry", "formal", "features"], default="registry")
    args = parser.parse_args()
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    RESULTS.mkdir(parents=True, exist_ok=True)
    samples = choose_samples()
    all_rows, summaries, failures = [], [], []
    registry = load_model_registry(PROJECT / "模型資產庫")
    registry_count = sum(bool(item.get("available")) for item in registry.get("models", []))
    existing_formal = [
        PROJECT / "資料治理與泛化修復" / "results" / "formal_v1" / "regularized_seed17" / "best.pt",
        PROJECT / "資料治理與泛化修復" / "results" / "formal_v2_long" / "regularized_seed17" / "best.pt",
        PROJECT / "資料治理與泛化修復" / "results" / "formal_v3a_coverage" / "regularized_seed17" / "best.pt",
    ]
    existing_features = [
        PROJECT / "資料治理與泛化修復" / "顯式影像特徵融合實驗" / "results" / "fusion_seed17" / "best.pt",
        PROJECT / "資料治理與泛化修復" / "顯式影像特徵融合實驗" / "results" / "feature_only_seed17" / "best.pt",
    ]
    if args.scope == "registry":
        total, adapters = registry_count, registry_adapters()
    elif args.scope == "formal":
        total, adapters = sum(path.is_file() for path in existing_formal), formal_adapters()
    else:
        total, adapters = sum(path.is_file() for path in existing_features), feature_adapters()
    print(f"device={DEVICE} models={total} samples={len(samples)}", flush=True)
    for model_index, adapter in enumerate(adapters, start=1):
        print(f"[{model_index:02d}/{total:02d}] {adapter.model_id} / {adapter.name}", flush=True)
        try:
            rows, summary = evaluate_adapter(adapter, samples)
            all_rows.extend(rows)
            summaries.append(summary)
            print(f"  BA={summary['balanced_accuracy']:.4f} heatmap={summary['heatmap_available_rate']:.0%}", flush=True)
        except Exception as error:
            failures.append({"model_id": adapter.model_id, "model_name": adapter.name, "error": repr(error)})
            summaries.append({
                "model_id": adapter.model_id, "model_name": adapter.name, "category": adapter.category,
                "parameters": sum(parameter.numel() for parameter in adapter.model.parameters()),
                "image_size": adapter.image_size, "samples": 0, "error": repr(error),
            })
            print(f"  FAILED: {error!r}", flush=True)
        finally:
            adapter.model.to("cpu")
            del adapter
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    scope_per_image = pd.DataFrame(all_rows)
    scope_summary = pd.DataFrame(summaries)
    scope_per_image.to_csv(RESULTS / f"per_image_results_{args.scope}.csv", index=False, encoding="utf-8-sig")
    scope_summary.to_csv(RESULTS / f"model_summary_{args.scope}.csv", index=False, encoding="utf-8-sig")
    (RESULTS / f"failures_{args.scope}.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")

    per_parts, summary_parts = [], []
    combined_failures = []
    for scope in ("registry", "formal", "features"):
        per_path = RESULTS / f"per_image_results_{scope}.csv"
        summary_path = RESULTS / f"model_summary_{scope}.csv"
        failure_path = RESULTS / f"failures_{scope}.json"
        if per_path.is_file():
            per_parts.append(pd.read_csv(per_path))
        if summary_path.is_file():
            summary_parts.append(pd.read_csv(summary_path))
        if failure_path.is_file():
            combined_failures.extend(json.loads(failure_path.read_text(encoding="utf-8")))
    per_image = pd.concat(per_parts, ignore_index=True)
    summary = add_screening_score(pd.concat(summary_parts, ignore_index=True))
    per_image.to_csv(RESULTS / "per_image_results.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(RESULTS / "model_summary.csv", index=False, encoding="utf-8-sig")
    (RESULTS / "failures.json").write_text(json.dumps(combined_failures, ensure_ascii=False, indent=2), encoding="utf-8")
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device": str(DEVICE),
        "seed": SEED,
        "sample_count": len(samples),
        "model_count": int(len(summary)),
        "successful_model_count": int((summary["samples"].fillna(0) > 0).sum()),
        "heatmap_eligible_model_count": int((summary["heatmap_available_rate"].fillna(0) >= 0.999).sum()),
        "ranking": summary.fillna("").to_dict(orient="records"),
        "limitations": [
            "十張樣本只供快速篩選。",
            "沒有病灶分割遮罩，不能計算病灶定位準確率。",
            "中央熱量占比與 Grad-CAM 外觀不納入篩選分數。",
            "正式基底仍需擴大驗證與多 seed 複驗。",
        ],
    }
    (RESULTS / "screening_result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("完成：" + str(RESULTS / "model_summary.csv"), flush=True)


if __name__ == "__main__":
    main()
