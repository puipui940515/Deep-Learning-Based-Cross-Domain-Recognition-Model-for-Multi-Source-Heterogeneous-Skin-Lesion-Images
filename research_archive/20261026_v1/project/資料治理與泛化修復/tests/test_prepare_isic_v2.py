from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_isic_v2 import assign_new_splits, confirmation_info, split_group


def sample(image_id: str, label_name: str, group_id: str) -> dict[str, str]:
    return {
        "image_id": image_id,
        "label_name": label_name,
        "split_group_id": group_id,
        "split": "pending",
        "split_origin": "",
    }


class PrepareIsicV2Tests(unittest.TestCase):
    def test_group_priority_is_patient_then_lesion_then_image(self):
        self.assertEqual(split_group({"patient_id": "P1", "lesion_id": "L1", "isic_id": "I1"})[:2], ("patient:P1", "patient"))
        self.assertEqual(split_group({"patient_id": "", "lesion_id": "L1", "isic_id": "I1"})[:2], ("lesion:L1", "lesion"))
        self.assertEqual(split_group({"patient_id": "", "lesion_id": "", "isic_id": "I1"})[:2], ("image:I1", "image"))

    def test_confirmation_weights_are_conservative_for_missing_labels(self):
        self.assertEqual(confirmation_info("histopathology"), ("high", 1.0))
        self.assertEqual(confirmation_info(""), ("unknown", 0.35))

    def test_split_is_deterministic_and_never_splits_a_group(self):
        rows = [
            sample("I1", "VASC", "patient:P1"),
            sample("I2", "VASC", "patient:P1"),
            sample("I3", "VASC", "image:I3"),
            sample("I4", "NV", "image:I4"),
        ]
        first = assign_new_splits(rows)
        splits = {row["split"] for row in rows if row["split_group_id"] == "patient:P1"}
        self.assertEqual(len(splits), 1)
        self.assertEqual(first["group_leakage_count"], 0)
        original = [row["split"] for row in rows]
        assign_new_splits(rows)
        self.assertEqual(original, [row["split"] for row in rows])


if __name__ == "__main__":
    unittest.main()
