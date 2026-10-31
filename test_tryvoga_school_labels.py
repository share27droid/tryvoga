import unittest
from datetime import date, datetime

from build_tryvoga_school_labels import build_labels, merge_minutes


def alert(start, end, region="kyiv"):
    return {"region_id": region, "start_kyiv": start, "end_kyiv": end}


class SchoolLabelTests(unittest.TestCase):
    def test_overlapping_intervals_are_merged(self):
        intervals = [
            (datetime(2026, 10, 1, 8, 30), datetime(2026, 10, 1, 9, 30)),
            (datetime(2026, 10, 1, 9, 0), datetime(2026, 10, 1, 10, 0)),
        ]
        self.assertEqual(merge_minutes(intervals, datetime(2026, 10, 1, 8, 30),
                                       datetime(2026, 10, 1, 15, 0)), 90)

    def test_threshold_labels_for_complete_window(self):
        rows = [alert("2026-10-01 08:30", "2026-10-01 10:30")]
        result = build_labels(rows, date(2026, 10, 1), date(2026, 10, 1),
                              datetime(2026, 10, 2, 0, 0), True)[0]
        self.assertEqual(result["window_status"], "complete")
        self.assertEqual(result["alert_min_lower_bound"], "120")
        self.assertEqual(result["p_ge_60_label"], "1")
        self.assertEqual(result["p_ge_120_label"], "1")
        self.assertEqual(result["p_ge_180_label"], "0")

    def test_open_interval_censors_label(self):
        rows = [alert("2026-10-01 14:00", "")]
        result = build_labels(rows, date(2026, 10, 1), date(2026, 10, 1),
                              datetime(2026, 10, 1, 14, 30), True)[0]
        self.assertEqual(result["window_status"], "incomplete_window")
        self.assertEqual(result["p_ge_60_label"], "")

    def test_non_kyiv_intervals_do_not_change_kyiv_label(self):
        rows = [alert("2026-10-01 08:30", "2026-10-01 11:30", region="odesa")]
        result = build_labels(rows, date(2026, 10, 1), date(2026, 10, 1),
                              datetime(2026, 10, 2, 0, 0), True)[0]
        self.assertEqual(result["alert_min_lower_bound"], "0")

    def test_requires_explicit_source_coverage_confirmation(self):
        with self.assertRaisesRegex(ValueError, "without --assume-source-complete"):
            build_labels([], date(2026, 10, 1), date(2026, 10, 1),
                         datetime(2026, 10, 2, 0, 0), False)


if __name__ == "__main__":
    unittest.main()
