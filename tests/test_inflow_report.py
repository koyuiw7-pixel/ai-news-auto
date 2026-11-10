"""scripts/inflow_report.py の表示と Threads 投稿との突き合わせ（通信しない）。python3 -m unittest tests/test_inflow_report.py"""
import contextlib
import io
import sys
import unittest
import unittest.mock
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import inflow_report as r  # noqa: E402

DATA = {
    "date": "2026-11-03", "views": 9, "visitors": 8,
    "bySource": [{"source": "threads", "views": 6, "visitors": 5}, {"source": "google", "views": 2, "visitors": 2}, {"source": "direct", "views": 1, "visitors": 1}],
    "rows": [
        {"page": "a-article", "source": "threads", "campaign": "classic", "content": "", "views": 3, "visitors": 3},
        {"page": "a-article", "source": "threads", "campaign": "", "content": "", "views": 1, "visitors": 1},
        {"page": "a-article", "source": "threads", "campaign": "sns_video", "content": "short", "views": 2, "visitors": 1},
        {"page": "old-article", "source": "google", "campaign": "", "content": "", "views": 2, "visitors": 2},
        {"page": "_home", "source": "direct", "campaign": "", "content": "", "views": 1, "visitors": 1},
    ],
}
POSTED = {
    "a-article": {"postedAt": "2026-11-02T23:10:00+00:00", "format": "classic", "metrics": {"views": 200}},
    "yesterday-no-visits": {"postedAt": "2026-11-01T23:10:00+00:00", "format": "classic"},
    "tomorrow": {"postedAt": "2026-11-04T01:00:00+00:00"},
}
VIDEOS = {"a-article": {"status": "posted", "variant": "short", "postedAt": "2026-11-03T03:00:00+00:00"}}


