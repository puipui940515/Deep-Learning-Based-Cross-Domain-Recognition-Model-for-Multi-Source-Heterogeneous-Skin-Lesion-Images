from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
REPORT = ROOT / "reports" / "02_leakage_audit.json"
OUTPUT = ROOT / "reports" / "near_duplicate_review"
PAIRS_PER_PAGE = 8
THUMB_SIZE = (420, 240)


def thumb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return ImageOps.fit(rgb, THUMB_SIZE, method=Image.Resampling.LANCZOS)


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    pairs = sorted(
        report["near_duplicates_for_manual_review"],
        key=lambda item: (item["phash_distance"], item["dhash_distance"]),
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    page_count = math.ceil(len(pairs) / PAIRS_PER_PAGE)
    for page_index in range(page_count):
        selected = pairs[page_index * PAIRS_PER_PAGE:(page_index + 1) * PAIRS_PER_PAGE]
        canvas = Image.new("RGB", (920, 70 + 310 * len(selected)), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((20, 18), f"Near-duplicate review {page_index + 1}/{page_count}", fill="black")
        for row_index, item in enumerate(selected):
            y = 60 + row_index * 310
            left = thumb(PROJECT / item["train_path"])
            right = thumb(PROJECT / item["validation_path"])
            canvas.paste(left, (20, y + 45)); canvas.paste(right, (480, y + 45))
            title = (
                f"p={item['phash_distance']} d={item['dhash_distance']} "
                f"same_label={item['same_label']}  train={item['train_row_id']} val={item['validation_row_id']}"
            )
            draw.text((20, y + 5), title, fill="black")
            draw.text((20, y + 286), Path(item["train_path"]).name, fill="black")
            draw.text((480, y + 286), Path(item["validation_path"]).name, fill="black")
        canvas.save(OUTPUT / f"review_{page_index + 1:02d}.jpg", quality=92)
    print(f"created {page_count} review sheets in {OUTPUT}")


if __name__ == "__main__":
    main()
