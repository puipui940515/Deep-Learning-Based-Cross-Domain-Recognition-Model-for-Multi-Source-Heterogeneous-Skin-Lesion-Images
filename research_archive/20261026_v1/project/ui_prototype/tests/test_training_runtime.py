from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training_runtime import build_command, validate_parameters


class TrainingRuntimeTests(unittest.TestCase):
    def test_rejects_command_injection_in_numeric_field(self):
        with self.assertRaises(ValueError):
            validate_parameters({"epochs": "1; whoami"})

    def test_rejects_out_of_range_batch_size(self):
        with self.assertRaises(ValueError):
            validate_parameters({"batch_size": 1024})

    def test_smoke_command_is_argument_list_with_limits(self):
        parameters = validate_parameters({"mode": "smoke", "epochs": 2})
        command = build_command(Path("C:/project"), parameters, Path("C:/output"))
        self.assertIsInstance(command, list)
        self.assertIn("--max-train-samples", command)
        self.assertEqual(command[command.index("--epochs") + 1], "2")

    def test_formal_command_uses_full_dataset(self):
        parameters = validate_parameters({"mode": "formal", "epochs": 12})
        command = build_command(Path("C:/project"), parameters, Path("C:/output"))
        self.assertNotIn("--max-train-samples", command)


if __name__ == "__main__":
    unittest.main()
