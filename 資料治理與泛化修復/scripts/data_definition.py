from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
SCHEMA_VERSION = "skindetect-data-contract-v1.0"

CLASS_INFO = {
    0: ("AKIEC", "光化性角化症／表皮內癌光譜"),
    1: ("BCC", "基底細胞癌"),
    2: ("BKL", "良性角化病變群"),
    3: ("DF", "皮膚纖維瘤"),
    4: ("NV", "黑色素細胞痣"),
    5: ("VASC", "血管性病變"),
    6: ("MEL", "黑色素瘤"),
}

# 保留來源詞彙的語意差異。family 表示可納入既有七分類，但不是嚴格同義詞。
DISEASE_MAP = {
    ("HAM10000", "AKIEC"): (0, "family", "medium"),
    ("HAM10000", "BCC"): (1, "exact", "high"),
    ("HAM10000", "BKL"): (2, "family", "medium"),
    ("HAM10000", "DF"): (3, "exact", "high"),
    ("HAM10000", "NV"): (4, "exact", "high"),
    ("HAM10000", "VASC"): (5, "exact", "high"),
    ("HAM10000", "MEL"): (6, "exact", "high"),
    ("BCN20000", "AK"): (0, "family", "medium"),
    ("BCN20000", "BCC"): (1, "exact", "high"),
    ("BCN20000", "BKL"): (2, "family", "medium"),
    ("BCN20000", "DF"): (3, "exact", "high"),
    ("BCN20000", "NV"): (4, "exact", "high"),
    ("BCN20000", "VASC"): (5, "exact", "high"),
    ("BCN20000", "MEL"): (6, "exact", "high"),
    ("PAD-UFES-20", "ACK"): (0, "family", "medium"),
    ("PAD-UFES-20", "BCC"): (1, "exact", "high"),
    ("PAD-UFES-20", "SEK"): (2, "family", "medium"),
    ("PAD-UFES-20", "NEV"): (4, "exact", "high"),
    ("PAD-UFES-20", "MEL"): (6, "exact", "high"),
}

SITE_INFO = {
    "head_neck": "頭頸部",
    "trunk": "軀幹",
    "upper_extremity": "上肢",
    "lower_extremity": "下肢",
    "acral": "掌蹠部",
    "oral_anogenital": "口腔／肛門生殖器區",
    "unknown": "未知",
}

SITE_MAP = {
    "HAM10000": {
        "Trunk": ("trunk", "high"),
        "Lower extremity": ("lower_extremity", "high"),
        "Upper extremity": ("upper_extremity", "high"),
        "Head and neck": ("head_neck", "high"),
        "Anogenital region": ("oral_anogenital", "high"),
    },
    "BCN20000": {
        "anterior torso": ("trunk", "high"),
        "posterior torso": ("trunk", "high"),
        "head/neck": ("head_neck", "high"),
        "lower extremity": ("lower_extremity", "high"),
        "upper extremity": ("upper_extremity", "high"),
        "palms/soles": ("acral", "high"),
        "oral/genital": ("oral_anogenital", "high"),
    },
    "PAD-UFES-20": {
        "FACE": ("head_neck", "medium"),
        "NOSE": ("head_neck", "medium"),
        "NECK": ("head_neck", "medium"),
        "EAR": ("head_neck", "medium"),
        "SCALP": ("head_neck", "medium"),
        "LIP": ("head_neck", "medium"),
        "CHEST": ("trunk", "medium"),
        "BACK": ("trunk", "medium"),
        "ABDOMEN": ("trunk", "medium"),
        "FOREARM": ("upper_extremity", "medium"),
        "ARM": ("upper_extremity", "medium"),
        "HAND": ("upper_extremity", "medium"),
        "THIGH": ("lower_extremity", "medium"),
        "FOOT": ("lower_extremity", "medium"),
    },
}

MODALITY = {
    "HAM10000": ("dermoscopy", "皮膚鏡影像"),
    "BCN20000": ("dermoscopy", "皮膚鏡影像"),
    "PAD-UFES-20": ("clinical_smartphone", "智慧型手機臨床影像"),
}