class InflowReportTest(unittest.TestCase):
    def test_threads_posts_join(self):
        posts = r.threads_posts(DATA, POSTED, VIDEOS)
        self.assertEqual([(p["slug"], p["kind"], p["visits"], p["utm"]) for p in posts], [
            ("a-article", "classic", 4, 3),
            ("a-article", "動画・短い版", 2, 2),
        ])

    def test_show_is_plain_japanese(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            r.show(DATA, POSTED, VIDEOS)
        text = out.getvalue()
        self.assertIn("外から来た人: 9回（推定 8人）", text)
        self.assertIn("Threads 6（5人）", text)
        self.assertIn("SNS 合計: 6回", text)
        self.assertIn("訪問 4（うち投稿のリンク 3・参照元だけ 1） / 表示 200 → 2.0%", text)
        self.assertIn("動画投稿から: 短い版 2回 / 全部の版 0回", text)
        self.assertIn("トップページ", text)
        self.assertLess(len(text.splitlines()), 25)

    def test_empty_day(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            r.show({"date": "2026-11-01", "views": 0, "visitors": 0, "bySource": [], "rows": []}, {}, {})
        self.assertIn("まだ記録がありません", out.getvalue())

    def test_uses_send_time_not_booking_time(self):
        """予約投稿の postedAt は予約した時刻。実際に出た時刻（sentAt / dueAt）で並べ、まだ出ていない予約は訪問0に入れない"""
        now = datetime(2026, 11, 3, 19, 0, tzinfo=r.JST)
        posted = {
            "sent": {"postedAt": "2026-11-03T00:26:57+00:00", "dueAt": "2026-11-03T06:30:00+00:00", "sentAt": "2026-11-03T06:30:05Z", "format": "classic"},
            "due-past": {"postedAt": "2026-11-03T02:06:29+00:00", "dueAt": "2026-11-03T09:30:00+00:00", "format": "classic"},
            "due-future": {"postedAt": "2026-11-03T04:17:29+00:00", "dueAt": "2026-11-03T12:00:00+00:00", "format": "classic"},
            "early": {"postedAt": "2026-11-02T15:11:47+00:00", "dueAt": "2026-11-02T15:11:47+00:00", "format": "classic"},
        }
        data = {"date": "2026-11-03", "views": 0, "visitors": 0, "bySource": [], "rows": []}
        posts = {p["slug"]: p for p in r.threads_posts(data, posted, {}, now=now)}
        self.assertEqual(f"{posts['sent']['at']:%H:%M}", "15:30")
        self.assertEqual(f"{posts['due-past']['at']:%H:%M}", "18:30")
        self.assertFalse(posts["due-past"]["pending"])
        self.assertTrue(posts["due-future"]["pending"])
        self.assertTrue(posts["early"]["before_start"])
        self.assertFalse(posts["sent"]["before_start"])

    def test_pending_and_pre_counter_posts_are_labelled(self):
        posted = {
            "early": {"dueAt": "2026-11-02T21:00:00+00:00", "format": "classic"},
            "future": {"dueAt": "2099-01-01T00:00:00+00:00", "format": "classic"},
        }
        data = {"date": "2026-11-03", "views": 1, "visitors": 1, "bySource": [{"source": "google", "views": 1, "visitors": 1}],
                "rows": [{"page": "x", "source": "google", "campaign": "", "content": "", "views": 1, "visitors": 1}]}
        posted["future"]["dueAt"] = "2026-11-03T14:59:00+00:00"
        out = io.StringIO()
        with contextlib.redirect_stdout(out), unittest.mock.patch.object(r, "datetime", wraps=datetime) as fake:
            fake.now.return_value = datetime(2026, 11, 3, 19, 0, tzinfo=r.JST)
            r.show(data, posted, {})
        text = out.getvalue()
        self.assertIn("訪問0: 1本（※06:00 classic）", text)
        self.assertIn("より前に出た投稿", text)
        self.assertIn("まだ出ていない予約: 1本（23:59 classic", text)

    def test_ai_answers_line(self):
        """AI の回答から来た数を1行で（内訳つき）。AI Overviews と参照元の無いアプリの扱いも書く（LLMO-A1）"""
        data = {"date": "2026-11-11", "views": 6, "visitors": 6, "bySource": [
            {"source": "google", "views": 2, "visitors": 2}, {"source": "chatgpt", "views": 2, "visitors": 2},
            {"source": "perplexity", "views": 1, "visitors": 1}, {"source": "meta_ai", "views": 1, "visitors": 1}],
            "rows": [
                {"page": "tools--furusato-limit", "source": "chatgpt", "campaign": "", "content": "", "views": 2, "visitors": 2},
                {"page": "guides--chatgpt-work", "source": "perplexity", "campaign": "", "content": "", "views": 1, "visitors": 1},
                {"page": "x", "source": "meta_ai", "campaign": "", "content": "", "views": 1, "visitors": 1},
                {"page": "x", "source": "google", "campaign": "", "content": "", "views": 2, "visitors": 2}]}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            r.show(data, {}, {})
        text = out.getvalue()
        self.assertIn("AIの回答から: 4回（ChatGPT 2・Perplexity 1・Meta AI 1）", text)
        self.assertIn("AI による概要からのクリックは Google検索", text)
        self.assertIn("直接・不明", text)
        self.assertIn("ChatGPT: 「計算ツール: ふるさと納税", text)
        self.assertNotIn("｜", text)
        self.assertNotIn("ざっくり", text)

    def test_ai_answers_zero(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            r.show(DATA, POSTED, VIDEOS)
        self.assertIn("AIの回答から: 0回（", out.getvalue())

    def test_title_of_landing_pages(self):
        self.assertTrue(r.title_of("tools--furusato-limit", 80).startswith("計算ツール: ふるさと納税の上限額"))
        self.assertTrue(r.title_of("guides--chatgpt-work", 80).startswith("ガイド: ChatGPT Work"))
        self.assertEqual(r.title_of("products--amazon-bedrock", 80), "製品: Amazon Bedrock")
        self.assertEqual(r.title_of("events--github-universe-2026", 80), "イベント: GitHub Universe 2026")
        self.assertEqual(r.title_of("guides--no-such-guide", 80), "ガイド: no-such-guide")
        self.assertLessEqual(len(r.title_of("tools--furusato-limit")), 26)
        self.assertEqual(r.title_of("_home"), "トップページ")

    def test_no_article_slug_has_double_hyphen(self):
        """記事の slug に "--" が無いので、guides--<slug> などの名前と重ならない"""
        articles = Path(r.ROOT) / "content" / "articles"
        self.assertEqual([p.name for p in articles.glob("*--*.json")], [])
        self.assertEqual(set(r.AI_SOURCES) <= set(r.LABELS), True)


if __name__ == "__main__":
    unittest.main()
