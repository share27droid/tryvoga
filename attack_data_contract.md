# Historical attack data contract for forecast features

## Purpose

Define a leakage-safe format for national attack observations before connecting them to Kyiv school-window forecasts. This document is a data contract, not a claim that the historical event table has already been assembled.

## One row per source-reported observation

Required fields:

- `event_date`: date/time of the attack or reporting interval, in Kyiv time when the source supports it.
- `published_at`: timestamp when this specific value became publicly available.
- `source_name`: publisher or dataset.
- `source_url`: exact article, report, dataset row, or stable URL.
- `observation_scope`: `night_morning`, `daytime`, `full_day`, `multi_day`, or `unknown`.
- `metric_name`: normalized metric such as `uav_launched`, `uav_jet_confirmed`, `uav_jet_minimum`, `cruise_missile_launched`, `ballistic_missile_launched`, `uav_intercepted`, or `impact_count`.
- `value`: numeric value, if explicitly reported.
- `lower_bound`: minimum defensible count if source says "at least" or gives an incomplete count.
- `unit`: objects, events, or percent.
- `status`: `exact`, `minimum`, `estimate`, `qualitative`, `missing`, or `revised`.
- `definition_note`: source-specific meaning and caveats.
- `supersedes_observation_id`: prior value ID if a later report revises the figure.

Recommended extra fields: `observation_id`, `attack_wave_id`, `region_scope`, `aircraft_type`, `daypart`, `source_confidence`, `captured_at`, `raw_quote`.

## Strict rules

1. A blank value is not zero. A report that does not quantify daytime launches is not evidence of no daytime launches.
2. Preserve exact counts, lower bounds, estimates, and qualitative reports as distinct statuses; do not silently convert them into one comparable count.
3. Keep the source publication timestamp. For a forecast made at cutoff time T, use only records with `published_at <= T`.
4. A monthly retrospective estimate published after month-end must not be used to predict days earlier in that month.
5. Do not equate launches, detected UAVs, intercepted UAVs, impacts, and air-raid alerts. They are different measures.
6. Keep observation window and timezone explicit. Do not compare a night-only count with a complete 24-hour count without marking the mismatch.
7. If a source revises its count, retain the original observation and link the revision; do not overwrite history in a way that leaks future knowledge into earlier forecasts.
8. Use national attack features to predict Kyiv alert outcomes only as candidate predictors. National totals do not identify the destination of each weapon.
9. Fit transformations, thresholds, and missing-data rules using training history only within each walk-forward fold.
10. Compare each feature model against the alerts-only baseline on the exact same test dates.

## Candidate public sources and limitations

- **Ukrainian Air Force daily reports**, compiled in the historical missile/drone attack dataset: https://www.kaggle.com/datasets/piterfm/massive-missile-attacks-on-ukraine/data . Useful for national totals by type, but the reported event is often a strike/reporting period rather than a timestamped launch stream.
- **ISIS monthly Shahed deployment analyses**: https://isis-online.org/isis-reports/monthly-analysis-of-russian-shahed-136-deployment-against-ukraine-updated . Useful for retrospective monthly context and jet-powered drone evidence; not usable as a daily predictor before the report's publication date.
- **Kyiv Dialogue Air War Monitor**: https://www.kyiv-dialogue.org/en/news/newsreader/ukraine-air-war-monitor-vol-xxi.html . Useful for analytical cross-checks, but estimates may use different definitions than official reports.

- **Coverage and reporting-regime caution (checked 24 October 2026):** the PiterFM dataset begins in late September 2022, not February 2022. A current independent data review documents a change in Ukrainian Air Force reporting in August 2026: ballistic-missile launch/interception details stopped appearing consistently in after-attack updates, and many August reports omit both launch and interception totals. These fields must be treated as partially observed / lower-bound data after the change, not as a real decline or as zero. See https://visua.no/en/charts/attacks-ua-missiles/ and the dataset's own review at https://www.kaggle.com/code/piterfm/massive-missile-attacks-on-ukraine-data-review.

- **tryvoga.live data**: https://tryvoga.live/en/data . Structured regional alerts and weapon statistics begin 5 October 2026, so this source alone is too short for a 2022–2026 historical backtest.
- **Kyiv official alert history**: https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal . Primary outcome source for Kyiv alert-window duration, not a national attack-launch dataset.

## First candidate features

Build only after historical values and publication times are assembled:
- trailing 1/3/7-day reported national UAV totals, with day/night scope kept separate;
- trailing 1/3/7-day reported jet-powered UAV counts or lower bounds;
- trailing missile-type counts only when definitions are comparable;
- daytime-activity share only on days where both numerator and denominator have adequate coverage;
- number of consecutive days with reported daytime waves;
- indicators for missing or partial reporting, rather than replacing missing values with zero.

Do not treat estimated Russian stockpiles or production capacity as precise daily measurements. They belong in a separate, slowly updated context layer with publication timestamps and wide uncertainty ranges.

## Evaluation plan

1. Assemble and quality-check event observations with publication timestamps.
2. Generate features "as known at forecast time" for every historical day.
3. Run walk-forward tests with identical test dates for (A) alerts-only baseline, (B) attack features alone, and (C) combined features.
4. Report Brier score and calibration for 60/120/180-minute school-window events, plus event counts and period-by-period performance.
5. Accept the attack-feature model only if it improves beyond the baseline across multiple periods without relying on future reports or a few rare events.

## Importer added

`import_attack_observations.py` normalizes a downloaded source CSV into a consistent table and writes a QA JSON report. It maps common spellings of the source columns but does not fetch the dataset itself or invent missing values.

Example:
```bash
python import_attack_observations.py --input missile_attacks_daily.csv \
  --output attack_observations_normalized.csv \
  --qa attack_observations_qa.json
```

The importer intentionally leaves `published_at` blank and marks rows `usable_for_asof_forecast=false` unless a publication-time column is explicitly supplied with `--publication-time-column COLUMN_NAME`. The PiterFM/Kaggle data review describes event start/end, model, launch place, target, and launched/destroyed counts, but that schema does not by itself establish when each value first became public. A retrospective CSV snapshot cannot support a leakage-safe historical daily forecast merely by sorting on attack time. If only one current CSV is available, it is suitable for descriptive analysis and candidate feature research, not a claimed as-of backtest.

## As-of feature builder

`build_attack_asof_features.py` builds daily features at a configurable Kyiv-local cutoff (default 08:30) for trailing 1-, 3-, and 7-day event windows. A row is eligible only when its event timestamp is parseable, its publication timestamp is timezone-aware and parseable, its usability flag is true, and `published_at <= cutoff`. For event timestamps without offsets, pass an explicit convention such as `--naive-event-timezone Europe/Kyiv`; publication timestamps without offsets are always rejected rather than guessed.

Example, after normalizing the downloaded source:
```bash
python import_attack_observations.py --input missile_attacks_daily.csv
python build_attack_asof_features.py --input attack_observations_normalized.csv \
  --naive-event-timezone Europe/Kyiv
```

Outputs are `attack_asof_daily_features.csv` and `attack_asof_daily_features_qa.json`. Sums remain blank if there are no numeric values in the eligible rows; separate known/missing-row counts make missingness visible. The script is a feature engineering scaffold, not proof that the source's publication timestamps represent the exact historical version of each row. Do not report a valid backtest until this provenance is verified.

