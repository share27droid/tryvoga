import json
import tempfile
import unittest
from pathlib import Path

from audit_school_daily import audit


class SchoolDailyAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "airAlert.json"
        self.daily = self.root / "daily.csv"
        self.source.write_text(json.dumps([
            {"dateTimeStart": "2026-10-01T08:30:00", "dateTimeEnd": "2026-10-01T09:15:00"},
            {"dateTimeStart": "2026-10-01T09:00:00", "dateTimeEnd": "2026-10-01T10:00:00"},
        ]), encoding="utf-8")
        self.daily.write_text(
            "date,school_window_min,any_school_alert,alert_ge_60,alert_ge_120,alert_ge_180\n"
            "2026-10-01,90.00,1,1,0,0\n", encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_overlaps_recomputed_and_labels_validated(self):
        result = audit(self.source, self.daily)
        self.assertEqual(result["structural_status"], "PASS")
        self.assertEqual(result["source_vs_daily_minute_mismatches"], [])
        self.assertEqual(result["label_or_range_invariant_errors"], [])

    def test_minute_mismatch_fails(self):
        self.daily.write_text(
            "date,school_window_min,any_school_alert,alert_ge_60,alert_ge_120,alert_ge_180\n"
            "2026-10-01,45.00,1,0,0,0\n", encoding="utf-8"
        )
        result = audit(self.source, self.daily)
        self.assertEqual(result["structural_status"], "FAIL")
        self.assertTrue(result["source_vs_daily_minute_mismatches"])

    def test_long_zero_streak_is_warning_not_proof_of_missing_data(self):
        self.source.write_text(json.dumps([
            {"dateTimeStart": "2026-10-01T08:30:00", "dateTimeEnd": "2026-10-01T09:00:00"},
            {"dateTimeStart": "2026-10-10T20:00:00", "dateTimeEnd": "2026-10-10T20:30:00"},
        ]), encoding="utf-8")
        result = audit(self.source, self.daily, zero_streak_warning_days=7)
        self.assertTrue(result["long_zero_school_window_streaks"])
        self.assertIn("not proof", result["interpretation"])


if __name__ == "__main__":
    unittest.main()
