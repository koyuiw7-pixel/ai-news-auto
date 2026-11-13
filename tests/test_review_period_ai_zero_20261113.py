"""2026-11-13: AdSense の審査の期間（scripts/ramp.py ADSENSE_REVIEW）に、速報でない海外の AI の記事が夜のあいだに3本出ていた。

- claude-meetings-google-meet-beta: リリースノートの見張り（page_watch）の候補は「大きなニュース」の流れに乗り、通常のレーンの門を通らなかった
- gemini-4-hydrogen-developers: 速報にならない大きなニュース（同じ流れ）
- openai-daybreak-gpt6-cyber-launch: 動画の経路（scripts/main.py）は審査の期間の門を通っていなかった

どの自動の経路も news_mix.review_ai_blocks の1つの門を通す。速報は止めない（台帳 S41）。Muse の経路には入れない。
"""
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import main as m  # noqa: E402
import news_mix  # noqa: E402
import roundup  # noqa: E402
import web_articles as w  # noqa: E402
from channels import CHANNELS  # noqa: E402

IN, OUT = "2026-11-13", "2026-11-27"
WATCH = {"title": "Claude: Claude Meetings is rolling out in beta on Team and Enterprise plans", "lang": "en", "watch": True,
         "source_slug": "claude-apps-release-notes", "published_at": datetime.now(timezone.utc) - timedelta(hours=1)}


class SharedGateTest(unittest.TestCase):
    def test_foreign_ai_blocked_in_review(self):
        self.assertTrue(news_mix.review_ai_blocks({"section": "ai", "lang": "en"}, today=IN))
        self.assertTrue(news_mix.review_ai_blocks({"genreSlug": "ai", "channelSlug": "openai"}, today=IN))

    def test_breaking_never_blocked(self):
        self.assertFalse(news_mix.review_ai_blocks({"section": "ai", "lang": "en"}, breaking=True, today=IN))

    def test_japanese_and_other_sections_pass(self):
        self.assertFalse(news_mix.review_ai_blocks({"section": "ai", "lang": "ja"}, today=IN))
        self.assertFalse(news_mix.review_ai_blocks({"section": "lifestyle", "lang": "en"}, today=IN))

    def test_after_review_passes(self):
        self.assertFalse(news_mix.review_ai_blocks({"section": "ai", "lang": "en"}, today=OUT))


