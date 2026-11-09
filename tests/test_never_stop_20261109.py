"""2026-11-09 オーナー「100本/日は必須」「作業止まるみたいなこと多いからなくして」:
1回あたりの本数（遅れたら自動で増やす）・指摘の文を削って門をもう一度・Muse も同じ直し・出典の読み取りの強化・止まりの見張り"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import feeds  # noqa: E402
import muse_articles  # noqa: E402
import pacing  # noqa: E402
import quality  # noqa: E402
import ramp  # noqa: E402
import stall_watch  # noqa: E402

JST = pacing.JST
AUTO_RUN = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")


class PerRunTest(unittest.TestCase):
    def test_base_numbers_for_100(self):
        self.assertEqual(ramp.broad_per_run(100), 4)
        self.assertEqual(ramp.ai_per_run(100), 2)

    def test_boost_only_when_behind(self):
        at = lambda h: datetime(2026, 11, 9, h, 0, tzinfo=JST)  # noqa: E731
        self.assertEqual(pacing.behind_boost(100, 5, 6, at(3)), 0)  # 夜中は増やさない
        self.assertEqual(pacing.behind_boost(100, 23, 6, at(14)), 0)  # 1回6本で間に合う
        self.assertGreater(pacing.behind_boost(100, 60, 6, at(22)), 0)  # 夜の遅れは増やす
        self.assertLessEqual(pacing.behind_boost(100, 0, 6, at(23)), pacing.BOOST_MAX)
        self.assertEqual(pacing.behind_boost(100, 100, 6, at(20)), 0)
        self.assertEqual(pacing.behind_boost(0, 0, 6, at(20)), 0)

    def test_workflow_uses_ramp_ai_number(self):
        self.assertIn("steps.ramp.outputs.ai_per_run", AUTO_RUN)
        self.assertIn("pacing.behind_boost", (ROOT / "scripts" / "web_articles.py").read_text("utf-8"))


def article(**extra):
    record = {
        "title": "楽天ふるさと納税のポイントの使い方", "lede": "ポイントの使い方をまとめます。どちらも有効期限はありませんが、寄付先の自治体の中でしか使えません。",
        "highlights": ["ポイントは寄付に使える", "寄付先の自治体の中でしか使えません"],
        "body": ("## 何が変わる\n\n楽天のポイントは寄付に使えます。どちらも有効期限はありませんが、寄付先の自治体の中でしか使えません。"
                 "手続きは公式ページで確認できます。ポイントの残高は会員ページで見られます。寄付の上限額は年収と家族の数で変わります。\n\n"
                 "| 項目 | 値 |\n|---|---|\n| 単価 | 0kWh×33.40円=10,020円 |\n| 期限 | 12月31日 |\n\n"
                 "- 予約受付専用電話は0570-05-4890（ナビダイヤル）です\n- 公式サイトの案内を見る\n\n"
                 "## まとめ\n\nまずは公式の案内を確認しましょう。寄付の記録は確定申告やワンストップ特例の申請で使います。"),
        "easy": "ポイントは寄付に使えます。", "verdict": {"status": "available"},
    }
    record.update(extra)
    return record


PROBLEMS = [
    "「どちらも有効期限はありませんが、寄付先の自治体の中でしか使えません」→ 元記事に無い",
    "元記事・確認済みの事実の束・計算済みの数字のどれにも無い数字がある（「0kWh×33.40円=10,020円」）",
    "「予約受付専用電話は0570-05-4890（ナビダイヤル）」→ 元記事に無い電話番号",
    "判定欄の「提供状況=available」→ 根拠がない",
]


class StrikeTest(unittest.TestCase):
    def test_strikes_only_flagged_sentences(self):
        fixed, info = quality.strike_flagged(article(), PROBLEMS)
        self.assertIsNotNone(fixed, info)
        self.assertNotIn("有効期限はありません", fixed["body"])
        self.assertNotIn("33.40", fixed["body"])
        self.assertNotIn("0570", fixed["body"])
        self.assertIn("手続きは公式ページで確認できます。", fixed["body"])
        self.assertIn("| 期限 | 12月31日 |", fixed["body"])
        self.assertIn("## まとめ", fixed["body"])
        self.assertEqual(fixed["lede"], "ポイントの使い方をまとめます。")
        self.assertEqual(fixed["highlights"], ["ポイントは寄付に使える"])
        self.assertIsNone(fixed["verdict"])

    def test_never_adds_text(self):
        fixed, _ = quality.strike_flagged(article(), PROBLEMS)
        self.assertLessEqual(len(fixed["body"]), len(article()["body"]))

    def test_title_or_heavy_cut_gives_up(self):
        self.assertIsNone(quality.strike_flagged(article(), ["「楽天ふるさと納税のポイントの使い方」→ 誤り"])[0])
        body_only = article(body="## 何が変わる\n\nどちらも有効期限はありませんが、寄付先の自治体の中でしか使えません。")
        self.assertIsNone(quality.strike_flagged(body_only, PROBLEMS[:1])[0])
        self.assertIsNone(quality.strike_flagged(article(), ["元記事との整合性が低い（score 40）"])[0])

    def test_regate_after_strike(self):
        calls = []

        def fake_eval(record, *_a, **_k):
            calls.append(record)
            return {"ok": True, "soft": False, "score": 92, "problems": []}

        with mock.patch.object(quality, "evaluate", side_effect=fake_eval):
            fixed, verdict = quality.strike_and_regate(article(), "src", "news", PROBLEMS)
        self.assertIsNotNone(fixed)
        self.assertTrue(verdict["fixed_by"].startswith("strike:"))
        self.assertEqual(len(calls), 1)

    def test_surgical_fix_falls_back_to_strike(self):
        ok = {"ok": True, "soft": False, "score": 90, "problems": []}
        with mock.patch.object(quality, "_surgical_once", return_value=(None, "直したあとの確認に不合格")), \
                mock.patch.object(quality, "evaluate", return_value=ok):
            quality._surgical_once.last_verdict = None
            fixed, info = quality.surgical_fix(article(), "src", "news", PROBLEMS)
        self.assertIsNotNone(fixed, info)
        self.assertIn("strike", info["fixed_by"])


class MuseRepairTest(unittest.TestCase):
    def test_muse_uses_the_same_repair_as_news(self):
        src = (ROOT / "scripts" / "muse_articles.py").read_text("utf-8")
        self.assertIn("quality.repairable(verdict)", src)
        self.assertNotIn("quality.surgical_ok(verdict)", src)

    def test_second_source_is_used_when_first_is_blocked(self):
        def fake(url):
            if "blocked" in url:
                raise RuntimeError("本文を取得できません（直接 HTTP 403）")
            return {"text": "公式の案内。" * 80, "title": "公式", "image": "", "published": ""}

        sources = [{"url": "https://blocked.example.jp/a"}, {"url": "https://ok.example.jp/b"}]
        with mock.patch.object(feeds, "fetch_article_text", side_effect=fake):
            got = muse_articles.fetch_sources(sources, skip_unreadable_first=True)
        self.assertEqual([s["url"] for s in got], ["https://ok.example.jp/b"])


class FetchTest(unittest.TestCase):
    def test_legacy_ssl_error_is_detected(self):
        import urllib.error
        error = urllib.error.URLError("[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled")
        self.assertTrue(feeds._is_legacy_ssl_error(error))
        self.assertFalse(feeds._is_legacy_ssl_error(urllib.error.URLError("timed out")))
        self.assertTrue(feeds.legacy_ssl_context().options & 0x4)

    def test_timeout_detection(self):
        self.assertTrue(feeds._is_timeout(TimeoutError("The read operation timed out")))
        self.assertFalse(feeds._is_timeout(ValueError("x")))

    def test_robots_via_reader(self):
        page = b"Title: Access Denied\n\nWarning: Target URL returned error 403: Forbidden\n\nMarkdown Content:\nDenied"
        with mock.patch.object(feeds, "fetch_jina", return_value=(page, "")):
            self.assertIsNone(feeds._robots_via_reader("https://blocked.example.jp"))
        rules = b"Title:\n\nMarkdown Content:\nUser-agent: *\nDisallow: /private/\n"
        with mock.patch.object(feeds, "fetch_jina", return_value=(rules, "")):
            parser = feeds._robots_via_reader("https://x.example.jp")
        self.assertFalse(parser.can_fetch("https://x.example.jp/private/a"))
        self.assertTrue(parser.can_fetch("https://x.example.jp/news/a"))
        with mock.patch.object(feeds, "fetch_jina", side_effect=OSError("down")):
            self.assertFalse(feeds._robots_via_reader("https://y.example.jp").can_fetch("https://y.example.jp/"))


class StallWatchTest(unittest.TestCase):
    def state(self, at):
        return {"processed_web": {"a": {"slug": "x", "at": at}}}

    def test_article_gap(self):
        now = datetime(2026, 11, 9, 14, 0, tzinfo=JST)
        self.assertIsNone(stall_watch.article_alert(self.state("2026-11-09T13:00:00+09:00"), now))
        hit = stall_watch.article_alert(self.state("2026-11-09T12:00:00+09:00"), now)
        self.assertEqual(hit["kind"], "no_article")
        # 夜中は数えない・朝は 6 時から数える
        self.assertIsNone(stall_watch.article_alert(self.state("2026-11-08T22:00:00+09:00"), datetime(2026, 11, 9, 5, 0, tzinfo=JST)))
        self.assertIsNone(stall_watch.article_alert(self.state("2026-11-08T22:00:00+09:00"), datetime(2026, 11, 9, 7, 0, tzinfo=JST)))
        self.assertIsNotNone(stall_watch.article_alert(self.state("2026-11-08T22:00:00+09:00"), datetime(2026, 11, 9, 7, 31, tzinfo=JST)))

    def test_sns_missed_slot(self):
        now = datetime(2026, 11, 9, 14, 0, tzinfo=JST)
        plan = {"date": "2026-11-09", "sns": {
            "x": {"slots": ["12:15", "13:45"], "actual": [{"time": "12:20"}]},
            "threads": {"slots": ["12:15", "13:00"], "actual": [{"time": "11:40"}]},
        }}
        alerts = stall_watch.sns_alerts(plan, now)
        kinds = {a["kind"]: a["message"] for a in alerts}
        self.assertNotIn("sns_missed_x", kinds)  # 13:45 はまだ30分たっていない
        self.assertIn("13:00", kinds["sns_missed_threads"])  # 12:15 は 11:40 の投稿で数える
        self.assertNotIn("12:15", kinds["sns_missed_threads"])
        self.assertEqual(stall_watch.sns_alerts({**plan, "date": "2026-11-08"}, now), [])

    def test_state_file_written_only_on_alert_or_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "stall.json"
            with mock.patch.object(stall_watch, "OUT", out):
                now = datetime(2026, 11, 9, 14, 0, tzinfo=JST)
                self.assertTrue(stall_watch.write_state([], now))  # 初回は書く
                self.assertFalse(stall_watch.write_state([], now))
                self.assertTrue(stall_watch.write_state([{"kind": "no_article", "message": "m"}], now))
                self.assertTrue(stall_watch.write_state([], now))
                data = json.loads(out.read_text("utf-8"))
                self.assertTrue(data["ok"])
                self.assertEqual([row["kinds"] for row in data["log"]], [["no_article"], []])

    def test_workflows_wired(self):
        watch = (ROOT / ".github" / "workflows" / "stall_watch.yml").read_text("utf-8")
        self.assertIn("scripts/stall_watch.py --issue --state", watch)
        self.assertIn("[no-deploy]", watch)
        self.assertIn("scripts/stall_watch.py --issue --skip-tests", AUTO_RUN)


if __name__ == "__main__":
    unittest.main()
