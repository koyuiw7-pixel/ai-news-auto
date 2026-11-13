"""2026-11-13: 発言の引用は「報道の文の写し」に数えない（scripts/muse_articles.py の mask_exempt_quotes・repair_press_copies）。

きっかけ: 消費税減税法案の記事が、首相の国会答弁（「…現役勤労者に占める割合を…」）を「」で引用しただけで見送りになった。
同じ答弁は報道の記事にもそのまま載るので、30字の写しの門に当たっていた。だれの発言かを書いた引用は、報道機関の文の写しではない。

守ること:
- だれが述べたかを書いた「」『』の引用は、写しの門の前に外す（同じ文に「〜は「…」と述べた／答弁した／としている」「〜によると「…」」。
  引用だけの文は、同じ段落の直前・直後の文に発言の動詞があるとき）
- 1つ120字まで・記事全体で3つまで。超えた引用・だれの発言か書いていない引用は今までどおり写しとして見る
- 引用でない所の30字の写しは、見送りの前に、その所だけ言い換えさせる（quality.surgical_fix に同じ所をそのまま渡す）。
  言い換えても残れば今までどおり作り直し → 見送り
- 報道の出典が無い記事は何も変わらない
ネット・LLM を使わない。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import easy_version  # noqa: E402
import llm  # noqa: E402
import main as m  # noqa: E402
import muse_articles as ma  # noqa: E402
import quality  # noqa: E402
import web_articles as w  # noqa: E402
import test_muse_press_sources_20261113 as base  # noqa: E402

CAS = "https://www.cas.go.jp/jp/seisaku/shouhizei_zeigakukoujo/index.html"
NHK = "https://news.web.nhk/newsweb/na/nd-20261113de75111"
ANSWER = "支援金の対象については、現役勤労者に占める割合を見ながら、制度の設計を丁寧に進めていきたいと考えております"
SECOND = "財源については、歳出の見直しと税収の上振れ分を充てることを基本に、年末までに具体的な案をお示しします"
THIRD = "食料品の値上がりが家計を圧迫している現状を重く受け止め、できるだけ早く負担を軽くする必要があります"
FOURTH = "給付の方法については、自治体の事務の負担が重くならないよう、既存の仕組みを最大限に活用してまいります"
PROSE = "法案は衆議院の特別委員会で審議が続いていて、与党は今の国会での成立を目指す方針を改めて確認しました"
CAS_TEXT = "2027年4月1日から2年間、飲食料品の消費税率を1%とします。" + "法律案の概要の説明です。" * 20
NHK_TEXT = (f"首相は衆議院の特別委員会で「{ANSWER}」と答弁しました。財務大臣は「{SECOND}」と述べました。"
            f"首相は「{THIRD}」とも述べました。総務大臣は「{FOURTH}」と説明しました。{PROSE}。") + "国会の動きを伝える記事です。" * 20
SOURCES = [base.src(CAS, CAS_TEXT, name="内閣官房"), base.src(NHK, NHK_TEXT, "NHK")]
OFFICIAL_ONLY = [base.src(CAS, CAS_TEXT, name="内閣官房")]
LONG = "、".join([ANSWER, SECOND, THIRD])  # 120字を超える引用
LONG_TEXT = f"首相は「{LONG}」と答弁しました。" + "国会の動きを伝える記事です。" * 20


def record(body: str, **kw) -> dict:
    out = {"title": "消費税減税法案の審議はどこまで進んだか", "lede": "食料品の消費税率を1%にする法案が審議されています。",
           "body": body, "easy": "", "highlights": [], "threadsPost": ""}
    out.update(kw)
    return out


def copy_problems(rec: dict, sources: list[dict] = SOURCES) -> list[str]:
    return [p for p in ma.press_problems(rec, sources) if "写している" in p]


class AttributedQuoteTest(unittest.TestCase):
    def test_limits(self):
        self.assertEqual((ma.PRESS_COPY_MIN, ma.QUOTE_EXEMPT_MAX, ma.QUOTE_EXEMPT_CHARS), (30, 3, 120))

    def test_attributed_quote_of_the_diet_answer_passes(self):
        """きっかけの形: 首相の答弁を「」で引用し、同じ文にだれが述べたかがある"""
        for sentence in (f"首相は13日の衆議院の特別委員会で「{ANSWER}」と答弁した。",
                         f"首相は「{ANSWER}」と述べました。",
                         f"首相は『{ANSWER}』と国会で説明した。",
                         f"首相は「{ANSWER}」としている。",
                         f"NHKによると、首相は「{ANSWER}」と話した。",
                         f"首相官邸によると「{ANSWER}」。"):
            with self.subTest(sentence=sentence):
                rec = record(f"## 国会の答弁\n\n{sentence}法案の柱は税率1%です。\n")
                self.assertEqual(ma.press_problems(rec, SOURCES), [])
                self.assertEqual(ma.press_copy_scan(rec, NHK_TEXT)[1], [quality._norm(ANSWER)])  # noqa: SLF001

    def test_quote_sentence_attributed_by_the_sentence_before_or_after(self):
        for body in (f"首相は特別委員会でこう答弁した。「{ANSWER}」。法案の柱は税率1%です。\n",
                     f"税率は1%です。「{ANSWER}」。首相は特別委員会でそう述べた。\n"):
            with self.subTest(body=body):
                self.assertEqual(copy_problems(record(body)), [])

    def test_attribution_in_another_paragraph_does_not_count(self):
        body = f"首相は特別委員会でこう答弁した。\n\n「{ANSWER}」。\n\n法案の柱は税率1%です。\n"
        self.assertTrue(copy_problems(record(body)))

    def test_unattributed_quote_fails(self):
        for body in (f"## 国会\n\n「{ANSWER}」。法案の柱は税率1%です。\n",
                     f"## 国会\n\n対象は「{ANSWER}」という形で決まる見通しです。\n",
                     f"## 国会\n\n対象は「{ANSWER}」という説明は公式の資料にありません。\n",
                     f"## 国会\n\n法案の柱は税率1%です。その中身は「{ANSWER}」。対象はこれから決まります。\n"):
            with self.subTest(body=body):
                got = copy_problems(record(body))
                self.assertEqual(len(got), 1)
                self.assertIn("報道の文をそのまま写している", got[0])

    def test_quoting_does_not_excuse_copied_text_outside_the_quote(self):
        rec = record(f"首相は「{ANSWER}」と答弁した。{PROSE}。\n")
        hits, exempt = ma.press_copy_scan(rec, NHK_TEXT)
        self.assertEqual(len(exempt), 1)
        self.assertEqual([(field, spans) for field, _sentence, spans in hits], [("body", [PROSE])])
        self.assertTrue(copy_problems(rec))

    def test_fourth_quote_is_checked_as_before(self):
        three = f"首相は「{ANSWER}」と答弁した。財務大臣は「{SECOND}」と述べた。首相は「{THIRD}」とも述べた。"
        self.assertEqual(copy_problems(record(three + "\n")), [])
        rec = record(three + f"総務大臣は「{FOURTH}」と説明した。\n")
        hits, exempt = ma.press_copy_scan(rec, NHK_TEXT)
        self.assertEqual(len(exempt), 3)
        self.assertEqual(len(hits), 1)
        self.assertIn(FOURTH[:20], hits[0][1])
        self.assertTrue(copy_problems(rec))

    def test_same_quote_in_lede_and_body_counts_once(self):
        three = f"首相は「{ANSWER}」と答弁した。財務大臣は「{SECOND}」と述べた。首相は「{THIRD}」とも述べた。"
        rec = record(three + "\n", lede=f"首相は「{ANSWER}」と答弁した。", easy=f"首相は「{THIRD}」と述べました。",
                     highlights=[f"財務大臣は「{SECOND}」と述べた"])
        self.assertEqual(copy_problems(rec), [])
        self.assertEqual(len(ma.press_copy_scan(rec, NHK_TEXT)[1]), 3)

    def test_quote_longer_than_120_chars_is_not_exempt(self):
        self.assertGreater(len(LONG), ma.QUOTE_EXEMPT_CHARS)
        sources = [SOURCES[0], base.src(NHK, LONG_TEXT, "NHK")]
        self.assertTrue(copy_problems(record(f"首相は「{LONG}」と答弁した。\n"), sources))
        short = LONG[:ma.QUOTE_EXEMPT_CHARS]
        self.assertEqual(copy_problems(record(f"首相は「{short}」と答弁した。\n"), sources), [])

    def test_quote_that_does_not_overlap_uses_no_allowance(self):
        rec = record("首相は「検討を進める」と述べた。担当者は「準備中です」と話した。\n")
        self.assertEqual(ma.press_copy_scan(rec, NHK_TEXT), ([], []))

    def test_exempt_quotes_are_logged(self):
        rec = record(f"首相は「{ANSWER}」と答弁した。\n")
        with mock.patch.object(ma, "log") as logged:
            self.assertEqual(ma.ensure_press_attribution(rec, SOURCES), [])
        lines = [c.args[0] for c in logged.call_args_list]
        self.assertTrue(any("発言の引用は写しに数えない" in line and "現役勤労者に占める割合" in line for line in lines), lines)

    def test_prompt_tells_the_writer_how_to_quote(self):
        self.assertIn("1つ120字まで・記事全体で3つまで", ma.MUSE_PRESS_NOTE)


class CopySpanTest(unittest.TestCase):
    def test_exact_overlap_is_returned_in_the_article_s_own_characters(self):
        text = f"一方で、{PROSE[:20]}　{PROSE[20:]}と伝えられています。次の文は関係ありません。"
        hits = ma.press_copy_hits(text, NHK_TEXT)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][1], [f"{PROSE[:20]}　{PROSE[20:]}"])  # 間の空白は記事のまま。前後の「一方で、」「と伝えられています」は入らない

    def test_agrees_with_the_old_sentence_check(self):
        for text in (f"{PROSE}。", "NHKによると、法案の審議は続いています。", f"## 見出し\n\n- {PROSE[:35]}\n"):
            with self.subTest(text=text):
                self.assertEqual(bool(ma.press_copy_hits(text, NHK_TEXT)), bool(ma.press_copies(text, NHK_TEXT)))


DATA = {"title": "消費税減税法案の審議はどこまで進んだか", "genre": "お金", "notes": "", "body": "## 国会\n\n本文。"}
OK = {"ok": True, "soft": False, "score": 95, "problems": [], "fact": {"grounded": True, "score": 95, "problems": []}}
QUOTED = {"title": DATA["title"], "lede": "食料品の消費税率を1%にする法案が審議されています。", "threadsPost": "消費税の法案、国会で審議中。",
          "body": f"## 国会の答弁\n\n首相は特別委員会で「{ANSWER}」と答弁した。\n"}
COPIED = {**QUOTED, "body": f"## 国会の答弁\n\n首相は特別委員会で「{ANSWER}」と答弁した。{PROSE}。\n"}
REPHRASED = {**QUOTED, "body": f"## 国会の答弁\n\n首相は特別委員会で「{ANSWER}」と答弁した。与党は今国会で成立させたい考えです。\n"}


def run_build(fetched: list[dict], drafts: list[dict], fixes: list):
    """build_article を、LLM・記事の組み立て・品質の門を差し替えて動かす。（結果, 指示文, surgical_fix に渡した指摘, 事実確認の回数, ログ）"""
    prompts: list[str] = []
    fix_calls: list[list[str]] = []
    made = iter(drafts)
    results = iter(fixes)

    def fake_generate(system, prompt, schema, **kwargs):
        prompts.append(prompt)
        return {"is_relevant": True}, "stub-model"

    def fake_record(item, draft, page, model, voice, bundle):
        return {"slug": "shouhizei", "sourceType": "web", "sourceUrl": item["url"], "sourceName": item["source_name"],
                "channelSlug": item["source_slug"], "genreSlug": "lifestyle", "disclaimer": "x", **next(made)}

    def fake_fix(record, source, kind, problems, context=""):
        fix_calls.append(list(problems))
        result = next(results)
        return ({**record, **result}, {**OK, "fixed_by": "stub"}) if isinstance(result, dict) else result

    patches = [
        mock.patch.object(w, "compose_with_facts", return_value=("lifestyle", "system", "＜指示＞", {}, "news", "", {})),
        mock.patch.object(m, "pick_voice", return_value=("v1", "声")),
        mock.patch.object(ma.source_date, "check", return_value=[]), mock.patch.object(ma.source_date, "past_change", return_value=[]),
        mock.patch.object(llm, "generate_json", side_effect=fake_generate),
        mock.patch.object(w, "build_web_record", side_effect=fake_record),
        mock.patch.object(w, "pre_gate"), mock.patch.object(w, "publish_blocked", return_value=None),
        mock.patch.object(w, "finalize_facts"), mock.patch.object(w, "stamp_times"),
        mock.patch.object(ma.own_view, "ensure"), mock.patch.object(ma.quality_bar, "ensure"),
        mock.patch.object(ma.quality_bar, "check", return_value={}), mock.patch.object(ma.quality_bar, "stamp"),
        mock.patch.object(ma.quality_bar, "summary_line", return_value="-"), mock.patch.object(easy_version, "ensure", return_value="-"),
        mock.patch.object(quality, "surgical_fix", side_effect=fake_fix),
    ]
    for p in patches:
        p.start()
    try:
        with mock.patch.object(quality, "evaluate", return_value=dict(OK)) as evaluate, mock.patch.object(ma, "log") as logged:
            result = ma.build_article(Path("20261113-お金-消費税減税法案の審議.md"), DATA, fetched)
    finally:
        for p in reversed(patches):
            p.stop()
    return result, prompts, fix_calls, evaluate.call_count, [c.args[0] for c in logged.call_args_list]


class BuildArticleTest(unittest.TestCase):
    def test_article_with_the_attributed_quote_is_published_without_any_repair(self):
        (status, rec), prompts, fixes, _evals, logs = run_build(SOURCES, [dict(QUOTED)], [])
        self.assertEqual(status, "ok", rec)
        self.assertIn(ANSWER, rec["body"])
        self.assertEqual((len(prompts), fixes), (1, []))
        self.assertTrue(any("発言の引用は写しに数えない" in line for line in logs))

    def test_copied_span_outside_quotes_is_sent_to_the_targeted_repair(self):
        (status, rec), prompts, fixes, evals, logs = run_build(SOURCES, [dict(COPIED)], [{"body": REPHRASED["body"]}])
        self.assertEqual(status, "ok", rec)
        self.assertEqual(rec["body"], REPHRASED["body"])
        self.assertEqual(len(prompts), 1)   # 作り直していない
        self.assertEqual(len(fixes), 1)
        self.assertEqual(len(fixes[0]), 1)  # 引用は渡さない。写した所だけ
        self.assertIn(f"「{PROSE}」", fixes[0][0])
        self.assertIn("この部分だけを", fixes[0][0])
        self.assertNotIn(ANSWER[:20], fixes[0][0])
        self.assertEqual(quality.flagged_spans(fixes[0]), [quality._norm(PROSE)])  # noqa: SLF001 - 直せないときに削る文も、この所だけ
        self.assertEqual(evals, 0)          # 言い換えの段が事実確認を済ませている（二重に確かめない）
        self.assertTrue(any("報道と同じ所を言い換えた" in line and PROSE[:20] in line for line in logs), logs)
        self.assertTrue(any("1 か所 → 残り 0 か所" in line for line in logs), logs)

    def test_still_copied_after_the_repair_is_regenerated_then_rejected(self):
        (status, why), prompts, fixes, _evals, _logs = run_build(SOURCES, [dict(COPIED) for _ in range(ma.MAX_ATTEMPTS)],
                                                                [{"body": COPIED["body"]}] * ma.MAX_ATTEMPTS)
        self.assertEqual(status, "reject")
        self.assertIn("報道の文をそのまま写している", why)
        self.assertEqual((len(prompts), len(fixes)), (ma.MAX_ATTEMPTS, ma.MAX_ATTEMPTS))
        self.assertIn("報道の文をそのまま写している", prompts[1])

    def test_repair_that_cannot_fix_falls_back_to_regeneration(self):
        (status, rec), prompts, fixes, _evals, _logs = run_build(SOURCES, [dict(COPIED), dict(REPHRASED)], [(None, "直したあとの確認に不合格")])
        self.assertEqual(status, "ok", rec)
        self.assertEqual((len(prompts), len(fixes)), (2, 1))

    def test_unattributed_quote_goes_to_the_repair_too(self):
        bare = {**QUOTED, "body": f"## 国会の答弁\n\n対象は「{ANSWER}」という形で決まる見通しです。\n"}
        (status, _), _prompts, fixes, _evals, _logs = run_build(SOURCES, [bare], [{"body": REPHRASED["body"]}])
        self.assertEqual(status, "ok")
        self.assertIn(ANSWER, fixes[0][0])

    def test_articles_without_press_sources_are_unchanged(self):
        self.assertEqual(ma.press_problems(record(f"{PROSE}。「{ANSWER}」。\n"), OFFICIAL_ONLY), [])
        self.assertEqual(ma.repair_press_copies(COPIED, OFFICIAL_ONLY, "資料", "news", ""), (COPIED, None))
        (status, rec), prompts, fixes, evals, logs = run_build(OFFICIAL_ONLY, [dict(COPIED)], [])
        self.assertEqual(status, "ok", rec)
        self.assertEqual(rec["body"], COPIED["body"])
        self.assertEqual((len(prompts), fixes, evals), (1, [], 1))
        self.assertFalse(any("写し" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
