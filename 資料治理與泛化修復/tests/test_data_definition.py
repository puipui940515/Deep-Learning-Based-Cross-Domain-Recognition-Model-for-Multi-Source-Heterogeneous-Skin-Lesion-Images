from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from data_definition import canonical_sex, canonical_site, unify_row


class DataDefinitionTests(unittest.TestCase):
    def test_pad_sek_is_family_level_bkl(self):
        base = {
            "row_id": "1", "source": "PAD-UFES-20", "split": "train",
            "image_path": "image.png", "image_id": "PAT_1_2_3", "group_id": "PAT_1",
            "diagnosis_original": "SEK", "label": "2", "label_name": "BKL",
            "license": "CC BY 4.0", "split_origin": "fixture", "original_row_id": "8",
        }
        meta = {
            "patient_id": "PAT_1", "lesion_id": "2", "region": "CHEST", "age": "54",
            "gender": "FEMALE", "fitspatrick": "3.0", "biopsed": "True",
        }
        result = unify_row(base, meta)
        self.assertEqual(result["diagnosis_canonical_code"], "BKL")
        self.assertEqual(result["mapping_relation"], "family")
        self.assertEqual(result["patient_id"], "PAT_1")
        self.assertEqual(result["anatomical_site_canonical_code"], "trunk")

    def test_unknown_site_is_not_invented(self):
        self.assertEqual(canonical_site("HAM10000", ""), ("unknown", "missing"))

    def test_new_unmapped_site_is_visible_to_audit(self):
        self.assertEqual(canonical_site("BCN20000", "unexpected-site"), ("unknown", "unmapped"))

    def test_sex_normalisation(self):
        self.assertEqual(canonical_sex("FEMALE"), "female")
        self.assertEqual(canonical_sex(""), "unknown")

    def test_existing_label_mismatch_fails(self):
        base = {
            "row_id": "1", "source": "BCN20000", "split": "train", "image_path": "x.jpg",
            "image_id": "ISIC_1", "group_id": "lesion-1", "diagnosis_original": "MEL",
            "label": "4", "label_name": "NV", "license": "CC BY 4.0", "split_origin": "fixture",
        }
        with self.assertRaises(ValueError):
            unify_row(base, {"lesion_id": "lesion-1"})


if __name__ == "__main__":
    unittest.main()
