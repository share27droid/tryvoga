#!/usr/bin/env python3
"""Regression tests for the attack-data import and as-of feature pipeline.

Run from the repository root with:
    python -m unittest -v test_attack_pipeline.py

Tests use only the Python standard library and tiny synthetic CSV fixtures.
They do not validate the provenance of any real-world source timestamps.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMPORTER = ROOT / "import_attack_observations.py"
BUILDER = ROOT / "build_attack_asof_features.py"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class AttackPipelineTests(unittest.TestCase):
    def test_importer_requires_explicit_timezone_aware_publication_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tempdir = Path(temp)
            source = tempdir / "source.csv"
            normalized = tempdir / "normalized.csv"
            qa_path = tempdir / "qa.json"
            write_csv(source, ["time_start", "model", "launched", "published_at"], [
                {"time_start": "2026-10-09 22:00:00", "model": "Shahed", "launched": "12",
                 "published_at": "2026-10-10T07:00:00+03:00"},
                {"time_start": "2026-10-09 23:00:00", "model": "Missile", "launched": "",
                 "published_at": "2026-10-10T07:00:00"},
                {"time_start": "2026-10-10 00:00:00", "model": "Drone", "launched": "4",
                 "published_at": ""},
            ])
            subprocess.run([
                sys.executable, str(IMPORTER), "--input", str(source),
                "--output", str(normalized), "--qa", str(qa_path),
            ], check=True, capture_output=True, text=True)
            rows = read_csv(normalized)
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            self.assertEqual([r["usable_for_asof_forecast"] for r in rows],
                             ["true", "false", "false"])
            self.assertEqual(rows[0]["launched"], "12")
            self.assertEqual(rows[1]["launched"], "")
            self.assertEqual(qa["rows_eligible_for_asof_forecast"], 1)
            self.assertEqual(qa["rows_with_timezone_ambiguous_publication_timestamp"], 1)

    def test_asof_builder_excludes_future_publications_and_keeps_unknown_sums_blank(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tempdir = Path(temp)
            source = tempdir / "normalized.csv"
            output = tempdir / "features.csv"
            qa_path = tempdir / "qa.json"
            fields = [
                "observation_id", "event_start_iso", "published_at",
                "usable_for_asof_forecast", "model", "launched", "destroyed",
                "not_reach_goal", "still_attacking",
            ]
            write_csv(source, fields, [
                # Known before the cutoff; launched value is known.
                {"observation_id": "known", "event_start_iso": "2026-10-09T20:00:00+03:00",
                 "published_at": "2026-10-10T07:00:00+03:00", "usable_for_asof_forecast": "true",
                 "model": "Shahed", "launched": "10", "destroyed": "", "not_reach_goal": "",
                 "still_attacking": ""},
                # Event occurred before cutoff but was published after it: must not leak.
                {"observation_id": "future", "event_start_iso": "2026-10-09T21:00:00+03:00",
                 "published_at": "2026-10-10T09:00:00+03:00", "usable_for_asof_forecast": "true",
                 "model": "Missile", "launched": "99", "destroyed": "5", "not_reach_goal": "",
                 "still_attacking": ""},
                # Explicitly marked unusable and has no valid publication timestamp.
                {"observation_id": "unknown", "event_start_iso": "2026-10-09T22:00:00+03:00",
                 "published_at": "", "usable_for_asof_forecast": "false",
                 "model": "Drone", "launched": "500", "destroyed": "", "not_reach_goal": "",
                 "still_attacking": ""},
            ])
            subprocess.run([
                sys.executable, str(BUILDER), "--input", str(source),
                "--output", str(output), "--qa", str(qa_path),
                "--start-date", "2026-10-10", "--end-date", "2026-10-10",
            ], check=True, capture_output=True, text=True)
            rows = read_csv(output)
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["observations_known_1d"], "1")
            self.assertEqual(row["launched_sum_1d"], "10")
            self.assertEqual(row["launched_known_rows_1d"], "1")
            self.assertEqual(row["launched_missing_rows_1d"], "0")
            self.assertEqual(row["destroyed_sum_1d"], "")
            self.assertEqual(row["destroyed_known_rows_1d"], "0")
            self.assertEqual(row["destroyed_missing_rows_1d"], "1")
            self.assertEqual(qa["rows_usable_after_timestamp_checks"], 2)
            self.assertEqual(qa["rejected_or_flagged_rows"]["flagged_not_usable"], 1)

    def test_builder_rejects_naive_publication_time_even_if_flag_is_true(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tempdir = Path(temp)
            source = tempdir / "normalized.csv"
            output = tempdir / "features.csv"
            qa_path = tempdir / "qa.json"
            fields = [
                "event_start_iso", "published_at", "usable_for_asof_forecast", "model",
                "launched", "destroyed", "not_reach_goal", "still_attacking",
            ]
            write_csv(source, fields, [{
                "event_start_iso": "2026-10-09T20:00:00+03:00",
                "published_at": "2026-10-10T07:00:00", "usable_for_asof_forecast": "true",
                "model": "Shahed", "launched": "10", "destroyed": "", "not_reach_goal": "",
                "still_attacking": "",
            }])
            subprocess.run([
                sys.executable, str(BUILDER), "--input", str(source),
                "--output", str(output), "--qa", str(qa_path),
                "--start-date", "2026-10-10", "--end-date", "2026-10-10",
            ], check=True, capture_output=True, text=True)
            rows = read_csv(output)
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            self.assertEqual(rows[0]["observations_known_1d"], "0")
            self.assertEqual(rows[0]["launched_sum_1d"], "")
            self.assertEqual(
                qa["rejected_or_flagged_rows"]["missing_or_timezone_ambiguous_publication_time"], 1
            )


if __name__ == "__main__":
    unittest.main()
