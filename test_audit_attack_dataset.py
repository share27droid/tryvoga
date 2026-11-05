import unittest

from audit_attack_dataset import audit_rows


HEADERS = [
    "time_start", "time_end", "model", "source", "launched", "destroyed",
    "not_reach_goal", "still_attacking", "num_hit_location", "num_fall_fragment_location",
]


class AttackDatasetAuditTests(unittest.TestCase):
    def test_flags_absent_publication_timestamp_and_non_url_post_refs(self):
        rows = [
            {
                "time_start": "2026-10-23 18:00", "time_end": "2026-10-24 08:00",
                "model": "Shahed", "source": "kpszsu/posts/pfbid123",
                "launched": "126", "destroyed": "101", "not_reach_goal": "",
                "still_attacking": "8", "num_hit_location": "14", "num_fall_fragment_location": "5",
            },
            {
                "time_start": "2026-10-23", "time_end": "2026-10-23",
                "model": "Unknown UAV", "source": "kpszsu/posts/pfbid123",
                "launched": "0", "destroyed": "0", "not_reach_goal": "",
                "still_attacking": "", "num_hit_location": "", "num_fall_fragment_location": "",
            },
        ]
        report = audit_rows(rows, HEADERS)
        self.assertEqual(report["rows"], 2)
        self.assertFalse(report["publication_timestamps_available_in_schema"])
        self.assertEqual(report["forecast_eligibility"]["rows_eligible_from_this_file_alone"], 0)
        self.assertEqual(report["source_reference"]["absolute_http_urls"], 0)
        self.assertEqual(report["source_reference"]["post_id_like_paths_containing_pfbid"], 2)
        self.assertEqual(report["numeric_fields"]["launched"]["zero"], 1)
        self.assertEqual(report["numeric_fields"]["not_reach_goal"]["blank"], 2)

    def test_detects_publication_column_and_bad_rows(self):
        headers = HEADERS + ["published_at"]
        rows = [{
            "time_start": "not-a-date", "time_end": "", "model": "x",
            "source": "https://example.org/post/1", "published_at": "",
        }]
        report = audit_rows(rows, headers)
        self.assertTrue(report["publication_timestamps_available_in_schema"])
        self.assertEqual(report["invalid_or_blank_event_start"], 1)
        self.assertEqual(report["invalid_or_blank_event_end"], 1)
        self.assertEqual(report["source_reference"]["absolute_http_urls"], 1)

    def test_requires_source_and_event_columns(self):
        with self.assertRaises(ValueError):
            audit_rows([{"model": "x"}], ["model"])


if __name__ == "__main__":
    unittest.main()
