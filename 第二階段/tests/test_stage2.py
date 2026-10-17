import sys
import unittest
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stage2.losses import LogitAdjustedCrossEntropy
from stage2.models import build_model, parameter_groups_with_layer_decay


class Stage2Tests(unittest.TestCase):
    def test_resnet18_output_shape(self):
        model = build_model("resnet18", pretrained=False, num_classes=7)
        self.assertEqual(tuple(model(torch.zeros(2, 3, 64, 64)).shape), (2, 7))

    def test_convnext_tiny_output_shape(self):
        model = build_model("convnext_tiny", pretrained=False, num_classes=7)
        self.assertEqual(tuple(model(torch.zeros(1, 3, 64, 64)).shape), (1, 7))

    def test_logit_adjusted_loss_backward(self):
        logits = torch.randn(4, 7, requires_grad=True)
        loss = LogitAdjustedCrossEntropy([229, 360, 769, 80, 4693, 98, 779])(
            logits, torch.tensor([0, 1, 4, 6])
        )
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertIsNotNone(logits.grad)

    def test_layer_decay_groups_have_learning_rates(self):
        model = build_model("convnext_tiny", pretrained=False, num_classes=7)
        groups = parameter_groups_with_layer_decay(model, 3e-4, 1e-4, 0.8)
        self.assertGreater(len(groups), 1)
        self.assertTrue(all(group["lr"] > 0 for group in groups))


if __name__ == "__main__":
    unittest.main()