class WebMajorLaneTest(unittest.TestCase):
    """大きなニュースの流れ（リリースノートの見張り・発表から時間のたった発表）"""

    def test_watch_item_is_not_breaking_and_blocked(self):
        self.assertEqual(w.major_lane(WATCH), "ai")
        self.assertFalse(w.breaking_candidate(WATCH))
        self.assertTrue(news_mix.review_ai_blocks({**WATCH, "section": w.major_lane(WATCH)}, breaking=w.breaking_candidate(WATCH), today=IN))

    def test_fast_lane_item_stays_exempt(self):
        fast = {"title": "Introducing Gemini 4 Hydrogen", "lang": "en", "fast": True, "source_slug": "google-deepmind-blog",
                "published_at": datetime.now(timezone.utc) - timedelta(hours=30)}
        self.assertTrue(w.breaking_candidate(fast))
        self.assertFalse(news_mix.review_ai_blocks({**fast, "section": "ai"}, breaking=w.breaking_candidate(fast), today=IN))

    def test_fresh_breaking_major_stays_exempt(self):
        item = {"title": "x", "lang": "en", "source_slug": "openai-news", "published_at": datetime.now(timezone.utc) - timedelta(hours=2)}
        with mock.patch.object(w, "is_breaking", lambda i: True):
            self.assertTrue(w.breaking_candidate(item))
            old = {**item, "published_at": datetime.now(timezone.utc) - timedelta(hours=20)}
            self.assertFalse(w.breaking_candidate(old))
        self.assertTrue(news_mix.review_ai_blocks({**old, "section": "ai"}, breaking=False, today=IN))

    def test_japanese_public_interest_major_passes(self):
        item = {"title": "リコールのお知らせ", "source_slug": "not-an-ai-feed", "lang": "ja", "section": "lifestyle",
                "published_at": datetime.now(timezone.utc) - timedelta(hours=20)}
        self.assertEqual(w.major_lane(item), "lifestyle")
        self.assertFalse(news_mix.review_ai_blocks({**item, "section": w.major_lane(item)}, breaking=False, today=IN))

    def test_every_web_lane_calls_the_gate(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text(encoding="utf-8")
        pick = src[src.index("    def _pick(cand"):]
        pick = pick[: pick.index("\n    def ", 10)]
        # 大きなニュース: 門が「if not major:」より前（major でも通る）。見送りの印を付けて見張りの候補を残さない
        head = pick[: pick.index("if not major:")]
        self.assertIn("news_mix.review_ai_blocks({**cand, \"section\": major_lane(cand)}, breaking=breaking_candidate(cand))", head)
        self.assertIn("mark(state, cand, skipped=True", head)
        # 通常の AI のレーン（上限の変数の渡し忘れに頼らない）と話題のレーン
        self.assertIn('if is_ai and news_mix.review_ai_blocks({**cand, "section": "ai"})', pick)
        # 話題のレーン（急上昇の言葉。2026-11-13 オーナー「注目する話題がとれていない」）は速報と同じ扱いで、この門の外:
        # _pick は trend のとき、種類別の上限・審査の期間の門を通さない（事件・ゴシップ・選挙・お知らせの転載だけ見送る）
        self.assertLess(pick.index("if trend:"), pick.index("elif not major:"))
        trend_block = pick[pick.index("if trend:"):pick.index("elif not major:")]
        self.assertIn("trend_prefilter(cand)", trend_block)
        self.assertNotIn("review_ai_blocks(", trend_block)
        trend = src[src.index("        for q in queue:"):src.index("        # 公式フィード（AI）と幅広い話題を、レーンごとに1本ずつ交互に処理する")]
        self.assertNotIn("news_mix.review_ai_blocks(", trend)
        # 記事に速報の印を付ける判定と、作る前の見立ては同じ関数
        self.assertIn("if major and breaking_record(item):", src)


class VideoPathTest(unittest.TestCase):
    """動画の経路（scripts/main.py。auto_run.yml の6時間ごとの回）"""

    def entries(self, channel):
        now = datetime.now(timezone.utc)
        return [{"video_id": "YmxpxJZvm4M", "title": "Cyber at the Frontier", "published": (now - timedelta(hours=3)).isoformat(),
                 "summary": "OpenAI Daybreak and GPT-6 Cyber", "channel": channel}]

    def collect(self, day_in_review: bool):
        channel = next(c for c in CHANNELS if c.slug == "openai")
        with mock.patch.object(m, "parse_feed", lambda c: self.entries(c)), mock.patch.object(m, "is_off_topic", lambda *a: False), \
                mock.patch("ramp.in_adsense_review", lambda today: day_in_review), mock.patch.object(m, "log", lambda *a: None):
            return m.collect_candidates([channel], 10, {"processed": {}, "failed": {}})

    def test_foreign_ai_video_skipped_in_review(self):
        self.assertEqual(self.collect(True), [])

    def test_video_kept_after_review(self):
        self.assertEqual([e["video_id"] for e in self.collect(False)], ["YmxpxJZvm4M"])

    def test_all_active_ai_channels_are_gated(self):
        with mock.patch("ramp.in_adsense_review", lambda today: True):
            for channel in CHANNELS:
                if channel.active and channel.genre.slug == "ai":
                    self.assertTrue(m.review_skips({"channel": channel}), channel.slug)

    def test_non_ai_channel_not_gated(self):
        channel = SimpleNamespace(slug="some-money-channel", genre=SimpleNamespace(slug="investment"))
        with mock.patch("ramp.in_adsense_review", lambda today: True):
            self.assertFalse(m.review_skips({"channel": channel}))


class RoundupPathTest(unittest.TestCase):
    def test_foreign_ai_roundup_skipped_only_in_review(self):
        cluster = SimpleNamespace(key="GPT-6", slugs=["a", "b"], genre_slug="ai")
        by_slug = {"a": {"slug": "a", "genreSlug": "ai", "channelSlug": "openai"}, "b": {"slug": "b", "genreSlug": "ai", "channelSlug": "openai"}}
        with mock.patch("ramp.in_adsense_review", lambda today: True):
            self.assertTrue(roundup.review_skips(cluster, by_slug))
            life = {s: {**a, "genreSlug": "lifestyle"} for s, a in by_slug.items()}
            self.assertFalse(roundup.review_skips(SimpleNamespace(key="x", slugs=["a", "b"], genre_slug="lifestyle"), life))
        with mock.patch("ramp.in_adsense_review", lambda today: False):
            self.assertFalse(roundup.review_skips(cluster, by_slug))


class MuseUntouchedTest(unittest.TestCase):
    def test_muse_pipeline_does_not_call_the_gate(self):
        self.assertNotIn("review_ai_blocks", (ROOT / "scripts" / "muse_articles.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
