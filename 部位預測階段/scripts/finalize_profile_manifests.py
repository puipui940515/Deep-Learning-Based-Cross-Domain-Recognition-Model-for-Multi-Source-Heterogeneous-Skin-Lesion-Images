from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ("ham", "bcn", "ham_bcn"):
    path = ROOT / f"data/profiles/{name}.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"空 manifest：{path}")
    fields = list(rows[0])
    if "isic_id" not in fields:
        fields.insert(fields.index("image_id") + 1, "isic_id")
    for row in rows:
        row["isic_id"] = row["image_id"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"finalized {name}: {len(rows)} rows")
