"""OpenAI API の段（2026-11-18 オーナー決定・台帳 O18）: ChatGPT Pro の API クレジット（月 $100・8日〜翌月7日・今の期間は残り $69）を
記事づくりに使い、予算に届く前に止める。止まったら Claude API ではなく今までの無料の経路へ（CLAUDE_API_FALLBACK_PURPOSES の段だけ Claude）。
OPENAI_API_KEY が無いときは何も変わらない。実際の API には一切つながない（_openai_request・_api_request をモックする）。"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import llm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = {"type": "OBJECT", "properties": {"answer": {"type": "STRING"}, "note": {"type": "STRING"}}, "required": ["answer"]}
NOW = datetime(2026, 11, 18, 3, 0, tzinfo=timezone.utc)  # 日本時間 11/18 12:00（期間 11/8〜12/7・残り20日）


def jst(y, m, d, h=12):
    return datetime(y, m, d, h - 9, 0, tzinfo=timezone.utc) if h >= 9 else datetime(y, m, d - 1, h + 15, 0, tzinfo=timezone.utc)


def openai_response(text='{"answer": "openai", "note": null}', inp=1000, out=500, cached=0, status="completed"):
    return {"status": status, "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": inp, "output_tokens": out, "input_tokens_details": {"cached_tokens": cached}}}


def claude_message(text='{"answer": "claude"}'):
    usage = SimpleNamespace(input_tokens=1000, output_tokens=500, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn", usage=usage)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-not-real", "OPENAI_API_KEY": "test-key-not-real"}, clear=False)
        self.env.start()
        for key in [k for k in os.environ if k.startswith(("CLAUDE_API_", "LLM_DEFAULT_", "LLM_PROVIDER_ORDER", "OPENAI_API_", "OPENAI_MODEL_"))
                    and k != "OPENAI_API_KEY"]:
            os.environ.pop(key)
        self.patches = [
            patch.object(llm, "API_STATE_DIR", tmp),
            patch.object(llm, "USAGE_PATH", tmp / "llm_usage.json"),
            patch.object(llm, "LLM_STATE_DIR", tmp),
            patch.object(llm, "_now", return_value=NOW),
            patch.object(llm, "models_for", return_value=["gemini-free"]),
            patch.object(llm, "_claude_models", return_value=[]),
        ]
        for p in self.patches:
            p.start()
        for name in ("_api_off", "_openai_off"):
            setattr(llm, name, None)
        llm._api_transient_failures = llm._openai_transient_failures = 0
        llm._exhausted.clear()
        llm._limit_logged.clear()
        llm._api_summary_logged.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()
        llm._api_off = llm._openai_off = None
        llm._exhausted.clear()
        self.tmp.cleanup()

    def spend(self, day: str, usd: float, name="claude_api_usage.json", purpose="core"):
        path = llm.API_STATE_DIR / name
        data = json.loads(path.read_text("utf-8")) if path.exists() else {}
        entry = data.setdefault("openai", {}).setdefault("runs", {}).setdefault(day, {}).setdefault(f"gh-{len(str(data))}", {})
        entry["usd"] = usd
        entry["by"] = {f"{purpose}|gpt-6.1-terra": {"n": 1, "usd": usd}}
        path.write_text(json.dumps(data), "utf-8")


class CycleTests(Base):
    def test_cycle_runs_from_the_8th_to_the_7th_in_japan_time(self):
        self.assertEqual(llm.openai_cycle_bounds(jst(2026, 11, 7, 23)), (datetime(2026, 10, 8).date(), datetime(2026, 11, 7).date()))
        self.assertEqual(llm.openai_cycle_bounds(jst(2026, 11, 8, 0)), (datetime(2026, 11, 8).date(), datetime(2026, 12, 7).date()))
        self.assertEqual(llm.openai_cycle_bounds(jst(2026, 12, 7, 23)), (datetime(2026, 11, 8).date(), datetime(2026, 12, 7).date()))
        self.assertEqual(llm.openai_cycle_bounds(jst(2026, 12, 8, 0)), (datetime(2026, 12, 8).date(), datetime(2027, 1, 7).date()))
        self.assertEqual(llm.openai_cycle_bounds(jst(2027, 1, 3)), (datetime(2026, 12, 8).date(), datetime(2027, 1, 7).date()))

    def test_current_cycle_cap_is_69_and_next_cycle_is_100(self):
        s = llm.openai_ledger_summary(NOW)
        self.assertEqual((s["cycle_start"], s["cycle_end"], s["budget"]), ("2026-11-08", "2026-12-07", 69.0))
        self.assertEqual(llm.openai_ledger_summary(jst(2026, 12, 8, 10))["budget"], 100.0)

    def test_env_override_until_date_then_monthly_default(self):
        os.environ["OPENAI_API_CYCLE_BUDGET_USD"] = "50"
        os.environ["OPENAI_API_CYCLE_BUDGET_UNTIL"] = "2026-12-07"
        self.assertEqual(llm.openai_ledger_summary(NOW)["budget"], 50.0)
        self.assertEqual(llm.openai_ledger_summary(jst(2026, 12, 8, 10))["budget"], 100.0)
        os.environ["OPENAI_API_MONTHLY_BUDGET_USD"] = "40"
        self.assertEqual(llm.openai_ledger_summary(NOW)["budget"], 40.0)  # 月の額より上にはしない

    def test_spend_is_summed_across_all_ledgers_and_only_this_cycle(self):
        self.spend("2026-11-07", 30.0)  # 前の期間
        self.spend("2026-11-08", 5.0)
        self.spend("2026-11-17", 2.5, name="claude_api_usage_video.json")
        self.spend("2026-11-18", 1.0, name="claude_api_usage_provider_trial.json")
        s = llm.openai_ledger_summary(NOW)
        self.assertAlmostEqual(s["spent"], 8.5)
        self.assertAlmostEqual(s["spent_today"], 1.0)

    def test_claude_summary_ignores_openai_spend(self):
        self.spend("2026-11-18", 9.0)
        self.assertEqual(llm.api_ledger_summary(NOW)["spent"], 0.0)

    def test_first_day_also_checks_the_previous_cycle(self):
        # 切り替えの時刻が分からないので、8日の分は前の期間にも数える
        self.spend("2026-11-20", 65.0)  # 前の期間（11/8〜12/7、上限 $69）
        day8 = jst(2026, 12, 8, 3)
        self.spend("2026-12-08", 1.0)
        why = llm.openai_block_reason("core", estimate=0.5, now=day8)
        self.assertIn("前の期間", why or "")
        self.assertIsNone(llm.openai_block_reason("core", estimate=0.5, now=jst(2026, 12, 9, 3)))


class HardStopTests(Base):
    def test_blocks_before_the_call_would_exceed_the_cycle_budget(self):
        self.spend("2026-11-10", 65.5)
        # 上限 $69 − 余裕 $3 = $66。$65.5 ＋ この回 $0.6 は超えるので呼ばない
        self.assertIn("予算", llm.openai_block_reason("breaking", estimate=0.6) or "")
        self.assertIsNone(llm.openai_block_reason("breaking", estimate=0.4))

    def test_over_budget_falls_back_to_free_path_not_claude(self):
        self.spend("2026-11-10", 68.0)
        os.environ["LLM_PROVIDER_ORDER"] = "openai,claude"
        with patch.object(llm, "_openai_request") as oa, patch.object(llm, "_api_request") as cl, \
                patch.object(llm, "_call_gemini", return_value='{"answer": "free"}'):
            data, model = llm.generate_json("sys", "prompt", SCHEMA, purpose="core")
        oa.assert_not_called()
        cl.assert_not_called()
        self.assertEqual((data["answer"], model), ("free", "gemini-free"))

    def test_claude_fallback_only_for_listed_purposes(self):
        self.spend("2026-11-10", 68.0)
        os.environ["LLM_PROVIDER_ORDER"] = "openai"
        os.environ["CLAUDE_API_FALLBACK_PURPOSES"] = "breaking"
        self.assertEqual(llm.provider_order("breaking"), ["openai", "claude"])
        self.assertEqual(llm.provider_order("core"), ["openai"])
        with patch.object(llm, "_openai_request") as oa, patch.object(llm, "_api_request", return_value=claude_message()):
            data, model = llm.generate_json("sys", "prompt", SCHEMA, purpose="breaking")
        oa.assert_not_called()
        self.assertTrue(model.startswith(llm.API_PREFIX))

    def test_insufficient_quota_marks_exhausted_until_next_cycle(self):
        os.environ["LLM_PROVIDER_ORDER"] = "openai"
        err = llm.OpenAIError(429, "insufficient_quota", "You exceeded your current quota")
        with patch.object(llm, "_openai_request", side_effect=err), patch.object(llm, "_call_gemini", return_value='{"answer": "free"}'):
            _, model = llm.generate_json("sys", "prompt", SCHEMA, purpose="core")
        self.assertEqual(model, "gemini-free")
        llm._openai_off = None
        s = llm.openai_ledger_summary(NOW)
        self.assertEqual(s["exhausted_until"][:10], "2026-12-08")
        self.assertIn("クレジット切れ", llm.openai_block_reason("core") or "")

    def test_daily_pace_stops_non_protected_but_not_breaking(self):
        self.spend("2026-11-18", 5.2)  # 目安 = 69/20×1.5 = $5.17
        self.assertIn("今日の目安", llm.openai_block_reason("core", estimate=0.1) or "")
        self.assertIsNone(llm.openai_block_reason("breaking", estimate=0.1))

    def test_usage_is_recorded_with_cost(self):
        os.environ["LLM_PROVIDER_ORDER"] = "openai"
        with patch.object(llm, "_openai_request", return_value=openai_response(inp=10000, out=2000, cached=4000)):
            data, model = llm.generate_json("sys", "prompt", SCHEMA, purpose="core")
        self.assertEqual(model, "openai-api:gpt-6.1-terra")
        self.assertEqual(data, {"answer": "openai"})  # null の任意の項目は消す
        expected = (6000 * 1.00 + 4000 * 0.05 + 2000 * 5.00) / 1_000_000
        s = llm.openai_ledger_summary(NOW)
        self.assertAlmostEqual(s["spent"], expected, places=6)
        self.assertEqual(s["calls_today"], {"core": 1})

    def test_merge_keeps_openai_runs(self):
        mine = {"openai": {"runs": {"2026-11-18": {"gh-1-1": {"usd": 2.0}}}}}
        dest = {"runs": {}, "openai": {"runs": {"2026-11-18": {"gh-2-1": {"usd": 1.0}}}}}
        merged = llm.merge_api_usage(mine, dest)
        self.assertEqual(set(merged["openai"]["runs"]["2026-11-18"]), {"gh-1-1", "gh-2-1"})


class ProviderOrderTests(Base):
    def test_default_order_is_claude_even_with_key(self):
        self.assertEqual(llm.provider_order("core"), ["claude"])

    def test_global_and_per_purpose_order(self):
        os.environ["LLM_PROVIDER_ORDER"] = "openai,claude"
        os.environ["LLM_PROVIDER_ORDER_SNS"] = "claude,openai"
        self.assertEqual(llm.provider_order("core"), ["openai"])
        self.assertEqual(llm.provider_order("sns"), ["claude", "openai"])
        os.environ["CLAUDE_API_FALLBACK_PURPOSES"] = "all"
        self.assertEqual(llm.provider_order("core"), ["openai", "claude"])

    def test_video_stays_on_claude(self):
        os.environ["LLM_PROVIDER_ORDER"] = "openai"
        self.assertEqual(llm.provider_order("video"), ["claude"])
        self.assertEqual(llm.provider_order("video_review"), ["claude"])

    def test_openai_first_then_claude_when_listed(self):
        os.environ["LLM_PROVIDER_ORDER"] = "openai"
        with patch.object(llm, "_openai_request", return_value=openai_response()) as oa, patch.object(llm, "_api_request") as cl:
            _, model = llm.generate_json("sys", "prompt", SCHEMA, purpose="check")
        self.assertEqual(model, "openai-api:gpt-6-luna")
        self.assertEqual(oa.call_args[0][0], "gpt-6-luna")
        cl.assert_not_called()

    def test_strict_schema_requires_all_and_allows_null_for_optional(self):
        s = llm._openai_schema(SCHEMA)
        self.assertEqual(sorted(s["required"]), ["answer", "note"])
        self.assertEqual(s["properties"]["note"]["type"], ["string", "null"])
        self.assertEqual(s["properties"]["answer"]["type"], "string")
        self.assertFalse(s["additionalProperties"])


class AbsentKeyTests(Base):
    def test_absent_key_changes_nothing(self):
        os.environ.pop("OPENAI_API_KEY")
        os.environ["LLM_PROVIDER_ORDER"] = "openai"  # 変数があっても、キーが無ければ今までどおり
        self.assertEqual(llm.provider_order("core"), ["claude"])
        self.assertEqual(llm.paid_block_reason("core"), llm.api_block_reason("core"))
        with patch.object(llm, "_openai_request") as oa, patch.object(llm, "_api_request", return_value=claude_message()):
            _, model = llm.generate_json("sys", "prompt", SCHEMA, purpose="core")
        oa.assert_not_called()
        self.assertTrue(model.startswith(llm.API_PREFIX))
        self.assertFalse((llm.API_STATE_DIR / "claude_api_usage.json").exists()
                         and "openai" in json.loads((llm.API_STATE_DIR / "claude_api_usage.json").read_text("utf-8")))


class WiringTests(unittest.TestCase):
    def test_every_workflow_with_claude_key_also_passes_openai_key(self):
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            text = path.read_text("utf-8")
            self.assertEqual(text.count("secrets.ANTHROPIC_API_KEY"), text.count("secrets.OPENAI_API_KEY"), path.name)

    def test_comparison_command_is_documented_and_dry(self):
        wf = (ROOT / ".github" / "workflows" / "compare_providers.yml").read_text("utf-8")
        self.assertIn("gh workflow run compare_providers.yml", wf)
        self.assertIn("CLAUDE_API_LEDGER: provider_trial", wf)
        self.assertNotIn("schedule:", wf)

    def test_recent_slugs_skip_articles_without_source(self):
        import compare_providers  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.json").write_text(json.dumps({"slug": "a", "sourceUrl": "https://x.example/a", "publishedAt": "2026-11-18T00:00:00Z"}))
            (d / "b.json").write_text(json.dumps({"slug": "b", "publishedAt": "2026-11-18T01:00:00Z"}))
            (d / "c.json").write_text(json.dumps({"slug": "c", "sourceUrl": "https://x.example/c", "publishedAt": "2026-11-17T00:00:00Z"}))
            self.assertEqual(compare_providers.recent_slugs(5, d), ["a", "c"])


if __name__ == "__main__":
    unittest.main()
