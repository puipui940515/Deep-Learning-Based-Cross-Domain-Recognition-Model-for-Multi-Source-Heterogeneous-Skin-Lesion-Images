import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "第一階段/src"))
from stage1.metrics import metrics_from_logits


class MetricsTest(unittest.TestCase):
    def test_majority_baseline_balanced_accuracy_is_one_seventh(self):
        targets = np.repeat(np.arange(7), [3, 4, 5, 6, 20, 7, 8])
        logits = np.zeros((len(targets), 7)); logits[:, 4] = 1
        self.assertAlmostEqual(metrics_from_logits(logits, targets)["balanced_accuracy"], 1 / 7)

    def test_perfect_predictions(self):
        targets = np.arange(7); logits = np.eye(7) * 10
        result = metrics_from_logits(logits, targets)
        self.assertAlmostEqual(result["balanced_accuracy"], 1.0)
        self.assertAlmostEqual(result["macro_f1"], 1.0)

