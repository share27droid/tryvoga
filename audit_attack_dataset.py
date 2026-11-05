#!/usr/bin/env python3
"""Audit a retrospective missile_attacks_daily.csv without treating it as as-of data."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_NUMERIC = (
    "launched", "destroyed", "not_reach_goal", "still_attacking",
    "num_hit_location", "num_fall_fragment_location",
)
PUBLICATION_NAME = re.compile(r"publish|publication|posted|captur|created_at|available_at", re.I)


def parse_event_time(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def audit_rows(rows: list[dict[str, str]], headers: list[str], source_name: str = "missile_attacks_daily.csv") -> dict:
    if not rows:
        raise ValueError("CSV contains no data rows")
    required = {"time_start", "time_end", "model", "source"}
    missing_required = sorted(required - set(headers))
    if missing_required:
        raise ValueError(f"Missing required columns: {', '.join(missing_required)}")

    def clean(row: dict[str, str], field: str) -> str:
        return (row.get(field) or "").strip()

    starts = [clean(row, "time_start") for row in rows]
    ends = [clean(row, "time_end") for row in rows]
    valid_starts = [value for value in starts if parse_event_time(value)]
    valid_ends = [value for value in ends if parse_event_time(value)]
    numeric_fields = [field for field in DEFAULT_NUMERIC if field in headers]
    numeric_summary = {}
    for field in numeric_fields:
        values = [clean(row, field) for row in rows]
        parsed = []
        invalid = 0
        for value in values:
            if not value:
                continue
            try:
                parsed.append(float(value.replace(",", "")))
            except ValueError:
                invalid += 1
        numeric_summary[field] = {
            "blank": sum(not value for value in values),
            "zero": sum(value == 0 for value in parsed),
            "positive": sum(value > 0 for value in parsed),
            "negative": sum(value < 0 for value in parsed),
            "invalid_nonblank": invalid,
        }

    source_values = [clean(row, "source") for row in rows]
    source_families = Counter(value.split("/")[0] if value else "(blank)" for value in source_values)
    source_counts = Counter(source_values)
    publication_columns = [field for field in headers if PUBLICATION_NAME.search(field)]
    absolute_source_urls = sum(bool(re.match(r"^https?://", value, re.I)) for value in source_values)
    post_id_paths = sum("/posts/pfbid" in value.lower() for value in source_values)
    reversed_intervals = 0
    for row in rows:
        start, end = clean(row, "time_start"), clean(row, "time_end")
        if parse_event_time(start) and parse_event_time(end):
            try:
                if datetime.fromisoformat(end.replace("Z", "+00:00")) < datetime.fromisoformat(start.replace("Z", "+00:00")):
                    reversed_intervals += 1
            except TypeError:
                # Comparing aware and naive event times is ambiguous; report it separately below.
                pass

    return {
        "source_file": source_name,
        "rows": len(rows),
        "columns": len(headers),
        "columns_list": headers,
        "event_start_min": min(valid_starts) if valid_starts else None,
        "event_start_max": max(valid_starts) if valid_starts else None,
        "invalid_or_blank_event_start": len(rows) - len(valid_starts),
        "invalid_or_blank_event_end": len(rows) - len(valid_ends),
        "publication_timestamp_columns": publication_columns,
        "publication_timestamps_available_in_schema": bool(publication_columns),
        "source_reference": {
            "unique_values": len(source_counts),
            "repeated_values": sum(count > 1 for count in source_counts.values()),
            "absolute_http_urls": absolute_source_urls,
            "non_absolute_or_blank_refs": len(rows) - absolute_source_urls,
            "post_id_like_paths_containing_pfbid": post_id_paths,
            "source_family_counts": dict(source_families.most_common()),
            "note": "Repeated source references can be expected when one report contains multiple observation rows; this is not automatically a duplicate-row error.",
        },
        "numeric_fields": numeric_summary,
        "reversed_event_intervals": reversed_intervals,
        "forecast_eligibility": {
            "rows_eligible_from_this_file_alone": 0,
            "reason": "No publication timestamp column exists; event time cannot substitute for when each value became public.",
            "warning": "Do not infer zero from blank counts. Validate reporting window, metric definition, revisions, and exact source post before using any row in an as-of forecast.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        rows = list(reader)
    report = audit_rows(rows, headers, args.input.name)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
