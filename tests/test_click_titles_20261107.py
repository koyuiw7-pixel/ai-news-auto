"""2026-11-07 オーナー承認（台帳 A50）: 検索でクリックされる見出しの決まりを、新しい記事の見出しを作るところ
（記事を書くプロンプト・書き出す前の見出しの手直し・使い方ガイド）に入れる。外部への通信なし。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import headline_normalize as hn  # noqa: E402
import rewrite_titles  # noqa: E402

LEDE = "IPAは11月6日、個人情報が漏えいしたときに最初の72時間で行う手順をまとめました。"


class ClickTitleRulesTest(unittest.TestCase):
    def test_prompt_has_the_four_rules_and_breaking_exception(self):
        p = hn.TITLE_STYLE_PROMPT
        for needle in ("台帳 A50", "発表した組織（官公庁・団体・会社）を主語にしない", "最初の15字", "具体的な数字を1つ",
                       "「〜とは？〜を解説」の決まり文句は使わない", "速報"):
            self.assertIn(needle, p)
        self.assertNotIn("{", p)

    def test_org_subject_is_flagged_but_not_for_breaking(self):
        rec = {"title": "IPAが個人情報の漏えい対策を公開", "lede": LEDE}
        self.assertTrue(any("組織が主語" in x for x in hn.click_problems(rec)))
        self.assertEqual(hn.click_problems({**rec, "breaking": True}), [])
        good = {"title": "個人情報が漏れたら最初の72時間ですること　IPAが手順を公開", "lede": LEDE}
        self.assertEqual(hn.click_problems(good), [])
        self.assertTrue(any("組織が主語" in x for x in hn.click_problems({"title": "厚労省、遺族年金の調査結果を公表", "lede": ""})))

    def test_number_required_when_source_has_one(self):
        self.assertTrue(any("数字" in x for x in hn.click_problems({"title": "漏えいしたときの手順　IPAがまとめ直し", "lede": LEDE})))
        self.assertEqual(hn.click_problems({"title": "ゆうちょの手数料が変わる　対象と時期", "lede": "数字の無いリード"}), [])

    def test_announcement_date_is_not_the_number(self):
        """発表した日（「11月6日に発表」）は読む人に役立つ数字に数えない。要請・指示も組織が主語の形"""
        rec = {"title": "Amazonの買い物AIがテキストで依頼可能に　米国で招待制", "lede": "Amazonは11月6日に発表しました。"}
        self.assertEqual(hn.click_problems(rec), [])
        self.assertTrue(any("組織が主語" in x for x in hn.click_problems({"title": "総務省、事業者に不正アクセス対策の徹底を要請", "lede": ""})))

    def test_template_explain_is_a_title_problem(self):
        for bad in ("ChatGPTとは？使い方と料金を解説", "新NISAの使い方を解説"):
            self.assertTrue(any("決まり文句" in x for x in hn.title_problems(bad)), bad)
        self.assertFalse(any("決まり文句" in x for x in hn.title_problems("Geminiの無料版、使える回数が1日50回に")))

    def test_write_article_sends_click_failures_to_fix_one(self):
        rec = {"slug": "ipa-x", "title": "IPAが個人情報の漏えい対策を公開", "lede": LEDE, "highlights": [], "body": LEDE}
        with patch.object(rewrite_titles, "_ask", return_value={"ipa-x": {"title": "個人情報が漏えいしたら最初の72時間で行う手順　IPAがまとめ", "seo_title": ""}}), \
                patch.object(rewrite_titles, "llm_grounding_problems", return_value=[]):
            note = rewrite_titles.fix_one(rec)
        self.assertIn("見出しを書き直した", note)
        self.assertTrue(rec["title"].startswith("個人情報が漏えいしたら"))
        # 組織が主語に戻した案は採らない
        rec2 = {"slug": "ipa-y", "title": "IPAが個人情報の漏えい対策を公開", "lede": LEDE, "highlights": [], "body": LEDE}
        with patch.object(rewrite_titles, "_ask", return_value={"ipa-y": {"title": "IPAが72時間の漏えい対応の手順を公開", "seo_title": ""}}), \
                patch.object(rewrite_titles, "llm_grounding_problems", return_value=[]):
            self.assertIn("不合格", rewrite_titles.fix_one(rec2))
        main_src = (ROOT / "scripts" / "main.py").read_text("utf-8")
        self.assertIn("headline_normalize.click_problems(record)", main_src)

    def test_about_title_without_leading_name_goes_to_fix_one(self):
        """2026-11-11: 「…資産に変える「ナレッジ スパイン」とは」が書き出しの門を通った（台帳 A68 ⑤ は指示文だけだった）"""
        body = "AIエージェントを業務に使う企業は、教訓を共有できます。\n\n「ナレッジ スパイン」は、教訓を保存・更新する共有システムです。"
        rec = {"slug": "spine-x", "title": "AIエージェントを自社特有の資産に変える「ナレッジ スパイン」とは", "lede": "202社を調査しました。",
               "highlights": [], "body": body}
        self.assertTrue(rewrite_titles.about_name_problems(rec))
        # 本文の最初の1文に名前が無いのに「とは」を残した案は採らない
        with patch.object(rewrite_titles, "_ask", return_value={"spine-x": {"title": "「ナレッジ スパイン」とは　AIエージェントの教訓を共有、202社を調査", "seo_title": ""}}), \
                patch.object(rewrite_titles, "llm_grounding_problems", return_value=[]):
            self.assertIn("不合格", rewrite_titles.fix_one(dict(rec)))
        # 「とは」を使わない案、または本文の最初の1文に名前があるときの名前が先の案は採る
        with patch.object(rewrite_titles, "_ask", return_value={"spine-x": {"title": "AIエージェントの教訓を「ナレッジ スパイン」で共有　202社を調査", "seo_title": ""}}), \
                patch.object(rewrite_titles, "llm_grounding_problems", return_value=[]):
            self.assertIn("見出しを書き直した", rewrite_titles.fix_one(dict(rec)))
        named = {**rec, "slug": "spine-y", "body": "「ナレッジ スパイン」は、教訓を保存・更新する共有システムです。"}
        with patch.object(rewrite_titles, "_ask", return_value={"spine-y": {"title": "「ナレッジ スパイン」とは　AIエージェントの教訓を共有、202社を調査", "seo_title": ""}}), \
                patch.object(rewrite_titles, "llm_grounding_problems", return_value=[]):
            self.assertIn("見出しを書き直した", rewrite_titles.fix_one(named))
        self.assertEqual(rewrite_titles.about_name_problems(named), [])
        self.assertIn("rewrite_titles.about_name_problems(record)", (ROOT / "scripts" / "main.py").read_text("utf-8"))

    # ---- 書き直した見出しの根拠（2026-11-07 コーディネーター指摘: 例1が「個人情報が狙われる」を作り、事業者を事業所に変えた）
    SOUMU = {"slug": "soumu-x", "title": "総務省、事業者に不正アクセス対策の徹底を要請　AI悪用の侵入も指摘",
             "lede": "総務省は11月6日、事業者に不正アクセス対策の徹底を求める注意喚起を出しました。", "highlights": [],
             "body": "AIを悪用した侵入の手口も指摘しています。"}

    def test_sample1_invented_words_are_rejected(self):
        bad = "個人情報が狙われる不正アクセス対策を徹底　総務省が11月6日に事業所へ要請"
        problems = rewrite_titles.check_title(dict(self.SOUMU), bad)
        self.assertTrue(any("個人情報" in p and "事業所" in p for p in problems), problems)
        self.assertEqual(rewrite_titles.check_title(dict(self.SOUMU), "不正アクセス対策の徹底を事業者に要請　AI悪用の侵入も（総務省）"), [])

    def test_ungrounded_rewrite_keeps_original_title(self):
        rec = dict(self.SOUMU)
        original = rec["title"]
        with patch.object(rewrite_titles, "_ask", return_value={"soumu-x": {"title": "個人情報が狙われる不正アクセス対策を徹底　総務省が11月6日に事業所へ要請", "seo_title": ""}}):
            note = rewrite_titles.fix_one(rec)
        self.assertIn("元の見出しのまま", note)
        self.assertEqual(rec["title"], original)

    def test_llm_grounding_gate(self):
        rec = dict(self.SOUMU)
        original = rec["title"]
        good = "不正アクセス対策の徹底を事業者に要請　AI悪用の侵入も（総務省）"
        with patch.object(rewrite_titles, "_ask", return_value={"soumu-x": {"title": good, "seo_title": ""}}), \
                patch.object(rewrite_titles.llm, "generate_json", return_value=({"grounded": False, "unsupported": ["侵入も"]}, "m")):
            self.assertIn("根拠が無い", rewrite_titles.fix_one(rec))
        self.assertEqual(rec["title"], original)
        # 確かめられなかったときも元の見出しのまま
        with patch.object(rewrite_titles, "_ask", return_value={"soumu-x": {"title": good, "seo_title": ""}}), \
                patch.object(rewrite_titles.llm, "generate_json", side_effect=RuntimeError("down")):
            self.assertIn("元の見出しのまま", rewrite_titles.fix_one(rec))
        self.assertEqual(rec["title"], original)
        with patch.object(rewrite_titles, "_ask", return_value={"soumu-x": {"title": good, "seo_title": ""}}), \
                patch.object(rewrite_titles.llm, "generate_json", return_value=({"grounded": True, "unsupported": []}, "m")):
            self.assertIn("見出しを書き直した", rewrite_titles.fix_one(rec))
        self.assertEqual(rec["title"], good)

    def test_evergreen_title_rules(self):
        src = (ROOT / "scripts" / "evergreen.py").read_text("utf-8")
        self.assertIn("台帳 A50", src)
        import evergreen  # noqa: PLC0415
        data = {"title": "Midjourneyとは？使い方と料金をわかりやすく解説します", "seo_title": "x"}
        self.assertTrue(any("決まり文句" in p for p in evergreen.style_notes(data)))


if __name__ == "__main__":
    unittest.main()