OUTPUT_FIELDS = [
    "schema_version", "row_id", "record_id", "source", "source_dataset", "split",
    "image_path", "image_id", "patient_id", "lesion_id", "group_id", "split_group_id",
    "split_group_type", "diagnosis_original", "diagnosis_canonical_code",
    "diagnosis_canonical_zh", "label", "label_id", "label_name", "mapping_relation",
    "mapping_confidence", "training_eligible", "exclusion_reason", "image_modality",
    "image_modality_zh", "anatomical_site_original", "anatomical_site_canonical_code",
    "anatomical_site_canonical_zh", "anatomical_site_mapping_confidence", "age_years",
    "sex_original", "sex_canonical", "fitzpatrick_skin_type",
    "diagnosis_confirmation_original", "license", "split_origin", "leakage_status",
    "original_row_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean(value: object) -> str:
    return str(value or "").strip()


def canonical_sex(value: str) -> str:
    normal = clean(value).lower()
    if normal in {"male", "m"}:
        return "male"
    if normal in {"female", "f"}:
        return "female"
    return "unknown"


def canonical_site(source: str, original: str) -> tuple[str, str]:
    if not clean(original):
        return "unknown", "missing"
    return SITE_MAP.get(source, {}).get(original, ("unknown", "unmapped"))


def metadata_indices() -> dict[str, dict[str, dict[str, str]]]:
    ham = {
        row["isic_id"]: row
        for row in read_csv(PROJECT / "Dataset/HAM10000/HAM10000_ISIC_metadata.csv")
    }
    bcn = {
        Path(row["bcn_filename"]).stem: row
        for row in read_csv(PROJECT / "Dataset/BCN20000/metadata/available_train.csv")
    }
    pad = {
        Path(row["img_id"]).stem: row
        for row in read_csv(PROJECT / "Dataset/PAD-UFES-20/metadata.csv")
    }
    return {"HAM10000": ham, "BCN20000": bcn, "PAD-UFES-20": pad}


def metadata_values(source: str, meta: dict[str, str], base: dict[str, str]) -> dict[str, str]:
    if source == "HAM10000":
        return {
            "patient_id": "",
            "lesion_id": clean(meta.get("lesion_id")) or clean(base.get("group_id")),
            "site": clean(meta.get("anatom_site_1")),
            "age": clean(meta.get("age_approx")),
            "sex": clean(meta.get("sex")),
            "fitzpatrick": "",
            "confirmation": clean(meta.get("diagnosis_confirm_type")),
            "group_type": "lesion",
        }
    if source == "BCN20000":
        return {
            "patient_id": "",
            "lesion_id": clean(meta.get("lesion_id")) or clean(base.get("group_id")),
            "site": clean(meta.get("anatom_site_general")),
            "age": clean(meta.get("age_approx")),
            "sex": clean(meta.get("sex")),
            "fitzpatrick": "",
            "confirmation": "",
            "group_type": "lesion",
        }
    if source == "PAD-UFES-20":
        return {
            "patient_id": clean(meta.get("patient_id")) or clean(base.get("group_id")),
            "lesion_id": clean(meta.get("lesion_id")),
            "site": clean(meta.get("region")),
            "age": clean(meta.get("age")),
            "sex": clean(meta.get("gender")),
            "fitzpatrick": clean(meta.get("fitspatrick")),
            "confirmation": f"biopsed={clean(meta.get('biopsed')).lower()}" if clean(meta.get("biopsed")) else "",
            "group_type": "patient",
        }
    raise ValueError(f"不支援的資料來源：{source}")


def unify_row(base: dict[str, str], meta: dict[str, str]) -> dict[str, str]:
    source = clean(base.get("source"))
    original_diagnosis = clean(base.get("diagnosis_original")).upper()
    mapping = DISEASE_MAP.get((source, original_diagnosis))
    if mapping is None:
        raise ValueError(f"未定義疾病映射：source={source}, diagnosis={original_diagnosis}")
    label_id, relation, confidence = mapping
    code, name_zh = CLASS_INFO[label_id]
    if clean(base.get("label")) != str(label_id) or clean(base.get("label_name")) != code:
        raise ValueError(
            f"既有標籤與資料契約不一致：row_id={base.get('row_id')} "
            f"existing={base.get('label')}:{base.get('label_name')} contract={label_id}:{code}"
        )

    values = metadata_values(source, meta, base)
    site_code, site_confidence = canonical_site(source, values["site"])
    modality, modality_zh = MODALITY[source]
    image_id = clean(base.get("image_id"))
    group_id = clean(base.get("group_id"))
    return {
        "schema_version": SCHEMA_VERSION,
        "row_id": clean(base.get("row_id")),
        "record_id": f"{source}::{image_id}",
        "source": source,
        "source_dataset": source,
        "split": clean(base.get("split")),
        "image_path": clean(base.get("image_path")),
        "image_id": image_id,
        "patient_id": values["patient_id"],
        "lesion_id": values["lesion_id"],
        "group_id": group_id,
        "split_group_id": group_id,
        "split_group_type": values["group_type"],
        "diagnosis_original": original_diagnosis,
        "diagnosis_canonical_code": code,
        "diagnosis_canonical_zh": name_zh,
        "label": str(label_id),
        "label_id": str(label_id),
        "label_name": code,
        "mapping_relation": relation,
        "mapping_confidence": confidence,
        "training_eligible": "true",
        "exclusion_reason": "",
        "image_modality": modality,
        "image_modality_zh": modality_zh,
        "anatomical_site_original": values["site"],
        "anatomical_site_canonical_code": site_code,
        "anatomical_site_canonical_zh": SITE_INFO[site_code],
        "anatomical_site_mapping_confidence": site_confidence,
        "age_years": values["age"],
        "sex_original": values["sex"],
        "sex_canonical": canonical_sex(values["sex"]),
        "fitzpatrick_skin_type": values["fitzpatrick"],
        "diagnosis_confirmation_original": values["confirmation"],
        "license": clean(base.get("license")),
        "split_origin": clean(base.get("split_origin")),
        "leakage_status": "passed_clean_manifest_v1",
        "original_row_id": clean(base.get("original_row_id")),
    }


def audit(rows: list[dict[str, str]], metadata_missing: list[dict[str, str]]) -> dict:
    record_ids = Counter(row["record_id"] for row in rows)
    groups = defaultdict(set)
    for row in rows:
        groups[(row["source"], row["split_group_id"])].add(row["split"])
    group_leakage = [
        {"source": source, "split_group_id": group_id, "splits": sorted(splits)}
        for (source, group_id), splits in groups.items() if len(splits) > 1
    ]
    duplicate_records = sorted(key for key, count in record_ids.items() if count > 1)
    by_source = Counter(row["source"] for row in rows)
    by_class = Counter((row["source"], row["diagnosis_canonical_code"]) for row in rows)
    by_site = Counter((row["source"], row["anatomical_site_canonical_code"]) for row in rows)
    family_rows = sum(row["mapping_relation"] == "family" for row in rows)
    unknown_site_rows = sum(row["anatomical_site_canonical_code"] == "unknown" for row in rows)
    unmapped_site_rows = sum(row["anatomical_site_mapping_confidence"] == "unmapped" for row in rows)
    passed = not metadata_missing and not duplicate_records and not group_leakage and unmapped_site_rows == 0
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": passed,
        "total_rows": len(rows),
        "training_eligible_rows": sum(row["training_eligible"] == "true" for row in rows),
        "metadata_missing_count": len(metadata_missing),
        "metadata_missing": metadata_missing[:100],
        "duplicate_record_id_count": len(duplicate_records),
        "duplicate_record_ids": duplicate_records[:100],
        "group_leakage_count": len(group_leakage),
        "group_leakage": group_leakage[:100],
        "family_level_mapping_rows": family_rows,
        "unknown_anatomical_site_rows": unknown_site_rows,
        "unmapped_anatomical_site_rows": unmapped_site_rows,
        "rows_by_source": dict(sorted(by_source.items())),
        "rows_by_source_and_class": [
            {"source": source, "class": label, "count": count}
            for (source, label), count in sorted(by_class.items())
        ],
        "rows_by_source_and_site": [
            {"source": source, "site": site, "count": count}
            for (source, site), count in sorted(by_site.items())
        ],
        "policy": {
            "missing_values": "空字串代表原資料未提供；不得由影像推測患者屬性",
            "disease_mapping": "保留 diagnosis_original；AKIEC/AK/ACK 與 BKL/SEK 使用家族級映射",
            "split_group": "HAM10000、BCN20000 依病灶；PAD-UFES-20 依患者",
            "unknown_site": "來源欄位空白可保留為 unknown；出現未定義新值則稽核失敗",
        },
    }


def build_unified_manifest(input_path: Path, output_path: Path, report_path: Path) -> dict:
    base_rows = read_csv(input_path)
    indices = metadata_indices()
    rows: list[dict[str, str]] = []
    metadata_missing: list[dict[str, str]] = []
    for base in base_rows:
        source = clean(base.get("source"))
        image_id = clean(base.get("image_id"))
        meta = indices.get(source, {}).get(image_id)
        if meta is None:
            metadata_missing.append({"source": source, "image_id": image_id, "row_id": clean(base.get("row_id"))})
            continue
        rows.append(unify_row(base, meta))
    report = audit(rows, metadata_missing)
    if not report["passed"]:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"統一資料定義稽核未通過：{report_path}")
    write_csv(output_path, rows)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="將清理後資料轉換為 SkinDetect 統一資料定義")
    parser.add_argument("--input", type=Path, default=ROOT / "data/clean_manifest.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data/unified_manifest_v1.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/00_data_definition_v1.json")
    args = parser.parse_args()
    report = build_unified_manifest(args.input, args.output, args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

