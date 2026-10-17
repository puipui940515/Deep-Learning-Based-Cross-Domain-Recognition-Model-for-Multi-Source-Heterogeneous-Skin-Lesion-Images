from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader


STAGE = Path(__file__).resolve().parents[1]
PROJECT = STAGE.parent
sys.path.insert(0, str(STAGE / "src"))
sys.path.insert(0, str(PROJECT / "資料治理與泛化修復" / "scripts"))

from configurable_data import ConfigurableDataset, build_transform, load_feature_cache, read_csv
from configurable_model import build_model


def output_dir(config: dict, smoke: bool) -> Path:
    root = PROJECT / config["output"]["smoke_root" if smoke else "root"]
    return root / f"{config['experiment_id']}_seed{config['seed']}"


def feature_tensor(row, cache, names, mean, std, device):
    if cache is None:
        return None
    cached = cache[row["record_id"]]
    values = np.asarray([float(cached[name]) for name in names], dtype=np.float32)
    return torch.from_numpy((values - mean) / std).unsqueeze(0).to(device)


@torch.inference_mode()
def collect_logits(model, loader, device):
    logits, targets = [], []
    model.eval()
    for images, explicit, disease, _site, _source, _record, _source_name in loader:
        images, explicit = images.to(device), explicit.to(device)
        output = model(images, explicit if explicit.numel() else None)["disease"]
        logits.append(output.float())
        targets.append(disease.to(device))
    return torch.cat(logits), torch.cat(targets)


def calibration_error(logits: torch.Tensor, targets: torch.Tensor, temperature: float, bins: int = 15) -> float:
    probabilities = torch.softmax(logits / temperature, dim=1)
    confidence, prediction = probabilities.max(1)
    correct = prediction.eq(targets).float()
    score = torch.zeros((), device=logits.device)
    boundaries = torch.linspace(0, 1, bins + 1, device=logits.device)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        chosen = (confidence >= left) & (confidence < right if float(right) < 1 else confidence <= right)
        if bool(chosen.any()):
            score += chosen.float().mean() * (correct[chosen].mean() - confidence[chosen].mean()).abs()
    return float(score)


def fit_temperature(logits: torch.Tensor, targets: torch.Tensor, max_iterations: int) -> float:
    log_temperature = nn.Parameter(torch.zeros((), device=logits.device))
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.05, max_iter=max_iterations, line_search_fn="strong_wolfe")

    def closure():
        optimizer.zero_grad()
        temperature = log_temperature.exp().clamp(0.05, 10.0)
        loss = F.cross_entropy(logits / temperature, targets)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(log_temperature.exp().clamp(0.05, 10.0).detach())


