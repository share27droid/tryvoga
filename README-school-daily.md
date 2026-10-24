# Kyiv school-window daily dataset

This branch adds a derived daily table and a reproducible builder from the official Kyiv alert snapshot.

## Files
- `kyiv_school_daily.csv`: one row per date in the source interval (2022-02-28 through 2026-10-19).
- `build_school_daily.py`: rebuilds the CSV from `airAlert.json`.

## Method
- School window: 08:30–15:00, Kyiv local clock.
- Intersect each recorded alert interval with the school window, then merge overlapping intervals before computing total minutes and threshold labels.
- Threshold outcomes: at least 60, 120, or 180 minutes of alert during the school window.
- `raw_overlap_min` sums overlaps before merging; `overlap_excess_min` records time that would be double-counted without merging.
- Missing level/cause values are counted as unknown and are not inferred.
- The snapshot is historical, not a live feed. The CSV is an outcome/label dataset; forecasting features must be lagged to avoid target leakage.

## Rebuild
Run from the repository root:
```bash
python build_school_daily.py
```
