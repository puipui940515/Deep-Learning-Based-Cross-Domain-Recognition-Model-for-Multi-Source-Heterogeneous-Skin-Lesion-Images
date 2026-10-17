"""Audit noisefilter design behaviour on the fixed HAM10000 validation split.

Outputs deterministic PeripheralReference weight maps and numerical correction
strengths. This is an implementation audit, not a model-performance experiment.
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "files_test"))

from noisefilter import FilterChain  # noqa: E402


REPORT_ROOT = ROOT / "驗證" / "reports" / "noisefilter_design"
MAP_ROOT = REPORT_ROOT / "peripheral_weight_maps"
ALPHA = torch.tensor([0.25, 0.5, 0.5, 0.5], dtype=torch.float32)
CLASS_NAMES = ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL"]


def load_validation_rows() -> list[dict[str, str]]:
    split_files = list(ROOT.rglob("fixed_split.csv"))
    if not split_files:
        raise FileNotFoundError("fixed_split.csv not found")
    sets = []
    for path in split_files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row["split"] == "val"]
        sets.append(rows)
    ids = [{row["isic_id"] for row in rows} for rows in sets]
    if not all(item == ids[0] for item in ids):
        raise RuntimeError("Stage fixed validation splits do not match")
    return sorted(sets[0], key=lambda row: row["isic_id"])


def load_rgb(row: dict[str, str], size: int = 224) -> torch.Tensor:
    path = ROOT / "Dataset" / "HAM10000" / row["image_path"]
    with Image.open(path) as image:
        image = image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
        array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(array).permute(2, 0, 1)


def load_filter(device: torch.device) -> tuple[FilterChain, Path]:
    checkpoints = list(ROOT.rglob("stage2_v5_noisefilter_core_fixed_seed42.pt"))
    if len(checkpoints) != 1:
        raise RuntimeError(f"Expected one stage2 seed42 checkpoint, got {len(checkpoints)}")
    checkpoint = torch.load(checkpoints[0], map_location="cpu", weights_only=False)
    chain = FilterChain(alpha_init=ALPHA.tolist(), learn_alpha=False)
    state = {
        key.removeprefix("filter."): value
        for key, value in checkpoint["model"].items()
        if key.startswith("filter.")
    }
    chain.load_state_dict(state, strict=True)
    chain.eval().to(device)
    return chain, checkpoints[0]


def apply_stages(
    chain: FilterChain, x: torch.Tensor, skip: set[int] | None = None
) -> tuple[torch.Tensor, list[torch.Tensor], list[torch.Tensor]]:
    skip = skip or set()
    out = x
    before, deltas = [], []
    for index, (stage, enabled) in enumerate(zip(chain.stages, chain.enabled)):
        if not enabled or index in skip:
            continue
        previous = out
        transformed = stage(previous)
        alpha = ALPHA[index].to(device=x.device, dtype=x.dtype)
        out = (1.0 - alpha) * previous + alpha * transformed
        before.append(previous)
        deltas.append(out - previous)
    return out, before, deltas


def peripheral_weight(chain: FilterChain, x: torch.Tensor) -> torch.Tensor:
    stage = chain.stages[3]
    _, _, height, width = x.shape
    ys = torch.linspace(-1.0, 1.0, height, device=x.device, dtype=x.dtype)
    xs = torch.linspace(-1.0, 1.0, width, device=x.device, dtype=x.dtype)
    yy, xx = torch.meshgrid(ys, xs, indexing="ij")
    radius = torch.sqrt(xx**2 + yy**2).view(1, 1, height, width)
    radial = torch.sigmoid((radius - stage.r0()) / stage.radial_tau)
    luminance = x.mean(dim=1, keepdim=True)
    bright = torch.sigmoid((luminance - stage.dark_thresh) / stage.dark_tau)
    return (radial * bright).clamp_min(1e-6)


def cosine_per_image(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    a = a.flatten(1)
    b = b.flatten(1)
    return (a * b).sum(1) / (a.norm(dim=1) * b.norm(dim=1)).clamp_min(1e-12)


def summarize(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(array.mean()),
        "std": float(array.std(ddof=0)),
        "median": float(np.median(array)),
        "p05": float(np.quantile(array, 0.05)),
        "p95": float(np.quantile(array, 0.95)),
    }


def audit_strengths(rows: list[dict[str, str]], chain: FilterChain, device: torch.device) -> dict:
    names = ["LogContrast", "IlluminationFlatten", "GlobalColorConstancy", "PeripheralReference"]
    metrics: dict[str, list[float]] = defaultdict(list)
    batch_size = 16
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            batch_rows = rows[start : start + batch_size]
            x = torch.stack([load_rgb(row) for row in batch_rows]).to(device)
            final, before, deltas = apply_stages(chain, x)
            no_gcc, _, _ = apply_stages(chain, x, {2})
            no_peripheral, _, _ = apply_stages(chain, x, {3})

            for index, (previous, delta) in enumerate(zip(before, deltas)):
                stage_name = names[index]
                applied_mae = delta.abs().mean(dim=(1, 2, 3))
                full_mae = (delta / ALPHA[index].to(device)).abs().mean(dim=(1, 2, 3))
                channel_shift = delta.mean(dim=(2, 3))
                brightness_shift = channel_shift.mean(dim=1).abs()
                chroma_shift = (channel_shift - channel_shift.mean(dim=1, keepdim=True)).norm(dim=1)
                for key, tensor in {
                    f"{stage_name}.applied_pixel_mae": applied_mae,
                    f"{stage_name}.full_transform_pixel_mae": full_mae,
                    f"{stage_name}.absolute_mean_brightness_shift": brightness_shift,
                    f"{stage_name}.channel_differential_shift_l2": chroma_shift,
                }.items():
                    metrics[key].extend(tensor.detach().cpu().tolist())

            metrics["combined.final_vs_input_mae"].extend(
                (final - x).abs().mean(dim=(1, 2, 3)).cpu().tolist()
            )
            metrics["combined.actual_GCC_contribution_mae"].extend(
                (final - no_gcc).abs().mean(dim=(1, 2, 3)).cpu().tolist()
            )
            metrics["combined.actual_PeripheralReference_contribution_mae"].extend(
                (final - no_peripheral).abs().mean(dim=(1, 2, 3)).cpu().tolist()
            )
            metrics["overlap.cosine_LogContrast_vs_GCC_delta"].extend(
                cosine_per_image(deltas[0], deltas[2]).cpu().tolist()
            )
            metrics["overlap.cosine_LogContrast_vs_Peripheral_delta"].extend(
                cosine_per_image(deltas[0], deltas[3]).cpu().tolist()
            )
            metrics["overlap.cosine_GCC_vs_Peripheral_delta"].extend(
                cosine_per_image(deltas[2], deltas[3]).cpu().tolist()
            )
    return {key: summarize(value) for key, value in sorted(metrics.items())}


def select_map_rows(rows: list[dict[str, str]], count: int = 40) -> list[dict[str, str]]:
    rng = random.Random(20260815)
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["label"])].append(row)
    for group in grouped.values():
        rng.shuffle(group)
    selected = []
    while len(selected) < count:
        made_progress = False
        for label in range(7):
            if grouped[label] and len(selected) < count:
                selected.append(grouped[label].pop())
                made_progress = True
        if not made_progress:
            break
    return selected


def save_weight_maps(rows: list[dict[str, str]], chain: FilterChain, device: torch.device) -> dict:
    MAP_ROOT.mkdir(parents=True, exist_ok=True)
    tiles = []
    statistics: dict[str, list[float]] = defaultdict(list)
    with torch.inference_mode():
        for index, row in enumerate(rows, start=1):
            x = load_rgb(row).unsqueeze(0).to(device)
            weight = peripheral_weight(chain, x)[0, 0].cpu().numpy()
            original = (x[0].permute(1, 2, 0).cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
            heat = np.stack(
                [255 * weight, 190 * weight, 255 * (1.0 - weight)], axis=-1
            ).clip(0, 255).astype(np.uint8)
            overlay = (0.48 * original + 0.52 * heat).clip(0, 255).astype(np.uint8)
            panel = Image.new("RGB", (448, 246), "white")
            panel.paste(Image.fromarray(original), (0, 22))
            panel.paste(Image.fromarray(overlay), (224, 22))
            draw = ImageDraw.Draw(panel)
            title = f"{index:02d} {row['isic_id']} {CLASS_NAMES[int(row['label'])]} | original / weight overlay"
            draw.text((4, 4), title, fill="black")
            output = MAP_ROOT / f"{index:02d}_{row['isic_id']}_{CLASS_NAMES[int(row['label'])]}.png"
            panel.save(output)
            tiles.append(panel.resize((336, 184), Image.Resampling.LANCZOS))

            height, width = weight.shape
            yy, xx = np.mgrid[-1:1:complex(height), -1:1:complex(width)]
            radius = np.sqrt(xx**2 + yy**2)
            statistics["fraction_weight_gt_0_5"].append(float((weight > 0.5).mean()))
            statistics["central_weight_mean_r_lt_0_5"].append(float(weight[radius < 0.5].mean()))
            statistics["peripheral_weight_mean_r_gt_0_8"].append(float(weight[radius > 0.8].mean()))

    columns = 4
    rows_count = math.ceil(len(tiles) / columns)
    sheet = Image.new("RGB", (columns * 336, rows_count * 184), "white")
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * 336, (index // columns) * 184))
    sheet.save(REPORT_ROOT / "peripheral_weight_maps_contact_sheet.png")
    return {
        "sample_count": len(rows),
        "selection": "deterministic class-round-robin from fixed HAM10000 validation split",
        "statistics": {key: summarize(value) for key, value in sorted(statistics.items())},
    }


def main() -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    rows = load_validation_rows()
    if len(rows) != 1504:
        raise RuntimeError(f"Expected 1504 validation rows, got {len(rows)}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    chain, checkpoint = load_filter(device)
    maps = save_weight_maps(select_map_rows(rows), chain, device)
    strengths = audit_strengths(rows, chain, device)
    report = {
        "status": "complete",
        "scope": "HAM10000 fixed validation split",
        "validation_images": len(rows),
        "device": str(device),
        "checkpoint": str(checkpoint.relative_to(ROOT)),
        "filter_description": chain.describe(),
        "peripheral_weight_maps": maps,
        "correction_strengths": strengths,
        "limitations": [
            "HAM10000 has no lesion segmentation masks in this project, so lesion-area contamination cannot be quantified reliably.",
            "Weight maps show where the implementation samples; they do not prove that sampled pixels are normal skin.",
        ],
    }
    (REPORT_ROOT / "design_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "validation_images": len(rows),
        "device": str(device),
        "weight_maps": maps["sample_count"],
        "output": str(REPORT_ROOT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
