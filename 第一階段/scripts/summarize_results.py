from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config/stage1.json").read_text(encoding="utf-8"))
rows = []
previous_mean = None
for version in ("v1", "v2", "v3", "v4"):
    results = []
    for seed in config["seeds"]:
        path = ROOT / f"results/{version}_seed{seed}.json"
        if path.exists():
            results.append(json.loads(path.read_text(encoding="utf-8")))
    if len(results) != len(config["seeds"]):
        rows.append({"version": version, "completed_seeds": len(results), "decision": "尚未完成三種種子"})
        continue
    scores = np.array([r["best_validation"]["balanced_accuracy"] for r in results])
    macro_f1 = np.array([r["best_validation"]["macro_f1"] for r in results])
    gaps = np.array([r["best_train"]["balanced_accuracy"] - r["best_validation"]["balanced_accuracy"] for r in results])
    mean, std = float(scores.mean()), float(scores.std(ddof=1))
    delta = "" if previous_mean is None else mean - previous_mean
    decision = "基線" if previous_mean is None else ("納入" if delta >= std else "不納入：提升小於種子標準差")
    rows.append({"version": version, "completed_seeds": len(results), "balanced_accuracy_mean": mean,
                 "balanced_accuracy_std": std, "delta_vs_previous": delta, "macro_f1_mean": float(macro_f1.mean()),
                 "train_val_gap_mean": float(gaps.mean()), "decision": decision})
    previous_mean = mean

fields = ["version", "completed_seeds", "balanced_accuracy_mean", "balanced_accuracy_std", "delta_vs_previous",
          "macro_f1_mean", "train_val_gap_mean", "decision"]
with (ROOT / "results/version_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
print(json.dumps(rows, ensure_ascii=False, indent=2))

