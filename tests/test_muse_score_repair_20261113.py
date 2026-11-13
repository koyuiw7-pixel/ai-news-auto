"""2026-11-13: 事実確認の点数が合格点に少し届かない Muse の記事は、落とさずに校閲の指摘の文だけ直して確かめ直す。

きっかけ: 7日で22本が点数だけで落ち、13本は88点だった（手続きは90点以上）。作り直しの指示には「点数が足りない」しか渡っていなかった。
合格点（PROCEDURE_PASS_SCORE = 90）は変えない。直しても届かなければ今までどおり見送る。ネット・LLM を使わない。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import easy_version  # noqa: E402
import llm  # noqa: E402
import main as m  # noqa: E402
import muse_articles as ma  # noqa: E402
import quality  # noqa: E402
import web_articles as w  # noqa: E402

OBJECTION = "「申請は30日以内」→ 資料には期限の記載がない"


def verdict(score: int, problems: list[str] | None = None, ok: bool = True) -> dict:
    """quality.evaluate の形。合格（70点以上・創作なし）のとき problems は空で、校閲の指摘は fact に残る"""
    return {"ok": ok, "soft": False, "score": score, "problems": [] if ok else list(problems or []),
            "fact": {"grounded": ok, "score": score, "problems": list(problems or []), "fatal": not ok}}


class LiftScoreTest(unittest.TestCase):
    def test_pass_score_is_unchanged(self):
        self.assertEqual(ma.PROCEDURE_PASS_SCORE, 90)
        self.assertEqual(ma.MUSE_PASS_SCORE, 80)
        self.assertEqual(ma.pass_score("手続き"), 90)

    def test_objections_come_from_the_fact_check_even_when_ok(self):
        self.assertEqual(ma.score_objections(verdict(88, [OBJECTION])), [OBJECTION])
        self.assertEqual(ma.score_objections({"ok": True, "score": 88}), [])

    def test_repairs_the_flagged_sentences_and_stops_when_it_passes(self):
        calls = []

        def fix(record, source, kind, problems, context=""):
            calls.append(problems)
            return {**record, "body": "直した本文"}, verdict(93)

        with mock.patch.object(quality, "surgical_fix", side_effect=fix):
            record, out = ma.lift_score({"body": "元の本文"}, verdict(88, [OBJECTION]), 90, "資料", "news", "")
        self.assertEqual(calls, [[OBJECTION]])
        self.assertEqual((record["body"], out["score"]), ("直した本文", 93))

    def test_second_round_uses_the_new_objections(self):
        second = "「全員が対象」→ 資料では一部の人だけ"
        results = iter([verdict(89, [second]), verdict(92)])
        seen = []

        def fix(record, source, kind, problems, context=""):
            seen.append(problems)
            return {**record, "round": len(seen)}, next(results)

        with mock.patch.object(quality, "surgical_fix", side_effect=fix):
            record, out = ma.lift_score({}, verdict(88, [OBJECTION]), 90, "資料", "news", "")
        self.assertEqual(seen, [[OBJECTION], [second]])
        self.assertEqual((record["round"], out["score"]), (2, 92))

    def test_at_most_two_rounds(self):
        scores = iter([89, 89, 95])

        def fix(record, source, kind, problems, context=""):
            return dict(record), verdict(next(scores), [OBJECTION])

        with mock.patch.object(quality, "surgical_fix", side_effect=fix) as patched:
            _, out = ma.lift_score({}, verdict(85, [OBJECTION]), 90, "資料", "news", "")
        self.assertLessEqual(patched.call_count, ma.SCORE_REPAIR_ROUNDS)
        self.assertEqual(out["score"], 89)  # 上がらなかった2回目で止める。合格点には届いていない

    def test_keeps_the_original_when_the_repair_fails_or_gets_worse(self):
        original = {"body": "元の本文"}
        start = verdict(88, [OBJECTION])
        for result in ((None, "直したあとの確認に不合格"), ({"body": "悪くなった"}, verdict(84, [OBJECTION]))):
            with mock.patch.object(quality, "surgical_fix", return_value=result):
                record, out = ma.lift_score(original, start, 90, "資料", "news", "")
            self.assertIs(record, original)
            self.assertIs(out, start)
        with mock.patch.object(quality, "surgical_fix", side_effect=RuntimeError("LLM が使えない")):
            record, out = ma.lift_score(original, start, 90, "資料", "news", "")
        self.assertIs(record, original)

    def test_does_not_touch_low_scores_failed_checks_or_no_objections(self):
        with mock.patch.object(quality, "surgical_fix") as patched:
            ma.lift_score({}, verdict(79, [OBJECTION]), 90, "資料", "news", "")       # 80点未満は作り直しへ
            ma.lift_score({}, verdict(88, [OBJECTION], ok=False), 90, "資料", "news", "")  # 創作・矛盾ありは別の道（その場の手直し）
            ma.lift_score({}, verdict(88, []), 90, "資料", "news", "")                # 指摘が無ければ直す所が分からない
            ma.lift_score({}, verdict(91, [OBJECTION]), 90, "資料", "news", "")       # もう合格
        patched.assert_not_called()


DATA = {"title": "介護休業給付金は賃金の67%　通算93日まで3回に分けて受け取れる", "genre": "手続き", "notes": "",
        "body": "## 支給率\n介護休業給付金は休業開始時賃金日額の67%です。"}
FETCHED = [{"url": "https://www.mhlw.go.jp/kaigo", "name": "厚生労働省", "page": {"text": "67%"}, "published": None, "text": "67% 93日"}]


def run_build(evaluations: list[dict], fixes: list[tuple]):
    """build_article を、LLM・記事の組み立て・門を差し替えて動かす。（結果, LLM に渡した指示文, surgical_fix の呼び出し）"""
    prompts: list[str] = []
    evals = iter(evaluations)
    fix_results = iter(fixes)
    fix_calls: list[list[str]] = []

    def fake_generate(system, prompt, schema, **kwargs):
        prompts.append(prompt)
        return {"is_relevant": True}, "stub-model"

    def fake_fix(record, source, kind, problems, context=""):
        fix_calls.append(list(problems))
        return next(fix_results)

    def fake_record(item, draft, page, model, voice, bundle):
        return {"slug": "kaigo", "title": DATA["title"], "body": DATA["body"], "sourceType": "web"}

    composed = ("public", "system", "＜指示＞", {}, "news", "", {})
    patches = [
        mock.patch.object(w, "compose_with_facts", return_value=composed),
        mock.patch.object(m, "pick_voice", return_value=("v1", "声")),
        mock.patch.object(ma, "source_text_of", return_value="67% 93日"),
        mock.patch.object(ma.source_date, "check", return_value=[]),
        mock.patch.object(ma.source_date, "past_change", return_value=[]),
        mock.patch.object(llm, "generate_json", side_effect=fake_generate),
        mock.patch.object(w, "build_web_record", side_effect=fake_record),
        mock.patch.object(w, "pre_gate"), mock.patch.object(w, "publish_blocked", return_value=None),
        mock.patch.object(w, "finalize_facts"), mock.patch.object(w, "stamp_times"),
        mock.patch.object(ma.own_view, "ensure"), mock.patch.object(ma.quality_bar, "ensure"),
        mock.patch.object(ma.quality_bar, "check", return_value={}), mock.patch.object(ma.quality_bar, "stamp"),
        mock.patch.object(ma.quality_bar, "summary_line", return_value="-"),
        mock.patch.object(easy_version, "ensure", return_value="-"),
        mock.patch.object(quality, "evaluate", side_effect=lambda *a, **k: next(evals)),
        mock.patch.object(quality, "surgical_fix", side_effect=fake_fix),
    ]
    for p in patches:
        p.start()
    try:
        result = ma.build_article(Path("20261113-手続き-介護休業給付金.md"), DATA, FETCHED)
    finally:
        for p in reversed(patches):
            p.stop()
    return result, prompts, fix_calls


class BuildArticleScoreTest(unittest.TestCase):
    def test_88_is_repaired_and_published_when_it_reaches_90(self):
        (status, record), prompts, fixes = run_build([verdict(88, [OBJECTION])],
                                                     [({"slug": "kaigo", "title": DATA["title"], "body": "直した"}, verdict(92))])
        self.assertEqual(status, "ok")
        self.assertEqual(record["qualityScore"], 92)
        self.assertEqual(record["body"], "直した")
        self.assertEqual(fixes, [[OBJECTION]])
        self.assertEqual(len(prompts), 1)  # 作り直していない

    def test_still_below_90_after_repairs_is_rejected_with_the_objections(self):
        """直しても届かなければ今までどおり見送る（合格点は下げない）。作り直しの指示と理由には校閲の指摘の中身が入る"""
        stuck = (None, "直したあとの確認に不合格")
        (status, why), prompts, fixes = run_build([verdict(88, [OBJECTION]), verdict(88, [OBJECTION])], [stuck, stuck])
        self.assertEqual(status, "reject")
        self.assertIn("88 点（Muse の記事は 90 点以上）", why)
        self.assertIn(OBJECTION, why)
        self.assertEqual(len(prompts), ma.MAX_ATTEMPTS)
        self.assertNotIn(OBJECTION, prompts[0])
        self.assertIn(OBJECTION, prompts[1])  # 作り直しの指示に校閲の指摘が入る
        self.assertEqual(len(fixes), 2)

    def test_89_after_two_repair_rounds_is_not_published(self):
        (status, _), _, fixes = run_build(
            [verdict(85, [OBJECTION]), verdict(85, [OBJECTION])],
            [({"slug": "kaigo", "body": "a"}, verdict(87, [OBJECTION])), ({"slug": "kaigo", "body": "b"}, verdict(89, [OBJECTION]))] * 2)
        self.assertEqual(status, "reject")
        self.assertEqual(len(fixes), ma.MAX_ATTEMPTS * ma.SCORE_REPAIR_ROUNDS)

    def test_90_passes_without_any_repair(self):
        (status, record), _, fixes = run_build([verdict(90, [OBJECTION])], [])
        self.assertEqual((status, record["qualityScore"], fixes), ("ok", 90, []))


if __name__ == "__main__":
    unittest.main()
