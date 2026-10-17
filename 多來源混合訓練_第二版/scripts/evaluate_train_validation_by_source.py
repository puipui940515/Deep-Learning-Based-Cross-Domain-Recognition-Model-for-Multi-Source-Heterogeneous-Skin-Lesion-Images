from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
STAGE2 = PROJECT / "第二階段"
sys.path.insert(0, str(STAGE2 / "src"))

from stage2.models import build_model


def load_helper():
    path = ROOT / "scripts/train_mixed_v2.py"
    spec = importlib.util.spec_from_file_location("train_mixed_v2_source_eval", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@torch.inference_mode()
def evaluate(model, rows, helper, device, supported_labels):
    dataset = helper.MixedDataset(rows, image_size=224, train=False)
    loader = DataLoader(
        dataset, batch_size=64, shuffle=False, num_workers=0,
        pin_memory=device.type == "cuda",
    )
    logits_all, targets_all = [], []
    processed = 0
    for images, targets, _image_ids, _sources in loader:
        logits_all.append(model(images.to(device, non_blocking=True)).float().cpu().numpy())
        targets_all.append(targets.numpy())
        processed += len(targets)
        if processed % 2048 == 0 or processed == len(dataset):
            print(f"inference {processed}/{len(dataset)}", flush=True)
    metrics = helper.source_metrics(
        np.concatenate(logits_all), np.concatenate(targets_all), supported_labels
    )
    metrics["samples"] = len(dataset)
    return metrics


def main() -> None:
    helper = load_helper()
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    rows = read_csv(ROOT / "data/mixed_manifest.csv")
    checkpoint = ROOT / "results/imagenet_seed17/best.pt"
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model("convnext_tiny", pretrained=False, num_classes=7)
    model.load_state_dict(state["model"])
    model.to(device).eval()

    results = {}
    for source in ["HAM10000", "BCN20000", "PAD-UFES-20"]:
        results[source] = {}
        supported = config["sources"][source]["supported_labels"]
        for split in ["train", "validation"]:
            selected = [row for row in rows if row["source"] == source and row["split"] == split]
            print(f"evaluate source={source} split={split} samples={len(selected)}", flush=True)
            results[source][split] = evaluate(model, selected, helper, device, supported)

    output = {
        "evaluation_only": True,
        "training_performed": False,
        "checkpoint": checkpoint.relative_to(PROJECT).as_posix(),
        "checkpoint_epoch": state.get("epoch"),
        "transform": "deterministic_resize_224_no_augmentation",
        "metrics_by_source_split": results,
        "test_used": False,
    }
    output_dir = ROOT / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "v2_best_train_validation_by_source.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {output_path}", flush=True)


if __name__ == "__main__":
    main()
