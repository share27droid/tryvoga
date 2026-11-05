#!/usr/bin/env python3
"""Build leakage-aware national attack features available by a daily forecast cutoff.

Input must be the output of import_attack_observations.py. This script never
uses event rows published after the target cutoff. It deliberately emits blanks
for numeric sums when no eligible rows contain a numeric value; a blank is not
a zero. A current retrospective CSV is not sufficient for a valid as-of test
unless each value's publication/version history is trustworthy.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
COUNT_FIELDS = ("launched", "destroyed", "not_reach_goal", "still_attacking")
HORIZONS = (1, 3, 7)


def parse_timestamp(value: str, naive_timezone: ZoneInfo | None = None) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        if naive_timezone is None:
            return None
        result = result.replace(tzinfo=naive_timezone)
    return result.astimezone(KYIV)


def parse_number(value: str) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        result = float(str(value).replace(",", "").strip())
    except ValueError:
        return None
    return result


def fmt_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="attack_observations_normalized.csv")
    parser.add_argument("--output", default="attack_asof_daily_features.csv")
    parser.add_argument("--qa", default="attack_asof_daily_features_qa.json")
    parser.add_argument("--start-date", default="", help="First target date YYYY-MM-DD; defaults to earliest event date")
    parser.add_argument("--end-date", default="", help="Last target date YYYY-MM-DD; defaults to latest event date")
    parser.add_argument("--cutoff", default="08:30", help="Kyiv local forecast cutoff, HH:MM (default 08:30)")
    parser.add_argument(
        "--naive-event-timezone",
        default="",
        help="Explicit timezone for event_start_iso values without an offset, e.g. Europe/Kyiv. Naive published_at is always rejected.",
    )
    args = parser.parse_args()

    try:
        cutoff_time = time.fromisoformat(args.cutoff)
    except ValueError as exc:
        raise SystemExit(f"Invalid --cutoff {args.cutoff!r}; expected HH:MM") from exc
    if cutoff_time.tzinfo is not None:
        raise SystemExit("--cutoff must be a local wall-clock time without a timezone offset")

    naive_event_tz = ZoneInfo(args.naive_event_timezone) if args.naive_event_timezone else None
    input_path = Path(args.input)
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"event_start_iso", "published_at", "usable_for_asof_forecast", *COUNT_FIELDS}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise SystemExit(f"Input is missing required columns: {missing}")
        rows = list(reader)

    usable = []
    rejected = defaultdict(int)
    for row in rows:
        if (row.get("usable_for_asof_forecast") or "").lower() != "true":
            rejected["flagged_not_usable"] += 1
            continue
        event_dt = parse_timestamp(row.get("event_start_iso", ""), naive_event_tz)
        published_dt = parse_timestamp(row.get("published_at", ""), None)
        if event_dt is None:
            rejected["invalid_or_timezone_ambiguous_event_time"] += 1
            continue
        if published_dt is None:
            rejected["missing_or_timezone_ambiguous_publication_time"] += 1
            continue
        if published_dt < event_dt - timedelta(days=7):
            # Unusual but not impossible; retain the row but surface it in QA.
            rejected["published_more_than_7d_before_event"] += 1
        row["_event_dt"] = event_dt
        row["_published_dt"] = published_dt
        usable.append(row)

    event_dates = [r["_event_dt"].date() for r in usable]
    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
    elif event_dates:
        start_date = min(event_dates)
    else:
        start_date = None
    if args.end_date:
        end_date = date.fromisoformat(args.end_date)
    elif event_dates:
        end_date = max(event_dates)
    else:
        end_date = None

    output_rows = []
    if start_date and end_date:
        if end_date < start_date:
            raise SystemExit("--end-date must be on or after --start-date")
        target = start_date
        while target <= end_date:
            cutoff_dt = datetime.combine(target, cutoff_time, tzinfo=KYIV)
            out = {"date": target.isoformat(), "cutoff_kyiv": cutoff_dt.isoformat()}
            for horizon in HORIZONS:
                lower_bound = cutoff_dt - timedelta(days=horizon)
                eligible = [
                    row for row in usable
                    if lower_bound <= row["_event_dt"] < cutoff_dt
                    and row["_published_dt"] <= cutoff_dt
                ]
                out[f"observations_known_{horizon}d"] = str(len(eligible))
                for field in COUNT_FIELDS:
                    values = [parse_number(row.get(field, "")) for row in eligible]
                    known = [v for v in values if v is not None]
                    out[f"{field}_known_rows_{horizon}d"] = str(len(known))
                    out[f"{field}_missing_rows_{horizon}d"] = str(len(values) - len(known))
                    out[f"{field}_sum_{horizon}d"] = fmt_number(sum(known)) if known else ""
                out[f"distinct_models_{horizon}d"] = str(len({
                    (row.get("model") or "").strip() for row in eligible
                    if (row.get("model") or "").strip()
                }))
            output_rows.append(out)
            target += timedelta(days=1)

    fields = ["date", "cutoff_kyiv"]
    for horizon in HORIZONS:
        fields.append(f"observations_known_{horizon}d")
        for field in COUNT_FIELDS:
            fields.extend([
                f"{field}_known_rows_{horizon}d",
                f"{field}_missing_rows_{horizon}d",
                f"{field}_sum_{horizon}d",
            ])
        fields.append(f"distinct_models_{horizon}d")

    with Path(args.output).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    qa = {
        "input_file": str(input_path),
        "output_file": args.output,
        "rows_in_input": len(rows),
        "rows_usable_after_timestamp_checks": len(usable),
        "target_days_written": len(output_rows),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "cutoff_kyiv": args.cutoff,
        "naive_event_timezone_assumption": args.naive_event_timezone or None,
        "rejected_or_flagged_rows": dict(rejected),
        "warnings": [
            "This builder does not prove that a publication timestamp belongs to the exact value/version in a mutable retrospective dataset.",
            "Rows published after the target cutoff are excluded, even if their event time is earlier.",
            "A zero observations count means no eligible rows were present in this input, not that no attacks occurred.",
            "Blank numeric sums mean no eligible numeric values were reported; they are not zero.",
            "These generic row sums are exploratory features, not deduplicated counts of unique weapons or attacks.",
        ],
    }
    Path(args.qa).write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
