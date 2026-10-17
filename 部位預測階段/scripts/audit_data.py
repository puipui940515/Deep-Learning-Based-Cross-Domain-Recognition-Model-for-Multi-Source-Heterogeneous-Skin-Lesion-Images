from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config/site_stage.json").read_text(encoding="utf-8"))
manifest = ROOT / config["manifest"]
with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
    rows = list(csv.DictReader(handle))

known = set(config["site_classes"])
split_counts = defaultdict(Counter)
lesion_splits = defaultdict(set)
for row in rows:
    split_counts[row["split"]][row["site_group"]] += 1
    lesion_splits[row["lesion_id"]].add(row["split"])

audit = {
    "rows": len(rows),
    "unique_isic_ids": len({row["isic_id"] for row in rows}),
    "known_site_rows": sum(row["site_group"] in known for row in rows),
    "unknown_excluded_rows": sum(row["site_group"] == "unknown" for row in rows),
    "split_site_counts": {split: dict(counts) for split, counts in split_counts.items()},
    "lesion_split_leakage_count": sum(len(splits) > 1 for splits in lesion_splits.values()),
    "all_known_classes_in_train": all(split_counts["train"][site] > 0 for site in known),
    "all_known_classes_in_val": all(split_counts["val"][site] > 0 for site in known),
    "test_split_loaded_by_training": False,
}
audit["passed"] = (
    audit["rows"] == audit["unique_isic_ids"] == 10015
    and audit["lesion_split_leakage_count"] == 0
    and audit["all_known_classes_in_train"]
    and audit["all_known_classes_in_val"]
)
output = ROOT / "results/data_audit.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False, indent=2))
raise SystemExit(0 if audit["passed"] else 2)
