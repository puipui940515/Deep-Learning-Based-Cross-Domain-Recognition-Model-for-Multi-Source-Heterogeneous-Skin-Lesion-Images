from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
SCHEMA = ROOT / "schema"
EXPANDED = PROJECT / "Dataset" / "ISIC_Archive_擴充_2026-09-09"
SOURCE = "ISIC_Archive_Expanded"
SCHEMA_VERSION = "skindetect-data-contract-v2.0"
SPLIT_SEED = 20260911
BASE_VALIDATION_FRACTION = 0.10

MINIMUM_VALIDATION_ROWS = {
    "AKIEC": 200,
    "BCC": 300,
    "BKL": 300,
    "DF": 150,
    "NV": 300,
    "VASC": 150,
    "MEL": 300,
    "SCC": 200,
}

CLASS_INFO = {
    0: ("AKIEC", "光化性角化症／表皮內癌光譜"),
    1: ("BCC", "基底細胞癌"),
    2: ("BKL", "良性角化病變群"),
    3: ("DF", "皮膚纖維瘤"),
    4: ("NV", "黑色素細胞痣"),
    5: ("VASC", "血管性病變"),
    6: ("MEL", "黑色素瘤"),
    7: ("SCC", "鱗狀細胞癌"),
}

SITE_INFO = {
    "Head and neck": ("head_neck", "頭頸部", "high"),
    "Trunk": ("trunk", "軀幹", "high"),
    "Upper extremity": ("upper_extremity", "上肢", "high"),
    "Lower extremity": ("lower_extremity", "下肢", "high"),
    "Anogenital region": ("oral_anogenital", "口腔／肛門生殖器區", "high"),
    "": ("unknown", "未知", "missing"),
}

MODALITY_INFO = {
    "dermoscopic": ("dermoscopy", "皮膚鏡影像"),
    "clinical: close-up": ("clinical_closeup", "臨床近照"),
    "clinical: overview": ("clinical_overview", "臨床全景"),
    "TBP tile: close-up": ("tbp_closeup", "全身攝影近照"),
    "RCM: tile": ("rcm", "反射式共軛焦顯微影像"),
    "RCM: mosaic": ("rcm", "反射式共軛焦顯微影像"),
    "RCM: macroscopic": ("rcm", "反射式共軛焦顯微影像"),
    "": ("unknown", "未知影像類型"),
}

CONFIRMATION_INFO = {
    "histopathology": ("high", 1.0),
    "confocal microscopy with consensus dermoscopy": ("high", 1.0),
    "serial imaging showing no change": ("medium", 0.80),
    "single image expert consensus": ("medium", 0.75),
    "single contributor clinical assessment": ("low", 0.50),
    "": ("unknown", 0.35),
}

FINGERPRINT_FIELDS = [
    "image_path", "file_size", "mtime_ns", "sha256", "phash", "dhash", "width", "height",
    "aspect_ratio", "brightness_mean", "brightness_std", "saturation_mean", "edge_mean",
]

