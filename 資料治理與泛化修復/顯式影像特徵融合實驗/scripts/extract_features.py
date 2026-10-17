from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image


EXPERIMENT = Path(__file__).resolve().parents[1]
GENERAL_ROOT = EXPERIMENT.parent
PROJECT = GENERAL_ROOT.parent
sys.path.insert(0, str(EXPERIMENT / "src"))

from explicit_features import FEATURE_NAMES, FEATURE_VERSION, extract_explicit_features

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_kwargs):
        return iterable


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def balanced_limit(rows: list[dict[str, str]], max_per_group: int | None) -> list[dict[str, str]]:
    if not max_per_group:
        return rows
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["split"], row["source"], row["label"])].append(row)
    selected: list[dict[str, str]] = []
    for key in sorted(groups):
        selected.extend(sorted(groups[key], key=lambda item: item["record_id"])[:max_per_group])
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="擷取全圖色彩、紋理、構圖與品質統計")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=GENERAL_ROOT / "data" / "unified_manifest_v1.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=EXPERIMENT / "data" / "explicit_features_v1.csv",
    )
    parser.add_argument("--max-per-group", type=int, help="只供煙霧測試：每個 split/source/label 最多擷取幾張")
    args = parser.parse_args()

    rows = [row for row in read_rows(args.manifest) if row["training_eligible"].lower() == "true"]
    rows = balanced_limit(rows, args.max_per_group)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["feature_version", "record_id", "source", "split", "label"] + FEATURE_NAMES
    failures: list[str] = []
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in tqdm(rows, desc="擷取顯式影像特徵", unit="image"):
            try:
                with Image.open(PROJECT / row["image_path"]) as image:
                    values = extract_explicit_features(image)
            except Exception as exc:
                failures.append(f'{row["record_id"]}: {exc}')
                continue
            output_row = {
                "feature_version": FEATURE_VERSION,
                "record_id": row["record_id"],
                "source": row["source"],
                "split": row["split"],
                "label": row["label"],
            }
            output_row.update({name: f"{float(value):.9g}" for name, value in zip(FEATURE_NAMES, values)})
            writer.writerow(output_row)
    if failures:
        raise RuntimeError(f"有 {len(failures)} 張影像擷取失敗；首筆：{failures[0]}")
    print(f"完成：{len(rows)} 張、{len(FEATURE_NAMES)} 個特徵 -> {args.output}")


if __name__ == "__main__":
    main()

