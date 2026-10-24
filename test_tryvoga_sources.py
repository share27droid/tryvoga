import unittest

from audit_tryvoga_sources import audit_rows


def alert(start="2026-10-01 10:00", end="2026-10-01 11:00", duration="60"):
    return {
        "region_id": "kyiv", "start_kyiv": start, "end_kyiv": end,
        "duration_min": duration, "red_level": "0", "red_min": "0",
    }


def daily(date="2026-10-01", region="kyiv"):
    return {
        "date": date, "region_id": region, "alerts": "1", "alerts_red": "0",
        "alerts_yellow": "1", "alert_min": "60", "red_min": "0",
        "drones": "3", "drones_jet": "1", "missiles": "0",
        "missiles_ballistic": "0", "guided_bombs": "0",
    }


def night():
    return {
        "night_of": "2026-10-02", "from": "18:00 01.10", "as_of": "08:30",
        "launched": "12", "launched_at_least": "0", "source_url": "https://example.test/source",
    }


class TryvogaSourceAuditTests(unittest.TestCase):
    def test_open_alert_interval_is_flagged_without_duration_mismatch(self):
        row = alert(end="", duration="120")
        report = audit_rows([row], [daily()], [night()])
        self.assertEqual(report["alerts"]["open_intervals"], 1)
        self.assertEqual(report["alerts"]["closed_interval_duration_mismatches_over_2min"], 0)

    def test_daily_duplicate_keys_and_missing_numeric_cells_are_reported(self):
        row = daily()
        row["drones"] = ""
        report = audit_rows([], [row, daily()], [night()])
        self.assertEqual(report["daily"]["duplicate_date_region_keys"], 1)
        self.assertEqual(report["daily"]["blank_numeric_cells"], 1)

    def test_clock_only_as_of_is_not_publication_timestamp(self):
        report = audit_rows([], [], [night()])
        self.assertFalse(report["nights"]["publication_timestamp_available"])
        self.assertIn("clock time", report["nights"]["publication_time_warning"])

    def test_closed_interval_duration_mismatch_is_flagged(self):
        report = audit_rows([alert(duration="10")], [daily()], [night()])
        self.assertEqual(report["alerts"]["closed_interval_duration_mismatches_over_2min"], 1)


if __name__ == "__main__":
    unittest.main()
