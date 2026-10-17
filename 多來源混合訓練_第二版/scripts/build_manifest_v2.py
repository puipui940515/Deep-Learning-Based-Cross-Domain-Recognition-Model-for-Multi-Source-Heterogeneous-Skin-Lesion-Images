from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
CONFIG_PATH = ROOT / "config.json"

CLASS_NAMES = {0: "AKIEC", 1: "BCC", 2: "BKL", 3: "DF", 4: "NV", 5: "VASC", 6: "MEL"}
BCN_MAP = {"AK": 0, "BCC": 1, "BKL": 2, "DF": 3, "NV": 4, "VASC": 5, "MEL": 6}
PAD_MAP = {"ACK": 0, "BCC": 1, "SEK": 2, "NEV": 4, "MEL": 6}
PAD_SPLIT_SEED = 20260901


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def project_relative_file(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved.relative_to(PROJECT).as_posix()


def append_row(
    rows: list[dict], *, source: str, split: str, image_path: Path, image_id: str,
    group_id: str, diagnosis: str, label: int, license_name: str, split_origin: str,
) -> None:
    rows.append({
        "row_id": len(rows),
        "source": source,
        "split": split,
        "image_path": project_relative_file(image_path),
        "image_id": image_id,
        "group_id": group_id,
        "diagnosis_original": diagnosis,
        "label": label,
        "label_name": CLASS_NAMES[label],
        "license": license_name,
        "split_origin": split_origin,
    })


def add_ham(rows: list[dict], excluded: Counter) -> None:
    for row in read_csv(PROJECT / "第二階段/data/fixed_split.csv"):
        if row["split"] == "test":
            excluded["HAM10000_test_sealed"] += 1
            continue
        label = int(row["label"])
        append_row(
            rows,
            source="HAM10000",
            split="validation" if row["split"] == "val" else "train",
            image_path=PROJECT / "Dataset/HAM10000" / row["image_path"],
            image_id=row["isic_id"],
            group_id=row["lesion_id"],
            diagnosis=CLASS_NAMES[label],
            label=label,
            license_name="CC BY-NC 4.0",
            split_origin="第二階段固定病灶切分",
        )


def add_bcn(rows: list[dict], excluded: Counter) -> None:
    metadata = read_csv(PROJECT / "Dataset/BCN20000/metadata/available_train.csv")
    meta_by_file = {row["bcn_filename"]: row for row in metadata}
    validation_lesions = set()
    for profile_row in read_csv(PROJECT / "部位預測階段/data/profiles/bcn.csv"):
        if profile_row["split"] != "val":
            continue
        meta = meta_by_file.get(Path(profile_row["image_path"]).name)
        if meta is not None:
            validation_lesions.add(meta["lesion_id"])

    for row in metadata:
        diagnosis = row["diagnosis"]
        if diagnosis not in BCN_MAP:
            excluded[f"BCN20000_unmapped_{diagnosis or 'EMPTY'}"] += 1
            continue
        label = BCN_MAP[diagnosis]
        append_row(
            rows,
            source="BCN20000",
            split="validation" if row["lesion_id"] in validation_lesions else "train",
            image_path=PROJECT / "Dataset/BCN20000/images/train" / row["bcn_filename"],
            image_id=Path(row["bcn_filename"]).stem,
            group_id=row["lesion_id"],
            diagnosis=diagnosis,
            label=label,
            license_name="CC BY 4.0",
            split_origin="既有 BCN 病灶切分；同 lesion_id 強制同 split",
        )


def add_pad(rows: list[dict], excluded: Counter) -> None:
    metadata = read_csv(PROJECT / "Dataset/PAD-UFES-20/metadata.csv")
    image_index = {
        path.name: path
        for path in (PROJECT / "Dataset/PAD-UFES-20/all_images").rglob("*")
        if path.is_file()
    }
    mapped = []
    for row in metadata:
        diagnosis = row["diagnostic"]
        if diagnosis not in PAD_MAP:
            excluded[f"PAD-UFES-20_unmapped_{diagnosis or 'EMPTY'}"] += 1
            continue
        if row["img_id"] not in image_index:
            excluded["PAD-UFES-20_missing_image"] += 1
            continue
        mapped.append(row)

    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=PAD_SPLIT_SEED)
    labels = np.asarray([PAD_MAP[row["diagnostic"]] for row in mapped], dtype=np.int64)
    patient_ids = np.asarray([row["patient_id"] for row in mapped])
    placeholder = np.zeros((len(mapped), 1), dtype=np.float32)
    _train_indices, validation_indices = next(splitter.split(placeholder, labels, patient_ids))
    validation_patients = {mapped[index]["patient_id"] for index in validation_indices}

    for row in mapped:
        diagnosis = row["diagnostic"]
        label = PAD_MAP[diagnosis]
        append_row(
            rows,
            source="PAD-UFES-20",
            split="validation" if row["patient_id"] in validation_patients else "train",
            image_path=image_index[row["img_id"]],
            image_id=Path(row["img_id"]).stem,
            group_id=row["patient_id"],
            diagnosis=diagnosis,
            label=label,
            license_name="CC BY 4.0",
            split_origin="StratifiedGroupKFold；patient_id 隔離；n=5 fold=0 seed=20260901",
        )


