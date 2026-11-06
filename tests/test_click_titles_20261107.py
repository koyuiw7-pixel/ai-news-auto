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

    def test_template_explain_is_a_title_problem(self):
        for bad in ("ChatGPTとは？使い方と料金を解説", "新NISAの使い方を解説"):
            self.assertTrue(any("決まり文句" in x for x in hn.title_problems(bad)), bad)
        self.assertFalse(any("決まり文句" in x for x in hn.title_problems("Geminiの無料版、使える回数が1日50回に")))

    def test_write_article_sends_click_failures_to_fix_one(self):
        rec = {"slug": "ipa-x", "title": "IPAが個人情報の漏えい対策を公開", "lede": LEDE, "highlights": [], "body": LEDE}
        with patch.object(rewrite_titles, "_ask", return_value={"ipa-x": {"title": "個人情報が漏れたら72時間以内にすること　IPAが手順", "seo_title": ""}}):
            note = rewrite_titles.fix_one(rec)
        self.assertIn("見出しを書き直した", note)
        self.assertTrue(rec["title"].startswith("個人情報が漏れたら"))
        # 組織が主語に戻した案は採らない
        rec2 = {"slug": "ipa-y", "title": "IPAが個人情報の漏えい対策を公開", "lede": LEDE, "highlights": [], "body": LEDE}
        with patch.object(rewrite_titles, "_ask", return_value={"ipa-y": {"title": "IPAが72時間の漏えい対応の手順を公開", "seo_title": ""}}):
            self.assertIn("不合格", rewrite_titles.fix_one(rec2))
        main_src = (ROOT / "scripts" / "main.py").read_text("utf-8")
        self.assertIn("headline_normalize.click_problems(record)", main_src)

    def test_evergreen_title_rules(self):
        src = (ROOT / "scripts" / "evergreen.py").read_text("utf-8")
        self.assertIn("台帳 A50", src)
        import evergreen  # noqa: PLC0415
        data = {"title": "Midjourneyとは？使い方と料金をわかりやすく解説します", "seo_title": "x"}
        self.assertTrue(any("決まり文句" in p for p in evergreen.structural_problems(data, [])))


if __name__ == "__main__":
    unittest.main()
