from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
SEEDS = (17, 42, 2026)
SITE_GROUPS = ("head_neck", "trunk", "upper_extremity", "lower_extremity", "anogenital", "unknown")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_site_manifest(base_path, site_path):
    report = {"exists": site_path.exists(), "passed": False}
    if not site_path.exists():
        return report
    base_rows = read_csv(base_path)
    site_rows = read_csv(site_path)
    required = {"anatom_site_raw", "site_group", "site_label", "site_known"}
    report.update(rows=len(site_rows), expected_rows=len(base_rows))
    if len(base_rows) != len(site_rows) or not site_rows or not required.issubset(site_rows[0]):
        return report
    base_fields = ("image_path", "isic_id", "lesion_id", "label", "split")
    base_unchanged = all(
        tuple(base_row[field] for field in base_fields) == tuple(site_row[field] for field in base_fields)
        for base_row, site_row in zip(base_rows, site_rows)
    )
    labels_valid = all(
        row["site_group"] in SITE_GROUPS
        and int(row["site_label"]) == SITE_GROUPS.index(row["site_group"])
        and row["site_known"] == ("0" if row["site_group"] == "unknown" else "1")
        for row in site_rows
    )
    report.update(
        base_rows_unchanged=base_unchanged,
        labels_valid=labels_valid,
        unique_isic_ids=len({row["isic_id"] for row in site_rows}),
        unknown_site_count=sum(row["site_group"] == "unknown" for row in site_rows),
    )
    report["passed"] = (
        base_unchanged and labels_valid and report["unique_isic_ids"] == len(site_rows) == 10015
    )
    return report


def inspect():
    gate_path = PROJECT_ROOT / "驗證/reports/validation_gate.json"
    stage2_split = PROJECT_ROOT / "第二階段/data/fixed_split.csv"
    stage3_split = ROOT / "data/fixed_split.csv"
    site_manifest = ROOT / "data/fixed_split_with_site.csv"
    site_report = validate_site_manifest(stage3_split, site_manifest)
    checks = {
        "validation_gate_passed": gate_path.exists()
        and json.loads(gate_path.read_text(encoding="utf-8")).get("passed", False),
        "manifest_matches_stage2": stage2_split.exists()
        and stage3_split.exists()
        and sha256(stage2_split) == sha256(stage3_split),
        "site_manifest": site_report,
        "v9_checkpoints": {
            str(seed): (PROJECT_ROOT / f"第二階段/checkpoints/v9_seed{seed}.pt").exists()
            for seed in SEEDS
        },
        "v9_results": {
            str(seed): (PROJECT_ROOT / f"第二階段/results/v9_seed{seed}.json").exists()
            for seed in SEEDS
        },
    }
    checks["formal_v10_ready"] = (
        checks["validation_gate_passed"]
        and checks["manifest_matches_stage2"]
        and checks["site_manifest"]["passed"]
        and all(checks["v9_checkpoints"].values())
        and all(checks["v9_results"].values())
    )
    return checks


if __name__ == "__main__":
    report = inspect()
    output = ROOT / "results/prerequisite_gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["formal_v10_ready"] else 2)
