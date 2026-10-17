from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
results = [json.loads((ROOT / f"results/seed{seed}.json").read_text(encoding="utf-8")) for seed in (17, 42, 2026)]

rows = []
for result in results:
    for branch in ("control", "site_balanced"):
        metrics = result["branches"][branch]["validation"]
        rows.append({
            "seed": result["seed"],
            "branch": branch,
            "balanced_accuracy": metrics["balanced_accuracy"],
            "macro_f1": metrics["macro_f1"],
            "accuracy": metrics["accuracy"],
            "ece": metrics["ece"],
            "worst_known_site_balanced_accuracy": metrics["by_site"]["worst_known_site_balanced_accuracy"],
        })

with (ROOT / "results/comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

summary = {"seeds": [17, 42, 2026], "epochs_per_branch": results[0]["epochs_per_branch"], "branches": {}}
for branch in ("control", "site_balanced"):
    branch_rows = [row for row in rows if row["branch"] == branch]
    summary["branches"][branch] = {
        key: {"mean": float(np.mean([row[key] for row in branch_rows])), "sample_std": float(np.std([row[key] for row in branch_rows], ddof=1))}
        for key in ("balanced_accuracy", "macro_f1", "accuracy", "ece", "worst_known_site_balanced_accuracy")
    }

summary["site_balanced_minus_control"] = {
    key: {
        "mean": float(np.mean([result["site_balanced_minus_control"][key] for result in results])),
        "sample_std": float(np.std([result["site_balanced_minus_control"][key] for result in results], ddof=1)),
        "per_seed": {str(result["seed"]): result["site_balanced_minus_control"][key] for result in results},
    }
    for key in ("balanced_accuracy", "macro_f1", "ece", "worst_known_site_balanced_accuracy")
}
summary["test_split_used"] = False
summary["interpretation_limit"] = "短程 A/B 先導測試；不得取代從頭訓練的正式三 seed 結果"
(ROOT / "results/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
