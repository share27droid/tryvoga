import unittest
import random

from bootstrap_school_calibration import (
    brier,
    circular_block_indices,
    laplace_probability,
    log_loss,
    summarize_bootstrap,
)


class BootstrapCalibrationTests(unittest.TestCase):
    def test_circular_blocks_preserve_contiguous_runs(self):
        indices = circular_block_indices(20, 4, random.Random(7))
        self.assertEqual(len(indices), 20)
        self.assertTrue(all(0 <= index < 20 for index in indices))
        for offset in range(0, 16, 4):
            block = indices[offset:offset + 4]
            self.assertTrue(all(block[i] == (block[0] + i) % 20 for i in range(4)))

    def test_scoring_rules(self):
        self.assertAlmostEqual(brier([0.8, 0.2], [1, 0]), 0.04)
        self.assertGreater(log_loss([0.8, 0.2], [1, 0]), 0)
        with self.assertRaises(ValueError):
            brier([], [])

    def test_laplace_rate(self):
        self.assertAlmostEqual(laplace_probability(0.0, 30), 1 / 32)
        self.assertAlmostEqual(laplace_probability(0.2, 30), 7 / 32)
        with self.assertRaises(ValueError):
            laplace_probability(0.2, 0)

    def test_bootstrap_is_deterministic_and_intervals_cover_point_estimate(self):
        actual = [0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 0, 1] * 3
        probabilities = [0.15, 0.10, 0.25, 0.10, 0.30, 0.15, 0.05, 0.25, 0.1, 0.1, 0.05, 0.2] * 3
        baseline = [sum(actual[:i]) / i if i else 0.2 for i in range(len(actual))]
        first = summarize_bootstrap(
            actual, probabilities, baseline, replicates=200, block_days=4, seed=42
        )
        second = summarize_bootstrap(
            actual, probabilities, baseline, replicates=200, block_days=4, seed=42
        )
        self.assertEqual(first, second)
        low, high = first["brier_score_95pct_block_bootstrap_interval"]
        self.assertLessEqual(low, first["brier_score"])
        self.assertGreaterEqual(high, first["brier_score"])
        self.assertEqual(first["replicates"], 200)
        self.assertIn("not proof of operational safety", first["interpretation"])

    def test_rejects_invalid_probabilities_and_short_bootstrap(self):
        with self.assertRaises(ValueError):
            summarize_bootstrap([0, 1], [0.2, 1.1], [0.3, 0.4], replicates=100)
        with self.assertRaises(ValueError):
            summarize_bootstrap([0, 1], [0.2, 0.8], [0.3, 0.4], replicates=20)


if __name__ == "__main__":
    unittest.main()