def audit_group_leakage(rows: list[dict]) -> list[dict]:
    splits = defaultdict(set)
    for row in rows:
        splits[(row["source"], row["group_id"])].add(row["split"])
    return [
        {"source": source, "group_id": group_id, "splits": sorted(values)}
        for (source, group_id), values in splits.items()
        if len(values) > 1
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def audit_exact_duplicates(rows: list[dict]) -> list[dict]:
    by_hash = defaultdict(list)
    for index, row in enumerate(rows, 1):
        by_hash[sha256(PROJECT / row["image_path"])].append(row)
        if index % 1000 == 0 or index == len(rows):
            print(f"hash audit: {index}/{len(rows)}", flush=True)
    duplicates = []
    for digest, items in by_hash.items():
        sources = {item["source"] for item in items}
        splits = {item["split"] for item in items}
        if len(items) > 1 and (len(sources) > 1 or len(splits) > 1):
            duplicates.append({
                "sha256": digest,
                "sources": sorted(sources),
                "splits": sorted(splits),
                "rows": [item["row_id"] for item in items],
                "image_paths": [item["image_path"] for item in items],
            })
    return duplicates


def write_manifest(path: Path, rows: list[dict]) -> None:
    fields = [
        "row_id", "source", "split", "image_path", "image_id", "group_id",
        "diagnosis_original", "label", "label_name", "license", "split_origin",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="建立 HAM10000 + BCN20000 + PAD-UFES-20 混合清單")
    parser.add_argument("--hash-audit", action="store_true")
    args = parser.parse_args()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))

    rows: list[dict] = []
    excluded: Counter = Counter()
    add_ham(rows, excluded)
    add_bcn(rows, excluded)
    add_pad(rows, excluded)

    leakage = audit_group_leakage(rows)
    if leakage:
        raise RuntimeError(f"發現 {len(leakage)} 個 group_id 跨越 train/validation")

    write_manifest(ROOT / config["manifest"], rows)
    duplicates = audit_exact_duplicates(rows) if args.hash_audit else []
    if args.hash_audit:
        (ROOT / "data/exact_duplicate_audit.json").write_text(
            json.dumps(duplicates, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    counts = Counter((row["source"], row["split"], row["label_name"]) for row in rows)
    patients = Counter()
    for source in {row["source"] for row in rows}:
        for split in {"train", "validation"}:
            patients[(source, split)] = len({
                row["group_id"] for row in rows if row["source"] == source and row["split"] == split
            })
    summary = {
        "experiment_id": config["experiment_id"],
        "total_rows": len(rows),
        "train_rows": sum(row["split"] == "train" for row in rows),
        "validation_rows": sum(row["split"] == "validation" for row in rows),
        "counts": [
            {"source": source, "split": split, "label": label, "count": count}
            for (source, split, label), count in sorted(counts.items())
        ],
        "unique_groups": [
            {"source": source, "split": split, "count": count}
            for (source, split), count in sorted(patients.items())
        ],
        "excluded": dict(excluded),
        "group_leakage_count": 0,
        "exact_hash_audit_performed": args.hash_audit,
        "exact_cross_source_or_split_duplicates": len(duplicates),
        "ISIC_Archive_training_used": False,
        "test_used": False,
    }
    (ROOT / "data/manifest_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
