import unittest
from datetime import date, datetime

from summarize_manual_kyiv_alerts import merge_minutes, summarize


def row(day, start, end, level="yellow"):
    return {"date": day, "start_kyiv": start, "end_kyiv": end, "level": level}


class ManualKyivAlertTests(unittest.TestCase):
    def test_school_window_clips_interval(self):
        result = summarize([row("2026-10-24", "14:42", "16:07")])[0]
        self.assertEqual(result["school_window_min"], 18)
        self.assertEqual(result["alert_ge_60"], 0)

    def test_overlapping_intervals_are_not_double_counted(self):
        intervals = [
            (datetime(2026, 10, 22, 8, 51), datetime(2026, 10, 22, 9, 41)),
            (datetime(2026, 10, 22, 9, 20), datetime(2026, 10, 22, 10, 0)),
        ]
        self.assertEqual(
            merge_minutes(intervals, datetime(2026, 10, 22, 8, 30),
                          datetime(2026, 10, 22, 15, 0)),
            69,
        )

    def test_pasted_days_match_manual_calculation(self):
        rows = [
            row("2026-10-22", "08:51", "09:41"),
            row("2026-10-22", "11:22", "11:53"),
            row("2026-10-22", "12:34", "13:40", "red"),
            row("2026-10-23", "08:26", "08:49"),
            row("2026-10-23", "10:12", "10:34"),
            row("2026-10-23", "11:13", "11:55"),
            row("2026-10-23", "14:24", "14:49"),
            row("2026-10-24", "14:42", "16:07"),
        ]
        result = {r["date"]: r for r in summarize(rows)}
        self.assertEqual(result["2026-10-22"]["school_window_min"], 147)
        self.assertEqual(result["2026-10-23"]["school_window_min"], 108)
        self.assertEqual(result["2026-10-24"]["school_window_min"], 18)
        self.assertEqual(result["2026-10-22"]["alert_ge_120"], 1)
        self.assertEqual(result["2026-10-23"]["alert_ge_120"], 0)
        self.assertEqual(result["2026-10-24"]["label_status"],
                         "manual_transcription_unverified_coverage")

    def test_invalid_level_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "level must be"):
            summarize([row("2026-10-24", "14:42", "15:00", "unknown")])


if __name__ == "__main__":
    unittest.main()
