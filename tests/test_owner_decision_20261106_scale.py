"""2026-11-06 オーナー決定（台帳 A47）: 記事を1日100本へ。増やす分は検索される話題（使い方・料金・いつから・比較・手続き・対策）と
国内のニュース。海外 AI は増やさない。品質の門はそのまま。月の Claude API の予算 $95 は変えない。"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import llm  # noqa: E402
import news_mix  # noqa: E402
import public_interest  # noqa: E402
import ramp  # noqa: E402
import web_articles as w  # noqa: E402

JST = timezone(timedelta(hours=9))
AUTO_RUN = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
EVERGREEN = (ROOT / ".github" / "workflows" / "evergreen.yml").read_text("utf-8")


class DailyTargetTest(unittest.TestCase):
    def test_ramp_reaches_100_from_nov_6_and_never_more(self):
        self.assertEqual(ramp.OWNER_DAILY_TARGET, 100)
        self.assertEqual(ramp.pick(ramp.WEB_RAMP, "2026-11-05"), 95)
        self.assertEqual(ramp.review_cap(ramp.pick(ramp.WEB_RAMP, "2026-11-06"), "2026-11-06"), 100)
        # 2026-11-09 オーナー「目標を妨げるルールは消そう」: 100本は最低ライン、上限は 200
        # 2026-11-12〜11-26 は AdSense の審査の期間で30本（tests/test_adsense_review_20261112.py）。その前後は200本
        for day in ("2026-11-09", "2026-11-27", "2026-12-31"):
            cap = ramp.review_cap(ramp.pick(ramp.WEB_RAMP, day), day)
            self.assertEqual(cap, ramp.WEB_CEILING, day)
            self.assertGreaterEqual(cap, 100, day)

    def test_per_run_counts_make_100_reachable(self):
        # 実際に回るのは日中1時間に3回ほど（約54回）。2026-11-09 オーナー「100本/日は必須」: 国内のレーンを1回4本・AI を1回2本にする
        self.assertEqual(ramp.broad_per_run(100), 4)
        self.assertEqual(ramp.ai_per_run(100), 2)
        self.assertLessEqual(ramp.broad_per_run(45), 1)
        self.assertEqual(ramp.ai_per_run(60), 1)
        self.assertGreaterEqual(50 * 0.7 * (ramp.broad_per_run(100) + ramp.ai_per_run(100)), 100)

    def test_main_writes_100_without_the_old_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "github_output"
            # 2026-11-08 台帳 A58: 100本は段（WEB_STAGE_TARGET）を100まで上げたとき。既定の段は60（tests/test_volume_stage_20261108.py）
            env = {"GITHUB_OUTPUT": str(out), "WEB_DAILY_CAP": "80", "WEB_STAGE_TARGET": "100"}
            with mock.patch.dict(os.environ, env, clear=False):
                os.environ.pop("WEB_DAILY_CAP_OVERRIDE", None)
                os.environ.pop("BROAD_MAX_PER_RUN_OVERRIDE", None)
                with mock.patch.object(ramp, "datetime") as dt:
                    dt.now.return_value = datetime(2026, 11, 7, 12, tzinfo=JST)
                    ramp.main()
            text = out.read_text("utf-8")
            self.assertIn("web_daily_cap=100", text)
            self.assertIn("broad_per_run=4", text)
            self.assertIn("ai_per_run=2", text)

    def test_workflow_reads_only_the_brake_variable(self):
        self.assertIn("WEB_DAILY_CAP_OVERRIDE: ${{ vars.WEB_DAILY_CAP_BRAKE }}", AUTO_RUN)
        self.assertNotIn("vars.WEB_DAILY_CAP }}", AUTO_RUN)
        # AI のレーンの1回あたりは ramp.py が決める（変数 WEB_MAX_PER_RUN があればそちら。海外の AI は1日の上限で止まる）
        self.assertIn("--max \"${{ vars.WEB_MAX_PER_RUN || steps.ramp.outputs.ai_per_run || '1' }}\"", AUTO_RUN)


class SearchIntentGuidesTest(unittest.TestCase):
    def test_evergreen_runs_more_often_with_a_higher_cap(self):
        self.assertIn('cron: "41 */2 * * *"', EVERGREEN)
        self.assertIn("EVERGREEN_DAILY_CAP: ${{ vars.EVERGREEN_DAILY_CAP_BRAKE || '40' }}", EVERGREEN)  # A58 で 16→20、11/9 オーナーで 40
        self.assertNotIn("vars.EVERGREEN_DAILY_CAP ||", EVERGREEN)
        self.assertIn("--max \"${{ inputs.max || '4' }}\"", EVERGREEN)

    def test_evergreen_is_written_by_claude_not_demoted_to_free(self):
        self.assertIn("LLM_DEFAULT_PURPOSE: core", EVERGREEN)
        self.assertEqual(llm.API_TIERS["core"][1], 1, "中心の段は予算が苦しくても Haiku より下げない")

    def test_quality_gate_of_guides_is_unchanged(self):
        import evergreen

        self.assertGreaterEqual(evergreen.MIN_PROSE, 1800)
        self.assertGreaterEqual(evergreen.PASS_SCORE, 75)
        self.assertIn("python -m unittest discover -s tests -p test_evergreen_editorial.py", EVERGREEN)


class MixTest(unittest.TestCase):
    def test_foreign_ai_is_capped_at_todays_level(self):
        self.assertGreaterEqual(w.FOREIGN_AI_DAILY_CAP, 1000)  # 2026-11-09 オーナー: 上限なし
        self.assertTrue(w.is_foreign_ai({"source_slug": "openai-news", "lang": "en"}))
        self.assertFalse(w.is_foreign_ai({"source_slug": "google-japan-blog", "lang": "ja"}))
        self.assertFalse(w.is_foreign_ai({"source_slug": "ntt-news-ai"}), "フィードの言語で判定（NTT は日本語）")

    def test_foreign_ai_today_counts_flags_and_old_records(self):
        now = datetime(2026, 11, 6, 20, tzinfo=JST)
        at = now.astimezone(timezone.utc).isoformat()
        state = {"processed_web": {
            "a": {"at": at, "slug": "a", "section": "ai", "foreignAi": True, "url": "https://openai.com/x"},
            "b": {"at": at, "slug": "b", "section": "ai", "url": "https://blog.google/technology/ai/x"},  # 印の無い古い記録
            "c": {"at": at, "slug": "c", "section": "ai", "url": "https://group.ntt/jp/newsrelease/x"},  # 国内
            "d": {"at": at, "slug": "d", "section": "ai", "major": True, "foreignAi": True, "url": "https://openai.com/y"},  # 大きなニュースは外
            "e": {"at": at, "slug": "e", "section": "business", "url": "https://www.toyota.co.jp/x"},
            "f": {"at": at, "skipped": True, "section": "ai", "url": "https://openai.com/z"},
            "g": {"at": (now - timedelta(days=1)).astimezone(timezone.utc).isoformat(), "slug": "g", "section": "ai", "foreignAi": True, "url": "https://openai.com/w"},
        }}
        self.assertEqual(w.foreign_ai_today(state, now), 2)

    def test_pipeline_enforces_the_foreign_cap_and_records_it(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("is_ai and is_foreign_ai(cand) and foreign_left[0] <= 0", src)
        self.assertIn('{"foreignAi": True}', src)

    def test_enterprise_cap_stays_two_with_a_larger_daily_basis(self):
        self.assertEqual(news_mix.CONFIG["daily_basis"], 100)
        self.assertEqual(news_mix.cap_of("enterprise_dev"), 2)
        self.assertEqual(news_mix.cap_of("enterprise_dev", basis=300), 2)
        self.assertIsNone(news_mix.cap_of("money"))

    def test_domestic_public_interest_news_has_no_daily_cap(self):
        """2026-11-08 の台帳の見直し（オーナー承認）: 公共性の高いニュースの1日12本の上限（旧 A40）は外した（0＝上限なし）"""
        self.assertEqual(json.loads((ROOT / "scripts" / "public_interest_rules.json").read_text("utf-8"))["daily_cap"], 0)
        if not os.environ.get("PUBLIC_INTEREST_DAILY_CAP"):
            self.assertEqual(public_interest.DAILY_CAP, 0)
            self.assertEqual(public_interest.left_today({}), public_interest.UNLIMITED)

    def test_search_demand_candidates_go_first(self):
        signals = [{"title": "遺族年金", "traffic": 5000}]
        hit = {"title": "遺族年金の調査票について", "source_slug": "x"}
        miss = {"title": "A社が新しい取り組みを紹介", "source_slug": "x"}
        self.assertEqual(w.demand_rank(hit, signals), 0)
        self.assertEqual(hit["_trend_hit"], "遺族年金")
        self.assertEqual(w.demand_rank(miss, signals), 1)
        self.assertEqual(w.demand_rank(miss, []), 1)
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        # 2026-11-07（台帳 A54）: 検索の急上昇（demand_rank）が最初。その次に検索で上位に出やすい話題の並び、その次に1日の配分
        self.assertIn("demand_rank(i, pi_signals), rank_intent.sort_key(i, intent_counts), news_mix.order_key(i, mix_counts)", src)


class BudgetTest(unittest.TestCase):
    def test_monthly_budget_is_unchanged_and_caps_scale_with_volume(self):
        self.assertEqual(llm.API_MONTHLY_BUDGET_DEFAULT, 95.0)
        self.assertGreaterEqual(llm.API_DAILY_CALLS["check"], 600)
        self.assertGreaterEqual(llm.API_DAILY_CALLS["helper"], 600)
        self.assertGreaterEqual(llm.API_DAILY_CALLS["core"], 120)
        self.assertGreaterEqual(llm.API_DAILY_CALLS["breaking"], 1000, "2026-11-09 オーナー: 速報は上限なし")
        self.assertEqual(llm.API_MAX_LEVEL, 2, "Opus は使わない")

    def test_quality_gates_are_not_loosened(self):
        # 本文の下限（A10: 1,500字）と、お知らせの転載の門（A26）はそのまま
        import indexnow

        self.assertGreaterEqual(indexnow.THIN_BODY, 1500)
        self.assertIn("notice_reason(item)", (ROOT / "scripts" / "web_articles.py").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
