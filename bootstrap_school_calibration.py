#!/usr/bin/env python3
"""Moving-block bootstrap uncertainty for Kyiv school-window calibration metrics.

The bootstrap resamples aligned (prediction, outcome) sequences in contiguous
blocks so short-range temporal dependence is not treated as independent days.
Intervals quantify test-period sampling variability only; they do not establish
forecast safety or account for all model-selection uncertainty.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "kyiv_window_predictions.csv"
THRESHOLDS = (60, 120, 180)
WINDOWS = (30, 60, 90, 180, 365)
DEFAULT_BLOCK_DAYS = 14
DEFAULT_REPLICATES = 1000
DEFAULT_SEED = 20261024
EPSILON = 1e-15


def brier(probabilities: Sequence[float], actual: Sequence[int]) -> float:
    if not actual or len(probabilities) != len(actual):
        raise ValueError("Probabilities and outcomes must be non-empty and aligned")
    return sum((p - y) ** 2 for p, y in zip(probabilities, actual)) / len(actual)


def log_loss(probabilities: Sequence[float], actual: Sequence[int]) -> float:
    if not actual or len(probabilities) != len(actual):
        raise ValueError("Probabilities and outcomes must be non-empty and aligned")
    total = 0.0
    for p, y in zip(probabilities, actual):
        p = min(1.0 - EPSILON, max(EPSILON, p))
        total -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return total / len(actual)


def laplace_probability(probability: float, window: int) -> float:
    if window <= 0:
        raise ValueError("window must be positive")
    # Backtest rolling rates are emitted to six decimal places; round back to
    # the underlying integer count before applying the Beta(1, 1) smoothing.
    events = round(probability * window)
    return (events + 1) / (window + 2)


def circular_block_indices(n: int, block_days: int, rng: random.Random) -> list[int]:
    if n < 1 or block_days < 1:
        raise ValueError("n and block_days must be positive")
    indices: list[int] = []
    while len(indices) < n:
        start = rng.randrange(n)
        indices.extend((start + offset) % n for offset in range(block_days))
    return indices[:n]


def percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values or not 0 <= q <= 1:
        raise ValueError("percentile requires values and q in [0, 1]")
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def summarize_bootstrap(
    actual: Sequence[int],
    probabilities: Sequence[float],
    baseline: Sequence[float],
    *,
    replicates: int = DEFAULT_REPLICATES,
    block_days: int = DEFAULT_BLOCK_DAYS,
    seed: int = DEFAULT_SEED,
) -> dict:
    if len(actual) != len(probabilities) or len(actual) != len(baseline) or not actual:
        raise ValueError("Actuals, probabilities, and baseline must be aligned and non-empty")
    if replicates < 100:
        raise ValueError("Use at least 100 replicates for a rough interval")
    if block_days < 1 or block_days > len(actual):
        raise ValueError("block_days must be between 1 and the number of rows")
    if any(y not in (0, 1) for y in actual):
        raise ValueError("Outcomes must be binary")
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in [*probabilities, *baseline]):
        raise ValueError("Probabilities must be finite and in [0, 1]")

    point_brier = brier(probabilities, actual)
    baseline_brier = brier(baseline, actual)
    point_skill = None if baseline_brier == 0 else 1 - point_brier / baseline_brier
    rng = random.Random(seed)
    brier_values: list[float] = []
    logloss_values: list[float] = []
    skill_values: list[float] = []
    for _ in range(replicates):
        indices = circular_block_indices(len(actual), block_days, rng)
        ys = [actual[i] for i in indices]
        ps = [probabilities[i] for i in indices]
        bs = [baseline[i] for i in indices]
        candidate_brier = brier(ps, ys)
        baseline_score = brier(bs, ys)
        brier_values.append(candidate_brier)
        logloss_values.append(log_loss(ps, ys))
        if baseline_score > 0:
            skill_values.append(1 - candidate_brier / baseline_score)

    def interval(values: list[float]) -> list[float]:
        ordered = sorted(values)
        return [round(percentile(ordered, 0.025), 8), round(percentile(ordered, 0.975), 8)]

    return {
        "n_days": len(actual),
        "event_count": sum(actual),
        "replicates": replicates,
        "block_days": block_days,
        "seed": seed,
        "brier_score": round(point_brier, 8),
        "brier_score_95pct_block_bootstrap_interval": interval(brier_values),
        "log_loss": round(log_loss(probabilities, actual), 8),
        "log_loss_95pct_block_bootstrap_interval": interval(logloss_values),
        "brier_skill_vs_expanding": None if point_skill is None else round(point_skill, 8),
        "brier_skill_95pct_block_bootstrap_interval": interval(skill_values) if skill_values else None,
        "interpretation": "Intervals describe test-period sampling variability under a circular moving-block bootstrap; they are not proof of operational safety and do not account for all model-selection uncertainty.",
    }


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"No predictions found in {path}")
    dates = [row["date"] for row in rows]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise SystemExit("Prediction dates must be unique and chronological")
    return rows


def build_report(rows: list[dict[str, str]], replicates: int, block_days: int, seed: int) -> dict:
    report = {
        "source": SOURCE.name,
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "test_days": len(rows),
        "method": "circular moving-block bootstrap of aligned daily predictions and outcomes",
        "metrics": {},
        "caveats": [
            "The block length is fixed at 14 days before reading results; sensitivity to other lengths is not covered by this run.",
            "Intervals quantify test-period sampling variability and not all uncertainty from model selection or regime change.",
            "All compared predictions use only data before their target date; no national attack predictors are included.",
            "Official alerts, not this retrospective analysis, govern safety decisions.",
        ],
    }
    for threshold in THRESHOLDS:
        actual = [int(row[f"actual_ge{threshold}"]) for row in rows]
        baseline = [float(row[f"expanding_ge{threshold}"]) for row in rows]
        models: dict[str, dict] = {}
        candidates = [f"rolling{window}" for window in WINDOWS]
        candidates += [f"rolling{window}_laplace" for window in WINDOWS]
        candidates += ["expanding"]
        for model_index, model in enumerate(candidates):
            if model.endswith("_laplace"):
                window = int(model[len("rolling"):-len("_laplace")])
                probabilities = [
                    laplace_probability(float(row[f"rolling{window}_ge{threshold}"]), window)
                    for row in rows
                ]
            else:
                probabilities = [float(row[f"{model}_ge{threshold}"]) for row in rows]
            models[model] = summarize_bootstrap(
                actual, probabilities, baseline,
                replicates=replicates, block_days=block_days,
                seed=seed + threshold * 100 + model_index,
            )
        report["metrics"][str(threshold)] = models
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=SOURCE)
    parser.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES)
    parser.add_argument("--block-days", type=int, default=DEFAULT_BLOCK_DAYS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    rows = load_rows(args.input)
    print(json.dumps(build_report(rows, args.replicates, args.block_days, args.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
