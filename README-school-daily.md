# Kyiv school-window daily dataset and baseline forecast test

This branch adds reproducible daily labels, lagged features, and a leakage-safe baseline backtest derived from the official Kyiv alert snapshot.

## Files
- `kyiv_school_daily.csv`: one row per date from 2022-02-28 through 2026-10-19.
- `build_school_daily.py`: rebuilds daily school-window labels from `airAlert.json`.
- `kyiv_school_features.csv` and `build_school_features.py`: lagged features for prior 1, 3, 7, 14, 30, and 90 days.
- `kyiv_baseline_predictions.csv`, `kyiv_baseline_backtest_summary.json`, and `backtest_school_baselines.py`: walk-forward comparison of expanding-history and rolling-90-day frequency baselines.

## Method
- School window: 08:30–15:00, Kyiv local clock as recorded in the source.
- Intersect alert intervals with the school window and merge overlaps before computing total minutes and threshold labels.
- Outcomes are at least 60, 120, or 180 minutes of alert during the school window.
- `raw_overlap_min` sums overlaps before merging; `overlap_excess_min` records time that would be double-counted without merging.
- Missing level/cause values remain unknown and are not inferred.
- Features named `prev_Nd_*` use only rows strictly before the target date. Target-day labels are included only for retrospective evaluation.
- The baseline test uses the first 180 days as warm-up and then evaluates each day chronologically. Brier score is lower-is-better.
- The snapshot is historical, not a live feed. These baseline results are not the four-model comparison and do not establish operational safety.

## Rebuild and test
Run from the repository root:
```bash
python build_school_daily.py
python build_school_features.py
python backtest_school_baselines.py
```
