"""2026-11-13 オーナー「落とすのは嘘だけ。書き方の問題は自動で直す」: 報道にしか無い数字に報道機関の名前が無い文は、
作り直し・見送りの前に、機械で名前を足す（scripts/muse_articles.py の repair_press_attribution）。

きっかけ: 消費税減税法案の解説（その日いちばん急ぎの記事）が、この門で続けて見送りになった。
- 本文の文「支援金の枠は年およそ6,000億円と示されているため、…」
- 見出し「## 財源は約5兆円とされ、まだ示されていません」
どちらも主要な報道機関の記事に裏付けのある数字で、抜けていたのは報道機関の名前だけ。

守ること:
- 足す名前は、その数字が実際に載っている報道機関（2つまで）。文はほかを変えない
- 見出し・表・題名は、後ろにかっこ書き（「（NHK）」）。長さの上限を超える欄は変えない（今までどおり LLM の作り直しへ）
- 同じ段落に、その数字の載っている報道機関の名前があれば、名前のある文として扱う（段落をまたぐと数えない）
- どの資料にも無い数字はここでは直さない（数字の門が今までどおり落とす）。30字の書き写しの門も変えない
ネット・LLM を使わない。
"""
from __future__ import annotations

import sys
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import muse_articles as ma  # noqa: E402
import muse_format as mf  # noqa: E402
import quality  # noqa: E402
import test_muse_press_sources_20261113 as base  # noqa: E402

CAS = "https://www.cas.go.jp/jp/seisaku/shouhizei_zeigakukoujo/index.html"
NHK = "https://www3.nhk.or.jp/nhkworld/news/20261106de71799/"
NTV = "https://news.ntv.co.jp/category/economy/7367b237e24b4bef9054c35d9eaebd0e"
JIJI = "https://www.jiji.com/jc/article?k=2026100901104&g=pol"
CAS_TEXT = ("2027年4月1日から2年間、飲食料品の消費税率を1%とし、1%相当分の範囲内で就業者負担軽減支援金を2027年度に先行導入します。"
            + "法律案の概要の説明です。" * 20)
NHK_TEXT = "法案は衆議院本会議で可決されました。減税にはおよそ5兆円の財源が必要とされています。" + "国会の動きを伝える記事です。" * 20
NTV_TEXT = "支援金は消費税の1%相当分、およそ6000億円の範囲内で給付します。" + "税制改正大綱を伝える記事です。" * 20
JIJI_TEXT = "支給が始まる所得の下限は給与収入で約53万円超などの案が例示されました。必要な財源は約5兆円です。" + "審議を伝える記事です。" * 20
src = base.src
SOURCES = [src(CAS, CAS_TEXT, name="内閣官房"), src(NHK, NHK_TEXT, "NHK"), src(NTV, NTV_TEXT, "日本テレビ")]
WITH_JIJI = SOURCES + [src(JIJI, JIJI_TEXT, "時事通信")]

SENTENCE = "支援金の枠は年およそ6,000億円と示されているため、対象を広げれば1人あたりの額は小さくなります。"
HEADING = "## 財源は約5兆円とされ、まだ示されていません"


def record(**kw) -> dict:
    out = {"title": "消費税減税法案の成立はいつ？ 食料品1%は2027年4月から", "lede": "食料品の消費税率を1%にする法案が審議されています。",
           "body": "## 法案の柱\n\n2027年4月1日から2年間、税率は1%です。\n", "easy": "", "highlights": [], "threadsPost": ""}
    out.update(kw)
    return out


