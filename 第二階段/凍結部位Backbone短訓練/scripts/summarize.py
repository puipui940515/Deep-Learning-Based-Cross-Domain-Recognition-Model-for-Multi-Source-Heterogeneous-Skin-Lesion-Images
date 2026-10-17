from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, stdev


ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
records = []
for condition in config["conditions"]:
    for seed in config["seeds"]:
        path = ROOT / "results" / condition / f"seed{seed}" / "result.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        best = result["best"]["val"]
        records.append({
            "condition": condition, "seed": seed, "best_epoch": result["best"]["epoch"],
            "validation_accuracy": best["accuracy"], "validation_balanced_accuracy": best["balanced_accuracy"],
            "validation_macro_f1": best["macro_f1"], "validation_ece": best["ece"],
            "test_used": result["test_used"], "direct_comparison_valid": result["direct_comparison_valid"]
        })

aggregate = []
for condition in config["conditions"]:
    subset = [row for row in records if row["condition"] == condition]
    if not subset:
        continue
    values = [row["validation_balanced_accuracy"] for row in subset]
    aggregate.append({
        "condition": condition, "n": len(values), "mean_validation_balanced_accuracy": mean(values),
        "sample_sd_validation_balanced_accuracy": stdev(values) if len(values) > 1 else None,
        "direct_comparison_valid": all(row["direct_comparison_valid"] for row in subset)
    })

payload = {"comparison_id": config["comparison_id"], "records": records, "aggregate": aggregate, "test_used": False}
(ROOT / "results" / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
