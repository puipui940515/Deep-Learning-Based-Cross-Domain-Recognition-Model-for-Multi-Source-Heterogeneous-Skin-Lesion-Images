from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from coverage_sampler import FullCoverageCappedSampler


class FullCoverageCappedSamplerTests(unittest.TestCase):
    def rows(self):
        return (
            [{"source": "large", "label": "0"} for _ in range(6)]
            + [{"source": "small", "label": "0"} for _ in range(2)]
            + [{"source": "small", "label": "1"} for _ in range(1)]
        )

    def test_every_sample_appears_at_least_once_and_at_most_twice(self):
        rows = self.rows()
        sampler = FullCoverageCappedSampler(rows, max_repeats=2, seed=3)
        sampled = list(iter(sampler))
        counts = Counter(sampled)
        self.assertEqual(set(counts), set(range(len(rows))))
        self.assertGreaterEqual(min(counts.values()), 1)
        self.assertLessEqual(max(counts.values()), 2)

    def test_small_source_is_capped_instead_of_forced_to_full_balance(self):
        sampler = FullCoverageCappedSampler(self.rows(), max_repeats=2, seed=3)
        audit = sampler.audit()
        self.assertEqual(audit["unique_source_counts"], {"large": 6, "small": 3})
        self.assertEqual(audit["source_samples_per_epoch"], {"large": 6, "small": 6})
        self.assertEqual(len(sampler), 12)

    def test_same_epoch_and_seed_are_reproducible(self):
        left = FullCoverageCappedSampler(self.rows(), max_repeats=2, seed=9)
        right = FullCoverageCappedSampler(self.rows(), max_repeats=2, seed=9)
        left.set_epoch(4)
        right.set_epoch(4)
        self.assertEqual(list(left), list(right))

    def test_invalid_repeat_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            FullCoverageCappedSampler(self.rows(), max_repeats=0)


if __name__ == "__main__":
    unittest.main()
