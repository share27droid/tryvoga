#!/usr/bin/env python3
"""Resolve exact publication timestamps from Telegram post URLs in an attack CSV.

Only a row whose source_url identifies one specific public Telegram post can be
enriched. The event timestamp is never substituted for publication time. Rows
without a resolvable exact post URL remain ineligible for as-of forecasting.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


POST_URL = re.compile(r"^https?://(?:www\\.)?t\\.me/(?:s/)?([A-Za-z0-9_]+)/([0-9]+)(?:[/?#].*)?$", re.I)


def telegram_post_ref(value: str) -> tuple[str, str] | None:
    match = POST_URL.match((value or "").strip())
    if not match:
        return None
    channel, message_id = match.group(1), match.group(2)
    if channel.lower() == "c":
        return None
    return channel, message_id


def parse_exact_post_timestamp(html: str, channel: str, message_id: str) -> str | None:
    target = f"{channel}/{message_id}"
    markers = list(re.finditer(r"data-post=[\\\"']([^\\\"']+)[\\\"']", html))
    for index, marker in enumerate(markers):
        if unescape(marker.group(1)) != target:
            continue
        end = markers[index + 1].start() if index + 1 < len(markers) else len(html)
        section = html[marker.start():end]
        times = re.findall(r"<time\\b[^>]*\\bdatetime=[\\\"']([^\\\"']+)[\\\"']", section, flags=re.I)
        for raw in times:
            try:
                parsed = datetime.fromisoformat(unescape(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is not None:
                return parsed.isoformat()
    return None


def fetch_html(channel: str, message_id: str, timeout: float = 20.0) -> str:
    request = Request(f"https://t.me/s/{channel}/{message_id}", headers={"User-Agent": "tryvoga-research/1.0 (public-source timestamp audit)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def enrich_rows(rows: list[dict[str, str]], delay_seconds: float = 1.0,
                overwrite_existing: bool = False, fetcher=fetch_html) -> tuple[list[dict[str, str]], dict]:
    if delay_seconds < 0:
        raise ValueError("delay_seconds must be >= 0")
    qa = {"rows_in_input": len(rows), "resolved_from_telegram": 0,
          "kept_existing_publication_timestamp": 0, "skipped_no_exact_telegram_post_url": 0,
          "unresolved_post_timestamp": 0, "fetch_errors": 0, "errors": []}
    output = []
    for row in rows:
        updated = dict(row)
        existing = (row.get("published_at") or "").strip()
        if existing and not overwrite_existing:
            try:
                parsed = datetime.fromisoformat(existing.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
            if parsed is not None and parsed.tzinfo is not None:
                updated["publication_time_status"] = updated.get("publication_time_status") or "existing_timezone_aware"
                updated["usable_for_asof_forecast"] = "true"
                qa["kept_existing_publication_timestamp"] += 1
                output.append(updated)
                continue
        ref = telegram_post_ref(row.get("source_url", ""))
        if ref is None:
            updated["publication_time_status"] = "unavailable_no_exact_telegram_post_url"
            updated["usable_for_asof_forecast"] = "false"
            qa["skipped_no_exact_telegram_post_url"] += 1
            output.append(updated)
            continue
        channel, message_id = ref
        try:
            published_at = parse_exact_post_timestamp(fetcher(channel, message_id), channel, message_id)
            if published_at is None:
                updated["publication_time_status"] = "unresolved_exact_post_timestamp"
                updated["usable_for_asof_forecast"] = "false"
                qa["unresolved_post_timestamp"] += 1
            else:
                updated["published_at"] = published_at
                updated["publication_time_status"] = "telegram_exact_post_timestamp"
                updated["usable_for_asof_forecast"] = "true"
                qa["resolved_from_telegram"] += 1
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeError) as exc:
            updated["publication_time_status"] = "telegram_fetch_error"
            updated["usable_for_asof_forecast"] = "false"
            qa["fetch_errors"] += 1
            qa["errors"].append({"source_url": row.get("source_url", ""), "error": str(exc)})
        output.append(updated)
        if delay_seconds:
            time.sleep(delay_seconds)
    qa["rows_eligible_by_timestamp_flag"] = sum((row.get("usable_for_asof_forecast") or "").lower() == "true" for row in output)
    qa["caveat"] = "A timestamp is resolved only when the exact Telegram post URL matches a post block with a timezone-aware datetime. This verifies post publication time, not that every numeric value in a mutable retrospective CSV is an exact transcription of that post; review the post text and metric definitions before using values in a backtest."
    return output, qa


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="attack_observations_normalized.csv")
    parser.add_argument("--output", default="attack_observations_with_publication_times.csv")
    parser.add_argument("--qa", default="attack_publication_time_qa.json")
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--overwrite-existing", action="store_true")
    args = parser.parse_args()
    with Path(args.input).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows, fields = list(reader), list(reader.fieldnames or [])
    for field in ("source_url", "published_at", "publication_time_status", "usable_for_asof_forecast"):
        if field not in fields:
            fields.append(field)
    enriched, qa = enrich_rows(rows, args.delay_seconds, args.overwrite_existing)
    with Path(args.output).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched)
    Path(args.qa).write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
