from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DATASET_ROOT = PROJECT_ROOT / "Dataset"
CONFIG = json.loads((ROOT / "config/dataset_profiles.json").read_text(encoding="utf-8"))
SITE_CLASSES = CONFIG["target_schema"]
SITE_TO_LABEL = {name: index for index, name in enumerate(SITE_CLASSES)}

HAM_MAP = {
    "head_neck": "head_neck",
    "trunk": "trunk",
    "upper_extremity": "upper_extremity",
    "lower_extremity": "lower_extremity",
    "anogenital": "anogenital",
}
BCN_MAP = {
    "head/neck": "head_neck",
    "anterior torso": "trunk",
    "upper extremity": "upper_extremity",
    "lower extremity": "lower_extremity",
    "oral/genital": "anogenital",
}


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def stable_order(value: str, seed: int):
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def build_ham():
    rows = []
    source = read_csv(PROJECT_ROOT / "第三階段/data/fixed_split_with_site.csv")
    for row in source:
        site = HAM_MAP.get(row["site_group"])
        if site is None:
            continue
        rows.append({
            "source": "HAM10000",
            "image_id": row["isic_id"],
            "group_id": row["lesion_id"],
            "image_path": f"Dataset/HAM10000/{row['image_path']}",
            "split": row["split"],
            "site_group": site,
            "site_label": SITE_TO_LABEL[site],
            "license": "CC BY-NC 4.0",
        })
    return rows


def bcn_validation_lesions(train_rows):
    by_site = defaultdict(set)
    for row in train_rows:
        if row["anatom_site_general"] in BCN_MAP:
            by_site[BCN_MAP[row["anatom_site_general"]]].add(row["lesion_id"])
    selected = set()
    fraction = CONFIG["bcn_rules"]["internal_validation_lesion_fraction"]
    seed = CONFIG["bcn_rules"]["split_seed"]
    for site, lesions in by_site.items():
        ordered = sorted(lesions, key=lambda lesion: stable_order(f"{site}:{lesion}", seed))
        count = max(1, round(len(ordered) * fraction))
        selected.update(ordered[:count])
    return selected


def build_bcn():
    train_rows = read_csv(DATASET_ROOT / "BCN20000/metadata/available_train.csv")
    test_rows = read_csv(DATASET_ROOT / "BCN20000/metadata/available_test.csv")
    val_lesions = bcn_validation_lesions(train_rows)
    rows = []
    for source_split, source_rows in (("train", train_rows), ("official_test", test_rows)):
        for row in source_rows:
            site = BCN_MAP.get(row["anatom_site_general"])
            if site is None:
                continue
            if source_split == "official_test":
                split = "test"
                directory = "test"
            else:
                split = "val" if row["lesion_id"] in val_lesions else "train"
                directory = "train"
            rows.append({
                "source": "BCN20000",
                "image_id": Path(row["bcn_filename"]).stem,
                "group_id": row["lesion_id"],
                "image_path": f"Dataset/BCN20000/images/{directory}/{row['bcn_filename']}",
                "split": split,
                "site_group": site,
                "site_label": SITE_TO_LABEL[site],
                "license": "CC BY 4.0",
            })
    return rows


def write_profile(name: str, rows):
    output = ROOT / f"data/profiles/{name}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["source", "image_id", "group_id", "image_path", "split", "site_group", "site_label", "license"]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return output


ham = build_ham()
bcn = build_bcn()
profiles = {"ham": ham, "bcn": bcn, "ham_bcn": ham + bcn}
audit = {"profiles": {}, "rules": CONFIG["bcn_rules"], "test_loaded_by_training": False}
for name, rows in profiles.items():
    path = write_profile(name, rows)
    group_splits = defaultdict(set)
    missing_images = []
    for row in rows:
        group_splits[(row["source"], row["group_id"])].add(row["split"])
        if not (PROJECT_ROOT / row["image_path"]).exists():
            missing_images.append(row["image_path"])
    audit["profiles"][name] = {
        "path": str(path.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(Counter(row["split"] for row in rows)),
        "source_counts": dict(Counter(row["source"] for row in rows)),
        "site_counts": dict(Counter(row["site_group"] for row in rows)),
        "group_split_leakage": sum(len(splits) > 1 for splits in group_splits.values()),
        "missing_images": len(missing_images),
        "unique_image_ids_within_source": len({(row["source"], row["image_id"]) for row in rows}),
    }
audit["ham_bcn_cross_source_id_overlap"] = len(
    {row["image_id"] for row in ham} & {row["image_id"] for row in bcn}
)
audit["passed"] = all(
    item["group_split_leakage"] == 0 and item["missing_images"] == 0
    for item in audit["profiles"].values()
) and audit["ham_bcn_cross_source_id_overlap"] == 0
output = ROOT / "results/dataset_profiles_audit.json"
output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False, indent=2))
raise SystemExit(0 if audit["passed"] else 2)
