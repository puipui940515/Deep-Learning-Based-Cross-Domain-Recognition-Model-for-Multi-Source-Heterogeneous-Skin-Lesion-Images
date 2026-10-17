from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import torch
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from explicit_features import (
    AUDIT_ONLY_FEATURE_NAMES,
    FEATURE_NAMES,
    MODEL_FEATURE_NAMES,
    FeatureStandardizer,
    extract_explicit_features,
)
from fusion_model import ExplicitFeatureMLP


class ExplicitFeaturesTest(unittest.TestCase):
    def test_feature_vector_is_finite_and_stable_length(self):
        array = np.zeros((80, 120, 3), dtype=np.uint8)
        array[:, :, 0] = 180
        array[20:60, 35:85] = np.array([60, 30, 20], dtype=np.uint8)
        values = extract_explicit_features(Image.fromarray(array), size=64)
        self.assertEqual(values.shape, (len(FEATURE_NAMES),))
        self.assertTrue(np.isfinite(values).all())

    def test_standardizer_uses_supplied_training_values(self):
        values = np.array([[1.0, 10.0], [3.0, 14.0]], dtype=np.float32)
        scaler = FeatureStandardizer.fit(values)
        transformed = scaler.transform(values)
        np.testing.assert_allclose(transformed.mean(axis=0), 0.0, atol=1e-6)
        np.testing.assert_allclose(transformed.std(axis=0), 1.0, atol=1e-6)

    def test_feature_only_model_output_shape(self):
        model = ExplicitFeatureMLP(len(MODEL_FEATURE_NAMES), num_classes=7)
        logits = model(torch.empty(4, 0), torch.randn(4, len(MODEL_FEATURE_NAMES)))
        self.assertEqual(tuple(logits.shape), (4, 7))

    def test_audit_features_are_not_model_inputs(self):
        self.assertTrue(set(AUDIT_ONLY_FEATURE_NAMES).isdisjoint(MODEL_FEATURE_NAMES))
        self.assertEqual(len(FEATURE_NAMES), len(MODEL_FEATURE_NAMES) + len(AUDIT_ONLY_FEATURE_NAMES))


if __name__ == "__main__":
    unittest.main()