EXTRA_FIELDS = [
    "source_subset", "diagnosis_confirmation_confidence", "recommended_sample_weight",
    "copyright_attribution", "identity_completeness", "duplicate_status",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def stable_fraction(value: str, salt: str = "") -> float:
    digest = hashlib.sha256(f"{SPLIT_SEED}|{salt}|{value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def canonical_sex(value: str) -> str:
    normal = str(value or "").strip().lower()
    if normal in {"male", "m"}:
        return "male"
    if normal in {"female", "f"}:
        return "female"
    return "unknown"


def confirmation_info(value: str) -> tuple[str, float]:
    return CONFIRMATION_INFO.get(str(value or "").strip(), ("unknown", 0.35))


def split_group(meta: dict[str, str]) -> tuple[str, str, str]:
    patient = str(meta.get("patient_id") or "").strip()
    lesion = str(meta.get("lesion_id") or "").strip()
    image = str(meta.get("isic_id") or "").strip()
    if patient:
        return f"patient:{patient}", "patient", "patient_and_lesion" if lesion else "patient_only"
    if lesion:
        return f"lesion:{lesion}", "lesion", "lesion_only"
    return f"image:{image}", "image", "image_only"


def load_disease_map() -> dict[str, dict[str, str]]:
    result = {}
    for row in read_csv(SCHEMA / "disease_mapping_v2.csv"):
        if row["source_dataset"] == SOURCE:
            result[row["diagnosis_original"]] = row
    return result


def image_index(directory: Path) -> dict[str, Path]:
    allowed = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    return {
        path.stem: path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in allowed
    }


def assign_new_splits(rows: list[dict[str, str]]) -> dict:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["split_group_id"]].append(row)

    selected = {
        group_id
        for group_id in groups
        if stable_fraction(group_id, "base") < BASE_VALIDATION_FRACTION
    }
    totals = Counter(row["label_name"] for row in rows)
    targets = {
        code: min(total, max(MINIMUM_VALIDATION_ROWS[code], math.ceil(total * BASE_VALIDATION_FRACTION)))
        for code, total in totals.items()
    }

    def validation_counts() -> Counter:
        return Counter(
            row["label_name"]
            for group_id in selected
            for row in groups[group_id]
        )

    counts = validation_counts()
    for code in CLASS_INFO.values():
        class_code = code[0]
        if class_code not in targets:
            continue
        candidates = [
            group_id for group_id, members in groups.items()
            if group_id not in selected and any(row["label_name"] == class_code for row in members)
        ]
        candidates.sort(key=lambda group_id: stable_fraction(group_id, f"boost:{class_code}"))
        for group_id in candidates:
            if counts[class_code] >= targets[class_code]:
                break
            selected.add(group_id)
            counts.update(row["label_name"] for row in groups[group_id])

    for group_id, members in groups.items():
        split = "validation_ext" if group_id in selected else "train"
        for row in members:
            row["split"] = split
            row["split_origin"] = (
                f"deterministic_group_split_v2;seed={SPLIT_SEED};"
                f"base_fraction={BASE_VALIDATION_FRACTION}"
            )

    leakage = sum(
        len({row["split"] for row in members}) > 1
        for members in groups.values()
    )
    return {
        "groups": len(groups),
        "validation_groups": len(selected),
        "group_leakage_count": leakage,
        "targets": targets,
        "actual_validation_rows": dict(sorted(counts.items())),
    }


def output_fields(base_rows: list[dict[str, str]]) -> list[str]:
    fields = list(base_rows[0]) if base_rows else []
    for name in EXTRA_FIELDS:
        if name not in fields:
            fields.append(name)
    return fields


def build_stage() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    base_path = DATA / "unified_manifest_v1.csv"
    plan_path = EXPANDED / "download_plan.json"
    if not base_path.is_file():
        raise FileNotFoundError(base_path)
    if not plan_path.is_file():
        raise FileNotFoundError(plan_path)

    base_rows = read_csv(base_path)
    fields = output_fields(base_rows)
    for row in base_rows:
        row["schema_version"] = SCHEMA_VERSION
        row["source_subset"] = "governance_v1"
        row["diagnosis_confirmation_confidence"] = "high" if row.get("diagnosis_confirmation_original") else "unknown"
        row["recommended_sample_weight"] = "1.0"
        row["copyright_attribution"] = ""
        row["identity_completeness"] = "legacy_group_id"
        row["duplicate_status"] = "v1_governance_passed"

    ham_ids = {
        row["isic_id"] for row in read_csv(PROJECT / "Dataset" / "HAM10000" / "HAM10000_ISIC_metadata.csv")
    }
    old_isic_ids = {
        path.stem
        for path in (PROJECT / "Dataset" / "ISIC_Archive").rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    }
    disease_map = load_disease_map()
    plans = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    new_rows: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    problems: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for item in plans:
        directory = Path(item["target_dir"])
        metadata_path = directory / "metadata.csv"
        images = image_index(directory)
        metadata = read_csv(metadata_path)
        for meta in metadata:
            image_id = str(meta.get("isic_id") or "").strip()
            diagnosis = str(meta.get("diagnosis_3") or "").strip()
            mapping = disease_map.get(diagnosis)
            image_path = images.get(image_id)
            reason = ""
            if not image_id:
                reason = "missing_isic_id"
            elif image_id in seen_ids:
                reason = "duplicate_isic_id_within_expanded"
            elif mapping is None:
                reason = "unmapped_diagnosis"
            elif image_path is None:
                reason = "metadata_without_image"
            elif meta.get("copyright_license") not in {"CC-0", "CC-BY", "CC-BY-NC"}:
                reason = "unsupported_license"
            seen_ids.add(image_id)

            if mapping is None:
                label_id, code, name_zh, relation, mapping_confidence = "", "", "", "", ""
            else:
                label_id = mapping["label_id"]
                code = mapping["diagnosis_canonical_code"]
                name_zh = mapping["diagnosis_canonical_zh"]
                relation = mapping["mapping_relation"]
                mapping_confidence = mapping["mapping_confidence"]

            group_id, group_type, identity = split_group(meta)
            site_original = str(meta.get("anatom_site_1") or "").strip()
            site_code, site_zh, site_confidence = SITE_INFO.get(site_original, ("unknown", "未知", "unmapped"))
            modality_original = str(meta.get("image_type") or "").strip()
            modality, modality_zh = MODALITY_INFO.get(modality_original, ("unknown", "未知影像類型"))
            confirmation = str(meta.get("diagnosis_confirm_type") or "").strip()
            confirmation_confidence, sample_weight = confirmation_info(confirmation)
            relative_path = image_path.relative_to(PROJECT).as_posix() if image_path else ""
            row = {name: "" for name in fields}
            row.update({
                "schema_version": SCHEMA_VERSION,
                "record_id": f"{SOURCE}::{image_id}",
                "source": SOURCE,
                "source_dataset": SOURCE,
                "split": "pending",
                "image_path": relative_path,
                "image_id": image_id,
                "patient_id": str(meta.get("patient_id") or "").strip(),
                "lesion_id": str(meta.get("lesion_id") or "").strip(),
                "group_id": group_id,
                "split_group_id": group_id,
                "split_group_type": group_type,
                "diagnosis_original": diagnosis,
                "diagnosis_canonical_code": code,
                "diagnosis_canonical_zh": name_zh,
                "label": label_id,
                "label_id": label_id,
                "label_name": code,
                "mapping_relation": relation,
                "mapping_confidence": mapping_confidence,
                "training_eligible": "false" if reason else "true",
                "exclusion_reason": reason,
                "image_modality": modality,
                "image_modality_zh": modality_zh,
                "anatomical_site_original": site_original,
                "anatomical_site_canonical_code": site_code,
                "anatomical_site_canonical_zh": site_zh,
                "anatomical_site_mapping_confidence": site_confidence,
                "age_years": str(meta.get("age_approx") or "").strip(),
                "sex_original": str(meta.get("sex") or "").strip(),
                "sex_canonical": canonical_sex(meta.get("sex", "")),
                "fitzpatrick_skin_type": str(meta.get("fitzpatrick_skin_type") or "").strip(),
                "diagnosis_confirmation_original": confirmation,
                "license": str(meta.get("copyright_license") or "").strip(),
                "leakage_status": "pending_content_audit" if not reason else "quarantined_pre_manifest",
                "source_subset": "isic_expand_cc0_ccby_ccbync",
                "diagnosis_confirmation_confidence": confirmation_confidence,
                "recommended_sample_weight": f"{sample_weight:.2f}",
                "copyright_attribution": str(meta.get("attribution") or "").strip(),
                "identity_completeness": identity,
                "duplicate_status": "pending",
            })

            if not reason and image_id in ham_ids:
                row["training_eligible"] = "false"
                row["exclusion_reason"] = "isic_id_overlap_ham10000"
                row["leakage_status"] = "quarantined_pre_manifest"
                excluded.append(row)
            elif reason:
                excluded.append(row)
                problems.append({"image_id": image_id, "diagnosis": diagnosis, "reason": reason})
            else:
                new_rows.append(row)

    split_report = assign_new_splits(new_rows)
    candidate_rows = base_rows + new_rows
    for index, row in enumerate(candidate_rows):
        row["row_id"] = str(index)
    for index, row in enumerate(excluded):
        row["row_id"] = f"excluded-{index}"

    write_csv(DATA / "candidate_manifest_v2.csv", candidate_rows, fields)
    write_csv(DATA / "pre_manifest_quarantine_v2.csv", excluded, fields + ["quarantine_reason"])

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-09-11",
        "passed": not problems and split_report["group_leakage_count"] == 0,
        "base_v1_rows": len(base_rows),
        "expanded_metadata_rows": len(seen_ids),
        "expanded_candidate_rows": len(new_rows),
        "candidate_total_rows": len(candidate_rows),
        "pre_manifest_quarantine_rows": len(excluded),
        "problem_rows": len(problems),
        "problems": problems[:100],
        "overlap": {
            "ham10000_isic_id_excluded": sum(row["exclusion_reason"] == "isic_id_overlap_ham10000" for row in excluded),
            "old_isic_safe_id_present_in_expanded": len(seen_ids & old_isic_ids),
            "old_isic_policy": "不另行抽樣；擴充來源中的相同影像只保留一個 canonical record",
        },
        "new_rows_by_class": dict(sorted(Counter(row["label_name"] for row in new_rows).items())),
        "new_rows_by_modality": dict(sorted(Counter(row["image_modality"] for row in new_rows).items())),
        "new_rows_by_license": dict(sorted(Counter(row["license"] for row in new_rows).items())),
        "new_rows_by_confirmation_confidence": dict(sorted(Counter(row["diagnosis_confirmation_confidence"] for row in new_rows).items())),
        "identity_completeness": dict(sorted(Counter(row["identity_completeness"] for row in new_rows).items())),
        "split": split_report,
        "outputs": {
            "candidate_manifest": "data/candidate_manifest_v2.csv",
            "pre_manifest_quarantine": "data/pre_manifest_quarantine_v2.csv",
        },
        "training_was_started": False,
    }
    write_json(REPORTS / "05_isic_v2_inventory.json", report)
    return report


