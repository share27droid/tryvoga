import math
import unittest

from evaluate_school_calibration import brier_score, calibration_bins, evaluate, log_loss


class CalibrationTests(unittest.TestCase):
    def test_perfect_predictions_have_zero_brier_and_small_log_loss(self):
        actual = [0, 1]
        probabilities = [0.0, 1.0]
        self.assertEqual(brier_score(probabilities, actual), 0.0)
        self.assertTrue(math.isfinite(log_loss(probabilities, actual)))
        self.assertLess(log_loss(probabilities, actual), 1e-12)

    def test_known_scores_and_skill(self):
        actual = [0, 1]
        probabilities = [0.25, 0.75]
        baseline = [0.5, 0.5]
        result = evaluate(probabilities, actual, baseline)
        self.assertAlmostEqual(result["brier_score"], 0.0625)
        self.assertAlmostEqual(result["log_loss"], -math.log(0.75))
        self.assertAlmostEqual(result["brier_skill_vs_expanding"], 0.75)
        self.assertAlmostEqual(result["expected_calibration_error_fixed_bins"], 0.25)

    def test_bins_cover_zero_and_one(self):
        bins = calibration_bins([0.0, 0.049, 0.05, 0.2, 0.4, 1.0], [0, 0, 1, 0, 1, 1])
        self.assertEqual(sum(item["n"] for item in bins), 6)
        self.assertEqual(bins[0]["bin"], "0.00-0.05")
        self.assertEqual(bins[-1]["bin"], "0.40-1.00")

    def test_probability_outcomes_alignment_is_validated(self):
        with self.assertRaises(ValueError):
            brier_score([0.5], [])
        with self.assertRaises(ValueError):
            log_loss([0.5], [0, 1])


if __name__ == "__main__":
    unittest.main()
