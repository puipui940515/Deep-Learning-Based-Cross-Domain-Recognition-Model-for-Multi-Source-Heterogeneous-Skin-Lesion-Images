from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
rows = []
for seed in config["seeds"]:
    path = ROOT / f"results/{config['experiment_id']}_seed{seed}.json"
    if not path.exists():
        raise SystemExit(f"缺少結果：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    ev = data["evaluation"]
    rows.append({
        "seed": seed,
        "baseline_clean_ba": ev["baseline_clean"]["balanced_accuracy"],
        "filtered_clean_ba": ev["filtered_clean"]["balanced_accuracy"],
        "clean_ba_delta": ev["clean_balanced_accuracy_delta"],
        "baseline_perturbed_ba": ev["baseline_perturbed"]["balanced_accuracy"],
        "filtered_perturbed_ba": ev["filtered_perturbed"]["balanced_accuracy"],
        "perturbed_ba_delta": ev["perturbed_balanced_accuracy_delta"],
        "baseline_robustness_drop": ev["baseline_robustness_drop"],
        "filtered_robustness_drop": ev["filtered_robustness_drop"],
    })

with (ROOT / "results/comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)

def mean(key): return float(np.mean([row[key] for row in rows]))
def std(key): return float(np.std([row[key] for row in rows]))
summary = {"experiment_id": config["experiment_id"], "seeds": config["seeds"],
           "mounted": config["mounted"], "alpha": config["alpha"],
           "mean": {key: mean(key) for key in rows[0] if key != "seed"},
           "std": {key: std(key) for key in rows[0] if key != "seed"}}
(ROOT / "results/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
