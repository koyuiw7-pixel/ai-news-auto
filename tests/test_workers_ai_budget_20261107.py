"""2026-11-07 台帳 O15: Workers AI（Cloudflare）の有料を避ける。ネットワークは使わない。

- 本文を書く段（write・quality）は Flash → 軽量の Gemini（flash-lite・Gemma）→ ほかの会社（Cloudflare は Gemini の後）
- Cloudflare の文章モデルの使用量（ニューロン）を応答の usage から数え、UTC の日ごとにジョブの記録へ足す
- 1日の目安を超えたら Cloudflare は候補の最後に回す（ほかが全部だめなときは使う＝止めない）
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import llm  # noqa: E402

CF = "cloudflare:@cf/openai/gpt-oss-120b"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "t", "CLOUDFLARE_ACCOUNT_ID": "a", "LLM_WORKFLOW": "articles"})
        self.env.start()
        for key in [k for k in os.environ if k.startswith(("LLM_CF_", "LLM_DEFAULT_", "LLM_DAILY_LIMIT_", "CLOUDFLARE_MODELS"))]:
            os.environ.pop(key)
        self.patches = [
            patch.object(llm, "LLM_STATE_DIR", tmp),
            patch.object(llm, "USAGE_PATH", tmp / "llm_usage.json"),
            patch.object(llm, "SLOW_PATH", tmp / "llm_slow.json"),
            patch.object(llm, "available_models", return_value=set(llm.QUALITY_MODELS + llm.BULK_MODELS)),
            patch.object(llm, "_groq_models", return_value=[]),
            patch.object(llm, "_openrouter_models", return_value=[]),
            patch.object(llm, "_claude_models", return_value=[]),
            patch.object(llm, "_codex_models", return_value=[]),
            patch("time.sleep"),
        ]
        for p in self.patches:
            p.start()
        llm._tiers.clear(); llm._exhausted.clear(); llm._limit_logged.clear()
        self.wf = tmp / "llm_usage_wf.json"

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()
        llm._tiers.clear(); llm._exhausted.clear(); llm._limit_logged.clear()
        self.tmp.cleanup()


class OrderTests(Base):
    def test_light_gemini_writes_before_gpt_oss(self):
        for tier in ("write", "quality"):
            chain = llm.models_for(tier)
            self.assertLess(chain.index("gemini-3.5-flash"), chain.index("gemini-3.5-flash-lite"), tier)
            self.assertLess(chain.index("gemini-3.5-flash-lite"), chain.index(CF), tier)
            self.assertLess(chain.index("gemma-4-31b-it"), chain.index(CF), tier)

    def test_flash_lite_drafts_when_flash_is_out(self):
        calls = []

        def gemini(model, *a, **k):
            calls.append(model)
            if "lite" not in model:
                raise RuntimeError("429 RESOURCE_EXHAUSTED PerDay")
            return '{"answer": "ok"}'

        with patch.object(llm, "_call_gemini", side_effect=gemini), \
             patch.object(llm, "_call_openai_compatible") as cf:
            _, model = llm.generate_json("s", "p", {"required": ["answer"]}, tier="write")
        self.assertEqual(model, "gemini-3.5-flash-lite")
        cf.assert_not_called()


class NeuronTests(Base):
    def test_neurons_from_usage_match_cloudflare_bill(self):
        # 2026-11-06 の実績: 入力 2,035,928・出力 519,345 → 100,189 ニューロン
        n = llm.cf_neurons("@cf/openai/gpt-oss-120b", {"prompt_tokens": 2035928, "completion_tokens": 519345})
        self.assertAlmostEqual(n, 100189, delta=100)

    def test_cloudflare_call_records_neurons_by_utc_day(self):
        reply = {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 20000, "completion_tokens": 5000}}
        with patch.object(llm, "_http_json", return_value=reply):
            llm._call_openai_compatible(CF, "s", "p", {}, 0.2, 256)
        day = llm._utc_day()
        self.assertEqual(llm.cf_neurons_today(), llm.cf_neurons("@cf/openai/gpt-oss-120b", reply["usage"]))
        data = json.loads(self.wf.read_text("utf-8"))
        self.assertIn(llm.CF_NEURON_KEY + day, json.dumps(data))
        # 前の日（UTC）の分は今日に数えない
        later = datetime.now(timezone.utc).replace(year=2099)
        self.assertEqual(llm.cf_neurons_today(later), 0)

    def test_counts_every_job_file(self):
        day = llm._utc_day()
        (Path(self.tmp.name) / "llm_usage_evergreen.json").write_text(json.dumps({"2026-11-06": {"evergreen": {llm.CF_NEURON_KEY + day: 1200}}}))
        self.wf.write_text(json.dumps({"2026-11-07": {"articles": {llm.CF_NEURON_KEY + day: 900, CF: 3}}}))
        self.assertEqual(llm.cf_neurons_today(), 2100)


class BudgetTests(Base):
    def spend(self, n):
        self.wf.write_text(json.dumps({"2026-11-07": {"articles": {llm.CF_NEURON_KEY + llm._utc_day(): n}}}))

    def test_over_budget_tries_free_models_first(self):
        self.spend(llm.CF_DAILY_NEURONS_DEFAULT)
        order = []

        def gemini(model, *a, **k):
            order.append(model)
            if model != "gemma-4-26b-a4b-it":
                raise RuntimeError("429 RESOURCE_EXHAUSTED PerDay")
            return '{"answer": "ok"}'

        with patch.object(llm, "models_for", return_value=["gemini-3.5-flash-lite", CF, "gemma-4-26b-a4b-it"]), \
             patch.object(llm, "_call_gemini", side_effect=gemini), \
             patch.object(llm, "_call_openai_compatible") as cf:
            _, model = llm.generate_json("s", "p", {"required": ["answer"]}, tier="bulk")
        self.assertEqual(model, "gemma-4-26b-a4b-it")
        cf.assert_not_called()

    def test_over_budget_still_uses_cloudflare_when_nothing_else_works(self):
        """止めない（台帳 A48）: ほかの無料モデルが全部だめなら、目安を超えていても Cloudflare で作る"""
        self.spend(10 ** 6)
        with patch.object(llm, "models_for", return_value=[CF, "gemini-3.5-flash-lite"]), \
             patch.object(llm, "_call_gemini", side_effect=RuntimeError("429 RESOURCE_EXHAUSTED PerDay")), \
             patch.object(llm, "_call_openai_compatible", return_value='{"answer": "ok"}'):
            _, model = llm.generate_json("s", "p", {"required": ["answer"]}, tier="bulk")
        self.assertEqual(model, CF)

    def test_under_budget_keeps_order(self):
        self.spend(10)
        with patch.object(llm, "models_for", return_value=[CF, "gemini-3.5-flash-lite"]), \
             patch.object(llm, "_call_gemini") as gemini, \
             patch.object(llm, "_call_openai_compatible", return_value='{"answer": "ok"}'):
            _, model = llm.generate_json("s", "p", {"required": ["answer"]}, tier="bulk")
        self.assertEqual(model, CF)
        gemini.assert_not_called()

    def test_budget_env_zero_means_no_budget(self):
        self.spend(10 ** 6)
        with patch.dict(os.environ, {"LLM_CF_DAILY_NEURONS": "0"}):
            self.assertFalse(llm.cf_over_budget())
        self.assertTrue(llm.cf_over_budget())


if __name__ == "__main__":
    unittest.main()
