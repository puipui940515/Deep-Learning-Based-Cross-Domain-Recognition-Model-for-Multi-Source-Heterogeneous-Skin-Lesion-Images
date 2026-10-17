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


def load_v2_module():
    path = ROOT / "scripts/train_mixed_v2.py"
    spec = importlib.util.spec_from_file_location("train_mixed_v2_eval", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    helper = load_v2_module()
    rows = [
        row for row in read_csv(ROOT / "data/mixed_manifest.csv")
        if row["split"] == "validation" and row["source"] == "PAD-UFES-20"
    ]
    if not rows:
        raise RuntimeError("PAD-UFES-20 validation rows are missing")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dataset = helper.MixedDataset(rows, image_size=224, train=False)
    loader = DataLoader(dataset, batch_size=32, shuffle=False, num_workers=0, pin_memory=device.type == "cuda")

    checkpoint = PROJECT / "多來源混合訓練_第一版/results/imagenet_seed17/best.pt"
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model = build_model("convnext_tiny", pretrained=False, num_classes=7)
    model.load_state_dict(state["model"])
    model.to(device).eval()

    logits_all, targets_all = [], []
    with torch.inference_mode():
        for images, targets, _image_ids, _sources in loader:
            logits_all.append(model(images.to(device, non_blocking=True)).float().cpu().numpy())
            targets_all.append(targets.numpy())
    logits = np.concatenate(logits_all)
    targets = np.concatenate(targets_all)
    metrics = helper.source_metrics(logits, targets, supported_labels=[0, 1, 2, 4, 6])
    metrics["samples"] = len(dataset)

    output = {
        "evaluation_only": True,
        "training_performed": False,
        "checkpoint": checkpoint.relative_to(PROJECT).as_posix(),
        "checkpoint_epoch": state.get("epoch"),
        "training_sources": state.get("mixed_sources", ["HAM10000", "BCN20000"]),
        "evaluation_source": "PAD-UFES-20",
        "manifest": "多來源混合訓練_第二版/data/mixed_manifest.csv",
        "split": "validation",
        "metrics": metrics,
        "test_used": False,
    }
    output_dir = ROOT / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "v1_best_on_v2_pad_validation.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
