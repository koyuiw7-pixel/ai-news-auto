"""threads_learn.fetch_metrics の問い合わせ（2026-11-05: startDate だけの絞り込みで Buffer が0件を返し、反応の取得が11/4から止まった）"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import threads_learn  # noqa: E402

ORGS = [{"id": "org", "channels": [{"id": "th", "service": "threads"}, {"id": "x", "service": "twitter"}, {"id": "fb", "service": "facebook"}]}]


def node(i: str, sent: datetime) -> dict:
    return {"node": {"id": i, "sentAt": sent.isoformat().replace("+00:00", "Z"), "externalLink": "", "metricsUpdatedAt": None,
                     "metrics": [{"type": "views", "value": 10}], "metadata": {"threadCount": 2}}}


class FetchMetricsTest(unittest.TestCase):
    def run_fetch(self, pages):
        queries = []

        def gql(_key, query, *a, **k):
            queries.append(query)
            edges, more = pages[len(queries) - 1]
            return {"posts": {"edges": edges, "pageInfo": {"endCursor": f"c{len(queries)}", "hasNextPage": more}}}

        with patch.object(threads_learn, "buffer_account", return_value=ORGS), patch.object(threads_learn, "buffer_graphql", side_effect=gql):
            return threads_learn.fetch_metrics("k"), queries

    def test_no_start_date_filter_and_newest_first(self):
        now = datetime.now(timezone.utc)
        result, queries = self.run_fetch([([node("a", now - timedelta(hours=5))], False)])
        self.assertEqual(result["a"]["metrics"], {"views": 10})
        self.assertEqual(result["a"]["ownReplies"], 1)
        q = queries[0]
        self.assertNotIn("startDate", q)  # sent + startDate だけ → Buffer は0件
        self.assertIn("status: [sent]", q)
        self.assertIn("sort: [{ field: createdAt, direction: desc }]", q)
        self.assertIn('"th"', q)
        self.assertIn('"x"', q)
        self.assertNotIn('"fb"', q)

    def test_stops_when_page_is_older_than_window(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=threads_learn.METRICS_DAYS + 2)
        pages = [([node("a", now - timedelta(days=1))], True), ([node("b", old)], True), ([node("c", old)], True)]
        result, queries = self.run_fetch(pages)
        self.assertEqual(len(queries), 2)
        self.assertEqual(set(result), {"a", "b"})

    def test_page_cap(self):
        now = datetime.now(timezone.utc)
        pages = [([node(f"p{i}", now)], True) for i in range(threads_learn.METRICS_MAX_PAGES + 3)]
        _, queries = self.run_fetch(pages)
        self.assertEqual(len(queries), threads_learn.METRICS_MAX_PAGES)

    def test_recent_sent_posts_ignores_scheduled(self):
        now = datetime.now(timezone.utc)
        state = {"posted": {
            "a": {"id": "1", "postedAt": (now - timedelta(days=1)).isoformat()},
            "b": {"id": "2", "status": "scheduled", "dueAt": (now + timedelta(hours=2)).isoformat()},
            "c": {"id": "3", "postedAt": (now - timedelta(days=30)).isoformat()},
        }}
        self.assertEqual(threads_learn.recent_sent_posts(state, now), 1)


if __name__ == "__main__":
    unittest.main()
