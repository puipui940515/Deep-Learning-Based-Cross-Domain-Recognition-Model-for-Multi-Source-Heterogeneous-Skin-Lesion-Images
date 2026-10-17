from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DATASET_ROOT = PROJECT_ROOT / "Dataset"
OUTPUT = ROOT / "data/profiles/all_compatible.csv"
SITE_CLASSES = ["head_neck", "trunk", "upper_extremity", "lower_extremity", "anogenital"]
SITE_TO_LABEL = {name: index for index, name in enumerate(SITE_CLASSES)}

PAD_MAP = {
    "NECK": "head_neck", "FACE": "head_neck", "NOSE": "head_neck", "SCALP": "head_neck",
    "EAR": "head_neck", "LIP": "head_neck", "CHEST": "trunk", "BACK": "trunk",
    "ABDOMEN": "trunk", "ARM": "upper_extremity", "FOREARM": "upper_extremity",
    "HAND": "upper_extremity", "THIGH": "lower_extremity", "FOOT": "lower_extremity",
}
SCIN_MAP = {
    "body_parts_head_or_neck": "head_neck",
    "body_parts_arm": "upper_extremity",
    "body_parts_palm": "upper_extremity",
    "body_parts_back_of_hand": "upper_extremity",
    "body_parts_torso_front": "trunk",
    "body_parts_torso_back": "trunk",
    "body_parts_genitalia_or_groin": "anogenital",
    "body_parts_leg": "lower_extremity",
    "body_parts_foot_top_or_side": "lower_extremity",
    "body_parts_foot_sole": "lower_extremity",
}
FIELDS = ["source", "image_id", "isic_id", "group_id", "image_path", "split", "site_group", "site_label", "license", "image_domain"]


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def deterministic_split(group_id: str):
    value = int(hashlib.sha256(f"20260823:{group_id}".encode()).hexdigest()[:8], 16) % 10000
    return "train" if value < 7000 else "val" if value < 8500 else "test"


base_rows = read_csv(ROOT / "data/profiles/ham_bcn.csv")
rows = []
for row in base_rows:
    rows.append({**{field: row.get(field, "") for field in FIELDS}, "image_domain": "dermoscopy"})

pad_images = {path.name: path for path in (DATASET_ROOT / "PAD-UFES-20/all_images").rglob("*.png")}
pad_missing = []
for row in read_csv(DATASET_ROOT / "PAD-UFES-20/metadata.csv"):
    site = PAD_MAP.get(row["region"])
    path = pad_images.get(row["img_id"])
    if site is None or path is None:
        if path is None:
            pad_missing.append(row["img_id"])
        continue
    image_id = Path(row["img_id"]).stem
    rows.append({
        "source": "PAD-UFES-20",
        "image_id": image_id,
        "isic_id": image_id,
        "group_id": row["patient_id"],
        "image_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "split": deterministic_split(f"PAD:{row['patient_id']}"),
        "site_group": site,
        "site_label": SITE_TO_LABEL[site],
        "license": "CC BY 4.0",
        "image_domain": "clinical_smartphone",
    })

scin_cases = {row["case_id"]: row for row in read_csv(DATASET_ROOT / "SCIN/source_repository/dataset/scin_cases.csv")}
scin_files = {}
for path in (DATASET_ROOT / "SCIN/metadata").glob("*.csv"):
    for row in read_csv(path):
        scin_files.setdefault(row["file_path"], row["case_id"])
scin_exclusion = Counter()
for relative_path, case_id in scin_files.items():
    path = DATASET_ROOT / "SCIN" / relative_path
    case = scin_cases.get(case_id)
    if case is None or not path.exists():
        scin_exclusion["missing_case_or_image"] += 1
        continue
    coarse_sites = {
        target for column, target in SCIN_MAP.items()
        if (case.get(column) or "").strip().upper() == "YES"
    }
    has_unmapped_positive = any(
        (case.get(column) or "").strip().upper() == "YES"
        for column in ("body_parts_buttocks", "body_parts_other")
    )
    if has_unmapped_positive or len(coarse_sites) != 1:
        scin_exclusion["not_uniquely_mappable"] += 1
        continue
    site = next(iter(coarse_sites))
    image_id = path.stem
    rows.append({
        "source": "SCIN",
        "image_id": image_id,
        "isic_id": image_id,
        "group_id": case_id,
        "image_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "split": deterministic_split(f"SCIN:{case_id}"),
        "site_group": site,
        "site_label": SITE_TO_LABEL[site],
        "license": "SCIN Data Use License",
        "image_domain": "clinical_crowdsourced",
    })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

group_splits = defaultdict(set)
for row in rows:
    group_splits[(row["source"], row["group_id"])].add(row["split"])
audit = {
    "profile": "all_compatible",
    "rows": len(rows),
    "split_counts": dict(Counter(row["split"] for row in rows)),
    "source_split_counts": {
        source: dict(Counter(row["split"] for row in rows if row["source"] == source))
        for source in sorted({row["source"] for row in rows})
    },
    "source_site_counts": {
        source: dict(Counter(row["site_group"] for row in rows if row["source"] == source))
        for source in sorted({row["source"] for row in rows})
    },
    "group_split_leakage": sum(len(splits) > 1 for splits in group_splits.values()),
    "missing_images": sum(not (PROJECT_ROOT / row["image_path"]).exists() for row in rows),
    "duplicate_source_image_ids": len(rows) - len({(row["source"], row["image_id"]) for row in rows}),
    "pad_missing_metadata_images": len(pad_missing),
    "scin_exclusions": dict(scin_exclusion),
    "selection": "SCIN only uniquely mappable coarse-site cases with locally available images",
    "test_loaded_by_training": False,
}
audit["passed"] = audit["group_split_leakage"] == audit["missing_images"] == audit["duplicate_source_image_ids"] == 0
audit_path = ROOT / "results/all_compatible_audit.json"
audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False, indent=2))
raise SystemExit(0 if audit["passed"] else 2)
