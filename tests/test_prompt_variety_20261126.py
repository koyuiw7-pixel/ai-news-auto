"""2026-11-26 オーナーの判断（台帳 A78）: 検索の訪問が減ったのは GPT の力ではなく、こちらの指示（プロンプト・決まり）のせい。

記事を書く段の指示から、記事を同じ形・薄い形にする決まりを外し、読者の問いに答える決まりを先に置く。
事実の決まり（資料に無いことは書かない・式の答えはプログラムが確かめる）はそのまま。

見つけた問題（11/18 以降の記事 444本と 11/10〜17 の 741本の比較）:
1. 「計算は自分でしない」と「式つきの計算は書いてよい」が食い違い、式つきの計算例が Muse の記事で 20% → 0% になった
2. 社会・行政の決まり「個別の事情で扱いが変わることを明記する」で、「個別の事情によって変わります」の締めが Muse の記事で 1% → 36%
3. 問いの形の Muse の題名 13本のうち 9本が「〇〇は△△　対象と申告書」の平らな形に言い換えられた
4. 「見出しに日本を入れる（必須・無いと作り直し）」は 2026-11-08 から公開も検索も止めないのに残り、国内の話題に「日本の〜」の見出し（11% → 31%）
5. 「見出しは1,000字に1つまで」（2026-11-08 に外した決まり）が文体の指示に残り、型の「数の上限は無い」と食い違っていた
6. SNS の決まり（約90行）が記事の指示の末尾に区切りなく続き、1行目の型の指示も「必ず呼びかけ」と「それ以外から選ぶ」が食い違っていた
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import article_style  # noqa: E402
import calc_facts  # noqa: E402
import headline_normalize as hn  # noqa: E402
import muse_articles  # noqa: E402
import news_types as nt  # noqa: E402
import own_view  # noqa: E402
import quality  # noqa: E402
import threads_hooks  # noqa: E402
import web_articles as w  # noqa: E402


class CalcRuleTest(unittest.TestCase):
    def test_writer_may_show_simple_formulas(self):
        note = w.WEB_SOURCE_NOTE
        self.assertIn("自分でしない", note)  # 割合・増減率は今までどおり計算済みの数字だけ
        self.assertIn("式をそのまま書き", note)
        self.assertIn("計算例は削らない", note)
        self.assertNotIn("（自分で計算しない）", own_view.PROMPT_RULE)
        self.assertIn("式を書いて「（サイソク編集部の計算）」", own_view.PROMPT_RULE)

    def test_gate_still_checks_the_formula(self):
        source = "令和7年分の基礎控除は68万円。令和8年分の基礎控除は104万円。"
        ok = {"title": "基礎控除", "body": "控除は104万円−68万円＝36万円増えます（サイソク編集部の計算）。"}
        self.assertEqual(quality.number_problems(ok, source), [])
        self.assertTrue(calc_facts.bad_expressions("104万円−68万円＝40万円（サイソク編集部の計算）"))
        made_up = {"title": "基礎控除", "body": "還付は7万3,500円増えます。"}
        self.assertTrue(quality.number_problems(made_up, source))


class FillerRuleTest(unittest.TestCase):
    def test_public_genre_does_not_order_the_hedge(self):
        persona = w.GENRES_BY_SLUG["public"].persona
        self.assertNotIn("個別の事情で扱いが変わることを明記する", persona)
        self.assertIn("決まり文句で段落や記事を締めない", persona)

    def test_own_view_bans_generic_closing(self):
        self.assertIn("個別の事情によって変わります", own_view.PROMPT_RULE)  # 禁止の例として
        self.assertIn("どの記事にも書ける文で章を埋めない", own_view.PROMPT_RULE)


class StructureRuleTest(unittest.TestCase):
    def test_every_type_starts_with_the_reader_question(self):
        for key in nt.TYPES:
            block = nt.prompt_block(key)
            with self.subTest(key=key):
                self.assertTrue(block.startswith(nt.READER_FIRST_RULE))
                self.assertIn("入れ替え・まとめ・省略してよい", block)
                self.assertNotIn("無いと公開前の門で作り直し", block)
                self.assertNotIn("（必須。例", block)

    def test_no_stale_heading_cap(self):
        import main as m  # noqa: PLC0415

        self.assertNotIn("1,000字に1つまで", m.SYSTEM_INSTRUCTION_BASE)
        self.assertNotIn("1,000字に1つまで", article_style.STYLE_PROMPT)


class TitleRuleTest(unittest.TestCase):
    def test_question_titles_are_a_listed_type(self):
        self.assertIn("10) 読者が検索する問い＋答え", hn.TITLE_STYLE_PROMPT)
        self.assertIn("平らな形に言い換えない", hn.TITLE_STYLE_PROMPT)
        self.assertIn("1文目でその答えを", article_style.LEDE_RULE)

    def test_muse_keeps_question_titles_and_formulas(self):
        note = muse_articles.MUSE_DRAFT_NOTE
        self.assertIn("問いの形を残す", note)
        self.assertIn("式つきの計算", note)
        self.assertIn("原稿の長さは保つ", note)


class SnsBlockTest(unittest.TestCase):
    def test_sns_rules_are_fenced_and_consistent(self):
        block = threads_hooks.prompt_block(["callout"])
        self.assertTrue(block.startswith("# ここから下は SNS の欄"))
        self.assertIn("必ず呼びかけ型", block)
        self.assertIn("1行目は呼びかけの形のまま", block)


class WordingTest(unittest.TestCase):
    def test_new_rules_follow_owner_words(self):
        # MUSE_DRAFT_NOTE は「「｜」は使わない」という禁止の文を前から含むので、新しく書いた決まりだけを見る
        for text in (nt.READER_FIRST_RULE, own_view.PROMPT_RULE, w.WEB_SOURCE_NOTE):
            self.assertNotIn("｜", text)
            self.assertNotIn("ざっくり", text)


if __name__ == "__main__":
    unittest.main()
