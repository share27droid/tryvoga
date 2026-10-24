# Kyiv school-window daily dataset and baseline forecast test

This branch adds reproducible daily labels, lagged features, and a leakage-safe baseline backtest derived from the official Kyiv alert snapshot.

## Files
- \`kyiv_school_daily.csv\`: one row per date from 2022-02-28 through 2026-10-19.
- \`build_school_daily.py\`: rebuilds daily school-window labels from \`airAlert.json\`.
- \`audit_school_daily.py\` and \`test_audit_school_daily.py\`: recompute the 08:30–15:00 totals from \`airAlert.json\`, validate labels/date continuity, and flag long zero-alert streaks for review without automatically calling them missing data.
- \`kyiv_school_features.csv\` and \`build_school_features.py\`: lagged features for prior 1, 3, 7, 14, 30, and 90 days.
- \`kyiv_baseline_predictions.csv\`, \`kyiv_baseline_backtest_summary.json\`, and \`backtest_school_baselines.py\`: initial walk-forward comparison of expanding-history and rolling-90-day frequency baselines.
- \`kyiv_window_predictions.csv\`, \`kyiv_window_backtest_summary.json\`, and \`backtest_school_windows.py\`: fair common-period walk-forward comparison of 30-, 60-, 90-, 180-, and 365-day rolling frequencies against expanding history.
- \`analyze_school_window_stability.py\` and \`kyiv_window_stability.json\`: half-year slices showing how the 30-day vs 90-day comparison changes across historical regimes.
- \`evaluate_adaptive_regime.py\`, \`kyiv_adaptive_regime_predictions.csv\`, and \`kyiv_adaptive_regime_summary.json\`: exploratory blend of 30- and 90-day rates that gives more weight to the 30-day estimate when the two disagree. This is a benchmark only, not a production forecast.
- \`diagnose_regime_changes.py\` and \`kyiv_regime_change_diagnostic.json\`: exploratory scan for a single change point in the historical frequency of 60-, 120-, and 180-minute school-window alert days; descriptive, not causal proof.
- \`strategy_regime_hypothesis.md\`: candidate attack-strategy change timeline and source limitations.
- \`attack_data_contract.md\`: schema and no-leakage rules for national attack predictors; explicitly distinguishes event time from publication time.
- \`import_attack_observations.py\`: normalizes a downloaded historical attack CSV and emits a QA report; rows without a timezone-aware publication timestamp are excluded from as-of forecasting by default.
- \`enrich_attack_publication_times.py\` and \`test_enrich_attack_publication_times.py\`: resolves publication timestamps only from exact public Telegram post URLs in the source column; generic dataset URLs and unresolved posts remain ineligible.
- \`build_attack_asof_features.py\`: builds exploratory trailing 1/3/7-day national features at a Kyiv-local forecast cutoff, filtering out observations published after the cutoff and keeping missing sums distinct from zero.
- \`tryvoga-alerts.csv\`, \`tryvoga-daily.csv\`, and \`tryvoga-nights.csv\`: user-added structured exports from tryvoga.live / official Air Force report links; currently short recent coverage only.
- \`audit_tryvoga_sources.py\` and \`test_tryvoga_sources.py\`: structural QA for the three exports, including duplicate keys, interval-duration mismatches, open intervals, and publication-time limitations.
- \`build_tryvoga_school_labels.py\` and \`test_tryvoga_school_labels.py\`: descriptive Kyiv City school-window totals and threshold labels from the interval export, with overlap merging and censoring safeguards.
- \`test_attack_pipeline.py\`: standard-library regression tests for timestamp eligibility, future-publication exclusion, and missing-vs-zero handling.

## Method
- School window: 08:30–15:00, Kyiv local clock as recorded in the source.
- Intersect alert intervals with the school window and merge overlaps before computing total minutes and threshold labels.
- Outcomes are at least 60, 120, or 180 minutes of alert during the school window.
- \`raw_overlap_min\` sums overlaps before merging; \`overlap_excess_min\` records time that would be double-counted without merging.
- Missing level/cause metadata is not imputed.
- Features named \`prev_Nd_*\` use only rows strictly before the target date. Target-day labels are included only for retrospective evaluation.
- The initial baseline test uses the first 180 days as warm-up. The window-comparison test uses a 365-day warm-up so all candidate windows are scored on exactly the same dates. Brier score is lower-is-better.
- Calibration metrics are descriptive diagnostics on the same common walk-forward period. Fixed-bin calibration error depends on the chosen bins; rare 120/180-minute events make estimates noisy. Brier skill is relative to the expanding-history baseline.
- The snapshot is historical, not a live feed. These baseline results are not the four-model comparison and do not establish operational safety.

## Probability calibration

`evaluate_school_calibration.py` evaluates the raw rolling-window probabilities and Laplace-smoothed variants on the existing 1,330-day common walk-forward test period. The smoothed variant uses `(events + 1) / (window_days + 2)` to avoid exact zero/one probabilities. This improves log loss in the current retrospective comparison, especially for rare events, but can worsen Brier score or shift average probabilities upward; it is a diagnostic comparison, not a production-model selection. See `kyiv_calibration_summary.json` and `kyiv_calibration_bins.csv`. Calibration results depend on this historical snapshot and do not establish live forecast quality.

## Rebuild and test
Run from the repository root:
\`\`\`bash
python build_school_daily.py
python build_school_features.py
python backtest_school_baselines.py
python backtest_school_windows.py
python evaluate_school_calibration.py
python analyze_school_window_stability.py
python -m unittest -v test_attack_pipeline.py test_tryvoga_sources.py test_tryvoga_school_labels.py test_audit_school_daily.py test_enrich_attack_publication_times.py
python audit_tryvoga_sources.py
python audit_school_daily.py --output kyiv_school_daily_audit.json
# Optional, after manually downloading the public dataset CSV:
python import_attack_observations.py --input missile_attacks_daily.csv
python enrich_attack_publication_times.py --input attack_observations_normalized.csv --delay-seconds 1
python build_attack_asof_features.py --naive-event-timezone Europe/Kyiv
\`\`\`

The timestamp resolver visits only source URLs that point to a specific public Telegram post. If the downloaded CSV has no such per-row source links, it cannot resolve publication times from the generic Kaggle dataset URL. A resolved Telegram post timestamp still requires checking that the row's numeric value and reporting window match the linked post.

To create a descriptive school-window label file from the tryvoga.live interval export, use only a date range for which source coverage has been verified and enter the actual export snapshot time (Kyiv local clock):
\`\`\`bash
python build_tryvoga_school_labels.py --input tryvoga-alerts.csv --output tryvoga_kyiv_school_labels.csv --start-date YYYY-MM-DD --end-date YYYY-MM-DD --snapshot-as-of "YYYY-MM-DD HH:MM" --assume-source-complete
\`\`\`
The script intentionally refuses to assume source coverage or infer a snapshot timestamp. Labels are blank for windows not fully elapsed at the snapshot or intersecting an interval that was still open at that snapshot. The output is descriptive, not a forecast-training dataset unless source completeness and historical availability are independently established.

The Kyiv audit compares the daily table with the interval snapshot and checks that threshold labels and date coverage agree. Long zero-alert streaks are warnings for independent source review, not automatic proof that records are missing. The official portal describes \`airAlert.json\` as the Kyiv chronological alert list updated weekly; its snapshot alone does not prove that all historical intervals were continuously captured.

The attack-pipeline and source-audit tests use synthetic fixtures only. The current tryvoga.live exports cover 2026-10-05 through 2026-10-24 (alert intervals may begin/end on different dates), and therefore are not a replacement for the long Kyiv outcome history. The \`tryvoga-nights.csv\` \`as_of\` field is clock-only, not a date-time; do not treat it as a trustworthy publication timestamp. The daily regional export is retrospective and does not, by itself, prove when each reported value became available. These exports are useful for descriptive analysis and pipeline QA, but must not enter leakage-safe attack-feature backtests until publication/version availability is established. Passing tests checks code behavior, not the truth or historical availability of publication timestamps in a real source. Do not claim an as-of national attack backtest until that provenance is independently verified.

## Manually transcribed Kyiv map history

- `kyiv-manual-alerts.csv` stores the 20 intervals pasted from the Kyiv alert-history map for 2026-10-22 through 2026-10-24. It is kept separate from the official `airAlert.json` snapshot and the tryvoga.live export; the source URL is recorded, but exact source publication time and independent completeness verification are not known.
- `summarize_manual_kyiv_alerts.py` merges overlaps, clips intervals to 08:30–15:00 Kyiv time, and produces descriptive threshold labels. `kyiv-manual-school-summary.csv` records the current calculation: 147 minutes on Oct 22, 108 on Oct 23, and 18 on Oct 24.
- Rebuild with `python summarize_manual_kyiv_alerts.py --input kyiv-manual-alerts.csv --output kyiv-manual-school-summary.csv`. The workflow runs this builder and its regression tests.
- These three dates are a manually transcribed supplement, not a continuous historical feed. Do not append them blindly to the long historical training table or use them as evidence of a live forecast's accuracy. Confirm source coverage and provenance before training/backtesting.
