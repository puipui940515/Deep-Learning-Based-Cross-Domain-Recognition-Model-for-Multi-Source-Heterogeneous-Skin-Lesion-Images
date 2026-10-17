from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
summary = {"comparison_id": config["comparison_id"], "conditions": {}, "test_used": False}
for condition in config["conditions"]:
    rows = []
    for seed in config["seeds"]:
        path = ROOT / "results" / condition / f"seed{seed}" / "result.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        best = result["best"]["val"]
        rows.append({"seed": seed, "best_epoch": result["best"]["epoch"], **best})
    if not rows:
        continue
    metrics = {}
    for metric in ("balanced_accuracy", "macro_f1", "accuracy", "ece", "loss"):
        values = np.asarray([row[metric] for row in rows], dtype=float)
        metrics[metric] = {"mean": float(values.mean()), "sample_std": float(values.std(ddof=1)) if len(values) > 1 else None}
    summary["conditions"][condition] = {"runs": rows, "aggregate": metrics}

baseline = summary["conditions"].get("imagenet_init")
true_group = summary["conditions"].get("densepose_true_init")
negative = summary["conditions"].get("densepose_shuffled_matched_init")
if baseline and true_group:
    difference = 100 * (true_group["aggregate"]["balanced_accuracy"]["mean"] - baseline["aggregate"]["balanced_accuracy"]["mean"])
    summary["true_minus_imagenet_balanced_accuracy_pp"] = difference
if negative and true_group:
    difference = 100 * (true_group["aggregate"]["balanced_accuracy"]["mean"] - negative["aggregate"]["balanced_accuracy"]["mean"])
    summary["true_minus_shuffled_balanced_accuracy_pp"] = difference
summary["complete"] = all(len(summary["conditions"].get(c, {}).get("runs", [])) == len(config["seeds"]) for c in config["conditions"])
(ROOT / "results").mkdir(parents=True, exist_ok=True)
(ROOT / "results/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
