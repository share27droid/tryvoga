#!/usr/bin/env python3
"""Summarize manually transcribed Kyiv alert intervals for the school window.

These summaries are descriptive only. The input is a manually pasted map
history, not a completeness-certified historical feed or a live forecast source.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime, time
from pathlib import Path


def parse_interval(row: dict[str, str]) -> tuple[datetime, datetime]:
    day = date.fromisoformat(row["date"].strip())
    start = datetime.combine(day, time.fromisoformat(row["start_kyiv"].strip()))
    end = datetime.combine(day, time.fromisoformat(row["end_kyiv"].strip()))
    if end <= start:
        raise ValueError(f"end_kyiv must be after start_kyiv on the same date: {row!r}")
    if row.get("level", "").strip().lower() not in {"yellow", "red"}:
        raise ValueError(f"level must be yellow or red: {row!r}")
    return start, end


def merge_minutes(intervals: list[tuple[datetime, datetime]],
                  window_start: datetime, window_end: datetime) -> int:
    clipped = sorted(
        (max(start, window_start), min(end, window_end))
        for start, end in intervals
        if min(end, window_end) > max(start, window_start)
    )
    if not clipped:
        return 0
    total = 0
    left, right = clipped[0]
    for start, end in clipped[1:]:
        if start <= right:
            right = max(right, end)
        else:
            total += int((right - left).total_seconds() // 60)
            left, right = start, end
    return total + int((right - left).total_seconds() // 60)


def summarize(rows: list[dict[str, str]]) -> list[dict[str, str | int]]:
    by_day: dict[date, list[tuple[datetime, datetime]]] = defaultdict(list)
    for row in rows:
        start, end = parse_interval(row)
        by_day[start.date()].append((start, end))

    output = []
    for day in sorted(by_day):
        start = datetime.combine(day, time(8, 30))
        end = datetime.combine(day, time(15, 0))
        minutes = merge_minutes(by_day[day], start, end)
        output.append({
            "date": day.isoformat(),
            "raw_interval_rows": len(by_day[day]),
            "school_window_min": minutes,
            "alert_ge_60": int(minutes >= 60),
            "alert_ge_120": int(minutes >= 120),
            "alert_ge_180": int(minutes >= 180),
            "label_status": "manual_transcription_unverified_coverage",
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="kyiv-manual-alerts.csv")
    parser.add_argument("--output", default="kyiv-manual-school-summary.csv")
    args = parser.parse_args()

    with Path(args.input).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("Input contains no alert rows")
    result = summarize(rows)
    with Path(args.output).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    print(json.dumps({
        "input_rows": len(rows),
        "dates_summarized": len(result),
        "output": args.output,
        "school_window": "08:30-15:00 Kyiv local time",
        "warning": "Descriptive manual transcription only; not a completeness-certified feed or forecast.",
        "daily": result,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
