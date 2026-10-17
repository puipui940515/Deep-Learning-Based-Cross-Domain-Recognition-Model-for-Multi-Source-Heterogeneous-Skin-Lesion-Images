from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

VALIDATION_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = VALIDATION_ROOT.parent
STAGE_ROOT = PROJECT_ROOT / "第一階段"
sys.path.insert(0, str(STAGE_ROOT / "src"))
from stage1.metrics import metrics_from_logits

with (STAGE_ROOT / "data/fixed_split.csv").open("r", encoding="utf-8-sig", newline="") as handle:
    rows = [row for row in csv.DictReader(handle) if row["split"] == "val"]
targets = np.array([int(row["label"]) for row in rows])
majority = int(np.bincount(targets).argmax())
logits = np.full((len(targets), 7), -10.0); logits[:, majority] = 10.0
result = metrics_from_logits(logits, targets)
expected = 1.0 / 7.0
result.update({"majority_class": majority, "expected_balanced_accuracy": expected,
               "passed": abs(result["balanced_accuracy"] - expected) < 1e-12})
(VALIDATION_ROOT / "reports").mkdir(parents=True, exist_ok=True)
(VALIDATION_ROOT / "reports/sanity_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
if not result["passed"]:
    raise SystemExit("balanced accuracy sanity check 失敗")

