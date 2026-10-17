from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
paths = [ROOT / f"results/site_resnet18_seed{seed}.json" for seed in (17, 42, 2026)]
available = [json.loads(path.read_text(encoding="utf-8")) for path in paths if path.exists()]
if not available:
    raise SystemExit("尚無訓練結果")
rows = []
for result in available:
    best = result["best"]["validation"]
    rows.append({
        "seed": result["seed"],
        "best_epoch": result["best"]["epoch"],
        "balanced_accuracy": best["balanced_accuracy"],
        "macro_f1": best["macro_f1"],
        "accuracy": best["accuracy"],
        "ece": best["ece"],
    })
with (ROOT / "results/summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
summary = {
    "completed_seeds": [row["seed"] for row in rows],
    "metrics": {
        key: {
            "mean": float(np.mean([row[key] for row in rows])),
            "sample_std": float(np.std([row[key] for row in rows], ddof=1)) if len(rows) > 1 else None,
        }
        for key in ("balanced_accuracy", "macro_f1", "accuracy", "ece")
    },
    "test_used": False,
}
(ROOT / "results/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
