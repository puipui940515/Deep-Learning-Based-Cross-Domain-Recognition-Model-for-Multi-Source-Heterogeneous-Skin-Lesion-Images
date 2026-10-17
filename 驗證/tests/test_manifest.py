import csv
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "第一階段/data/fixed_split.csv"


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_exact_image_count_and_unique_ids(self):
        self.assertEqual(len(self.rows), 10015)
        self.assertEqual(len({row["isic_id"] for row in self.rows}), 10015)

    def test_lesions_do_not_cross_splits(self):
        sets = {split: {r["lesion_id"] for r in self.rows if r["split"] == split} for split in ("train", "val", "test")}
        self.assertFalse(sets["train"] & sets["val"])
        self.assertFalse(sets["train"] & sets["test"])
        self.assertFalse(sets["val"] & sets["test"])

    def test_split_is_close_to_70_15_15(self):
        counts = {split: sum(r["split"] == split for r in self.rows) for split in ("train", "val", "test")}
        self.assertLess(abs(counts["train"] / 10015 - 0.70), 0.002)
        self.assertLess(abs(counts["val"] / 10015 - 0.15), 0.002)
        self.assertLess(abs(counts["test"] / 10015 - 0.15), 0.002)

