from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pipeline_lib import repair_leakage, source_audit


def row(row_id, source, split, image_path, image_id, group_id, label=4, label_name="NV", license_name="CC BY 4.0"):
    return {
        "row_id": str(row_id), "source": source, "split": split, "image_path": image_path,
        "image_id": image_id, "group_id": group_id, "diagnosis_original": label_name,
        "label": str(label), "label_name": label_name, "license": license_name,
        "split_origin": "fixture",
    }


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "class_names": ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL"],
            "sources": {
                "BCN20000": {
                    "modality": "dermoscopy", "modality_zh": "皮膚鏡影像",
                    "license": "CC BY 4.0", "supported_labels": list(range(7)),
                }
            },
            "leakage": {
                "near_duplicate_phash_distance": 1, "near_duplicate_dhash_distance": 2,
                "review_phash_distance": 4, "review_dhash_distance": 8,
            },
        }

    def test_group_cross_split_quarantines_training_member(self):
        rows = [
            row(0, "BCN20000", "train", "a.jpg", "a", "lesion-1"),
            row(1, "BCN20000", "validation", "b.jpg", "b", "lesion-1"),
        ]
        fingerprints = {
            "a.jpg": {"sha256": "A", "phash": "0000000000000000", "dhash": "0000000000000000"},
            "b.jpg": {"sha256": "B", "phash": "FFFFFFFFFFFFFFFF", "dhash": "FFFFFFFFFFFFFFFF"},
        }
        clean, quarantine, report = repair_leakage(rows, fingerprints, self.config)
        self.assertEqual([item["split"] for item in clean], ["validation"])
        self.assertIn("group_id_cross_split", quarantine[0]["quarantine_reason"])
        self.assertEqual(report["group_cross_split_count"], 1)

    def test_exact_cross_split_duplicate_quarantines_training_copy(self):
        rows = [
            row(0, "BCN20000", "train", "a.jpg", "a", "lesion-a"),
            row(1, "BCN20000", "validation", "b.jpg", "b", "lesion-b"),
        ]
        fingerprints = {
            "a.jpg": {"sha256": "SAME", "phash": "0F0F0F0F0F0F0F0F", "dhash": "00FF00FF00FF00FF"},
            "b.jpg": {"sha256": "SAME", "phash": "0F0F0F0F0F0F0F0F", "dhash": "00FF00FF00FF00FF"},
        }
        clean, quarantine, _ = repair_leakage(rows, fingerprints, self.config)
        self.assertEqual(len(clean), 1)
        self.assertIn("exact_duplicate_of_validation", quarantine[0]["quarantine_reason"])

    def test_exact_duplicate_with_conflicting_labels_quarantines_all(self):
        rows = [
            row(0, "BCN20000", "train", "a.jpg", "a", "lesion-a", 4, "NV"),
            row(1, "BCN20000", "validation", "b.jpg", "b", "lesion-b", 1, "BCC"),
        ]
        fingerprints = {
            "a.jpg": {"sha256": "SAME", "phash": "0F0F0F0F0F0F0F0F", "dhash": "00FF00FF00FF00FF"},
            "b.jpg": {"sha256": "SAME", "phash": "0F0F0F0F0F0F0F0F", "dhash": "00FF00FF00FF00FF"},
        }
        clean, quarantine, report = repair_leakage(rows, fingerprints, self.config)
        self.assertEqual(clean, [])
        self.assertEqual(len(quarantine), 2)
        self.assertTrue(all("exact_duplicate_label_conflict" in item["quarantine_reason"] for item in quarantine))
        self.assertEqual(report["exact_duplicate_label_conflict_set_count"], 1)

    def test_source_audit_rejects_wrong_license(self):
        sample = row(0, "BCN20000", "train", "missing.jpg", "a", "lesion-a")
        sample["license"] = "unknown"
        report = source_audit([sample], self.config)
        self.assertFalse(report["passed"])
        self.assertTrue(any(item["reason"] == "license_mismatch" for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
