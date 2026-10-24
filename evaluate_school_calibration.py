#!/usr/bin/env python3
"""Evaluate calibration of existing leakage-safe Kyiv school-window predictions.

Run after backtest_school_windows.py:
    python evaluate_school_calibration.py

Metrics are retrospective diagnostics, not a live forecast or safety decision.
Brier/log-loss are proper scoring rules; ECE is a coarse fixed-bin diagnostic.
Brier skill is measured against the expanding-history baseline on the same rows.
"""
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "kyiv_window_predictions.csv"
SUMMARY = ROOT / "kyiv_calibration_summary.json"
BINS_CSV = ROOT / "kyiv_calibration_bins.csv"
THRESHOLDS = (60, 120, 180)
WINDOWS = (30, 60, 90, 180, 365)
EPSILON = 1e-15
# Fixed before evaluating; wider upper bins are appropriate for rare outcomes.
BIN_EDGES = (0.0, 0.05, 0.10, 0.20, 0.40, 1.0)


def brier_score(probabilities, actual):
    if not actual or len(probabilities) != len(actual):
        raise ValueError("Probabilities and outcomes must be non-empty and aligned")
    return sum((p - y) ** 2 for p, y in zip(probabilities, actual)) / len(actual)


def log_loss(probabilities, actual):
    if not actual or len(probabilities) != len(actual):
        raise ValueError("Probabilities and outcomes must be non-empty and aligned")
    total = 0.0
    for p, y in zip(probabilities, actual):
        p = min(1.0 - EPSILON, max(EPSILON, p))
        total -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return total / len(actual)


def calibration_bins(probabilities, actual):
    """Return populated fixed bins, including the right edge in the last bin."""
    result = []
    for index, (low, high) in enumerate(zip(BIN_EDGES[:-1], BIN_EDGES[1:])):
        selected = [
            (p, y) for p, y in zip(probabilities, actual)
            if low <= p < high or (index == len(BIN_EDGES) - 2 and p == high)
        ]
        if not selected:
            continue
        mean_p = sum(p for p, _ in selected) / len(selected)
        rate = sum(y for _, y in selected) / len(selected)
        result.append({
            "bin": f"{low:.2f}-{high:.2f}",
            "n": len(selected),
            "mean_predicted": mean_p,
            "observed_rate": rate,
            "absolute_gap": abs(mean_p - rate),
        })
    return result


def evaluate(probabilities, actual, baseline_probabilities):
    bins = calibration_bins(probabilities, actual)
    ece = sum(item["n"] * item["absolute_gap"] for item in bins) / len(actual)
    score = brier_score(probabilities, actual)
    baseline_score = brier_score(baseline_probabilities, actual)
    skill = None if baseline_score == 0 else 1.0 - score / baseline_score
    return {
        "n": len(actual),
        "event_count": sum(actual),
        "observed_rate": sum(actual) / len(actual),
        "mean_predicted_probability": sum(probabilities) / len(probabilities),
        "brier_score": score,
        "log_loss": log_loss(probabilities, actual),
        "expected_calibration_error_fixed_bins": ece,
        "brier_skill_vs_expanding": skill,
        "calibration_bins": bins,
    }


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing {SOURCE.name}; run backtest_school_windows.py first.")
    with SOURCE.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("No predictions found; run backtest_school_windows.py first.")

    summary = {
        "source": SOURCE.name,
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "test_days": len(rows),
        "bin_edges": list(BIN_EDGES),
        "metrics": {},
        "caveats": [
            "Predictions are retrospective walk-forward estimates from Kyiv school-window history only.",
            "Brier skill is relative to the expanding-history frequency baseline on identical rows.",
            "Fixed-bin calibration error depends on the chosen bins and is descriptive, not a standalone selection criterion.",
            "Log loss clips probabilities at 1e-15 to keep exact zero/one predictions finite.",
            "Rare 120- and 180-minute outcomes have fewer events, so calibration estimates are noisy.",
            "No national attack predictors are included; the historical snapshot ends 2026-10-19 and is not live.",
            "This analysis does not establish operational safety; official alerts govern safety decisions."
        ],
    }
    bin_rows = []
    for threshold in THRESHOLDS:
        actual = [int(row[f"actual_ge{threshold}"]) for row in rows]
        if any(y not in (0, 1) for y in actual):
            raise SystemExit(f"Outcomes for threshold {threshold} must be binary.")
        baseline = [float(row[f"expanding_ge{threshold}"]) for row in rows]
        threshold_results = {}
        models = [f"rolling{window}" for window in WINDOWS] + ["expanding"]
        for model in models:
            probabilities = [float(row[f"{model}_ge{threshold}"]) for row in rows]
            if any(not math.isfinite(p) or p < 0 or p > 1 for p in probabilities):
                raise SystemExit(f"Invalid probability in {model}_ge{threshold}.")
            result = evaluate(probabilities, actual, baseline)
            bins = result.pop("calibration_bins")
            threshold_results[model] = {
                key: (round(value, 8) if isinstance(value, float) else value)
                for key, value in result.items()
            }
            for item in bins:
                bin_rows.append({
                    "threshold_minutes": threshold,
                    "model": model,
                    "bin": item["bin"],
                    "n": item["n"],
                    "mean_predicted": f"{item['mean_predicted']:.8f}",
                    "observed_rate": f"{item['observed_rate']:.8f}",
                    "absolute_gap": f"{item['absolute_gap']:.8f}",
                })
        summary["metrics"][str(threshold)] = threshold_results

    with BINS_CSV.open("w", newline="", encoding="utf-8") as f:
        fields = ["threshold_minutes", "model", "bin", "n", "mean_predicted", "observed_rate", "absolute_gap"]
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(bin_rows)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
