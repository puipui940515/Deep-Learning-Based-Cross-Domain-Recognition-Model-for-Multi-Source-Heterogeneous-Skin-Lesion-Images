from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


GROUPS = {
    "torso": (1,),
    "hands_feet": (2, 3, 4, 5),
    "lower_extremity": (6, 7, 8, 9),
    "upper_extremity": (10, 11, 12, 13),
    "head": (14,),
}
SOURCES = (
    ("train", "densepose_coco_2014_train.json", "train2014"),
    ("val", "densepose_coco_2014_valminusminival.json", "val2014"),
    ("test", "densepose_coco_2014_minival.json", "val2014"),
)


def compressed_counts(value: str) -> list[int]:
    counts: list[int] = []
    position = 0
    while position < len(value):
        result = 0
        shift = 0
        more = True
        while more:
            code = ord(value[position]) - 48
            position += 1
            result |= (code & 0x1F) << (5 * shift)
            more = bool(code & 0x20)
            if not more and code & 0x10:
                result |= -1 << (5 * (shift + 1))
            shift += 1
        if len(counts) > 2:
            result += counts[-2]
        counts.append(result)
    return counts


def mask_bounds(mask: object) -> tuple[int, int, int, int, int] | None:
    if not isinstance(mask, dict) or not mask:
        return None
    height, width = (int(value) for value in mask["size"])
    encoded = mask["counts"]
    counts = compressed_counts(encoded) if isinstance(encoded, str) else list(encoded)
    cursor = 0
    area = 0
    min_row, min_col = height, width
    max_row = max_col = -1
    foreground = False
    for run in counts:
        end = cursor + int(run)
        if foreground and end > cursor:
            area += end - cursor
            start_col, end_col = cursor // height, (end - 1) // height
            if start_col == end_col:
                local_min_row = cursor % height
                local_max_row = (end - 1) % height
            else:
                local_min_row, local_max_row = 0, height - 1
            min_row = min(min_row, local_min_row)
            max_row = max(max_row, local_max_row)
            min_col = min(min_col, start_col)
            max_col = max(max_col, end_col)
        cursor = end
        foreground = not foreground
    if area == 0:
        return None
    return min_col, min_row, max_col + 1, max_row + 1, area


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--margin", type=float, default=0.25)
    parser.add_argument("--min-mask-pixels", type=int, default=128)
    parser.add_argument("--min-crop-side", type=int, default=48)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    for split, filename, image_dir in SOURCES:
        print(f"loading {filename}", flush=True)
        with (args.annotations / filename).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        images = {int(item["id"]): item for item in data["images"]}
        for annotation in data["annotations"]:
            masks = annotation.get("dp_masks")
            if not masks:
                continue
            image = images[int(annotation["image_id"])]
            image_path = args.images / image_dir / image["file_name"]
            if not image_path.is_file():
                continue
            box_x, box_y, box_w, box_h = (float(value) for value in annotation["bbox"])
            for label, part_ids in GROUPS.items():
                parts = [mask_bounds(masks[index - 1]) for index in part_ids]
                parts = [part for part in parts if part is not None]
                if not parts:
                    continue
                area = sum(part[4] for part in parts)
                if area < args.min_mask_pixels:
                    continue
                left = min(part[0] for part in parts)
                top = min(part[1] for part in parts)
                right = max(part[2] for part in parts)
                bottom = max(part[3] for part in parts)
                x1 = box_x + left / 256.0 * box_w
                y1 = box_y + top / 256.0 * box_h
                x2 = box_x + right / 256.0 * box_w
                y2 = box_y + bottom / 256.0 * box_h
                margin_x = (x2 - x1) * args.margin
                margin_y = (y2 - y1) * args.margin
                x1 = max(0, math.floor(x1 - margin_x))
                y1 = max(0, math.floor(y1 - margin_y))
                x2 = min(int(image["width"]), math.ceil(x2 + margin_x))
                y2 = min(int(image["height"]), math.ceil(y2 + margin_y))
                if min(x2 - x1, y2 - y1) < args.min_crop_side:
                    continue
                rows.append({
                    "split": split,
                    "label": label,
                    "image_path": f"{image_dir}/{image['file_name']}",
                    "image_id": image["id"],
                    "annotation_id": annotation["id"],
                    "license_id": image.get("license", ""),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "mask_pixels_256": area,
                    "source_annotation": filename,
                })
        del data

    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts: dict[str, dict[str, int]] = {}
    for split, _, _ in SOURCES:
        counts[split] = {label: sum(row["split"] == split and row["label"] == label for row in rows) for label in GROUPS}
    summary = {"rows": len(rows), "counts": counts, "test_reserved": True, "groups": GROUPS}
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
