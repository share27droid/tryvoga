#!/usr/bin/env python3
"""Normalize the public PiterFM attack CSV without inventing publication times.

The source CSV is a retrospective event/report table. Unless a separate, auditable
publication timestamp is supplied, normalized rows are deliberately marked
unavailable for as-of forecasting. This prevents hindsight leakage.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ALIASES = {
    "time_start": ("time_start", "start_time", "start"),
    "time_end": ("time_end", "end_time", "end"),
    "model": ("model", "weapon_model", "weapon_type"),
    "launch_place": ("launch_place", "launch_location"),
    "target": ("target", "target_region"),
    "carrier": ("carrier", "target_main", "platform"),
    "launched": ("launched", "launches", "launched_count"),
    "destroyed": ("destroyed", "intercepted", "destroyed_count"),
    "not_reach_goal": ("not_reach_goal", "missed", "not_reached_goal"),
    "still_attacking": ("still_attacking", "ongoing"),
    "source": ("source", "source_url", "reference"),
    "published_at": ("published_at", "publication_time", "published"),
}

OUTPUT_FIELDS = [
    "observation_id", "event_start_raw", "event_end_raw", "event_start_iso",
    "event_end_iso", "model", "launch_place", "target", "carrier",
    "launched", "destroyed", "not_reach_goal", "still_attacking",
    "source_name", "source_url", "published_at", "publication_time_status",
    "usable_for_asof_forecast", "definition_note",
]


def parse_datetime(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    # Preserve timezone offsets if supplied; never assume a timezone silently.
    candidates = [value, value.replace("Z", "+00:00")]
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate).isoformat()
        except ValueError:
            pass
    return ""


def number_or_blank(value: str) -> str:
    value = (value or "").strip().replace(",", "")
    if not value:
        return ""
    try:
        number = float(value)
    except ValueError:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def choose(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    by_lower = {h.strip().lower(): h for h in headers}
    return next((by_lower[a] for a in aliases if a in by_lower), None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source CSV path")
    parser.add_argument("--output", default="attack_observations_normalized.csv")
    parser.add_argument("--qa", default="attack_observations_qa.json")
    parser.add_argument("--source-name", default="PiterFM Massive Missile Attacks on Ukraine")
    parser.add_argument("--source-url", default="https://www.kaggle.com/datasets/piterfm/massive-missile-attacks-on-ukraine/data")
    parser.add_argument(
        "--publication-time-column",
        default="",
        help="Explicit column name that records when each observation became public; do not use event time as a substitute.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        columns = {key: choose(headers, aliases) for key, aliases in ALIASES.items()}
        if not columns["time_start"] or not columns["model"]:
            raise SystemExit(
                "Required source columns not found. Need at least time_start and model; "
                f"found headers: {headers}"
            )
        if args.publication_time_column:
            if args.publication_time_column not in headers:
                raise SystemExit(f"Publication-time column not found: {args.publication_time_column}")
            columns["published_at"] = args.publication_time_column

        rows: list[dict[str, Any]] = []
        missing_start = missing_model = missing_publication = invalid_start = 0
        parsed_publication = 0
        for index, source_row in enumerate(reader, start=2):
            get = lambda key: (source_row.get(columns[key], "") or "").strip() if columns[key] else ""
            raw_start, raw_end = get("time_start"), get("time_end")
            start_iso, end_iso = parse_datetime(raw_start), parse_datetime(raw_end)
            model = get("model")
            publication_raw = get("published_at")
            publication_iso = parse_datetime(publication_raw)
            if not raw_start:
                missing_start += 1
            if not model:
                missing_model += 1
            if raw_start and not start_iso:
                invalid_start += 1
            if not publication_raw or not publication_iso:
                missing_publication += 1
            else:
                parsed_publication += 1

            source_url = get("source") or args.source_url
            rows.append({
                "observation_id": f"piterfm-row-{index}",
                "event_start_raw": raw_start,
                "event_end_raw": raw_end,
                "event_start_iso": start_iso,
                "event_end_iso": end_iso,
                "model": model,
                "launch_place": get("launch_place"),
                "target": get("target"),
                "carrier": get("carrier"),
                "launched": number_or_blank(get("launched")),
                "destroyed": number_or_blank(get("destroyed")),
                "not_reach_goal": number_or_blank(get("not_reach_goal")),
                "still_attacking": number_or_blank(get("still_attacking")),
                "source_name": args.source_name,
                "source_url": source_url,
                "published_at": publication_iso,
                "publication_time_status": "observed" if publication_iso else "unavailable",
                "usable_for_asof_forecast": "true" if publication_iso else "false",
                "definition_note": (
                    "Retrospective source row; verify reporting interval, metric definitions, "
                    "and publication timestamp before forecasting. Blank counts are unknown, not zero."
                ),
            })

    with Path(args.output).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    qa = {
        "input_file": str(input_path),
        "source_name": args.source_name,
        "source_url": args.source_url,
        "rows": len(rows),
        "source_headers": headers,
        "mapped_columns": columns,
        "missing_event_start_rows": missing_start,
        "invalid_event_start_rows": invalid_start,
        "missing_model_rows": missing_model,
        "rows_with_parseable_publication_timestamp": parsed_publication,
        "rows_without_parseable_publication_timestamp": missing_publication,
        "rows_eligible_for_asof_forecast": parsed_publication,
        "warnings": [
            "Event time is not publication time; never substitute event_start for published_at.",
            "A row is not leakage-safe merely because a publication timestamp exists; confirm it refers to that exact value/version.",
            "Blank numeric values remain blank and must not be interpreted as zero.",
            "Do not merge different source definitions (launched, detected, intercepted, impacts) into a single count.",
        ],
    }
    Path(args.qa).write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
