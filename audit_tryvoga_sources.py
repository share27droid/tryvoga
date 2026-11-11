#!/usr/bin/env python3
"""Quality-audit the three manually collected tryvoga.live CSV exports.

This script checks structural consistency only. It does not certify that weapon
counts were publicly available at a historical forecast cutoff, and it never
turns a clock-only `as_of` value into a publication timestamp.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_local_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat((value or "").strip())
    except ValueError:
        return None


def audit_rows(
    alerts: list[dict[str, str]],
    daily: list[dict[str, str]],
    nights: list[dict[str, str]],
) -> dict[str, Any]:
    alert_required = {
        "region_id", "start_kyiv", "end_kyiv", "duration_min", "red_level", "red_min"
    }
    daily_required = {
        "date", "region_id", "alerts", "alerts_red", "alerts_yellow",
        "alert_min", "red_min", "drones", "drones_jet", "missiles",
        "missiles_ballistic", "guided_bombs",
    }
    night_required = {
        "night_of", "from", "as_of", "launched", "launched_at_least", "source_url"
    }

    def missing_columns(rows: list[dict[str, str]], required: set[str]) -> list[str]:
        return sorted(required - set(rows[0].keys() if rows else []))

    alert_columns_missing = missing_columns(alerts, alert_required)
    daily_columns_missing = missing_columns(daily, daily_required)
    night_columns_missing = missing_columns(nights, night_required)

    alert_dates = sorted({
        row.get("start_kyiv", "")[:10] for row in alerts if row.get("start_kyiv")
    })
    alert_regions = sorted({row.get("region_id", "") for row in alerts if row.get("region_id")})
    open_intervals = [row for row in alerts if not row.get("end_kyiv", "").strip()]
    duration_mismatches = []
    invalid_alert_durations = 0
    for row in alerts:
        try:
            duration = float(row.get("duration_min", ""))
        except (TypeError, ValueError):
            invalid_alert_durations += 1
            continue
        start = _parse_local_datetime(row.get("start_kyiv", ""))
        end = _parse_local_datetime(row.get("end_kyiv", ""))
        if duration < 0:
            invalid_alert_durations += 1
        elif start and end:
            difference = abs((end - start).total_seconds() / 60 - duration)
            if difference > 2:
                duration_mismatches.append({
                    "region_id": row.get("region_id", ""),
                    "start_kyiv": row.get("start_kyiv", ""),
                    "end_kyiv": row.get("end_kyiv", ""),
                    "duration_min": row.get("duration_min", ""),
                    "difference_min": round(difference, 2),
                })

    daily_keys = [(r.get("date", ""), r.get("region_id", "")) for r in daily]
    daily_key_counts = Counter(daily_keys)
    rows_per_date = Counter(r.get("date", "") for r in daily if r.get("date"))
    daily_dates = sorted(rows_per_date)
    daily_regions = sorted({r.get("region_id", "") for r in daily if r.get("region_id")})
    daily_numeric_fields = [
        "alerts", "alerts_red", "alerts_yellow", "alert_min", "red_min",
        "drones", "drones_jet", "missiles", "missiles_ballistic", "guided_bombs",
    ]
    blank_daily_numeric = sum(
        1 for row in daily for field in daily_numeric_fields
        if not (row.get(field) or "").strip()
    )
    invalid_daily_numeric = []
    for row in daily:
        for field in daily_numeric_fields:
            value = (row.get(field) or "").strip()
            if value:
                try:
                    if float(value) < 0:
                        raise ValueError
                except ValueError:
                    invalid_daily_numeric.append({
                        "date": row.get("date", ""),
                        "region_id": row.get("region_id", ""),
                        "field": field,
                        "value": value,
                    })

    night_dates = sorted({r.get("night_of", "") for r in nights if r.get("night_of")})
    invalid_as_of = [
        {"night_of": r.get("night_of", ""), "as_of": r.get("as_of", "")}
        for r in nights
        if not __import__("re").fullmatch(r"\d{1,2}:\d{2}", (r.get("as_of") or "").strip())
    ]
    missing_night_sources = sum(1 for r in nights if not (r.get("source_url") or "").strip())
    missing_launch_counts = sum(1 for r in nights if not (r.get("launched") or "").strip())
    at_least_count = sum(
        1 for r in nights if (r.get("launched_at_least") or "").strip() == "1"
    )

    return {
        "scope": "structural QA only; not a leakage-safe forecast dataset certification",
        "alerts": {
            "rows": len(alerts),
            "missing_required_columns": alert_columns_missing,
            "date_range_by_interval_start": [alert_dates[0], alert_dates[-1]] if alert_dates else [],
            "distinct_regions_with_alert_rows": len(alert_regions),
            "open_intervals": len(open_intervals),
            "open_interval_examples": open_intervals[:10],
            "invalid_or_negative_duration_rows": invalid_alert_durations,
            "closed_interval_duration_mismatches_over_2min": len(duration_mismatches),
            "duration_mismatch_examples": duration_mismatches[:10],
        },
        "daily": {
            "rows": len(daily),
            "missing_required_columns": daily_columns_missing,
            "date_range": [daily_dates[0], daily_dates[-1]] if daily_dates else [],
            "distinct_dates": len(daily_dates),
            "distinct_regions": len(daily_regions),
            "rows_per_date": dict(sorted(rows_per_date.items())),
            "duplicate_date_region_keys": sum(n - 1 for n in daily_key_counts.values() if n > 1),
            "blank_numeric_cells": blank_daily_numeric,
            "invalid_or_negative_numeric_cells": len(invalid_daily_numeric),
            "invalid_numeric_examples": invalid_daily_numeric[:10],
        },
        "nights": {
            "rows": len(nights),
            "missing_required_columns": night_columns_missing,
            "date_range": [night_dates[0], night_dates[-1]] if night_dates else [],
            "distinct_nights": len(night_dates),
            "invalid_clock_only_as_of_values": invalid_as_of,
            "rows_missing_source_url": missing_night_sources,
            "rows_missing_launch_count": missing_launch_counts,
            "rows_marked_launched_at_least": at_least_count,
            "publication_timestamp_available": False,
            "publication_time_warning": (
                "The as_of column contains only a clock time. Without a date, timezone, "
                "and auditable capture/publication semantics, it is not a valid published_at timestamp."
            ),
        },
        "forecast_eligibility": {
            "tryvoga_alerts_csv": "candidate historical alert intervals; coverage is short and open intervals need special handling",
            "tryvoga_daily_csv": "descriptive regional daily features only until historical publication/version availability is established",
            "tryvoga_nights_csv": "descriptive night totals only; not eligible for as-of training from as_of clock alone",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alerts", default="tryvoga-alerts.csv")
    parser.add_argument("--daily", default="tryvoga-daily.csv")
    parser.add_argument("--nights", default="tryvoga-nights.csv")
    parser.add_argument("--output", default="tryvoga_sources_qa.json")
    args = parser.parse_args()

    report = audit_rows(
        read_csv(args.alerts),
        read_csv(args.daily),
        read_csv(args.nights),
    )
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
