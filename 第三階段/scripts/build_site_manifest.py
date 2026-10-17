from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from stage3.site_labels import SITE_GROUPS, normalize_ham_site, site_label


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", type=Path, default=ROOT / "data/fixed_split.csv")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=PROJECT_ROOT / "Dataset/HAM10000/HAM10000_ISIC_metadata.csv",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "data/fixed_split_with_site.csv")
    parser.add_argument("--audit", type=Path, default=ROOT / "results/site_manifest_audit.json")
    args = parser.parse_args()

    split_rows = read_csv(args.split)
    metadata_rows = read_csv(args.metadata)
    metadata = {}
    for row in metadata_rows:
        isic_id = row["isic_id"].strip()
        if isic_id in metadata:
            raise SystemExit(f"metadata 出現重複 isic_id：{isic_id}")
        metadata[isic_id] = row

    output_rows = []
    missing_ids = []
    site_counts = Counter()
    split_site_counts = defaultdict(Counter)
    diagnosis_site_counts = defaultdict(Counter)
    for row in split_rows:
        isic_id = row["isic_id"].strip()
        meta = metadata.get(isic_id)
        if meta is None:
            missing_ids.append(isic_id)
            continue
        raw_site = meta.get("anatom_site_1", "").strip()
        group = normalize_ham_site(raw_site)
        label = site_label(group)
        enriched = dict(row)
        enriched.update(
            anatom_site_raw=raw_site,
            site_group=group,
            site_label=str(label),
            site_known="0" if group == "unknown" else "1",
        )
        output_rows.append(enriched)
        site_counts[group] += 1
        split_site_counts[row["split"]][group] += 1
        diagnosis_site_counts[row["label"]][group] += 1

    if missing_ids:
        raise SystemExit(f"有 {len(missing_ids)} 個 split ID 找不到 metadata，例如 {missing_ids[:5]}")
    if len(output_rows) != 10015:
        raise SystemExit(f"預期 10,015 列，實際 {len(output_rows)}")
    if len({row['isic_id'] for row in output_rows}) != len(output_rows):
        raise SystemExit("輸出 manifest 的 isic_id 不唯一")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(split_rows[0]) + ["anatom_site_raw", "site_group", "site_label", "site_known"]
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    audit = {
        "source_split": str(args.split.resolve()),
        "source_metadata": str(args.metadata.resolve()),
        "output": str(args.output.resolve()),
        "rows": len(output_rows),
        "unique_isic_ids": len({row["isic_id"] for row in output_rows}),
        "site_groups": list(SITE_GROUPS),
        "site_counts": dict(site_counts),
        "split_site_counts": {key: dict(value) for key, value in split_site_counts.items()},
        "diagnosis_site_counts": {key: dict(value) for key, value in diagnosis_site_counts.items()},
        "unknown_site_count": site_counts["unknown"],
        "test_rows_read_for_training": False,
        "passed": True,
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
