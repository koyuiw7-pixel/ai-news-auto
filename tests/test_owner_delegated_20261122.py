"""2026-11-22 オーナー「任せるよ。最後に一番数字が伸びる方法を取って欲しい」で決めた5つのうち、Python 側の決まりを通信なしで確かめる。
S56 速報の自動投稿を止める・A76 検索の書き直しだけ OpenAI・W48 災害の広告の設定・A77 まとめ記事の言い方。"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import conftest  # noqa: E402
import a8_import  # noqa: E402
import breaking_post  # noqa: E402
import search_refresh  # noqa: E402


class BreakingNeverPosts(unittest.TestCase):
    def setUp(self):
        conftest.AUTO_POST_REAL["on"] = True

    def tearDown(self):
        conftest.AUTO_POST_REAL["on"] = False

    def test_live_dispatch_exits_ok_without_touching_posts(self):
        env = {"THREADS_MODE": "live", "BUFFER_API_KEY": "dummy"}
        with patch.dict(os.environ, env), patch.object(sys, "argv", ["breaking_post.py"]), \
                patch.object(breaking_post, "targets", side_effect=AssertionError("対象を選んだ")), \
                patch.object(breaking_post.tp, "share_now", side_effect=AssertionError("投稿した")):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(breaking_post.main(), 0)
        self.assertIn("投稿しません", out.getvalue())

    def test_every_switch_is_off_in_the_real_config(self):
        self.assertTrue(breaking_post.auto_post_stopped())


def fake_llm(**over):
    summary = {"budget": 69.0, "margin": 10.0, "spent": 15.0, "spent_today": 1.0, "daily_limit": 5.0, **over}
    llm = MagicMock()
    llm.openai_ledger_summary.return_value = summary
    llm.openai_block_reason.return_value = None
    return llm


class SearchRefreshOnOpenAI(unittest.TestCase):
    def test_needs_the_step_flag_and_openai_first(self):
        llm = fake_llm()
        llm.provider_order.return_value = ["openai"]
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEARCH_REFRESH_OPENAI", None)
            self.assertFalse(search_refresh.use_openai(llm))
        with patch.dict(os.environ, {"SEARCH_REFRESH_OPENAI": "1"}):
            self.assertTrue(search_refresh.use_openai(llm))
            llm.provider_order.return_value = ["claude"]
            self.assertFalse(search_refresh.use_openai(llm))

    def test_allowance_is_capped_at_five_and_by_budget(self):
        self.assertEqual(search_refresh.openai_allowance(20, fake_llm(), 0.25)[0], 5)
        self.assertEqual(search_refresh.openai_allowance(5, fake_llm(spent_today=4.6), 0.25)[0], 1)
        self.assertEqual(search_refresh.openai_allowance(5, fake_llm(spent=58.9), 0.25)[0], 0)
        blocked = fake_llm()
        blocked.openai_block_reason.return_value = "予算に届く"
        self.assertEqual(search_refresh.openai_allowance(5, blocked, 0.25)[0], 0)

    def test_only_the_search_step_gets_openai(self):
        text = (ROOT / ".github/workflows/types_rewrite.yml").read_text("utf-8")
        self.assertEqual(text.count('SEARCH_REFRESH_OPENAI: "1"'), 1)
        rewrite_step, search_step = text.split("- name: Search refresh (Mondays)")
        self.assertNotIn("SEARCH_REFRESH_OPENAI", rewrite_step)
        search_step = search_step.split("- name: Body images")[0]
        self.assertIn("LLM_PROVIDER_ORDER: openai", search_step)
        self.assertIn("OPENAI_API_SAFETY_MARGIN_USD", search_step)
        self.assertIn("--weekly --max 5", search_step)
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            if path.name != "types_rewrite.yml":
                self.assertNotIn("SEARCH_REFRESH_OPENAI", path.read_text("utf-8"), path.name)

    def test_default_writer_is_still_sonnet_only(self):
        import inspect

        import rewrite_types

        self.assertEqual(inspect.signature(rewrite_types.rewrite).parameters["writers"].default, ("anthropic-api:claude-sonnet",))


class DisasterAdConfig(unittest.TestCase):
    def test_disaster_rule_has_no_insurance_and_keeps_supplies(self):
        offers = json.loads((ROOT / "content/offers.json").read_text("utf-8"))
        for rules, key in ((a8_import.ACTION_ADS, "disaster"), (offers["actionAds"], "disaster"), (offers["topics"], "life-disaster")):
            rule = next(r for r in rules if r["key"] == key)
            self.assertNotIn("bang-kasai", rule["partners"])
            self.assertIn("jackery", rule["partners"])
            self.assertIn("akamaru-bousai", rule["partners"])


class RoundupWording(unittest.TestCase):
    def test_no_editorial_merge_claim_in_generator_or_articles(self):
        self.assertNotIn("編集部が統合", (ROOT / "scripts/roundup.py").read_text("utf-8"))
        self.assertIn("本の記事をまとめた記事", (ROOT / "scripts/roundup.py").read_text("utf-8"))
        left = [p.name for p in (ROOT / "content/articles").glob("*.json") if "編集部が統合" in p.read_text("utf-8")]
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main()
