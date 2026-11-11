# Candidate attack-strategy regime changes for Kyiv alert forecasting

## Purpose

Record candidate change points and data-quality cautions to test against the Kyiv school-window alert series. These are hypotheses for model validation, not proof of causality and not a live threat assessment.

## Candidate dates from public reporting

- **Late April 2026:** ISW's 1 September assessment says Russia intensified jet-powered drone use in late April in response to high interception rates against piston-engine drones.
- **August 2026:** ISW says jet-powered drones became a regular part of daily strike packages for the first time, and reports increasingly continuous daytime and overnight waves.
- **27 August 2026 onward:** RBC-Ukraine describes near-continuous attacks involving jet-powered drones alongside conventional Shahed-type drones, including daytime waves directed toward Kyiv.
- **September 2026:** ISIS's monthly analysis reports 6,732 Shahed-type UAVs (including decoys) across the separately published night/early-morning series and seven daytime reports. This is a reporting baseline, not a complete 24-hour census.

## Public references

- ISW, *Russian Offensive Campaign Assessment, September 1, 2026*: https://understandingwar.org/research/russia-ukraine/russian-offensive-campaign-assessment-september-1-2026/
- RBC-Ukraine, *Russia's new strategy for attacking Kyiv: Jet-powered Shaheds and strikes on energy*, 1 October 2026: https://newsukraine.rbc.ua/analytics/russia-s-new-strategy-for-attacking-kyiv-1790832542.html
- ISIS, *Monthly Analysis of Russian Shahed 136 Deployment Against Ukraine — Updated*, September 2026 report, published 13 October 2026: https://isis-online.org/isis-reports/monthly-analysis-of-russian-shahed-136-deployment-against-ukraine
- Kyiv official alert dataset: https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal
- Historical attack data compiled from Ukrainian Air Force reporting: https://www.kaggle.com/datasets/piterfm/massive-missile-attacks-on-ukraine/data

## Data caveats

1. Public reports often describe launches, detections, interceptions, or estimates with different definitions. Do not merge these counts without preserving source and definition.
2. ISIS notes that full 24-hour Air Force UAV counts were not published for every day in September; the reported total combines the regular night/early-morning series with seven separate daytime reports.
3. Public reporting about ballistic-missile counts changed in August 2026. The Visua data notes that launch/interception counts for later months can be lower-bound estimates. A missing count must not be treated as zero.
4. Historical alert records describe warning time, not necessarily launches, impacts, or time spent in shelter. Alert practices and regional granularity can also change.
5. Any attack features used for a day-ahead forecast must have been publicly available by the forecast cutoff. A monthly retrospective summary must not be backfilled into earlier daily forecasts.
6. The observed improvement of a short rolling window is consistent with a changing regime but does not establish that the weapon mix caused it. Validate with time-ordered out-of-sample tests and compare against an alerts-only baseline.

## Proposed test

1. Keep the alerts-only rolling-30 and rolling-90 models as control baselines.
2. Build daily attack features only from timestamped reports, preserving publication time and uncertainty.
3. Add day/night split, reported jet-powered drone counts or lower bounds, long-range UAV totals, and missile categories only where definitions are comparable.
4. Evaluate on common walk-forward dates and report Brier score, calibration, and event counts. Compare with and without regime features.
5. Do not promote the new model unless it beats the alerts-only control across multiple periods and is not dependent on one small set of rare events.
