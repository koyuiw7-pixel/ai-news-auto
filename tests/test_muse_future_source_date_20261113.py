"""Muse の記事: 出典の日付が今より先なら、発表の時刻として使わない（2026-11-13）。
映画の公式サイトのお知らせで公開初日（12月4日）を発表の日として読み、記事の sourcePublishedAt・publishedAt が 12/3 になっていた。"""

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import muse_articles  # noqa: E402

NOW = datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc)


class SourcePublished(unittest.TestCase):
    def test_future_date_is_clamped_to_now_and_logged(self):
        with mock.patch.object(muse_articles, "log") as log:
            at, guessed = muse_articles.source_published("2026-12-03T15:00:00+00:00", now=NOW, url="https://example.jp/news.html")
        self.assertEqual(NOW, at)
        self.assertTrue(guessed, "先の日付は発表の時刻として記録しない")
        self.assertEqual(1, log.call_count)
        self.assertIn("今より先", log.call_args[0][0])
        self.assertIn("https://example.jp/news.html", log.call_args[0][0])

    def test_past_and_today_are_kept(self):
        with mock.patch.object(muse_articles, "log") as log:
            at, guessed = muse_articles.source_published("2026-11-12T15:00:00+00:00", now=NOW)
            self.assertEqual((datetime(2026, 11, 12, 15, tzinfo=timezone.utc), False), (at, guessed))
            # 時刻の無い日付は日本時間として読む
            at, guessed = muse_articles.source_published("2026-11-13T00:00:00", now=NOW)
            self.assertEqual(datetime(2026, 11, 12, 15, tzinfo=timezone.utc), at)
            self.assertFalse(guessed)
            # 時計のずれ（10分まで）は先の日付にしない
            at, guessed = muse_articles.source_published((NOW + timedelta(minutes=5)).isoformat(), now=NOW)
            self.assertFalse(guessed)
            at, guessed = muse_articles.source_published(datetime(2026, 11, 13, 7, tzinfo=timezone.utc), now=NOW)
            self.assertEqual((datetime(2026, 11, 13, 7, tzinfo=timezone.utc), False), (at, guessed))
        self.assertEqual(0, log.call_count)

    def test_missing_or_unreadable_is_guessed_now(self):
        for value in (None, "", "12月4日", 0):
            self.assertEqual((NOW, True), muse_articles.source_published(value, now=NOW), value)

    def test_build_article_uses_it(self):
        src = (ROOT / "scripts" / "muse_articles.py").read_text("utf-8")
        self.assertIn('published, guessed = source_published(first.get("published"), url=first.get("url") or "")', src)


class NoFutureDates(unittest.TestCase):
    def test_vivant_source_date_is_the_announcement_day(self):
        a = json.loads((ROOT / "content" / "articles" / "vivant-movie-extra-tickets-nov15.json").read_text("utf-8"))
        # 公式サイトの NEWS の日付は 2026/11/13（日付だけ → 日本時間0時）
        self.assertEqual("2026-11-12T15:00:00+00:00", a["sourcePublishedAt"])
        self.assertEqual("2026-11-12T15:00:00+00:00", a["publishedAt"])

    def test_no_article_has_a_source_date_after_it_was_posted(self):
        """発表の時刻（sourcePublishedAt）が、サイソクに載せた時刻より1日を超えて先の記事は無い"""
        def parse(value):
            try:
                d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

        bad = []
        for path in sorted((ROOT / "content" / "articles").glob("*.json")):
            a = json.loads(path.read_text("utf-8"))
            src, born = parse(a.get("sourcePublishedAt") or ""), parse(a.get("generatedAt") or "")
            if src and born and src - born > timedelta(days=1):
                bad.append(path.stem)
        self.assertEqual([], bad)


if __name__ == "__main__":
    unittest.main()
