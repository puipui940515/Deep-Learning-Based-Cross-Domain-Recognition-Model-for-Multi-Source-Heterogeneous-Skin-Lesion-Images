from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stage3.data import V10NullControlDataset, build_transform
from stage3.metrics import metrics_by_site
from stage3.site_labels import SITE_GROUPS, build_within_diagnosis_site_weights


def main():
    config = json.loads((ROOT / "config/stage3.json").read_text(encoding="utf-8"))
    manifest = ROOT / config["split_manifest"]
    dataset_root = (ROOT / config["dataset_root"]).resolve()
    train_set = V10NullControlDataset(manifest, dataset_root, "train", build_transform(64, False))
    val_set = V10NullControlDataset(manifest, dataset_root, "val", build_transform(64, False))
    views, diagnosis, isic_id, site = train_set[0]
    weights, weight_audit = build_within_diagnosis_site_weights(
        train_set.rows, **{
            key: config["site_labels"]["site_balanced_sampling"][key]
            for key in ("power", "max_weight", "min_group_count")
        }
    )
    means = defaultdict(list)
    for row, weight in zip(train_set.rows, weights):
        means[int(row["label"])].append(weight)
    diagnosis_weight_means = {str(key): float(np.mean(value)) for key, value in means.items()}

    logits = np.eye(7, dtype=np.float64)[[0, 1, 0, 2, 1, 2]] * 4.0
    targets = np.asarray([0, 1, 0, 2, 1, 2])
    sites = np.asarray([0, 0, 1, 1, 2, 2])
    site_metrics = metrics_by_site(logits, targets, sites, SITE_GROUPS, min_support=2)
    report = {
        "manifest": str(manifest),
        "train_rows": len(train_set),
        "val_rows": len(val_set),
        "sample": {
            "isic_id": isic_id,
            "diagnosis": diagnosis,
            "site_label": site,
            "view_shapes": [list(view.shape) for view in views],
        },
        "site_groups": list(SITE_GROUPS),
        "diagnosis_weight_means": diagnosis_weight_means,
        "weight_audit": weight_audit,
        "metric_smoke": site_metrics,
        "test_split_loaded": False,
    }
    report["passed"] = (
        len(train_set) == 7008
        and len(val_set) == 1504
        and len(views) == 4
        and all(abs(value - 1.0) < 1e-9 for value in diagnosis_weight_means.values())
        and site_metrics["worst_known_site_balanced_accuracy"] == 1.0
    )
    output = ROOT / "results/site_label_smoke_test.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
