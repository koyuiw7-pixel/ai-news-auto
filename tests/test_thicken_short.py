"""scripts/thicken_short.py: 短い記事を公式の資料で厚くする（2026-11-12 オーナー承認）。選び方・書き直さない記事・記録（通信しない）"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import thicken_short as ts  # noqa: E402

NOW = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)


def art(slug, n, **kw):
    return {"slug": slug, "sourceType": "web", "sourceUrl": f"https://www.example.go.jp/{slug}", "body": "あ" * n,
            "title": slug, "generatedAt": "2026-11-10T00:00:00+00:00", **kw}


def pick(articles, state=None, retired=(), noindex=()):
    with patch.object(ts, "_noindexed", side_effect=lambda a, d: a["slug"] in noindex):
        return ts.candidates(articles, state or {"articles": {}}, NOW, retired=set(retired), corrected=set(), dups=set())


class CountTest(unittest.TestCase):
    def test_chars_ignore_spaces_and_newlines(self):
        self.assertEqual(ts.chars("あい う\n\nえ　お"), 5)
        self.assertEqual(ts.chars(None), 0)

    def test_tiers(self):
        self.assertEqual(ts.tier_of(799), 0)
        self.assertEqual(ts.tier_of(800), 1)
        self.assertEqual(ts.tier_of(1499), 1)
        self.assertIsNone(ts.tier_of(1500))


class SelectionTest(unittest.TestCase):
    def test_under_800_first_then_under_1500_shortest_first(self):
        todo, _ = pick([art("b", 1200), art("a", 700), art("c", 300), art("long", 3000)])
        self.assertEqual([a["slug"] for a in todo], ["c", "a", "b"])

    def test_indexed_before_noindexed_in_the_same_tier(self):
        todo, _ = pick([art("hidden", 200), art("shown", 600)], noindex={"hidden"})
        self.assertEqual([a["slug"] for a in todo], ["shown", "hidden"])

    def test_retired_articles_are_not_touched_or_listed(self):
        todo, skipped = pick([art("gone", 200), art("ok", 300)], retired={"gone"})
        self.assertEqual([a["slug"] for a in todo], ["ok"])
        self.assertEqual(skipped, [])

    def test_skip_rules(self):
        cases = {
            "dup": art("dup", 300, duplicateOf="other"),
            "muse": art("muse", 300, museFile="x.md"),
            "editorial": art("editorial", 300, refreshMode="editorial"),
            "corrected": art("corrected", 300, body="**編集部訂正（2026年11月1日）**：" + "あ" * 300),
            "roundup": art("roundup", 300, type="roundup"),
            "trend": art("trend", 300, trendKeyword="x"),
            "quake": art("quake", 300, disaster=True),
            "angle": art("angle", 300, angleOf="parent"),
            "video": art("video", 300, sourceType=None, sourceUrl=None, videoUrl="https://www.youtube.com/watch?v=x"),
            "press": art("press", 300, secondary=True),
        }
        todo, skipped = pick(list(cases.values()) + [art("plain", 300)])
        self.assertEqual([a["slug"] for a in todo], ["plain"])
        self.assertEqual(sorted(a["slug"] for a, _ in skipped), sorted(cases))
        self.assertIn("動画", dict((a["slug"], w) for a, w in skipped)["video"])
        self.assertIn("報道", dict((a["slug"], w) for a, w in skipped)["press"])

    def test_duplicate_non_representative_is_skipped(self):
        # 本文の長さで代表が決まる（indexnow.duplicate_slugs）。代表でない方を厚くすると代表が入れ替わるので触らない
        self.assertIsNotNone(ts.skip_reason(art("x", 300), set(), {"x"}))


class StateTest(unittest.TestCase):
    def test_thickened_and_final_states_are_never_retried(self):
        for status in ("thickened", "source-short", "not-newsworthy", "skipped"):
            state = {"articles": {"a": {"status": status, "tries": 1, "at": "2026-11-01T00:00:00+00:00"}}}
            todo, _ = pick([art("a", 300)], state)
            self.assertEqual(todo, [], status)

    def test_gate_failures_stop_after_two(self):
        state = {"articles": {}}
        ts.record(state, "a", "gate-failed", "品質ゲートに合格しなかった", NOW)
        self.assertEqual(len(pick([art("a", 300)], state)[0]), 1)
        ts.record(state, "a", "not-thicker", "厚くならなかった", NOW)
        self.assertEqual(state["articles"]["a"]["gateTries"], 2)
        self.assertEqual(pick([art("a", 300)], state)[0], [])

    def test_unfetchable_source_waits_two_days_and_stops_after_two(self):
        state = {"articles": {}}
        ts.record(state, "a", "source-unfetchable", "元の資料が読めない・短い（0字）", NOW - timedelta(days=1))
        self.assertEqual(pick([art("a", 300)], state)[0], [])  # 1日しかたっていない
        state["articles"]["a"]["at"] = (NOW - timedelta(days=3)).isoformat()
        self.assertEqual(len(pick([art("a", 300)], state)[0]), 1)
        ts.record(state, "a", "source-unfetchable", "元の資料が読めない・短い（0字）", NOW - timedelta(days=3))
        self.assertEqual(pick([art("a", 300)], state)[0], [])

    def test_transient_failures_have_their_own_limit(self):
        state = {"articles": {}}
        for _ in range(ts.MAX_TRANSIENT_TRIES - 1):
            ts.record(state, "a", "transient", "Sonnet が使えなかった", NOW)
        self.assertEqual(len(pick([art("a", 300)], state)[0]), 1)
        ts.record(state, "a", "transient", "Sonnet が使えなかった", NOW)
        self.assertEqual(pick([art("a", 300)], state)[0], [])

    def test_state_round_trip(self):
        import tempfile  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            state = ts.load_state(path)
            self.assertEqual(state, {"articles": {}, "runs": []})
            ts.record(state, "a", "thickened", "", NOW, before=300, after=900)
            ts.save_state(state, path)
            again = ts.load_state(path)
            self.assertEqual(again["articles"]["a"]["status"], "thickened")
            self.assertEqual(again["articles"]["a"]["after"], 900)


class ClassifyTest(unittest.TestCase):
    def test_reasons_map_to_states(self):
        self.assertEqual(ts.classify({"why": "元の資料が読めない・短い（0字）"})[0], "source-unfetchable")
        self.assertEqual(ts.classify({"why": "元の資料が読めない・短い（412字）"})[0], "source-short")
        self.assertEqual(ts.classify({"why": "Sonnet が使えなかった（gemini）。次の回に回す"})[0], "transient")
        self.assertEqual(ts.classify({"why": "無料モデルで書けなかった。次の回に回す", "transient": True})[0], "transient")
        self.assertEqual(ts.classify({"why": "記事にする価値なしと判定（告知）"})[0], "not-newsworthy")
        self.assertEqual(ts.classify({"why": "品質ゲートに合格しなかった（今の版のまま）", "problems": ["数字が資料と違う"]})[0], "gate-failed")
        thin = ts.accept_for(300)({"body": "あ" * 350})
        self.assertEqual(ts.classify({"why": "品質ゲートに合格しなかった（今の版のまま）", "problems": [thin]})[0], "not-thicker")


class AcceptTest(unittest.TestCase):
    def test_new_body_must_be_clearly_thicker(self):
        acc = ts.accept_for(400)
        self.assertIsNotNone(acc({"body": "あ" * 650}))   # +250字では足りない
        self.assertIsNone(acc({"body": "あ" * 700}))      # +300字
        acc = ts.accept_for(1400)
        self.assertIsNotNone(acc({"body": "あ" * 1750}))
        self.assertIsNone(acc({"body": "あ" * 1820}))     # 1.3倍

    def test_view_section_must_not_predict(self):
        acc = ts.accept_for(100)
        good = "あ" * 500 + "\n\n## サイソクの見方\n\n期限は前の制度より1か月早い。\n\n## まだ分からないこと\n- 未定"
        self.assertIsNone(acc({"body": good}))
        bad = "あ" * 500 + "\n\n## サイソクの見方\n\n産業競争力に影響を与える可能性があります。"
        self.assertIn("予測", acc({"body": bad}))
        # 見方の章の外の「可能性」は見ない（資料にある注意書きなど）
        self.assertIsNone(acc({"body": "被害の可能性があります。" + "あ" * 500}))

    def test_stamp_moves_updated_at_and_keeps_title(self):
        a = art("a", 300, title="題名", searchTitle="検索の題名")
        new = dict(a, body="い" * 900)
        ts.stamp(new, NOW, 300)
        self.assertEqual(new["title"], "題名")
        self.assertEqual(new["searchTitle"], "検索の題名")
        self.assertEqual(new["updatedAt"], "2026-11-12T06:00:00+00:00")
        self.assertEqual(new["thicken"], {"before": 300, "after": 900})
        self.assertEqual(new["updates"][-1]["kind"], "refresh")


class PromptAndWorkflowTest(unittest.TestCase):
    def test_focus_asks_for_answer_first_and_a_labeled_view_without_padding(self):
        text = ts.FOCUS.format(chars=300)
        for word in ("答えを先に", "〜の人は〜", "## サイソクの見方", "水増しはしない", "そのまま写さない", "予測"):
            self.assertIn(word, text)
        self.assertNotIn("｜", text)
        self.assertNotIn("ざっくり", text)

    def test_workflow_uses_shared_caps_and_safe_push(self):
        import llm  # noqa: PLC0415

        wf = (ROOT / ".github" / "workflows" / "thicken_short.yml").read_text("utf-8")
        self.assertIn("scripts/thicken_short.py --apply", wf)
        self.assertIn("LLM_WORKFLOW: thicken", wf)
        self.assertIn("CLAUDE_API_LEDGER: thicken", wf)
        self.assertIn("thicken", llm.MAINTENANCE_LEDGERS)  # 新しい記事の1日の回数を食わない
        self.assertNotIn("CLAUDE_API_DAILY_CALLS", wf)
        self.assertIn("git_safe_push.py --wait-idle auto_run.yml", wf)
        self.assertIn("scripts/deploy_tests.py", wf)
        self.assertIn("state/thicken_short.json", wf)
        self.assertNotIn("pull --rebase", wf)


class RewriteHookTest(unittest.TestCase):
    """rewrite_types.rewrite の無料モデル先の書き方と、ゲートの前の条件（通信しないところだけ）"""

    def test_default_rewrite_is_unchanged(self):
        import inspect  # noqa: PLC0415

        import rewrite_types as rt  # noqa: PLC0415

        sig = inspect.signature(rt.rewrite)
        self.assertFalse(sig.parameters["free_first"].default)
        self.assertEqual(sig.parameters["write_purpose"].default, "core")
        self.assertIsNone(sig.parameters["accept"].default)


if __name__ == "__main__":
    unittest.main()