class RealCasesTest(unittest.TestCase):
    def test_body_sentence_gets_the_outlet_that_carries_the_number(self):
        rec = record(body=f"## サイソクの見方\n\n今回の法案は柱だけが決まっています。{SENTENCE}どちらに倒れるかで変わります。\n")
        self.assertTrue(ma.press_problems(rec, SOURCES))
        done = ma.repair_press_attribution(rec, SOURCES)
        self.assertEqual([d[0] for d in done], ["body"])
        self.assertEqual(done[0][1], SENTENCE)
        # 6,000億円は日本テレビの記事にだけある（先頭の報道機関 NHK の名前を機械的に付けない）
        self.assertEqual(done[0][2], "日本テレビによると、" + SENTENCE)
        self.assertEqual(rec["body"], f"## サイソクの見方\n\n今回の法案は柱だけが決まっています。日本テレビによると、{SENTENCE}どちらに倒れるかで変わります。\n")
        self.assertEqual(rec["pressAttributionRepairs"], 1)
        self.assertEqual(ma.press_problems(rec, SOURCES), [])

    def test_heading_gets_a_short_parenthetical(self):
        rec = record(body=f"## 法案の柱\n\n税率は1%です。\n\n{HEADING}\n\n財源の中身はこれからです。\n")
        got = ma.press_problems(rec, SOURCES)
        self.assertIn("## 財源は約5兆円とされ", got[0])
        done = ma.repair_press_attribution(rec, SOURCES)
        self.assertEqual(done, [("body", HEADING, HEADING + "（NHK）")])
        self.assertIn(f"\n\n{HEADING}（NHK）\n\n財源の中身はこれからです。\n", rec["body"])
        self.assertEqual(ma.press_problems(rec, SOURCES), [])

    def test_two_outlets_are_both_named_and_more_are_shortened(self):
        rec = record(body=f"{HEADING}\n\n必要な財源は約5兆円です。\n")
        ma.repair_press_attribution(rec, WITH_JIJI)
        self.assertEqual(rec["body"], f"{HEADING}（NHK・時事通信）\n\nNHKと時事通信によると、必要な財源は約5兆円です。\n")
        three = WITH_JIJI + [src("https://www.asahi.com/articles/A.html", "財源は約5兆円。" + "続きです。" * 30, "朝日新聞")]
        rec = record(body=f"{HEADING}\n\n必要な財源は約5兆円です。\n")
        ma.repair_press_attribution(rec, three)
        self.assertEqual(rec["body"], f"{HEADING}（NHKなどの報道）\n\nNHKと時事通信などによると、必要な財源は約5兆円です。\n")
        self.assertEqual(ma.press_problems(rec, three), [])


class ShapesTest(unittest.TestCase):
    def fixed(self, body: str, sources=SOURCES) -> str:
        rec = record(body=body)
        ma.repair_press_attribution(rec, sources)
        self.assertEqual(ma.press_problems(rec, sources), [], rec["body"])
        return rec["body"]

    def test_already_attributed_sentences_are_untouched(self):
        for body in ("NHKは、減税には約5兆円の財源が必要とされると伝えています。",
                     "日本テレビは、支援金はおよそ6,000億円の範囲内で給付すると報じています。",
                     "必要な財源は約5兆円と報じられています。",
                     "NHKによると、法案は衆議院を通過しました。必要な財源は約5兆円だということです。"):
            rec = record(body=f"## 財源\n\n{body}\n")
            self.assertEqual(ma.repair_press_attribution(rec, SOURCES), [], body)
            self.assertEqual(rec["body"], f"## 財源\n\n{body}\n")
            self.assertNotIn("pressAttributionRepairs", rec)

    def test_outlet_named_in_the_same_paragraph_counts(self):
        # 同じ段落の前の文に、その数字の載っている報道機関の名前がある（言い切りの文でもよい）
        body = "## 財源\n\nNHKが国会の審議を伝えています。必要な財源は約5兆円です。政府は中身を示していません。\n"
        self.assertEqual(ma.press_problems(record(body=body), SOURCES), [])
        self.assertEqual(ma.repair_press_attribution(record(body=body), SOURCES), [])
        # 後ろの文に名前があるのも同じ段落
        self.assertEqual(ma.press_problems(record(body="## 財源\n\n必要な財源は約5兆円です。NHKが伝えました。\n"), SOURCES), [])

    def test_paragraph_must_name_an_outlet_that_carries_that_number(self):
        # 6,000億円は日本テレビの数字。同じ段落に NHK の名前があるだけでは足りない
        body = "## 支援金\n\nNHKが国会の審議を伝えています。支援金の枠は年およそ6,000億円です。\n"
        self.assertTrue(ma.press_problems(record(body=body), SOURCES))
        self.assertEqual(self.fixed(body), "## 支援金\n\nNHKが国会の審議を伝えています。日本テレビによると、支援金の枠は年およそ6,000億円です。\n")

    def test_another_paragraph_does_not_count(self):
        body = "## 財源\n\nNHKが国会の審議を伝えています。\n\n必要な財源は約5兆円です。\n"
        self.assertTrue(ma.press_problems(record(body=body), SOURCES))
        # 見出しの名前は、下の段落の文の名前にならない
        self.assertTrue(ma.press_problems(record(body="## NHKが伝えた財源\n\n必要な財源は約5兆円です。\n"), SOURCES))
        self.assertEqual(self.fixed(body), "## 財源\n\nNHKが国会の審議を伝えています。\n\nNHKによると、必要な財源は約5兆円です。\n")

    def test_bullets_tables_and_conjunctions(self):
        self.assertEqual(self.fixed("- 必要な財源は約5兆円です。\n- 税率は1%です。\n"), "- NHKによると、必要な財源は約5兆円です。\n- 税率は1%です。\n")
        self.assertEqual(self.fixed("- 財源: 約5兆円\n"), "- 財源: 約5兆円（NHK）\n")
        self.assertEqual(self.fixed("一方、必要な財源は約5兆円です。\n"), "一方、NHKによると、必要な財源は約5兆円です。\n")
        table = "| 項目 | 金額 |\n|---|---|\n| 財源 | 約5兆円 |\n| 税率 | 1% |\n"
        self.assertEqual(self.fixed(table), "| 項目 | 金額 |\n|---|---|\n| 財源 | 約5兆円（NHK） |\n| 税率 | 1% |\n")
        # 同じ段落で1か所に足せば、同じ報道機関の数字の続きの文には重ねて足さない
        self.assertEqual(self.fixed("必要な財源は約5兆円です。5兆円の中身は示されていません。\n"),
                         "NHKによると、必要な財源は約5兆円です。5兆円の中身は示されていません。\n")

    def test_other_fields_are_repaired_too(self):
        rec = record(lede="食料品の税率は1%に。必要な財源は約5兆円です。", highlights=["財源は約5兆円", "税率は1%"],
                     faq=[{"q": "財源はいくら？", "a": "約5兆円です。"}, {"q": "約5兆円はどこから？", "a": "NHKによると、まだ示されていません。"}],
                     todayActions=["約5兆円の財源の行方を見る"], workMoney={"points": ["枠はおよそ6,000億円です。"]},
                     threadsPost="食料品の消費税が1%に。\n\n必要な財源は約5兆円。年末までに示すとしています。", description="財源は約5兆円。")
        done = ma.repair_press_attribution(rec, SOURCES)
        self.assertEqual(ma.press_problems(rec, SOURCES), [])
        self.assertEqual(rec["lede"], "食料品の税率は1%に。NHKによると、必要な財源は約5兆円です。")
        self.assertEqual(rec["highlights"], ["財源は約5兆円（NHK）", "税率は1%"])
        self.assertEqual(rec["faq"][0], {"q": "財源はいくら？", "a": "NHKによると、約5兆円です。"})
        self.assertEqual(rec["faq"][1]["q"], "約5兆円はどこから？")  # 答えに名前がある問いは変えない（門と同じ見方）
        self.assertEqual(rec["todayActions"], ["約5兆円の財源の行方を見る（NHK）"])
        self.assertEqual(rec["workMoney"]["points"], ["日本テレビによると、枠はおよそ6,000億円です。"])
        self.assertTrue(rec["threadsPost"].startswith("食料品の消費税が1%に。\n\nNHKによると、必要な財源は約5兆円。"))
        self.assertEqual(rec["pressAttributionRepairs"], len(done))
        self.assertEqual(len(done), 7)


