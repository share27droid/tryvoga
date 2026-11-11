import unittest

from enrich_attack_publication_times import enrich_rows, parse_exact_post_timestamp, telegram_post_ref


class PublicationTimeEnrichmentTests(unittest.TestCase):
    def test_recognizes_exact_public_telegram_post_urls(self):
        self.assertEqual(telegram_post_ref("https://t.me/kpszsu/82298"), ("kpszsu", "82298"))
        self.assertEqual(telegram_post_ref("https://t.me/s/kpszsu/82298?single"), ("kpszsu", "82298"))
        self.assertIsNone(telegram_post_ref("https://www.kaggle.com/datasets/piterfm/example"))
        self.assertIsNone(telegram_post_ref("https://t.me/c/12345/678"))

    def test_extracts_timestamp_only_from_matching_post_block(self):
        html = '''
        <div data-post="kpszsu/100"><time datetime="2026-10-01T01:00:00+03:00"></time></div>
        <div data-post="kpszsu/101"><time datetime="2026-10-01T02:00:00+03:00"></time></div>
        '''
        self.assertEqual(parse_exact_post_timestamp(html, "kpszsu", "101"), "2026-10-01T02:00:00+03:00")
        self.assertIsNone(parse_exact_post_timestamp(html, "kpszsu", "102"))

    def test_enriches_exact_source_and_leaves_generic_source_unusable(self):
        rows = [
            {"source_url": "https://t.me/kpszsu/101", "published_at": "", "usable_for_asof_forecast": "false"},
            {"source_url": "https://www.kaggle.com/datasets/piterfm/example", "published_at": "", "usable_for_asof_forecast": "false"},
        ]

        def fake_fetch(channel, message_id):
            return '<div data-post="kpszsu/101"><time datetime="2026-10-01T02:00:00+03:00"></time></div>'

        output, qa = enrich_rows(rows, delay_seconds=0, fetcher=fake_fetch)
        self.assertEqual(output[0]["published_at"], "2026-10-01T02:00:00+03:00")
        self.assertEqual(output[0]["usable_for_asof_forecast"], "true")
        self.assertEqual(output[1]["usable_for_asof_forecast"], "false")
        self.assertEqual(qa["resolved_from_telegram"], 1)
        self.assertEqual(qa["skipped_no_exact_telegram_post_url"], 1)

    def test_keeps_existing_timezone_aware_timestamp(self):
        rows = [{
            "source_url": "https://t.me/kpszsu/101",
            "published_at": "2026-10-01T02:00:00+03:00",
            "usable_for_asof_forecast": "true",
        }]

        def fail_if_called(channel, message_id):
            raise AssertionError("must not fetch when existing timestamp is valid")

        output, qa = enrich_rows(rows, delay_seconds=0, fetcher=fail_if_called)
        self.assertEqual(output[0]["published_at"], rows[0]["published_at"])
        self.assertEqual(qa["kept_existing_publication_timestamp"], 1)


if __name__ == "__main__":
    unittest.main()
