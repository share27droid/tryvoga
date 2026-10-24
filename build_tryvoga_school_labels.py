#!/usr/bin/env python3
"""Build descriptive Kyiv school-window labels from tryvoga-alerts.csv.

This is a retrospective label builder, not a forecast or a live-feed collector.
The caller must explicitly confirm source coverage and provide the real export
snapshot time. Labels are withheld for incomplete windows and windows touched
by an alert interval that was still open (or not yet ended) at that snapshot.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, time, timedelta
from pathlib import Path


def parse_dt(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ValueError(f"Expected local Kyiv time YYYY-MM-DD HH:MM, got {value!r}") from exc


def merge_minutes(intervals: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> int:
    clipped = []
    for left, right in intervals:
        left, right = max(left, start), min(right, end)
        if left < right:
            clipped.append((left, right))
    clipped.sort()
    total = 0
    current_start = current_end = None
    for left, right in clipped:
        if current_start is None:
            current_start, current_end = left, right
        elif left <= current_end:
            current_end = max(current_end, right)
        else:
            total += int((current_end - current_start).total_seconds() // 60)
            current_start, current_end = left, right
    if current_start is not None:
        total += int((current_end - current_start).total_seconds() // 60)
    return total


def build_labels(rows: list[dict[str, str]], start_date: date, end_date: date,
                 snapshot: datetime, assume_source_complete: bool) -> list[dict[str, str]]:
    if not assume_source_complete:
        raise ValueError("Refusing to create labels without --assume-source-complete; verify source coverage first.")
    if end_date < start_date:
        raise ValueError("--end-date must be on or after --start-date")

    intervals: list[tuple[datetime, datetime | None]] = []
    for row in rows:
        if row.get("region_id", "").strip() != "kyiv":
            continue
        start = parse_dt(row.get("start_kyiv", ""))
        end = parse_dt(row.get("end_kyiv", ""))
        if start is None:
            raise ValueError(f"Kyiv row has invalid start_kyiv: {row!r}")
        if end is not None and end < start:
            raise ValueError(f"Kyiv interval ends before it starts: {row!r}")
        intervals.append((start, end))

    output = []
    day = start_date
    while day <= end_date:
        window_start = datetime.combine(day, time(8, 30))
        window_end = datetime.combine(day, time(15, 0))
        relevant: list[tuple[datetime, datetime]] = []
        censored = False
        for start, end in intervals:
            effective_end = end if end is not None else snapshot
            if effective_end <= window_start or start >= window_end:
                continue
            if end is None or end > snapshot:
                censored = True
            relevant.append((start, min(effective_end, snapshot)))
        lower_bound = merge_minutes(relevant, window_start, min(window_end, snapshot))
        complete_window = window_end <= snapshot
        status = "complete" if complete_window and not censored else (
            "incomplete_window" if not complete_window else "censored_open_or_future_interval"
        )
        row_out = {
            "date": day.isoformat(),
            "window_start_kyiv": window_start.strftime("%Y-%m-%d %H:%M"),
            "window_end_kyiv": window_end.strftime("%Y-%m-%d %H:%M"),
            "snapshot_as_of_kyiv": snapshot.strftime("%Y-%m-%d %H:%M"),
            "window_status": status,
            "alert_min_lower_bound": str(lower_bound),
            "p_ge_60_label": "",
            "p_ge_120_label": "",
            "p_ge_180_label": "",
        }
        if status == "complete":
            row_out["p_ge_60_label"] = str(int(lower_bound >= 60))
            row_out["p_ge_120_label"] = str(int(lower_bound >= 120))
            row_out["p_ge_180_label"] = str(int(lower_bound >= 180))
        output.append(row_out)
        day += timedelta(days=1)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="tryvoga-alerts.csv")
    parser.add_argument("--output", default="tryvoga_kyiv_school_labels.csv")
    parser.add_argument("--start-date", required=True, help="First target date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Last target date, YYYY-MM-DD")
    parser.add_argument("--snapshot-as-of", required=True, help="Actual export snapshot in Kyiv local time, YYYY-MM-DD HH:MM")
    parser.add_argument("--assume-source-complete", action="store_true",
                        help="Explicitly confirm alert intervals cover every target window in the selected date range.")
    args = parser.parse_args()
    snapshot = parse_dt(args.snapshot_as_of)
    if snapshot is None:
        parser.error("--snapshot-as-of is required")
    try:
        start_date, end_date = date.fromisoformat(args.start_date), date.fromisoformat(args.end_date)
        with Path(args.input).open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        labels = build_labels(rows, start_date, end_date, snapshot, args.assume_source_complete)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if not labels:
        parser.error("No output rows generated")
    with Path(args.output).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(labels[0]))
        writer.writeheader()
        writer.writerows(labels)
    complete = sum(row["window_status"] == "complete" for row in labels)
    print(f"Wrote {len(labels)} rows to {args.output}; complete labels={complete}; "
          f"censored/incomplete={len(labels)-complete}. This is descriptive QA, not a forecast.")


if __name__ == "__main__":
    main()
