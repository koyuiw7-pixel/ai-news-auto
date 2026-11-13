"""2026-11-06 オーナー「止まったという報告が多い。止まらない仕組みを作って」＋「お金はなるべく使わない」（台帳 A48）。

- 見送りは1件ずつ理由をログに出し、候補があるのに1件も試さない回は「おかしい」の合図として数える
- 本文はまず無料モデル。門に落ちたら Haiku で書き足し・手直し → だめなら Sonnet で作り直し（門の基準は変えない）
- 救済の段（repair・rescue）は1日の配分では下げず、月の予算に届いたときだけ止まる
- 0本の回が1回で次は救済モード。救済モードでも2回続けて0本なら、ふつうの言葉の issue
外部への通信なし。
"""

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import llm  # noqa: E402
import pipeline_health  # noqa: E402
import quality  # noqa: E402

NOW = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
WEB = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")


def summary(**over):
    base = {
        "period_start": "2026-11-04", "period_end": "2026-12-04", "budget": 190.0, "spent": 20.0, "spent_today": 9.0,
        "daily_limit": 3.0, "calls_today": {}, "req_today": {}, "tier_today": {}, "days_left": 24,
        "demand": dict(llm.API_DEMAND_DEFAULT), "cost_stats": {}, "exhausted_until": None, "exhausted_reason": "",
    }
    base.update(over)
    return base


class RescueTierTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-not-real"}, clear=False)
        self.env.start()
        for key in [k for k in os.environ if k.startswith("CLAUDE_API_")]:
            os.environ.pop(key)
        llm._api_off = None

    def tearDown(self):
        self.env.stop()

    def choose(self, purpose, s):
        with patch.object(llm, "api_ledger_summary", return_value=s):
            return llm.api_choose(purpose, now=NOW, record=False)

    def test_tiers_exist_and_are_not_protected(self):
        self.assertEqual(llm.API_TIERS["repair"][:4], (1, 1, 1, False))
        self.assertEqual(llm.API_TIERS["rescue"][:4], (2, 2, 2, False))
        self.assertEqual(llm.RESCUE_PURPOSES, {"repair", "rescue", "ymyl"})

    def test_daily_pace_over_does_not_stop_rescue(self):
        """今日の目安額を大きく超えても、救済は Haiku / Sonnet のまま（下がるのは SNS・その他などの段）"""
        s = summary(spent_today=9.0, daily_limit=3.0)
        self.assertEqual(self.choose("repair", s)[0], "claude-haiku-5-5")
        self.assertEqual(self.choose("rescue", s)[0], "claude-sonnet-5-5")
        self.assertEqual(self.choose("rest", s)[0], None)  # その他の段は配分で無料モデル（従来どおり）

    def test_monthly_cap_stops_rescue(self):
        s = summary(spent=190.0)
        model, why = self.choose("rescue", s)
        self.assertIsNone(model)
        self.assertIn("今月の予算", why)
        # 守る段の予備（protected margin）は救済に使わない
        self.assertIsNone(self.choose("repair", summary(spent=191.0))[0])

    def test_rescue_demand_does_not_shrink_other_tiers(self):
        s = summary(spent_today=0.0, daily_limit=50.0)
        with_rescue = llm.api_plan(NOW, s)["levels"]
        s2 = summary(spent_today=0.0, daily_limit=50.0, demand={**llm.API_DEMAND_DEFAULT, "repair": 0, "rescue": 0})
        self.assertEqual(with_rescue, llm.api_plan(NOW, s2)["levels"])

    def test_run_cost_tracks_per_article(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(llm, "API_STATE_DIR", Path(tmp)):
            mark = llm.run_cost_mark()
            usage = SimpleNamespace(input_tokens=10000, output_tokens=4000, cache_read_input_tokens=0, cache_creation_input_tokens=0)
            llm.record_api_usage("repair", "claude-haiku-5-5", usage, now=NOW)
            usd, detail = llm.cost_since(mark)
        self.assertAlmostEqual(usd, (10000 * 0.10 + 4000 * 0.50) / 1e6, places=5)
        self.assertIn("救済の手直し Haiku×1", detail)
        self.assertEqual(llm.cost_since(llm.run_cost_mark())[1], "Claude API なし（無料モデルだけ）")


class ExpandRepairTest(unittest.TestCase):
    SOURCE = "A社は11月6日、新しい料金プランを発表した。月額980円で、12月1日から日本で使える。対象は個人の契約者。"
    RECORD = {"title": "A社が新料金", "lede": "リード", "highlights": ["a"], "body": "短い本文。月額980円。", "easy": "かんたん"}

    def run_repair(self, body, purpose="repair"):
        out = {"title": "", "lede": "", "highlights": [], "body_markdown": body, "easy_markdown": "", "work_money_points": []}
        with patch.object(llm, "generate_json", return_value=(out, "anthropic-api:claude-haiku-5-5")) as gen:
            got = quality.expand_repair(dict(self.RECORD), self.SOURCE, ["公開前の門: 本文が短すぎます"], purpose=purpose)
        return got, gen

    def test_expanded_body_replaces_and_uses_requested_purpose(self):
        long_body = "A社の発表によると、月額980円の新プランは12月1日から使える。" * 40
        (fixed, model), gen = self.run_repair(long_body)
        self.assertEqual(fixed["body"], long_body)
        self.assertEqual(gen.call_args.kwargs["purpose"], "repair")
        self.assertIn("1500字以上", gen.call_args.args[1])
        self.assertIn(self.SOURCE, gen.call_args.args[1])  # 元記事を渡し、事実はそこからだけ

    def test_rejects_new_numbers_not_in_source(self):
        (fixed, why), _ = self.run_repair("A社の新プランは月額1,480円になる。" * 40)
        self.assertIsNone(fixed)
        self.assertIn("元に無い数字", why)

    def test_rejects_shrunk_body(self):
        (fixed, why), _ = self.run_repair("短")
        self.assertIsNone(fixed)
        self.assertIn("縮んだ", why)


class HealthRescueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(pipeline_health, "HEALTH_PATH", Path(self.tmp.name) / "h.json")
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("PIPELINE_RESCUE", None)

    def test_rescue_then_stalled_after_two_failed_rescues(self):
        self.assertEqual(pipeline_health.record(0, 5, "短い")["status"], "rescue")
        one = pipeline_health.record(0, 5, "短い", rescue=True, tried=["Claude で書いた"])
        self.assertEqual((one["status"], one["rescue_failed"]), ("rescue", 1))
        two = pipeline_health.record(0, 5, "短い", rescue=True, tried=["Claude で書いた"])
        self.assertEqual((two["status"], two["rescue_failed"]), ("stalled", 2))
        ok = pipeline_health.record(1, 5)
        self.assertEqual((ok["status"], ok["rescue_failed"], ok["consecutive_zero"]), ("ok", 0, 0))
        self.assertNotIn("tried", ok)

    def test_issue_body_is_plain_japanese_with_what_was_tried(self):
        body = pipeline_health.issue_body({"consecutive_zero": 3, "rescue_failed": 2, "reason": "本文が短い", "candidates": 4,
                                           "stalled_since": "2026-11-06T12:19:04+00:00", "tried": ["候補を6件試した"]})
        self.assertIn("自動で試したこと", body)
        self.assertIn("- 候補を6件試した", body)
        self.assertIn("品質の基準", body)
        self.assertIn("使い方ガイド", body)
        self.assertNotRegex(body, r"consecutive|rescue_failed|candidates|stalled")


class WebArticlesWiringTest(unittest.TestCase):
    def test_every_skip_is_logged_with_reason(self):
        self.assertIn("def pick(cand: dict, is_ai: bool, major: bool = False, trend: bool = False):", WEB)  # 2026-11-13 話題のレーン（trend）
        self.assertIn("action, found = _pick(cand, is_ai, major, trend)", WEB)
        self.assertIn("skip_counts[key] = skip_counts.get(key, 0) + 1", WEB)
        self.assertIn("[skip] 見送りの内訳（この回）", WEB)
        # 理由の無い見送りを残さない
        body = WEB[WEB.index("    def _pick("):WEB.index("    def major_retry(")]
        self.assertNotIn('return "next", None', body)
        self.assertNotIn('return "drop", None', body)

    def test_nothing_attempted_counts_as_bug_signal(self):
        self.assertIn("があったのに1件も試していない", WEB)
        self.assertIn("taken_counter[0] == 0", WEB)

    def test_free_first_then_claude_rescue(self):
        self.assertIn('FREE_FIRST_PURPOSES = {"core", "rest"}', WEB)
        self.assertIn('draft_purpose = "" if free_first else purpose', WEB)
        self.assertIn('steps = ["repair"] + (["rescue"]', WEB)  # Haiku から
        self.assertIn('draft_purpose = "rescue"', WEB)            # 作り直しは Sonnet
        self.assertIn("quality.expand_repair(", WEB)
        # 救済のあとも同じ門（公開前の門・事実確認）を通す
        regate = WEB[WEB.index("    def regate("):WEB.index("    def finish(")]
        self.assertIn("publish_blocked(record)", regate)
        self.assertIn("quality.evaluate(", regate)

    def test_rescue_mode_and_evergreen_fallback(self):
        self.assertIn('int(health_before.get("consecutive_zero") or 0) >= 1', WEB)
        self.assertIn("RESCUE_MAX_ATTEMPTS", WEB)
        self.assertIn("rescue_evergreen=1", WEB)
        wf = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("id: web", wf)
        self.assertIn("steps.web.outputs.rescue_evergreen == '1'", wf)
        self.assertIn("gh workflow run evergreen.yml", wf)

    def test_quality_gate_threshold_unchanged(self):
        import indexnow  # noqa: PLC0415
        self.assertEqual(indexnow.THIN_BODY, 1500)

    def test_owner_rule_row(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next((line for line in rules.splitlines() if line.startswith("| A58 |")), "")
        self.assertIn("止ま", row)
        self.assertIn("品質の門", row)


if __name__ == "__main__":
    unittest.main()
