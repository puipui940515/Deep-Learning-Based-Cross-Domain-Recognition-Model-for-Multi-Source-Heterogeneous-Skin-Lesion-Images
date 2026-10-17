from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


VALIDATION_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = VALIDATION_ROOT.parent
STAGE_ROOT = PROJECT_ROOT / "第一階段"
CONFIG = json.loads((STAGE_ROOT / "config/stage1.json").read_text(encoding="utf-8"))
HAM_ROOT = (STAGE_ROOT / CONFIG["dataset_root"]).resolve()
REPORT_ROOT = VALIDATION_ROOT / "reports"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def create_manifest():
    source_rows = read_csv(HAM_ROOT / "HAM10000_full_noleak.csv")
    metadata = read_csv(HAM_ROOT / "HAM10000_ISIC_metadata.csv")
    metadata_by_id = {row["isic_id"]: row for row in metadata}
    groups = defaultdict(list)
    for row in source_rows:
        isic_id = Path(row["image_path"]).stem
        if isic_id not in metadata_by_id:
            raise RuntimeError(f"metadata 缺少 {isic_id}")
        lesion_id = metadata_by_id[isic_id]["lesion_id"] or isic_id
        groups[lesion_id].append({"image_path": row["image_path"], "isic_id": isic_id,
                                  "lesion_id": lesion_id, "label": int(row["label"])})

    by_label = defaultdict(list)
    for lesion_id, rows in groups.items():
        labels = {row["label"] for row in rows}
        if len(labels) != 1:
            raise RuntimeError(f"同一 lesion_id 有多個標籤：{lesion_id}")
        by_label[next(iter(labels))].append((lesion_id, rows))

    assignments = {}
    ratios = {"train": 0.70, "val": 0.15, "test": 0.15}
    for label, label_groups in sorted(by_label.items()):
        rng = random.Random(CONFIG["split_seed"] + label)
        rng.shuffle(label_groups)
        label_groups.sort(key=lambda item: len(item[1]), reverse=True)
        total = sum(len(rows) for _, rows in label_groups)
        target = {name: total * ratio for name, ratio in ratios.items()}
        current = {name: 0 for name in ratios}
        for lesion_id, rows in label_groups:
            split = max(ratios, key=lambda name: (target[name] - current[name]) / max(target[name], 1))
            assignments[lesion_id] = split
            current[split] += len(rows)

    output = []
    for lesion_id, rows in groups.items():
        for row in rows:
            row["split"] = assignments[lesion_id]
            output.append(row)
    output.sort(key=lambda row: (row["split"], row["label"], row["isic_id"]))
    manifest = STAGE_ROOT / CONFIG["split_manifest"]
    with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "isic_id", "lesion_id", "label", "split"])
        writer.writeheader(); writer.writerows(output)
    return output


def validate_manifest(rows):
    ids = [row["isic_id"] for row in rows]
    split_lesions = {name: {r["lesion_id"] for r in rows if r["split"] == name} for name in ("train", "val", "test")}
    intersections = {"train_val": len(split_lesions["train"] & split_lesions["val"]),
                     "train_test": len(split_lesions["train"] & split_lesions["test"]),
                     "val_test": len(split_lesions["val"] & split_lesions["test"])}
    missing = [r["image_path"] for r in rows if not (HAM_ROOT / r["image_path"]).is_file()]
    counts = Counter(r["split"] for r in rows)
    per_class = {split: dict(Counter(str(r["label"]) for r in rows if r["split"] == split)) for split in counts}
    report = {"passed": len(rows) == 10015 and len(set(ids)) == 10015 and not missing and not any(intersections.values()),
              "total_images": len(rows), "unique_image_ids": len(set(ids)), "split_counts": dict(counts),
              "split_class_counts": per_class, "lesion_intersections": intersections, "missing_files": missing}
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    (REPORT_ROOT / "split_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("固定切分驗證失敗")
    return report


def check_isic_overlap():
    ham_ids = {r["isic_id"] for r in read_csv(HAM_ROOT / "HAM10000_ISIC_metadata.csv")}
    sources = {"basal_cell_carcinoma": PROJECT_ROOT / "Dataset/ISIC_Archive/basal_cell_carcinoma/metadata.csv",
               "squamous_cell_carcinoma": PROJECT_ROOT / "Dataset/ISIC_Archive/squamous_cell_carcinoma/metadata.csv",
               "melanoma": PROJECT_ROOT / "Dataset/ISIC_Archive/melanoma/metadata.csv"}
    details, all_overlap = {}, []
    for name, path in sources.items():
        rows = read_csv(path)
        overlap = sorted(row["isic_id"] for row in rows if row["isic_id"] in ham_ids)
        details[name] = {"isic_subset_images": len(rows), "overlap_count": len(overlap), "overlap_ids": overlap}
        all_overlap.extend(overlap)
    report = {"passed": not all_overlap, "total_overlap": len(set(all_overlap)), "datasets": details,
              "action": "交集為 0，不需移除。" if not all_overlap else "禁止訓練，先排除重疊 ID。"}
    (REPORT_ROOT / "isic_overlap_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("HAM10000 與 ISIC 子集存在重疊")
    return report


if __name__ == "__main__":
    manifest_rows = create_manifest()
    print(json.dumps({"split": validate_manifest(manifest_rows), "overlap": check_isic_overlap()}, ensure_ascii=False, indent=2))