class LimitsTest(unittest.TestCase):
    def test_title_gets_a_parenthetical_only_when_it_fits(self):
        short = "消費税減税法案の財源は約5兆円、成立はいつ"
        rec = record(title=short)
        ma.repair_press_attribution(rec, SOURCES)
        self.assertEqual(rec["title"], short + "（NHK）")
        self.assertLessEqual(len(rec["title"]), mf.TITLE_MAX)
        self.assertLessEqual(len(rec["title"]), quality.TITLE_RANGE[1])
        long = "消費税減税法案の成立はいつになるのか、財源の約5兆円はどこから出すのかをやさしく整理する"
        self.assertGreater(len(long) + 5, mf.TITLE_MAX)
        rec = record(title=long)
        self.assertEqual(ma.repair_press_attribution(rec, SOURCES), [])
        self.assertEqual(rec["title"], long)                      # 上限を超えるなら変えない
        self.assertTrue(ma.press_problems(rec, SOURCES))          # → 今までどおり LLM の作り直しへ
        self.assertNotIn("pressAttributionRepairs", rec)

    def test_search_title_hook_and_post_limits(self):
        seo = "消費税減税法案の財源は約5兆円、成立時期は"  # 全角換算 21.5字 → かっこ書きで 26.5字
        rec = record(seoTitle=seo)
        ma.repair_press_attribution(rec, SOURCES)
        self.assertEqual(rec["seoTitle"], seo + "（NHK）")
        full = "消費税減税法案の財源は約5兆円、成立はいつになるのかを整理"  # 足すと全角30字を超える
        rec = record(seoTitle=full, threadsHook="食料品の消費税が1%になる法案、財源の約5兆円はどこから出すのだろうか", threadsPost="財源は約5兆円。" + "あ" * 470)
        self.assertEqual(ma.repair_press_attribution(rec, SOURCES), [])
        self.assertEqual((rec["seoTitle"], len(rec["threadsPost"])), (full, 478))
        self.assertEqual(len(ma.press_problems(rec, SOURCES)), 1)


