# Kyiv school-window daily dataset and baseline forecast test

This branch adds reproducible daily labels, lagged features, and a leakage-safe baseline backtest derived from the official Kyiv alert snapshot.

## Files
- `kyiv_school_daily.csv`: one row per date from 2022-02-28 through 2026-10-19.
- `build_school_daily.py`: rebuilds daily school-window labels from `airAlert.json`.
- `kyiv_school_features.csv` and `build_school_features.py`: lagged features for prior 1, 3, 7, 14, 30, and 90 days.
- `kyiv_baseline_predictions.csv`, `kyiv_baseline_backtest_summary.json`, and `backtest_school_baselines.py`: initial walk-forward comparison of expanding-history and rolling-90-day frequency baselines.
- `kyiv_window_predictions.csv`, `kyiv_window_backtest_summary.json`, and `backtest_school_windows.py`: fair common-period walk-forward comparison of 30-, 60-, 90-, 180-, and 365-day rolling frequencies against expanding history.
- `analyze_school_window_stability.py` and `kyiv_window_stability.json`: half-year slices showing how the 30-day vs 90-day comparison changes across historical regimes.
- `evaluate_adaptive_regime.py`, `kyiv_adaptive_regime_predictions.csv`, and `kyiv_adaptive_regime_summary.json`: exploratory blend of 30- and 90-day rates that gives more weight to the 30-day estimate when the two disagree. This is a benchmark only, not a production forecast.
- `diagnose_regime_changes.py` and `kyiv_regime_change_diagnostic.json`: exploratory scan for a single change point in the historical frequency of 60-, 120-, and 180-minute school-window alert days; it is descriptive and not causal proof.
- `strategy_regime_hypothesis.md`: candidate strategy-change timeline and source limitations.
- `attack_data_contract.md`: schema and no-leakage rules for national attack predictors; explicitly distinguishes event time from publication time.\n- `import_attack_observations.py`: normalizes a downloaded historical attack CSV and emits a QA report; rows without a verifiable publication timestamp are excluded from as-of forecasting by default.\n- `build_attack_asof_features.py`: builds exploratory trailing 1/3/7-day national features at a Kyiv-local forecast cutoff, filtering out observations published after the cutoff and keeping missing counts distinct from zero.

## Method
- School window: 08:30–15:00, Kyiv local clock as recorded in the source.
- Intersect alert intervals with the school window and merge overlaps before computing total minutes and threshold labels.
- Outcomes are at least 60, 120, or 180 minutes of alert during the school window.
- `raw_overlap_min` sums overlaps before merging; `overlap_excess_min` records time that would be double-counted without merging.
- Missing level/cause values remain unknown and are not inferred.
- Features named `prev_Nd_*` use only rows strictly before the target date. Target-day labels are included only for retrospective evaluation.
- The initial baseline test uses the first 180 days as warm-up. The window-comparison test uses a 365-day warm-up so all candidate windows are scored on exactly the same dates. Brier score is lower-is-better.
- The snapshot is historical, not a live feed. These baseline results are not the four-model comparison and do not establish operational safety.

## Rebuild and test
Run from the repository root:
```bash
python build_school_daily.py
python build_school_features.py
python backtest_school_baselines.py
python backtest_school_windows.py
python analyze_school_window_stability.py
# Optional, after manually downloading the public dataset CSV:
python import_attack_observations.py --input missile_attacks_daily.csv
python build_attack_asof_features.py --naive-event-timezone Europe/Kyiv
```
