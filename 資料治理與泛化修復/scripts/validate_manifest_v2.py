"""Validate the governed v2 manifest and write a compact, machine-readable gate.

This script does not alter, move, or delete source images. Invalid source images
remain registered in quarantine_v2.csv and are excluded from the clean manifest.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GOV = ROOT / "資料治理與泛化修復"
DATA = GOV / "data"
REPORTS = GOV / "reports"
EXPECTED_CLASSES = {
    "0": "AKIEC",
    "1": "BCC",
    "2": "BKL",
    "3": "DF",
    "4": "NV",
    "5": "VASC",
    "6": "MEL",
    "7": "SCC",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    manifest_path = DATA / "unified_manifest_v2.csv"
    quarantine_path = DATA / "quarantine_v2.csv"
    fingerprints_path = DATA / "image_fingerprints_v2.csv"
    integrity_path = REPORTS / "06_image_integrity_v2.json"
    dedup_path = REPORTS / "07_isic_v2_dedup_and_split.json"

    rows = read_csv(manifest_path)
    quarantine = read_csv(quarantine_path)
    fingerprints = {
        row["image_path"]: row for row in read_csv(fingerprints_path)
        if not row.get("error") and row.get("sha256")
    }
    integrity = read_json(integrity_path)
    dedup = read_json(dedup_path)

    missing_files = [row["record_id"] for row in rows if not (ROOT / row["image_path"]).is_file()]
    missing_fingerprints = [row["record_id"] for row in rows if row["image_path"] not in fingerprints]

    record_counts = Counter(row["record_id"] for row in rows)
    duplicate_record_ids = [key for key, count in record_counts.items() if count > 1]

    sha_members: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        fingerprint = fingerprints.get(row["image_path"])
        if fingerprint:
            sha_members[fingerprint["sha256"]].append(row["record_id"])
    duplicate_sha_sets = [members for members in sha_members.values() if len(members) > 1]

    group_splits: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        group_splits[(row["source"], row["split_group_id"])].add(row["split"])
    cross_split_groups = [
        {"source": key[0], "split_group_id": key[1], "splits": sorted(splits)}
        for key, splits in group_splits.items() if len(splits) > 1
    ]

    label_errors = [
        row["record_id"] for row in rows
        if EXPECTED_CLASSES.get(row["label_id"]) != row["label_name"]
        or row["label"] != row["label_id"]
        or row["diagnosis_canonical_code"] != row["label_name"]
    ]
    eligibility_errors = [
        row["record_id"] for row in rows
        if row["training_eligible"].lower() != "true" or row["exclusion_reason"]
    ]

    invalid_quarantine_rows = sum(
        "image_decode_or_fingerprint_failed" in row.get("quarantine_reason", "")
        for row in quarantine
    )
    checks = {
        "manifest_nonempty": bool(rows),
        "all_files_exist": not missing_files,
        "all_rows_have_valid_fingerprint": not missing_fingerprints,
        "record_ids_unique": not duplicate_record_ids,
        "sha256_content_unique": not duplicate_sha_sets,
        "group_split_leakage_absent": not cross_split_groups,
        "labels_follow_v2_mapping": not label_errors,
        "all_manifest_rows_training_eligible": not eligibility_errors,
        "dedup_report_passed": bool(dedup.get("passed")),
    }
    report = {
        "schema_version": "skindetect-data-contract-v2.0",
        "generated_at": "2026-09-11",
        "passed": all(checks.values()),
        "checks": checks,
        "clean_rows": len(rows),
        "quarantine_rows": len(quarantine),
        "source_decode_or_fingerprint_errors": integrity.get("decode_or_fingerprint_errors", 0),
        "invalid_images_quarantined": invalid_quarantine_rows,
        "source_counts": dict(sorted(Counter(row["source"] for row in rows).items())),
        "split_counts": dict(sorted(Counter(row["split"] for row in rows).items())),
        "class_counts": dict(sorted(Counter(row["label_name"] for row in rows).items())),
        "license_counts": dict(sorted(Counter(row["license"] for row in rows).items())),
        "modality_counts": dict(sorted(Counter(row["image_modality"] for row in rows).items())),
        "problems": {
            "missing_files": missing_files[:100],
            "missing_fingerprints": missing_fingerprints[:100],
            "duplicate_record_ids": duplicate_record_ids[:100],
            "duplicate_sha256_sets": duplicate_sha_sets[:100],
            "cross_split_groups": cross_split_groups[:100],
            "label_errors": label_errors[:100],
            "eligibility_errors": eligibility_errors[:100],
        },
        "training_was_started": False,
    }
    write_json(REPORTS / "08_manifest_validation_v2.json", report)

    gate = {
        "pipeline_id": "isic_expansion_governance_v2",
        "passed": report["passed"],
        "inventory_passed": read_json(REPORTS / "05_isic_v2_inventory.json").get("passed", False),
        "source_image_integrity_passed_before_quarantine": integrity.get("passed", False),
        "source_decode_or_fingerprint_errors": integrity.get("decode_or_fingerprint_errors", 0),
        "invalid_images_quarantined": invalid_quarantine_rows,
        "final_training_manifest_integrity_passed": checks["all_files_exist"] and checks["all_rows_have_valid_fingerprint"],
        "dedup_and_split_passed": checks["sha256_content_unique"] and checks["group_split_leakage_absent"],
        "label_mapping_passed": checks["labels_follow_v2_mapping"],
        "schema": "schema/data_contract_v2.json",
        "disease_mapping": "schema/disease_mapping_v2.csv",
        "anatomical_site_mapping": "schema/anatomical_site_mapping_v2.csv",
        "source_registry": "../Dataset/SOURCE_REGISTRY.json",
        "unified_manifest": "data/unified_manifest_v2.csv",
        "quarantine_manifest": "data/quarantine_v2.csv",
        "clean_rows": len(rows),
        "quarantine_rows": len(quarantine),
        "class_count": len(EXPECTED_CLASSES),
        "class_order": [EXPECTED_CLASSES[str(index)] for index in range(len(EXPECTED_CLASSES))],
        "training_was_started": False,
    }
    write_json(REPORTS / "data_gate_v2.json", gate)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