def load_fingerprint_cache(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    return {row["image_path"]: row for row in read_csv(path)}


def fingerprint_stage() -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    from pipeline_lib import fingerprint_image

    candidate_path = DATA / "candidate_manifest_v2.csv"
    if not candidate_path.is_file():
        raise FileNotFoundError("請先執行 --stage build")
    rows = read_csv(candidate_path)
    paths = list(dict.fromkeys(row["image_path"] for row in rows))
    cache_path = DATA / "image_fingerprints_v2.csv"
    cache = load_fingerprint_cache(cache_path)
    old_cache = load_fingerprint_cache(DATA / "image_fingerprints.csv")
    for relative, item in old_cache.items():
        if relative not in cache:
            cache[relative] = item

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not cache_path.is_file() or cache_path.stat().st_size == 0
    errors: list[dict[str, str]] = []
    reused = 0
    computed = 0
    with cache_path.open("a", encoding="utf-8-sig" if needs_header else "utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FINGERPRINT_FIELDS, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        for index, relative in enumerate(paths, 1):
            path = PROJECT / relative
            previous = cache.get(relative)
            if previous and path.is_file():
                try:
                    if int(previous["file_size"]) == path.stat().st_size and int(previous["mtime_ns"]) == path.stat().st_mtime_ns:
                        reused += 1
                        if index % 500 == 0 or index == len(paths):
                            print(f"影像完整性與指紋：{index}/{len(paths)}（重用 {reused}，新增 {computed}）", flush=True)
                        continue
                except (KeyError, TypeError, ValueError):
                    pass
            try:
                item = fingerprint_image(path)
                cache[relative] = {key: str(value) for key, value in item.items()}
                writer.writerow(item)
                computed += 1
            except Exception as error:
                errors.append({"image_path": relative, "error": f"{type(error).__name__}: {error}"})
            if index % 100 == 0:
                handle.flush()
            if index % 500 == 0 or index == len(paths):
                print(f"影像完整性與指紋：{index}/{len(paths)}（重用 {reused}，新增 {computed}）", flush=True)

    compact = {relative: cache[relative] for relative in paths if relative in cache}
    write_csv(cache_path, list(compact.values()), FINGERPRINT_FIELDS)
    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": not errors and len(compact) == len(paths),
        "candidate_images": len(paths),
        "fingerprinted_images": len(compact),
        "reused_fingerprints": reused,
        "new_fingerprints": computed,
        "decode_or_fingerprint_errors": len(errors),
        "errors": errors[:500],
        "output": "data/image_fingerprints_v2.csv",
    }
    write_json(REPORTS / "06_image_integrity_v2.json", report)
    return report


def finalize_stage() -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    from pipeline_lib import BKTree, hamming

    candidate_path = DATA / "candidate_manifest_v2.csv"
    fingerprints_path = DATA / "image_fingerprints_v2.csv"
    if not candidate_path.is_file() or not fingerprints_path.is_file():
        raise FileNotFoundError("請先執行 --stage build 與 --stage fingerprint")

    rows = read_csv(candidate_path)
    fields = output_fields(rows)
    fingerprints = {row["image_path"]: row for row in read_csv(fingerprints_path)}
    drop_reasons: dict[int, set[str]] = defaultdict(set)
    exact_groups: list[dict] = []
    sha_members: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        fingerprint = fingerprints.get(row["image_path"])
        if fingerprint is None:
            drop_reasons[index].add("image_decode_or_fingerprint_failed")
        else:
            sha_members[fingerprint["sha256"]].append(index)

    def existing(index: int) -> bool:
        return rows[index]["source"] != SOURCE

    for digest, indices in sha_members.items():
        if len(indices) < 2:
            continue
        labels = {rows[index]["label_name"] for index in indices}
        exact_groups.append({
            "sha256": digest,
            "records": [rows[index]["record_id"] for index in indices],
            "sources": sorted({rows[index]["source"] for index in indices}),
            "labels": sorted(labels),
        })
        existing_indices = [index for index in indices if existing(index)]
        new_indices = [index for index in indices if not existing(index)]
        if existing_indices:
            for index in new_indices:
                drop_reasons[index].add(
                    "exact_content_label_conflict_with_existing" if len(labels) > 1
                    else "exact_content_duplicate_of_existing"
                )
        elif len(labels) > 1:
            for index in indices:
                drop_reasons[index].add("exact_content_label_conflict_within_isic")
        else:
            keep = min(
                indices,
                key=lambda index: (
                    0 if rows[index]["split"] == "validation_ext" else 1,
                    rows[index]["record_id"],
                ),
            )
            for index in indices:
                if index != keep:
                    drop_reasons[index].add("exact_content_duplicate_within_isic")

    # 新 ISIC 對既有來源：嚴格近重複一律隔離新資料，保存歷史 benchmark 定義。
    existing_tree = BKTree()
    existing_indices = [index for index, row in enumerate(rows) if row["source"] != SOURCE and index not in drop_reasons]
    for index in existing_indices:
        existing_tree.add(int(fingerprints[rows[index]["image_path"]]["phash"], 16), index)

    strict_cross_source_pairs = []
    review_cross_source_count = 0
    for index, row in enumerate(rows):
        if row["source"] != SOURCE or index in drop_reasons:
            continue
        fp = fingerprints[row["image_path"]]
        candidates = existing_tree.query(int(fp["phash"], 16), 4)
        best_review = None
        for other_index in candidates:
            other_fp = fingerprints[rows[other_index]["image_path"]]
            p_distance = hamming(fp["phash"], other_fp["phash"])
            d_distance = hamming(fp["dhash"], other_fp["dhash"])
            if d_distance > 8:
                continue
            pair = {
                "new_record": row["record_id"],
                "existing_record": rows[other_index]["record_id"],
                "existing_source": rows[other_index]["source"],
                "same_label": row["label_name"] == rows[other_index]["label_name"],
                "phash_distance": p_distance,
                "dhash_distance": d_distance,
            }
            if p_distance <= 1 and d_distance <= 2:
                drop_reasons[index].add("strict_near_duplicate_of_existing_source")
                strict_cross_source_pairs.append(pair)
                break
            if best_review is None:
                best_review = pair
        if best_review is not None and index not in drop_reasons:
            review_cross_source_count += 1

    # 新 ISIC 內部跨 train/validation_ext 的嚴格近重複：保留 validation_ext，隔離 train。
    validation_tree = BKTree()
    validation_indices = [
        index for index, row in enumerate(rows)
        if row["source"] == SOURCE and row["split"] == "validation_ext" and index not in drop_reasons
    ]
    for index in validation_indices:
        validation_tree.add(int(fingerprints[rows[index]["image_path"]]["phash"], 16), index)

    strict_cross_split_pairs = []
    review_cross_split_count = 0
    for index, row in enumerate(rows):
        if row["source"] != SOURCE or row["split"] != "train" or index in drop_reasons:
            continue
        fp = fingerprints[row["image_path"]]
        candidates = validation_tree.query(int(fp["phash"], 16), 4)
        review_found = False
        for other_index in candidates:
            other_fp = fingerprints[rows[other_index]["image_path"]]
            p_distance = hamming(fp["phash"], other_fp["phash"])
            d_distance = hamming(fp["dhash"], other_fp["dhash"])
            if d_distance > 8:
                continue
            if p_distance <= 1 and d_distance <= 2:
                drop_reasons[index].add("strict_near_duplicate_of_validation_ext")
                strict_cross_split_pairs.append({
                    "train_record": row["record_id"],
                    "validation_record": rows[other_index]["record_id"],
                    "same_label": row["label_name"] == rows[other_index]["label_name"],
                    "phash_distance": p_distance,
                    "dhash_distance": d_distance,
                })
                break
            review_found = True
        if review_found and index not in drop_reasons:
            review_cross_split_count += 1

    clean = []
    quarantine = read_csv(DATA / "pre_manifest_quarantine_v2.csv")
    for index, row in enumerate(rows):
        if index in drop_reasons:
            quarantined = dict(row)
            quarantined["training_eligible"] = "false"
            quarantined["exclusion_reason"] = ";".join(sorted(drop_reasons[index]))
            quarantined["leakage_status"] = "quarantined_v2_content_audit"
            quarantined["duplicate_status"] = quarantined["exclusion_reason"]
            quarantined["quarantine_reason"] = quarantined["exclusion_reason"]
            quarantine.append(quarantined)
        else:
            kept = dict(row)
            kept["training_eligible"] = "true"
            kept["exclusion_reason"] = ""
            kept["leakage_status"] = "passed_v2_content_and_group_audit"
            kept["duplicate_status"] = "unique_after_v2_audit"
            clean.append(kept)

    for index, row in enumerate(clean):
        row["row_id"] = str(index)

    groups = defaultdict(set)
    for row in clean:
        groups[(row["source"], row["split_group_id"])].add(row["split"])
    group_leakage = [
        {"source": source, "split_group_id": group_id, "splits": sorted(splits)}
        for (source, group_id), splits in groups.items() if len(splits) > 1
    ]

    record_counts = Counter(row["record_id"] for row in clean)
    duplicate_records = [record for record, count in record_counts.items() if count > 1]
    write_csv(DATA / "unified_manifest_v2.csv", clean, fields)
    write_csv(DATA / "quarantine_v2.csv", quarantine, fields + ["quarantine_reason"])

    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": not group_leakage and not duplicate_records,
        "input_candidate_rows": len(rows),
        "clean_rows": len(clean),
        "quarantine_rows_total": len(quarantine),
        "content_quarantine_rows": len(drop_reasons),
        "group_leakage_count": len(group_leakage),
        "duplicate_record_id_count": len(duplicate_records),
        "exact_duplicate_sets": len(exact_groups),
        "exact_duplicate_label_conflict_sets": sum(len(item["labels"]) > 1 for item in exact_groups),
        "strict_cross_source_near_duplicate_rows": len(strict_cross_source_pairs),
        "strict_cross_split_near_duplicate_rows": len(strict_cross_split_pairs),
        "manual_review_cross_source_candidates": review_cross_source_count,
        "manual_review_cross_split_candidates": review_cross_split_count,
        "strict_cross_source_examples": strict_cross_source_pairs[:200],
        "strict_cross_split_examples": strict_cross_split_pairs[:200],
        "clean_rows_by_source_and_split": [
            {"source": source, "split": split, "count": count}
            for (source, split), count in sorted(Counter((row["source"], row["split"]) for row in clean).items())
        ],
        "clean_rows_by_source_class_split": [
            {"source": source, "class": code, "split": split, "count": count}
            for (source, code, split), count in sorted(Counter((row["source"], row["label_name"], row["split"]) for row in clean).items())
        ],
        "outputs": {
            "unified_manifest": "data/unified_manifest_v2.csv",
            "quarantine": "data/quarantine_v2.csv",
            "fingerprints": "data/image_fingerprints_v2.csv",
        },
        "training_was_started": False,
    }
    write_json(REPORTS / "07_isic_v2_dedup_and_split.json", report)
    gate = {
        "pipeline_id": "isic_expansion_governance_v2",
        "passed": report["passed"],
        "inventory_passed": json.loads((REPORTS / "05_isic_v2_inventory.json").read_text(encoding="utf-8-sig"))["passed"],
        "image_integrity_passed": json.loads((REPORTS / "06_image_integrity_v2.json").read_text(encoding="utf-8-sig"))["passed"],
        "dedup_and_split_passed": report["passed"],
        "schema": "schema/data_contract_v2.json",
        "disease_mapping": "schema/disease_mapping_v2.csv",
        "source_registry": "../Dataset/SOURCE_REGISTRY.json",
        "unified_manifest": "data/unified_manifest_v2.csv",
        "clean_rows": len(clean),
        "quarantine_rows": len(quarantine),
        "class_count": 8,
        "class_order": [CLASS_INFO[index][0] for index in sorted(CLASS_INFO)],
        "training_was_started": False,
    }
    write_json(REPORTS / "data_gate_v2.json", gate)
    return {"report": report, "gate": gate}


def main() -> None:
    parser = argparse.ArgumentParser(description="SkinDetect 新 ISIC 擴充資料治理 v2")
    parser.add_argument("--stage", choices=("build", "fingerprint", "finalize", "all"), default="all")
    args = parser.parse_args()
    result: dict = {}
    if args.stage in {"build", "all"}:
        print("[1/3] 建立來源登記、八類映射與候選 manifest", flush=True)
        result["build"] = build_stage()
    if args.stage in {"fingerprint", "all"}:
        print("[2/3] 完整解碼、SHA-256、pHash/dHash 與構圖指紋", flush=True)
        result["fingerprint"] = fingerprint_stage()
    if args.stage in {"finalize", "all"}:
        print("[3/3] 內容重複、近重複、分組洩漏與正式 manifest", flush=True)
        result["finalize"] = finalize_stage()
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
