"""速度の分母・日時精度を誤認しない。外部通信・state更新なし。"""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import latency


class LatencyTest(unittest.TestCase):
    now = datetime(2026, 10, 31, 1, tzinfo=timezone.utc)

    def article(self, source="2026-10-30T12:00:00+00:00", **extra):
        return {"slug": "sample", "sourceUrl": "https://example.com/official",
                "sourceType": "web", "sourcePublishedAt": source,
                "publishedAt": "2026-10-30T12:00:00+00:00",
                "detectedAt": "2026-10-30T12:01:00+00:00",
                "generatedAt": "2026-10-30T12:02:00+00:00", **extra}

    def review(self, a, status="verified", **extra):
        return {a["slug"]: {"status": status, "sourceUrl": a["sourceUrl"],
                "articleSourcePublishedAt": a["sourcePublishedAt"],
                "officialPublishedAt": a["sourcePublishedAt"],
                "checkedAt": "2026-10-31T00:00:00+00:00", "precision": "timestamp", **extra}}

    def collect(self, a, reviews=None, live="2026-10-30T12:05:00+00:00"):
        entries = {a["slug"]: {"liveAt": live}} if live else {}
        with patch.object(latency, "articles", return_value=[a]), \
             patch.object(latency, "load_live", return_value={"live": entries}), \
             patch.object(latency, "load_source_reviews", return_value=reviews or {}), \
             patch.object(latency, "POSTED_PATH", Path(__file__).parent / "nonexistent-latency-test.json"):
            return latency.collect(7, self.now)[0]

    def test_missing_source_is_not_replaced_with_published_or_detected_time(self):
        row = self.collect(self.article(None))
        self.assertIsNone(row["publish_to_live"])
        self.assertIsNone(row["recorded_publish_to_live"])
        self.assertEqual(row["detect_to_live"], 4)
        summary = latency.summarize([row])["all"]
        self.assertEqual(summary["coverage"]["liveObserved"], 1)
        self.assertEqual(summary["publish_to_live"]["excluded"], {"missing_source_timestamp": 1})
        self.assertNotIn("within30Pct", summary["publish_to_live"])

    def test_date_only_midnight_naive_and_invalid_source_are_not_precise(self):
        cases = {"2026-10-30": "date_only_or_midnight",
                 "2026-10-30T00:00:00+00:00": "date_only_or_midnight",
                 "2026-10-30T00:00:00+09:00": "date_only_or_midnight",
                 "2026-10-30T12:00:00": "source_timezone_unknown",
                 "not-a-date": "invalid_source_timestamp"}
        for source, reason in cases.items():
            with self.subTest(source=source):
                # 直後の検知があっても、日時精度の根拠にはしない。
                a = self.article(source, detectedAt="2026-10-30T00:01:00+00:00")
                row = self.collect(a)
                self.assertIsNone(row["recorded_publish_to_live"])
                self.assertEqual(row["source_status"], reason)

    def test_negative_interval_is_reported_and_missing_live_is_not_zero(self):
        a = self.article("2026-10-30T12:10:00+00:00")
        row = self.collect(a, self.review(a))
        self.assertIsNone(row["publish_to_live"])
        self.assertEqual(row["metric_exclusions"]["publish_to_live"], "negative_interval")
        missing = self.collect(a, self.review(a), live=None)
        self.assertEqual(missing["metric_exclusions"]["publish_to_live"], "missing_end")
        self.assertIsNone(missing["detect_to_live"])

    def test_long_lag_is_kept_instead_of_excluding_slow_articles(self):
        a = self.article("2026-10-21T12:05:00+00:00")
        row = self.collect(a, self.review(a))
        self.assertEqual(row["publish_to_live"], 9 * 24 * 60)
        s = latency.summarize([row])["all"]["publish_to_live"]
        self.assertEqual(s["n"], 1)
        self.assertEqual(s["within30Count"], 0)
        self.assertEqual(s["excluded"], {})

    def test_unverified_conflict_and_stale_review_do_not_become_verified(self):
        a = self.article()
        raw = self.collect(a)
        self.assertEqual(raw["recorded_publish_to_live"], 5)
        self.assertIsNone(raw["publish_to_live"])
        confirmed = self.collect(a, self.review(a))
        self.assertEqual(confirmed["publish_to_live"], 5)
        conflict = self.collect(a, self.review(a, status="conflict"))
        self.assertIsNone(conflict["recorded_publish_to_live"])
        self.assertEqual(conflict["source_status"], "source_timestamp_conflict")
        for field, wrong in [("articleSourcePublishedAt", "2026-10-29T12:00:00+00:00"),
                             ("sourceUrl", "https://example.com/other"),
                             ("officialPublishedAt", "2026-10-29T12:00:00+00:00")]:
            with self.subTest(field=field):
                stale = self.collect(a, self.review(a, **{field: wrong}))
                self.assertIsNone(stale["publish_to_live"])

    def test_percentile_and_rate_use_valid_measurements_not_article_count(self):
        rows = []
        for minutes in [1, 2, 3, 4, 5, 6, 7, 8, 90, 100]:
            a = self.article()
            live = (datetime.fromisoformat(a["sourcePublishedAt"]) + timedelta(minutes=minutes)).isoformat()
            rows.append(self.collect(a, self.review(a), live))
        rows.append(self.collect(self.article(None)))
        s = latency.summarize(rows)["all"]["publish_to_live"]
        self.assertEqual(s["n"], 10)
        self.assertEqual(s["p90"], 90)
        self.assertEqual(s["within30Count"], 8)
        self.assertEqual(s["within30Pct"], 80)


if __name__ == "__main__":
    unittest.main()