def gradcam(model, images, explicit, target=None):
    activation = gradient = None

    def forward_hook(_module, _inputs, output):
        nonlocal activation
        activation = output
        output.register_hook(backward_hook)

    def backward_hook(value):
        nonlocal gradient
        gradient = value

    handle = model.spatial_layer.register_forward_hook(forward_hook)
    try:
        model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            values = images.detach().requires_grad_(True)
            logits = model(values, explicit)["disease"]
            chosen = int(logits.argmax(1)[0]) if target is None else int(target)
            logits[0, chosen].backward()
        weights = gradient.mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * activation).sum(dim=1, keepdim=True))
        cam = F.interpolate(cam, size=images.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
        cam = (cam - cam.min()) / (cam.max() - cam.min()).clamp_min(1e-12)
        return logits.detach(), chosen, cam.detach()
    finally:
        handle.remove()
        model.zero_grad(set_to_none=True)


def save_overlay(tensor, cam, path):
    values_rgb = tensor.detach()[0].float().cpu().numpy().transpose(1, 2, 0)
    values_rgb = values_rgb * np.asarray((0.229, 0.224, 0.225))[None, None, :] + np.asarray((0.485, 0.456, 0.406))[None, None, :]
    base = np.clip(values_rgb, 0.0, 1.0).astype(np.float32)
    values = cam.float().cpu().numpy()
    red = np.clip(1.5 - np.abs(4 * values - 3), 0, 1)
    green = np.clip(1.5 - np.abs(4 * values - 2), 0, 1)
    blue = np.clip(1.5 - np.abs(4 * values - 1), 0, 1)
    color = np.stack([red, green, blue], axis=-1)
    overlay = np.uint8(np.clip(0.56 * base + 0.44 * color, 0, 1) * 255)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(overlay, mode="RGB").save(path, quality=90, optimize=True)


@torch.inference_mode()
def disease_probability(model, images, explicit, target):
    return float(torch.softmax(model(images, explicit)["disease"], dim=1)[0, target])


def heatmap_audit(model, config, checkpoint, cache, device, output):
    audit_config = config["post_training"]["heatmap_audit"]
    if not audit_config["enabled"]:
        return None
    samples = read_csv(PROJECT / audit_config["sample_manifest"])
    transform = build_transform(config, train=False)
    names = tuple(checkpoint["feature_names"])
    mean = np.asarray(checkpoint["feature_mean"], dtype=np.float32)
    std = np.asarray(checkpoint["feature_std"], dtype=np.float32)
    top_fraction = float(audit_config["top_fraction"])
    records = []
    model.eval()
    for row in samples:
        with Image.open(PROJECT / row["image_path"]) as opened:
            image = opened.convert("RGB")
        tensor = transform(image).unsqueeze(0).to(device)
        explicit = feature_tensor(row, cache, names, mean, std, device)
        logits, predicted, cam = gradcam(model, tensor, explicit)
        confidence = float(torch.softmax(logits, dim=1)[0, predicted])
        upper = torch.quantile(cam.flatten(), 1.0 - top_fraction)
        lower = torch.quantile(cam.flatten(), top_fraction)
        top_mask, low_mask = cam >= upper, cam <= lower
        top_tensor, low_tensor = tensor.clone(), tensor.clone()
        top_tensor.masked_fill_(top_mask[None, None], 0.0)
        low_tensor.masked_fill_(low_mask[None, None], 0.0)
        top_drop = confidence - disease_probability(model, top_tensor, explicit, predicted)
        low_drop = confidence - disease_probability(model, low_tensor, explicit, predicted)
        flipped = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        flip_tensor = transform(flipped).unsqueeze(0).to(device)
        flip_logits, _target, flip_cam = gradcam(model, flip_tensor, explicit, predicted)
        flip_cam = torch.flip(flip_cam, dims=[1])
        flip_hot = flip_cam >= torch.quantile(flip_cam.flatten(), 1.0 - top_fraction)
        intersection = float((top_mask & flip_hot).sum())
        union = float((top_mask | flip_hot).sum())
        overlay_path = output / "heatmap_audit" / f"{row['sample_id']}.jpg"
        save_overlay(tensor, cam, overlay_path)
        records.append({
            "sample_id": row["sample_id"], "record_id": row["record_id"], "source": row["source"],
            "target": int(row["label"]), "prediction": predicted, "confidence": confidence,
            "correct": int(predicted == int(row["label"])),
            "top_probability_drop": top_drop, "low_probability_drop": low_drop,
            "faithfulness_margin": top_drop - low_drop,
            "flip_hot_iou": intersection / max(union, 1.0),
            "flip_prediction_same": int(int(flip_logits.argmax(1)[0]) == predicted),
            "overlay": str(overlay_path.relative_to(output)).replace("\\", "/"),
        })
    audit_dir = output / "heatmap_audit"
    with (audit_dir / "per_image.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    summary = {
        "samples": len(records),
        "accuracy": float(np.mean([row["correct"] for row in records])),
        "top_probability_drop": float(np.mean([row["top_probability_drop"] for row in records])),
        "low_probability_drop": float(np.mean([row["low_probability_drop"] for row in records])),
        "faithfulness_margin": float(np.mean([row["faithfulness_margin"] for row in records])),
        "flip_hot_iou": float(np.mean([row["flip_hot_iou"] for row in records])),
        "flip_prediction_consistency": float(np.mean([row["flip_prediction_same"] for row in records])),
        "explicit_features_fixed_during_perturbation": True,
        "localization_ground_truth_used": False,
    }
    (audit_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="正式訓練後校準與熱力圖稽核")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    output = output_dir(config, args.smoke)
    best_path = output / "best.pt"
    if not best_path.is_file():
        raise RuntimeError(f"找不到最佳 checkpoint：{best_path}")
    checkpoint = torch.load(best_path, map_location="cpu", weights_only=False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(config, len(checkpoint["feature_names"]))
    model.load_state_dict(checkpoint["model"])
    model = model.to(device).eval()
    cache = None
    if config["model"]["explicit_features"]["enabled"]:
        cache, _cache_names = load_feature_cache(PROJECT / config["data"]["explicit_feature_cache"])

    rows = [
        row for row in read_csv(PROJECT / config["data"]["manifest"])
        if row["training_eligible"].lower() == "true" and row["split"] == "validation"
    ]
    dataset = ConfigurableDataset(
        PROJECT, rows, config, False, cache, tuple(checkpoint["feature_names"]),
        np.asarray(checkpoint["feature_mean"], dtype=np.float32),
        np.asarray(checkpoint["feature_std"], dtype=np.float32),
    )
    loader = DataLoader(dataset, batch_size=int(config["training"]["batch_size"]), shuffle=False, num_workers=0)
    logits, targets = collect_logits(model, loader, device)
    logits, targets = logits.detach().clone(), targets.detach().clone()
    calibration_config = config["post_training"]["temperature_scaling"]
    before = calibration_error(logits, targets, 1.0)
    temperature = fit_temperature(logits, targets, int(calibration_config["max_iterations"])) if calibration_config["enabled"] else 1.0
    after = calibration_error(logits, targets, temperature)
    calibration = {
        "enabled": bool(calibration_config["enabled"]), "temperature": temperature,
        "validation_samples": int(targets.numel()), "ece_before": before, "ece_after": after,
        "argmax_unchanged": True, "test_used": False,
    }
    (output / "calibration.json").write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = heatmap_audit(model, config, checkpoint, cache, device, output)
    torch.save({
        **checkpoint, "temperature": temperature, "calibration": calibration,
        "heatmap_audit": audit, "artifact_role": "deployment_candidate_not_final_medical_device",
    }, output / "deployment_candidate.pt")
    print("校準=" + json.dumps(calibration, ensure_ascii=False), flush=True)
    print("熱力圖稽核=" + json.dumps(audit, ensure_ascii=False), flush=True)
    print(f"後處理完成：{output}", flush=True)


if __name__ == "__main__":
    main()
