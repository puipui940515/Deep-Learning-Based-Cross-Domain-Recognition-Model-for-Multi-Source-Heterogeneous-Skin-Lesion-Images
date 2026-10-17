from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
CONFIG_PATH = ROOT / "config.json"

CLASS_NAMES = {
    0: "AKIEC",
    1: "BCC",
    2: "BKL",
    3: "DF",
    4: "NV",
    5: "VASC",
    6: "MEL",
}
BCN_MAP = {"AK": 0, "BCC": 1, "BKL": 2, "DF": 3, "NV": 4, "VASC": 5, "MEL": 6}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def relative_existing(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved.relative_to(PROJECT).as_posix()


def add_ham_rows(rows: list[dict], excluded: Counter) -> None:
    for row in read_csv(PROJECT / "第二階段/data/fixed_split.csv"):
        split = row["split"]
        if split == "test":
            excluded["HAM10000_test_sealed"] += 1
            continue
        label = int(row["label"])
        rows.append({
            "row_id": len(rows),
            "source": "HAM10000",
            "split": "validation" if split == "val" else "train",
            "image_path": relative_existing(PROJECT / "Dataset/HAM10000" / row["image_path"]),
            "image_id": row["isic_id"],
            "group_id": row["lesion_id"],
            "diagnosis_original": CLASS_NAMES[label],
            "label": label,
            "label_name": CLASS_NAMES[label],
            "license": "CC BY-NC 4.0",
            "split_origin": "第二階段固定病灶切分",
        })


def add_bcn_rows(rows: list[dict], excluded: Counter) -> None:
    metadata = read_csv(PROJECT / "Dataset/BCN20000/metadata/available_train.csv")
    profile = read_csv(PROJECT / "部位預測階段/data/profiles/bcn.csv")
    meta_by_file = {row["bcn_filename"]: row for row in metadata}

    validation_lesions = set()
    for profile_row in profile:
        if profile_row["split"] != "val":
            continue
        filename = Path(profile_row["image_path"]).name
        meta = meta_by_file.get(filename)
        if meta is not None:
            validation_lesions.add(meta["lesion_id"])

    for row in metadata:
        diagnosis = row["diagnosis"]
        if diagnosis not in BCN_MAP:
            excluded[f"BCN20000_unmapped_{diagnosis or 'EMPTY'}"] += 1
            continue
        label = BCN_MAP[diagnosis]
        split = "validation" if row["lesion_id"] in validation_lesions else "train"
        filename = row["bcn_filename"]
        rows.append({
            "row_id": len(rows),
            "source": "BCN20000",
            "split": split,
            "image_path": relative_existing(PROJECT / "Dataset/BCN20000/images/train" / filename),
            "image_id": Path(filename).stem,
            "group_id": row["lesion_id"],
            "diagnosis_original": diagnosis,
            "label": label,
            "label_name": CLASS_NAMES[label],
            "license": "CC BY 4.0",
            "split_origin": "既有 BCN 病灶切分；同 lesion_id 強制同 split",
        })


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
    total = len(rows)
    for index, row in enumerate(rows, 1):
        by_hash[sha256(PROJECT / row["image_path"])].append(row)
        if index % 1000 == 0 or index == total:
            print(f"精確雜湊稽核：{index}/{total}", flush=True)
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


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="建立 HAM10000 + BCN20000 混合訓練清單")
    parser.add_argument("--hash-audit", action="store_true", help="計算全部影像 SHA-256，檢查跨來源或跨 split 的完全相同檔案")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    rows: list[dict] = []
    excluded: Counter = Counter()
    add_ham_rows(rows, excluded)
    add_bcn_rows(rows, excluded)

    leakage = audit_group_leakage(rows)
    if leakage:
        raise RuntimeError(f"發現 {len(leakage)} 個 group_id 跨越 train/validation")

    fields = [
        "row_id", "source", "split", "image_path", "image_id", "group_id",
        "diagnosis_original", "label", "label_name", "license", "split_origin",
    ]
    manifest_path = ROOT / config["manifest"]
    write_csv(manifest_path, rows, fields)

    exact_duplicates = audit_exact_duplicates(rows) if args.hash_audit else []
    if args.hash_audit:
        (ROOT / "data/exact_duplicate_audit.json").write_text(
            json.dumps(exact_duplicates, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    counts = Counter((row["source"], row["split"], row["label_name"]) for row in rows)
    summary = {
        "experiment_id": config["experiment_id"],
        "total_rows": len(rows),
        "train_rows": sum(row["split"] == "train" for row in rows),
        "validation_rows": sum(row["split"] == "validation" for row in rows),
        "counts": [
            {"source": source, "split": split, "label": label, "count": count}
            for (source, split, label), count in sorted(counts.items())
        ],
        "excluded": dict(excluded),
        "group_leakage_count": len(leakage),
        "exact_hash_audit_performed": args.hash_audit,
        "exact_cross_source_or_split_duplicates": len(exact_duplicates),
        "test_used": False,
    }
    (ROOT / "data/manifest_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
