import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP/'src'))
import common
sys.path.insert(0, str(EXP/'queue'))
import safety
import torch
import run_continuous


class SafetyTests(unittest.TestCase):
    def test_nonfinite_nested(self):
        for value in [float('nan'), float('inf'), torch.tensor([float('nan')]),
                      {'optimizer': [torch.tensor(float('inf'))]}]:
            with self.assertRaises(FloatingPointError): safety.check_finite(value)

    def test_invalid_save_preserves_good_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'best.pt'
            safety.safe_save({'model': torch.tensor([1.0])}, path)
            original = path.read_bytes()
            with self.assertRaises(FloatingPointError):
                safety.safe_save({'model': torch.tensor([float('nan')])}, path)
            self.assertEqual(original, path.read_bytes())
            with patch.object(safety.torch, 'save', side_effect=OSError('simulated disk failure')):
                with self.assertRaises(OSError): safety.safe_save({'model': torch.tensor([2.0])}, path)
            self.assertEqual(original, path.read_bytes())

    def test_low_disk(self):
        with patch.object(safety.shutil, 'disk_usage') as usage:
            usage.return_value.free = 10
            with self.assertRaises(RuntimeError): safety.check_disk(EXP)

    def test_gradient_nonfinite_rejected(self):
        p = torch.nn.Parameter(torch.tensor([1.]))
        p.grad = torch.tensor([float('inf')])
        with self.assertRaises(RuntimeError):
            torch.nn.utils.clip_grad_norm_([p], 1, error_if_nonfinite=True)

    def test_continuous_config(self):
        cfg = run_continuous.config('L-PAD', 10000)
        self.assertEqual(cfg['run']['held_out'], 'PAD-UFES-20')
        self.assertEqual(cfg['continuous_protocol'], 'independent-seeds-deferred-assessment-v1')


if __name__ == '__main__': unittest.main()
