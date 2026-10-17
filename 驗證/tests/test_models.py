import sys
import unittest
from pathlib import Path

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "第一階段/src"))
from stage1.models import build_model, count_parameters


class ModelTest(unittest.TestCase):
    def test_v1_shape_and_capacity(self):
        model = build_model("mlp", 64, 7)
        self.assertEqual(tuple(model(torch.zeros(2, 3, 64, 64)).shape), (2, 7))
        self.assertGreater(count_parameters(model), 6_000_000)

    def test_cnn_accepts_both_resolutions(self):
        for size in (64, 224):
            model = build_model("small_cnn", size, 7)
            self.assertEqual(tuple(model(torch.zeros(1, 3, size, size)).shape), (1, 7))