class TruthRulesTest(unittest.TestCase):
    def test_number_in_no_source_is_not_touched_and_still_fails_the_number_gate(self):
        body = "## 財源\n\n必要な財源は約9兆円です。\n"
        rec = record(body=body)
        self.assertEqual(ma.repair_press_attribution(rec, SOURCES), [])
        self.assertEqual(rec["body"], body)
        source_text = ma.source_text_of(SOURCES, rec["title"])
        self.assertTrue([p for p in quality.number_problems(rec, source_text) if "9兆円" in p])

    def test_number_stated_as_another_bodys_announcement_is_not_repaired(self):
        # 発表元の取り違え（報道にしか無い数字を役所の発表として書いた）は、名前を足しても直らない → 作り直しへ
        body = "## 財源\n\n内閣官房によると、必要な財源は約5兆円です。\n"
        rec = record(body=body)
        self.assertEqual(ma.repair_press_attribution(rec, SOURCES), [])
        self.assertEqual(rec["body"], body)
        self.assertTrue(ma.press_problems(rec, SOURCES))

    def test_copy_gate_is_unchanged_by_the_repair(self):
        copied = "減税を実施するためには国と地方をあわせておよそ5兆円の財源が必要になると政府は説明しています。"
        sources = [SOURCES[0], src(NHK, copied + "国会の動きを伝える記事です。" * 20, "NHK")]
        rec = record(body=f"## 財源\n\n{copied}\n")
        self.assertEqual(len(ma.press_problems(rec, sources)), 2)  # 名前が無い ＋ 写し
        ma.repair_press_attribution(rec, sources)
        # 名前を足しても、報道の文の写しは写しのまま（30字の門は変えない）
        self.assertEqual(rec["body"], f"## 財源\n\nNHKによると、{copied}\n")
        got = ma.press_problems(rec, sources)
        self.assertEqual(len(got), 1)
        self.assertIn("そのまま写している", got[0])
        self.assertEqual(ma.PRESS_COPY_MIN, 30)

    def test_official_numbers_and_no_press_sources_need_nothing(self):
        rec = record(body="## 柱\n\n税率は1%です。必要な財源は約5兆円です。\n")
        self.assertEqual(ma.repair_press_attribution(rec, [src(CAS, CAS_TEXT, name="内閣官房")]), [])
        rec = record()
        self.assertEqual(ma.repair_press_attribution(rec, SOURCES), [])
        self.assertNotIn("pressAttributionRepairs", rec)


class BuildArticleTest(unittest.TestCase):
    DRAFT = {"title": base.DATA["title"], "lede": "NHKによると、円相場は一時160円台まで値下がりしました。", "threadsPost": "NHKによると円が一時160円台に。",
             "body": "## 円相場は一時160円台\n\n12日の市場の動きです。\n\n## 家計への影響\n\n円相場は一時160円台まで値下がりしました。\n"}

    def test_missing_attribution_is_repaired_without_another_llm_round(self):
        (status, rec), seen = base.run_build(base.MIXED, [dict(self.DRAFT)])
        self.assertEqual(status, "ok", rec)
        self.assertEqual(len(seen["prompts"]), 1)  # 作り直していない
        self.assertIn("## 円相場は一時160円台（NHK）\n", rec["body"])
        self.assertIn("NHKによると、円相場は一時160円台まで値下がりしました。", rec["body"])
        self.assertEqual(rec["pressAttributionRepairs"], 2)
        self.assertEqual(ma.press_problems(rec, base.MIXED), [])

    def test_repairs_are_logged_before_and_after(self):
        lines: list[str] = []
        with unittest.mock.patch.object(ma, "log", side_effect=lines.append):
            base.run_build(base.MIXED, [dict(self.DRAFT)])
        logged = [line for line in lines if "報道の名前を足した" in line]
        self.assertEqual(len(logged), 2)
        self.assertIn("「## 円相場は一時160円台」→「## 円相場は一時160円台（NHK）」", logged[0])
        self.assertIn("（body）", logged[0])

    def test_unrepairable_goes_to_the_llm_then_is_rejected(self):
        bad = {**self.DRAFT, "body": "## 円安\n\n財務省によると、午後5時時点では159円81銭でした。\n"}
        (status, why), seen = base.run_build(base.MIXED, [dict(bad), dict(bad)])
        self.assertEqual(status, "reject")
        self.assertIn("報道と分かる形で書いていない", why)
        self.assertEqual(len(seen["prompts"]), ma.MAX_ATTEMPTS)
        (status, rec), seen = base.run_build(base.MIXED, [dict(bad), dict(self.DRAFT)])
        self.assertEqual(status, "ok", rec)
        self.assertEqual(len(seen["prompts"]), 2)


if __name__ == "__main__":
    unittest.main()
