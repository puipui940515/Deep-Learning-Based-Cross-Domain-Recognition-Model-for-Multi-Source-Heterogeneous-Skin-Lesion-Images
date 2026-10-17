from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
REQUIRED_COLUMNS = {
    "row_id", "source", "split", "image_path", "image_id", "group_id",
    "diagnosis_original", "label", "label_name", "license", "split_origin",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))


def input_rows(config: dict) -> list[dict[str, str]]:
    return read_csv(PROJECT / config["input_manifest"])


def source_audit(rows: list[dict[str, str]], config: dict) -> dict:
    columns = set(rows[0]) if rows else set()
    missing_columns = sorted(REQUIRED_COLUMNS - columns)
    errors: list[dict] = []
    row_ids = Counter(row.get("row_id", "") for row in rows)
    source_image_ids = Counter((row.get("source", ""), row.get("image_id", "")) for row in rows)
    class_names = config["class_names"]
    sources = config["sources"]
    counts = Counter()
    groups = defaultdict(set)
    missing_files = 0

    for row in rows:
        source = row.get("source", "")
        split = row.get("split", "")
        counts[(source, split, row.get("label_name", ""))] += 1
        groups[(source, split)].add(row.get("group_id", ""))
        if source not in sources:
            errors.append({"row_id": row.get("row_id"), "reason": "unknown_source", "value": source})
            continue
        if split not in {"train", "validation"}:
            errors.append({"row_id": row.get("row_id"), "reason": "invalid_split", "value": split})
        try:
            label = int(row.get("label", "-1"))
        except ValueError:
            label = -1
        expected_name = class_names[label] if 0 <= label < len(class_names) else None
        if expected_name != row.get("label_name"):
            errors.append({"row_id": row.get("row_id"), "reason": "label_mapping_mismatch"})
        if label not in sources[source]["supported_labels"]:
            errors.append({"row_id": row.get("row_id"), "reason": "unsupported_source_label", "label": label})
        if row.get("license") != sources[source]["license"]:
            errors.append({"row_id": row.get("row_id"), "reason": "license_mismatch"})
        if not row.get("group_id"):
            errors.append({"row_id": row.get("row_id"), "reason": "missing_group_id"})
        if not (PROJECT / row.get("image_path", "")).is_file():
            missing_files += 1

    duplicate_row_ids = [key for key, value in row_ids.items() if not key or value > 1]
    duplicate_source_image_ids = [
        {"source": key[0], "image_id": key[1], "count": value}
        for key, value in source_image_ids.items() if not key[1] or value > 1
    ]
    per_source = []
    for source, meta in sources.items():
        source_rows = [row for row in rows if row.get("source") == source]
        per_source.append({
            "source": source,
            "modality": meta["modality"],
            "modality_zh": meta["modality_zh"],
            "license": meta["license"],
            "supported_labels": meta["supported_labels"],
            "rows": len(source_rows),
            "train_rows": sum(row.get("split") == "train" for row in source_rows),
            "validation_rows": sum(row.get("split") == "validation" for row in source_rows),
            "unique_train_groups": len(groups[(source, "train")]),
            "unique_validation_groups": len(groups[(source, "validation")]),
        })
    passed = not missing_columns and not errors and not duplicate_row_ids and not duplicate_source_image_ids and missing_files == 0
    return {
        "stage": 1,
        "name": "來源差異與欄位一致性",
        "passed": passed,
        "total_rows": len(rows),
        "missing_columns": missing_columns,
        "missing_files": missing_files,
        "duplicate_row_ids": duplicate_row_ids[:100],
        "duplicate_source_image_ids": duplicate_source_image_ids[:100],
        "errors": errors[:500],
        "sources": per_source,
        "counts": [
            {"source": s, "split": p, "label": c, "count": n}
            for (s, p, c), n in sorted(counts.items())
        ],
        "confirmed_source_difference": len({meta["modality"] for meta in sources.values()}) > 1,
    }


