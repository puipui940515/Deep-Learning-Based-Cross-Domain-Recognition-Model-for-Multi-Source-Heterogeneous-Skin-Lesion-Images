from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from prepare_isic_v2 import (
    DATA,
    FINGERPRINT_FIELDS,
    PROJECT,
    REPORTS,
    SCHEMA_VERSION,
    load_fingerprint_cache,
    read_csv,
    write_csv,
    write_json,
)


def run(workers: int) -> dict:
    sys.path.insert(0, str(DATA.parent / "scripts"))
    from pipeline_lib import fingerprint_image

    candidate_path = DATA / "candidate_manifest_v2.csv"
    if not candidate_path.is_file():
        raise FileNotFoundError("請先執行 prepare_isic_v2.py --stage build")
    rows = read_csv(candidate_path)
    paths = list(dict.fromkeys(row["image_path"] for row in rows))
    cache_path = DATA / "image_fingerprints_v2.csv"
    cache = load_fingerprint_cache(cache_path)
    for relative, item in load_fingerprint_cache(DATA / "image_fingerprints.csv").items():
        cache.setdefault(relative, item)

    valid_cache: dict[str, dict[str, str]] = {}
    pending: list[str] = []
    for relative in paths:
        path = PROJECT / relative
        previous = cache.get(relative)
        if previous and path.is_file():
            try:
                if int(previous["file_size"]) == path.stat().st_size and int(previous["mtime_ns"]) == path.stat().st_mtime_ns:
                    valid_cache[relative] = previous
                    continue
            except (KeyError, TypeError, ValueError):
                pass
        pending.append(relative)

    print(
        f"指紋工作排程：總數 {len(paths)}，快取 {len(valid_cache)}，"
        f"待處理 {len(pending)}，workers={workers}",
        flush=True,
    )

    def compute(relative: str):
        try:
            return relative, fingerprint_image(PROJECT / relative), None
        except Exception as error:
            return relative, None, f"{type(error).__name__}: {error}"

    needs_header = not cache_path.is_file() or cache_path.stat().st_size == 0
    errors: list[dict[str, str]] = []
    computed = 0
    with cache_path.open("a", encoding="utf-8-sig" if needs_header else "utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FINGERPRINT_FIELDS, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            for index, (relative, item, error) in enumerate(executor.map(compute, pending), 1):
                if error is not None:
                    errors.append({"image_path": relative, "error": error})
                else:
                    valid_cache[relative] = {key: str(value) for key, value in item.items()}
                    writer.writerow(item)
                    computed += 1
                if index % 100 == 0:
                    handle.flush()
                if index % 500 == 0 or index == len(pending):
                    print(
                        f"影像完整性與指紋：{len(valid_cache)}/{len(paths)}"
                        f"（本次新增 {computed}，錯誤 {len(errors)}）",
                        flush=True,
                    )

    compact = {relative: valid_cache[relative] for relative in paths if relative in valid_cache}
    write_csv(cache_path, list(compact.values()), FINGERPRINT_FIELDS)
    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": not errors and len(compact) == len(paths),
        "candidate_images": len(paths),
        "fingerprinted_images": len(compact),
        "reused_fingerprints": len(paths) - len(pending),
        "new_fingerprints": computed,
        "decode_or_fingerprint_errors": len(errors),
        "errors": errors[:500],
        "workers": workers,
        "output": "data/image_fingerprints_v2.csv",
    }
    write_json(REPORTS / "06_image_integrity_v2.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="並行建立新 ISIC v2 影像指紋")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    run(args.workers)


if __name__ == "__main__":
    main()
