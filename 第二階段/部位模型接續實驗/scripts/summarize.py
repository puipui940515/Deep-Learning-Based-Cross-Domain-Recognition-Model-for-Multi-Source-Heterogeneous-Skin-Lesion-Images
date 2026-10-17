from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
results = [json.loads((ROOT / f"results/fusion_seed{seed}.json").read_text(encoding="utf-8")) for seed in (17, 42, 2026)]
rows = []
for result in results:
    seed = result["disease_seed"]
    rows.append({"seed": seed, "branch": "baseline", **{key: result["baseline"][key] for key in ("balanced_accuracy", "macro_f1", "accuracy", "ece")}})
    for branch in ("bias_control", "site_fusion", "shuffled_site"):
        metrics = result["branches"][branch]["validation"]
        rows.append({"seed": seed, "branch": branch, **{key: metrics[key] for key in ("balanced_accuracy", "macro_f1", "accuracy", "ece")}})
with (ROOT / "results/comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
summary = {"branches": {}, "paired_deltas": {}, "test_used": False}
for branch in ("baseline", "bias_control", "site_fusion", "shuffled_site"):
    current = [row for row in rows if row["branch"] == branch]
    summary["branches"][branch] = {
        key: {"mean": float(np.mean([row[key] for row in current])), "sample_std": float(np.std([row[key] for row in current], ddof=1))}
        for key in ("balanced_accuracy", "macro_f1", "accuracy", "ece")
    }
for comparison, right in (("site_minus_baseline", "baseline"), ("site_minus_bias", "bias_control"), ("site_minus_shuffled", "shuffled_site")):
    values = []
    for result in results:
        site_score = result["branches"]["site_fusion"]["validation"]["balanced_accuracy"]
        other = result["baseline"]["balanced_accuracy"] if right == "baseline" else result["branches"][right]["validation"]["balanced_accuracy"]
        values.append(site_score - other)
    summary["paired_deltas"][comparison] = {"mean": float(np.mean(values)), "sample_std": float(np.std(values, ddof=1)), "per_seed": dict(zip((17, 42, 2026), values))}
(ROOT / "results/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