def _dct_matrix(size: int = 32) -> np.ndarray:
    x = np.arange(size, dtype=np.float32)
    k = x[:, None]
    matrix = np.cos((math.pi / size) * (x + 0.5) * k)
    matrix[0] *= math.sqrt(1 / size)
    matrix[1:] *= math.sqrt(2 / size)
    return matrix


DCT32 = _dct_matrix()


def _bits_to_hex(bits: np.ndarray) -> str:
    value = 0
    for bit in bits.ravel():
        value = (value << 1) | int(bool(bit))
    return f"{value:016X}"


def fingerprint_image(path: Path) -> dict:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(block)
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        small = rgb.copy()
        small.thumbnail((128, 128), Image.Resampling.BILINEAR)
        array = np.asarray(small, dtype=np.float32) / 255.0
        value_max = array.max(axis=2)
        value_min = array.min(axis=2)
        saturation = np.divide(
            value_max - value_min, value_max,
            out=np.zeros_like(value_max), where=value_max > 1e-6,
        )
        gray_small = np.asarray(small.convert("L"), dtype=np.float32) / 255.0
        edge = np.asarray(small.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32) / 255.0
        gray32 = np.asarray(rgb.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
        coeff = DCT32 @ gray32 @ DCT32.T
        low = coeff[:8, :8]
        median = np.median(low.ravel()[1:])
        phash = _bits_to_hex(low > median)
        gray98 = np.asarray(rgb.convert("L").resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
        dhash = _bits_to_hex(gray98[:, 1:] > gray98[:, :-1])
    stat = path.stat()
    return {
        "image_path": path.relative_to(PROJECT).as_posix(),
        "file_size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha.hexdigest().upper(),
        "phash": phash,
        "dhash": dhash,
        "width": width,
        "height": height,
        "aspect_ratio": width / max(height, 1),
        "brightness_mean": float(gray_small.mean()),
        "brightness_std": float(gray_small.std()),
        "saturation_mean": float(saturation.mean()),
        "edge_mean": float(edge.mean()),
    }


def build_fingerprint_cache(rows: list[dict[str, str]]) -> dict[str, dict]:
    cache_path = DATA / "image_fingerprints.csv"
    cached = {row["image_path"]: row for row in read_csv(cache_path)} if cache_path.exists() else {}
    result: dict[str, dict] = {}
    unique_paths = list(dict.fromkeys(row["image_path"] for row in rows))
    for index, relative in enumerate(unique_paths, 1):
        path = PROJECT / relative
        stat = path.stat()
        previous = cached.get(relative)
        if previous and int(previous["file_size"]) == stat.st_size and int(previous["mtime_ns"]) == stat.st_mtime_ns:
            item = dict(previous)
        else:
            item = fingerprint_image(path)
        result[relative] = item
        if index % 500 == 0 or index == len(unique_paths):
            print(f"影像指紋與構圖統計：{index}/{len(unique_paths)}", flush=True)
    fields = [
        "image_path", "file_size", "mtime_ns", "sha256", "phash", "dhash", "width", "height",
        "aspect_ratio", "brightness_mean", "brightness_std", "saturation_mean", "edge_mean",
    ]
    write_csv(cache_path, list(result.values()), fields)
    return result


def hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


class BKTree:
    def __init__(self):
        self.root = None
        self.members: dict[int, list[int]] = defaultdict(list)

    def add(self, value: int, index: int) -> None:
        self.members[value].append(index)
        if self.root is None:
            self.root = [value, {}]
            return
        node = self.root
        while True:
            distance = (value ^ node[0]).bit_count()
            if distance == 0:
                return
            if distance not in node[1]:
                node[1][distance] = [value, {}]
                return
            node = node[1][distance]

    def query(self, value: int, radius: int) -> Iterable[int]:
        if self.root is None:
            return []
        found: list[int] = []
        stack = [self.root]
        while stack:
            node_value, children = stack.pop()
            distance = (value ^ node_value).bit_count()
            if distance <= radius:
                found.extend(self.members[node_value])
            low, high = distance - radius, distance + radius
            stack.extend(child for edge, child in children.items() if low <= edge <= high)
        return found


def repair_leakage(rows: list[dict[str, str]], fingerprints: dict[str, dict], config: dict) -> tuple[list[dict], list[dict], dict]:
    drop_reasons: dict[int, set[str]] = defaultdict(set)
    group_members = defaultdict(list)
    hash_members = defaultdict(list)
    for index, row in enumerate(rows):
        group_members[(row["source"], row["group_id"])].append(index)
        hash_members[fingerprints[row["image_path"]]["sha256"]].append(index)

    group_cross_split = []
    for (source, group_id), indices in group_members.items():
        splits = {rows[index]["split"] for index in indices}
        if len(splits) > 1:
            group_cross_split.append({"source": source, "group_id": group_id, "splits": sorted(splits)})
            for index in indices:
                if rows[index]["split"] == "train":
                    drop_reasons[index].add("group_id_cross_split")

    exact_duplicate_sets = []
    for digest, indices in hash_members.items():
        if len(indices) < 2:
            continue
        labels = {rows[index]["label"] for index in indices}
        groups = {f"{rows[index]['source']}:{rows[index]['group_id']}" for index in indices}
        exact_duplicate_sets.append({
            "sha256": digest,
            "rows": [rows[index]["row_id"] for index in indices],
            "splits": sorted({rows[index]["split"] for index in indices}),
            "sources": sorted({rows[index]["source"] for index in indices}),
            "labels": sorted(labels),
            "groups": sorted(groups),
            "label_conflict": len(labels) > 1,
        })
        if len(labels) > 1:
            for index in indices:
                drop_reasons[index].add("exact_duplicate_label_conflict")
            continue
        validation_indices = [index for index in indices if rows[index]["split"] == "validation"]
        if validation_indices:
            for index in indices:
                if rows[index]["split"] == "train":
                    drop_reasons[index].add("exact_duplicate_of_validation")
            for index in validation_indices[1:]:
                drop_reasons[index].add("exact_duplicate_within_validation")
        else:
            for index in indices[1:]:
                drop_reasons[index].add("exact_duplicate_within_train")

    leakage_config = config["leakage"]
    validation_indices = [i for i, row in enumerate(rows) if row["split"] == "validation"]
    train_indices = [i for i, row in enumerate(rows) if row["split"] == "train"]
    tree = BKTree()
    for index in validation_indices:
        tree.add(int(fingerprints[rows[index]["image_path"]]["phash"], 16), index)

    near_removed = []
    near_review = []
    seen_pairs = set()
    for train_index in train_indices:
        train_row = rows[train_index]
        train_fp = fingerprints[train_row["image_path"]]
        candidates = tree.query(int(train_fp["phash"], 16), leakage_config["review_phash_distance"])
        for validation_index in candidates:
            pair = (train_index, validation_index)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            validation_row = rows[validation_index]
            validation_fp = fingerprints[validation_row["image_path"]]
            p_distance = hamming(train_fp["phash"], validation_fp["phash"])
            d_distance = hamming(train_fp["dhash"], validation_fp["dhash"])
            if d_distance > leakage_config["review_dhash_distance"]:
                continue
            item = {
                "train_row_id": train_row["row_id"],
                "validation_row_id": validation_row["row_id"],
                "train_source": train_row["source"],
                "validation_source": validation_row["source"],
                "train_path": train_row["image_path"],
                "validation_path": validation_row["image_path"],
                "same_label": train_row["label"] == validation_row["label"],
                "phash_distance": p_distance,
                "dhash_distance": d_distance,
            }
            conservative = (
                item["same_label"]
                and p_distance <= leakage_config["near_duplicate_phash_distance"]
                and d_distance <= leakage_config["near_duplicate_dhash_distance"]
            )
            if conservative:
                drop_reasons[train_index].add("conservative_near_duplicate_of_validation")
                near_removed.append(item)
            else:
                near_review.append(item)

    clean_rows = []
    quarantine = []
    for index, row in enumerate(rows):
        if index in drop_reasons:
            quarantine.append({**row, "quarantine_reason": ";".join(sorted(drop_reasons[index]))})
            continue
        clean_rows.append({**row, "original_row_id": row["row_id"]})
    for index, row in enumerate(clean_rows):
        row["row_id"] = index

    report = {
        "stage": 2,
        "name": "資料重複與切分洩漏",
        "input_rows": len(rows),
        "clean_rows": len(clean_rows),
        "quarantined_rows": len(quarantine),
        "group_cross_split_count": len(group_cross_split),
        "exact_duplicate_set_count": len(exact_duplicate_sets),
        "exact_duplicate_label_conflict_set_count": sum(item["label_conflict"] for item in exact_duplicate_sets),
        "conservative_near_duplicate_removed_count": len(near_removed),
        "near_duplicate_review_count": len(near_review),
        "group_cross_split": group_cross_split,
        "exact_duplicate_sets": exact_duplicate_sets,
        "near_duplicates_removed": near_removed,
        "near_duplicates_for_manual_review": near_review,
        "passed": True,
        "policy": "驗證集保留不動；跨切分的訓練重複圖移入 quarantine；近重複只自動處理同標籤且雙雜湊極相近者。",
    }
    return clean_rows, quarantine, report


def overfit_audit(config: dict) -> dict:
    path = PROJECT / config["baseline_result"]
    if not path.exists():
        return {"stage": 3, "name": "過擬合基線", "available": False, "passed": False}
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    best = result["best"]
    train_ba = float(best["train"]["balanced_accuracy"])
    validation = {
        source: float(metrics["balanced_accuracy"])
        for source, metrics in best["validation_by_source"].items()
    }
    gaps = {source: train_ba - score for source, score in validation.items()}
    return {
        "stage": 3,
        "name": "過擬合基線",
        "available": True,
        "baseline_result": config["baseline_result"],
        "best_epoch": best["epoch"],
        "train_balanced_accuracy": train_ba,
        "validation_balanced_accuracy": validation,
        "train_validation_gap": gaps,
        "largest_gap": max(gaps.values()),
        "overfit_signal": max(gaps.values()) >= 0.10,
        "passed": max(gaps.values()) < 0.10,
        "remediation_in_training_script": [
            "label smoothing", "MixUp", "更高 weight decay", "梯度裁切",
            "來源與類別平衡抽樣", "以平均與最差來源共同選模", "設備／構圖擾動增強",
        ],
    }


def _quantiles(values: list[float]) -> dict:
    array = np.asarray(values, dtype=np.float64)
    return {
        "min": float(np.min(array)), "p05": float(np.quantile(array, 0.05)),
        "median": float(np.median(array)), "mean": float(np.mean(array)),
        "p95": float(np.quantile(array, 0.95)), "max": float(np.max(array)),
        "std": float(np.std(array)),
    }


def domain_audit(rows: list[dict[str, str]], fingerprints: dict[str, dict], config: dict) -> dict:
    profiles = []
    for source, meta in config["sources"].items():
        source_paths = list(dict.fromkeys(row["image_path"] for row in rows if row["source"] == source))
        items = [fingerprints[path] for path in source_paths]
        profiles.append({
            "source": source,
            "modality": meta["modality"],
            "modality_zh": meta["modality_zh"],
            "images": len(items),
            "width": _quantiles([float(item["width"]) for item in items]),
            "height": _quantiles([float(item["height"]) for item in items]),
            "aspect_ratio": _quantiles([float(item["aspect_ratio"]) for item in items]),
            "brightness_mean": _quantiles([float(item["brightness_mean"]) for item in items]),
            "saturation_mean": _quantiles([float(item["saturation_mean"]) for item in items]),
            "edge_mean": _quantiles([float(item["edge_mean"]) for item in items]),
        })
    pairwise = []
    for left_index, left in enumerate(profiles):
        for right in profiles[left_index + 1:]:
            pairwise.append({
                "left": left["source"], "right": right["source"],
                "different_modality": left["modality"] != right["modality"],
                "median_width_ratio": left["width"]["median"] / max(right["width"]["median"], 1e-9),
                "median_aspect_ratio_difference": abs(left["aspect_ratio"]["median"] - right["aspect_ratio"]["median"]),
                "mean_brightness_difference": abs(left["brightness_mean"]["mean"] - right["brightness_mean"]["mean"]),
                "mean_saturation_difference": abs(left["saturation_mean"]["mean"] - right["saturation_mean"]["mean"]),
            })
    return {
        "stage": 4,
        "name": "設備與構圖差異",
        "confirmed_modality_difference": len({p["modality"] for p in profiles}) > 1,
        "profiles": profiles,
        "pairwise_differences": pairwise,
        "mitigation_in_training_script": [
            "統一輸入尺寸但保留隨機尺度與長寬比", "亮度／對比／飽和度／色相擾動",
            "隨機模糊與自動對比", "隨機擦除降低背景與構圖捷徑",
            "逐來源驗證並以最差來源參與選模",
        ],
    }


def run_pipeline() -> dict:
    config = load_config()
    rows = input_rows(config)
    REPORTS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    print("[1/4] 來源差異與欄位一致性", flush=True)
    source_report = source_audit(rows, config)
    write_json(REPORTS / "01_source_audit.json", source_report)
    if not source_report["passed"]:
        gate = {"passed": False, "blocked_at_stage": 1, "reason": "來源或欄位稽核失敗"}
        write_json(REPORTS / "pipeline_gate.json", gate)
        raise RuntimeError(gate["reason"])

    fingerprints = build_fingerprint_cache(rows)
    print("[2/4] 資料重複與切分洩漏", flush=True)
    clean_rows, quarantine, leakage_report = repair_leakage(rows, fingerprints, config)
    fields = list(rows[0]) + ["original_row_id"]
    write_csv(DATA / "clean_manifest.csv", clean_rows, fields)
    quarantine_fields = list(rows[0]) + ["quarantine_reason"]
    write_csv(DATA / "quarantine.csv", quarantine, quarantine_fields)
    write_json(REPORTS / "02_leakage_audit.json", leakage_report)

    # 只有通過重複與洩漏處理的資料，才會被轉換成正式訓練使用的統一資料定義。
    from data_definition import build_unified_manifest
    data_definition_report = build_unified_manifest(
        DATA / "clean_manifest.csv",
        DATA / "unified_manifest_v1.csv",
        REPORTS / "00_data_definition_v1.json",
    )

    print("[3/4] 過擬合基線與修復設定", flush=True)
    overfit_report = overfit_audit(config)
    write_json(REPORTS / "03_overfit_baseline.json", overfit_report)

    print("[4/4] 設備與構圖差異", flush=True)
    domain_report = domain_audit(clean_rows, fingerprints, config)
    write_json(REPORTS / "04_equipment_composition_audit.json", domain_report)

    gate = {
        "pipeline_id": config["pipeline_id"],
        "passed": source_report["passed"] and leakage_report["passed"],
        "clean_manifest": "data/clean_manifest.csv",
        "input_rows": len(rows),
        "clean_rows": len(clean_rows),
        "quarantined_rows": len(quarantine),
        "near_duplicate_manual_review_count": leakage_report["near_duplicate_review_count"],
        "data_definition_schema": data_definition_report["schema_version"],
        "data_definition_passed": data_definition_report["passed"],
        "unified_manifest": "data/unified_manifest_v1.csv",
        "overfit_signal_confirmed": overfit_report.get("overfit_signal"),
        "domain_shift_confirmed": domain_report["confirmed_modality_difference"],
        "training_was_started": False,
    }
    write_json(REPORTS / "pipeline_gate.json", gate)
    return gate
