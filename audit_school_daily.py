#!/usr/bin/env python3
"""Audit the Kyiv daily school-window table against its source interval snapshot.

Long zero-alert streaks are reported as review flags, not automatically treated
as missing data: an interval snapshot alone cannot prove source completeness.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path


def parse_stamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", ""))


def merge_minutes(intervals: list[tuple[datetime, datetime]], lo: datetime, hi: datetime) -> float:
    clipped = sorted((max(a, lo), min(b, hi)) for a, b in intervals if min(b, hi) > max(a, lo))
    if not clipped:
        return 0.0
    total = 0.0
    left, right = clipped[0]
    for a, b in clipped[1:]:
        if a <= right:
            right = max(right, b)
        else:
            total += (right - left).total_seconds() / 60
            left, right = a, b
    return total + (right - left).total_seconds() / 60


def audit(source_path: str | Path, daily_path: str | Path, zero_streak_warning_days: int = 7) -> dict:
    source = json.loads(Path(source_path).read_text(encoding="utf-8"))
    intervals = []
    invalid_intervals = []
    for i, row in enumerate(source):
        try:
            start, end = parse_stamp(row["dateTimeStart"]), parse_stamp(row["dateTimeEnd"])
            if end <= start:
                raise ValueError("end is not after start")
            intervals.append((start, end))
        except (KeyError, TypeError, ValueError) as exc:
            invalid_intervals.append({"row": i, "reason": str(exc)})
    if not intervals:
        raise ValueError("No valid source intervals")
    first = min(a.date() for a, _ in intervals)
    last = max(b.date() for _, b in intervals)
    source_minutes = {}
    day = first
    while day <= last:
        lo, hi = datetime.combine(day, time(8, 30)), datetime.combine(day, time(15, 0))
        source_minutes[day.isoformat()] = round(merge_minutes(intervals, lo, hi), 2)
        day += timedelta(days=1)
    with Path(daily_path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    dates = [r.get("date", "") for r in rows]
    duplicate_dates = sorted({d for d in dates if dates.count(d) > 1})
    expected_dates = list(source_minutes)
    missing_dates = sorted(set(expected_dates) - set(dates))
    unexpected_dates = sorted(set(dates) - set(expected_dates))
    mismatches, invariant_errors = [], []
    row_by_date = {r.get("date", ""): r for r in rows}
    for d in sorted(set(expected_dates) & set(row_by_date)):
        row, expected_min = row_by_date[d], source_minutes[d]
        try:
            observed_min = float(row["school_window_min"])
            if abs(observed_min - expected_min) > 0.011:
                mismatches.append({"date": d, "daily_minutes": observed_min, "source_recomputed_minutes": expected_min})
            for threshold in (60, 120, 180):
                actual_label = int(row[f"alert_ge_{threshold}"])
                expected_label = int(expected_min >= threshold)
                if actual_label != expected_label:
                    invariant_errors.append({"date": d, "field": f"alert_ge_{threshold}", "actual": actual_label, "expected": expected_label})
            if int(row["any_school_alert"]) != int(expected_min > 0):
                invariant_errors.append({"date": d, "field": "any_school_alert", "actual": row["any_school_alert"], "expected": int(expected_min > 0)})
            if observed_min < 0 or observed_min > 390:
                invariant_errors.append({"date": d, "field": "school_window_min", "actual": observed_min, "expected_range": [0, 390]})
        except (KeyError, TypeError, ValueError) as exc:
            invariant_errors.append({"date": d, "field": "row_parse", "reason": str(exc)})
    zero_streaks = []
    start = previous = None
    for d, minutes in source_minutes.items():
        current = date.fromisoformat(d)
        if minutes == 0:
            if start is None:
                start = current
            previous = current
        elif start is not None:
            days = (previous - start).days + 1
            if days >= zero_streak_warning_days:
                zero_streaks.append({"start": start.isoformat(), "end": previous.isoformat(), "days": days})
            start = previous = None
    if start is not None:
        days = (previous - start).days + 1
        if days >= zero_streak_warning_days:
            zero_streaks.append({"start": start.isoformat(), "end": previous.isoformat(), "days": days})
    structural_errors = bool(invalid_intervals or duplicate_dates or missing_dates or unexpected_dates or mismatches or invariant_errors)
    return {
        "source_file": str(source_path), "daily_file": str(daily_path),
        "source_interval_rows": len(source), "valid_source_intervals": len(intervals),
        "invalid_source_intervals": invalid_intervals, "source_first_date": first.isoformat(),
        "source_last_date": last.isoformat(), "daily_rows": len(rows),
        "duplicate_dates": duplicate_dates, "missing_dates": missing_dates,
        "unexpected_dates": unexpected_dates, "source_vs_daily_minute_mismatches": mismatches,
        "label_or_range_invariant_errors": invariant_errors,
        "long_zero_school_window_streaks": zero_streaks,
        "zero_streak_warning_threshold_days": zero_streak_warning_days,
        "source_completeness": "not_verifiable_from_interval_snapshot_alone",
        "structural_status": "FAIL" if structural_errors else "PASS",
        "interpretation": "A long zero-alert streak is a review flag, not proof of missing source data. Confirm completeness and event definitions independently before treating historical scores as production evidence."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="airAlert.json")
    parser.add_argument("--daily", default="kyiv_school_daily.csv")
    parser.add_argument("--output", default="")
    parser.add_argument("--zero-streak-warning-days", type=int, default=7)
    args = parser.parse_args()
    if args.zero_streak_warning_days < 1:
        parser.error("--zero-streak-warning-days must be >= 1")
    report = audit(args.source, args.daily, args.zero_streak_warning_days)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if report["structural_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
