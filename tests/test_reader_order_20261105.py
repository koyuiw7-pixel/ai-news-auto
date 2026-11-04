"""2026-11-05 オーナー承認の記事の質のピボット: 読者順の型（通信しない）

とろいも（Muse）の批評 out/muse/saisoku-article-quality-critique.md の型を、生成のプロンプトと公開前の門に入れた。台帳 docs/owner_rules.md の A45・W34。
  - 本文の順番: 結論（題名・リード）→ 読者個人への影響（見出しなしの最初の段落）→ 何が起きたか → まだ分からないこと → 企業向け（必要なときだけ）
  - 決まった見出し（「あなたへの影響」「何が起きたか」「契約企業の方へ」）はそのまま使わない
  - 数字は読者に分かる単位（「約77百万件」→「約7,700万件」）。煽りの言葉・感嘆符は使わない
  - よくある質問は本文のくり返しにしない（どの記事にもある問い・本文の写しの答えは外す。無ければ欄を出さない）
  - 専門用語の説明は1回だけ
  - 要点の番号は画面が付ける（頭の「1.」は外す。lib/list-number.ts と tests/test_list_number.cjs）
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import article_style as st  # noqa: E402
import calc_facts  # noqa: E402
import headline_normalize as hn  # noqa: E402
import news_types as nt  # noqa: E402
import number_units as nu  # noqa: E402
import quality  # noqa: E402

FIXED = ("arara-message-data-leak-second-report", "yucho-bank-matsui-securities-alliance")


def load(slug: str) -> dict:
    return json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))


def record(**changes) -> dict:
    rec = {
        "sourceType": "web",
        "title": "アララのメール配信で約7,700万件流出の恐れ　不審メールに注意",
        "lede": "メール配信サービスで、メールアドレス約7,700万件が持ち出された恐れがあります。不審メールは最大約713万通です。URLは開かずに削除してください。",
        "highlights": ["持ち出されたメールアドレスは約7,700万件で、件数はまだ精査中", "被害はサーバー97台に拡大", "再開の時期は未定"],
        "body": "メールを受け取る側の個人に関係するのは、不審メールです。\n\n## 被害はサーバー97台に拡大\n\n10月29日の第1報では1つのシステムだけでしたが、11月2日の第2報でサーバー97台に広がったと分かりました。",
        "faq": [],
    }
    rec.update(changes)
    return rec


class NumberUnitsTest(unittest.TestCase):
    """[A45] 数字は読者に意味の分かる単位で（百万 → 万・億）"""

    def test_converts_million_units(self):
        cases = {
            "約77百万件のメールアドレス": "約7,700万件のメールアドレス",
            "約 77 百万件": "約 7,700万件",
            "150百万人": "1億5,000万人",
            "3,500百万円": "35億円",
            "1.5百万台": "150万台",
            "0.25百万件": "25万件",
            "123百万ドル": "1億2,300万ドル",
        }
        for before, after in cases.items():
            with self.subTest(before=before):
                self.assertEqual(nu.natural_units(before), after)

    def test_leaves_natural_text_alone(self):
        for text in ("数百万人が利用", "（単位：百万円）", "約7,700万件", "100万トークンあたり3ドル", "百万円単位の表"):
            with self.subTest(text=text):
                self.assertEqual(nu.natural_units(text), text)
                self.assertEqual(nu.unnatural_units(text), [])

    def test_fact_check_accepts_the_converted_number(self):
        """資料が「約 77 百万件」でも、記事の「約7,700万件」は資料にある数字とみなす（[A16] の照合で落ちない）"""
        allowed = calc_facts.values("持ち出されたメールアドレスは、現時点の調査で約 77 百万件です。")
        found = [q for q in calc_facts.extract("約7,700万件") if calc_facts.checkable(q)]
        self.assertTrue(found and all(calc_facts.supported(q, allowed) for q in found))

    def test_autofix_and_title_normalizer_convert_every_field(self):
        rec = record(title="「アララメッセージ」で約77百万件のメール流出の恐れ", lede="約77百万件のメールアドレスが持ち出されました。",
                     highlights=["持ち出されたメールアドレスは約77百万件（精査中）"], body="件数は約77百万件です。",
                     faq=[{"q": "流出したアドレスは何件？", "a": "約77百万件です。人数ではありません。"}])
        st.autofix(rec)
        hn.apply(rec)
        text = json.dumps(rec, ensure_ascii=False)
        self.assertNotIn("百万件", text)
        self.assertIn("約7,700万件", rec["title"])
        self.assertIn("約7,700万件", rec["lede"])

    def test_gate_rejects_unnatural_units_left_in_text(self):
        problems = st.problems(record(body="持ち出されたメールアドレスは約77百万件です。"))
        self.assertTrue(any("分かりにくい数字の単位" in p for p in problems), problems)
        self.assertTrue(any("分かりにくい数字の単位" in p for p in hn.title_problems("約77百万件の流出の恐れ")))


class FaqTest(unittest.TestCase):
    """[A45] よくある質問は本文のくり返しにしない。無ければ欄を出さない"""

    def test_generic_questions_and_copied_answers_are_dropped(self):
        body = ("アララメッセージは、10月31日19時53分に停止が完了しました。\n\n"
                "再開は、侵入経路の特定、認証情報の全面変更、システムの安全性確認を行ったうえで判断されます。")
        rec = record(body=body, faq=[
            {"q": "アララメッセージの流出は、何が発表された？", "a": "11月2日の第2報で、約7,700万件のメールアドレスが持ち出された恐れがあると公表されました。"},
            {"q": "アララメッセージの前の発表と何が違う？", "a": "第1報は1システムでしたが、第2報ではサーバー97台に広がりました。"},
            {"q": "アララメッセージはいつ再開する？", "a": "再開は、侵入経路の特定、認証情報の全面変更、システムの安全性確認を行ったうえで判断されます。"},
            {"q": "自分のアドレスが含まれるか分かる？", "a": "アララは、対象かどうかを契約企業ごとに個別に連絡するとしています。個人向けの窓口は設けられていません。"},
        ])
        self.assertEqual(len(st.faq_repeat_rows(rec)), 3)
        self.assertTrue(any("よくある質問が本文のくり返し" in p for p in st.problems(rec)))
        st.autofix(rec)
        self.assertEqual([r["q"] for r in rec["faq"]], ["自分のアドレスが含まれるか分かる？"])
        self.assertFalse(any("よくある質問" in p for p in st.problems(rec)))

    def test_faq_is_optional_and_up_to_four(self):
        import web_articles as w

        rows = [{"q": f"新しい問い{i}は？", "a": f"答え{i}です。資料にある事実で答えます。"} for i in range(6)]
        self.assertEqual(len(w.clean_faq(rows[:1])), 1)  # 1問でも出す（本文に無い情報があるときだけ書く）
        self.assertEqual(len(w.clean_faq(rows)), 4)
        self.assertEqual(w.clean_faq([]), [])
        self.assertEqual(quality.faq_problems({"faq": rows[:1]}), [])
        self.assertIn("0〜4問", w.FAQ_TODAY_FIELD)
        self.assertIn("本文のくり返しにしない", w.FAQ_TODAY_FIELD)
        self.assertNotIn("何が発表された？／前と何が違う？", w.FAQ_TODAY_FIELD)  # どの記事にもある問いをすすめない

    def test_empty_faq_is_not_refilled(self):
        """空の FAQ は「書くことが無い」答え。fill_faq_actions は今日やることだけ書き足す（LLM を呼ばずに確かめる）"""
        import web_articles as w

        calls = []
        orig = w.llm.generate_json
        w.llm.generate_json = lambda *a, **k: (calls.append(a) or ({"faq": [{"q": "x？", "a": "y"}] * 3, "today_actions": []}, "test"))
        try:
            rec = {"genreSlug": "ai", "faq": [], "todayActions": ["公式発表で条件を確かめる", "自分の契約を見直す"], "body": "本文"}
            self.assertEqual(w.fill_faq_actions(rec), [])
            self.assertEqual(calls, [])
            self.assertEqual(rec["faq"], [])
        finally:
            w.llm.generate_json = orig

    def test_article_page_shows_a_single_faq(self):
        page = (ROOT / "app" / "articles" / "[slug]" / "page.tsx").read_text("utf-8")
        self.assertIn("articleFaq.length >= 1", page)
        self.assertNotIn("articleFaq.length >= 3", page)


class StructureAndToneTest(unittest.TestCase):
    """[A45] 読者順の型（順番はプロンプト、見出しの決まり文句・煽り・感嘆符・用語の2回目の説明は門）"""

    def test_boilerplate_reader_order_headings_are_rejected(self):
        for heading in ("あなたへの影響", "何が起きたか", "まだ分からないこと・続報", "契約企業の方へ"):
            with self.subTest(heading=heading):
                body = f"最初の段落です。\n\n## {heading}\n\n" + "本文の中身の文です。" * 30
                self.assertTrue(any("決まった型の見出し" in p for p in st.problems(record(body=body))))
        ok = "最初の段落です。\n\n## アララメッセージを契約している企業へ\n\n" + "本文の中身の文です。" * 30
        self.assertFalse(any("決まった型の見出し" in p for p in st.problems(record(body=ok))))

    def test_sensational_words_and_exclamations(self):
        self.assertTrue(any("煽りの言葉" in p for p in st.problems(record(body="衝撃の発表がありました。"))))
        self.assertTrue(any("感嘆符" in p for p in st.problems(record(body="値下げです！ 今日からです！"))))
        self.assertFalse(any("感嘆符" in p for p in st.problems(record(body="Yahoo!ニュースとYahoo!ショッピングで配信します。"))))
        self.assertFalse(any("煽りの言葉" in p for p in st.problems(record(body="同社は「衝撃的な結果」と説明しています。"))))  # 引用は除く

    def test_jargon_is_explained_only_once(self):
        body = "Webサーバーの脆弱性（ソフトの弱点）が悪用されました。\n\n別の脆弱性（ソフトの弱点）も見つかりました。"
        self.assertTrue(any("同じ用語の説明が2回" in p for p in st.problems(record(body=body))))
        rec = record(body=body)
        st.autofix(rec)
        self.assertIn("別の脆弱性も見つかりました", rec["body"])
        self.assertIn("脆弱性（ソフトの弱点）が悪用", rec["body"])
        # 別の説明・注記は外さない
        keep = "API（アプリから呼び出す仕組み）と、Sanitizer API（HTMLを安全な形に整える仕組み）。Word ファイル（ウェブのみ）と Excel ファイル（ウェブのみ）"
        self.assertEqual(st.dedupe_glosses(keep)[0], keep)

    def test_list_numbers_are_stripped_from_points(self):
        rec = record(highlights=["1. 約7,700万件が持ち出された恐れ", "2）サーバー97台に拡大", "3.5GHz帯の電波を使う"],
                     todayActions=["① URLを開かずに削除する", "カード発行会社へ連絡する"])
        st.autofix(rec)
        self.assertEqual(rec["highlights"][0], "約7,700万件が持ち出された恐れ")
        self.assertEqual(rec["highlights"][1], "サーバー97台に拡大")
        self.assertEqual(rec["highlights"][2], "3.5GHz帯の電波を使う")  # 小数は番号ではない
        self.assertEqual(rec["todayActions"][0], "URLを開かずに削除する")

    def test_business_steps_in_the_first_paragraph_are_recorded(self):
        body = "ご契約企業は、再開時に管理画面のパスワードを再設定する必要があります。\n\n## 不審メールに注意\n\n本文。"
        self.assertTrue(any("企業向けの手続き" in w for w in st.warnings(record(body=body))))
        self.assertFalse(any("企業向けの手続き" in w for w in st.warnings(record())))

    def test_cliche_headlines(self):
        for title in ("AI規制の全貌に迫る", "情報流出の真相", "新型iPhoneを徹底解説"):
            with self.subTest(title=title):
                self.assertTrue(any("決まり文句" in p for p in hn.title_problems(title)))


class PromptTest(unittest.TestCase):
    """（O13）すべての生成の段が同じ読者順の型・やわらかい言い回しを使う"""

    def test_outline_has_reader_order_for_every_type(self):
        for key in nt.TYPES:
            block = nt.prompt_block(key)
            with self.subTest(key=key):
                self.assertIn(nt.READER_ORDER_RULE, block)
        for phrase in ("読者個人への影響", "企業・契約者向けの章", "まだ分からないこと", "1つの段落で大事な数字は1つ",
                       "専門用語は初めて出たところで1回だけ"):
            self.assertIn(phrase, nt.READER_ORDER_RULE)

    def test_style_prompt_has_soft_phrasing_and_units(self):
        self.assertIn(st.SOFT_STYLE_RULE, st.STYLE_PROMPT)
        for phrase in ("まだ決まっていません", "約7,700万件", "約2割", "感嘆符"):
            self.assertIn(phrase, st.SOFT_STYLE_RULE)
        self.assertIn("企業・契約者向けの手続き", st.LEDE_RULE)
        self.assertIn("約7,700万件", hn.TITLE_STYLE_PROMPT)
        self.assertIn("「〜に迫る」", hn.TITLE_STYLE_PROMPT)

    def test_every_writer_carries_the_rules(self):
        import main as m
        import web_articles as w

        self.assertIn(st.STYLE_PROMPT, m.SYSTEM_INSTRUCTION_BASE)
        for name, template in {"WEB": w.WEB_PROMPT_TEMPLATE, "BROAD": w.BROAD_PROMPT_TEMPLATE, "TREND": w.TREND_PROMPT_TEMPLATE,
                               "動画": m.PROMPT_TEMPLATE}.items():
            with self.subTest(path=name):
                self.assertIn(st.LEDE_RULE, template)
                self.assertIn(hn.TITLE_STYLE_PROMPT, template)
        self.assertIn(w.FAQ_TODAY_FIELD, w.extra_fields_block("ai"))

    def test_shared_gate_runs_the_new_checks(self):
        """every_path_problems（すべての段の共通の門）に A45 の検査が入っている"""
        problems = quality.every_path_problems(record(body="持ち出されたメールアドレスは約77百万件です。衝撃です。"))
        self.assertTrue(any("分かりにくい数字の単位" in p for p in problems))
        self.assertTrue(any("煽りの言葉" in p for p in problems))


class AuditTest(unittest.TestCase):
    """毎日の見張りが、読者順の型の門ができたあとの記事で [A45] を数える"""

    def test_audit_flags_a45_on_new_articles_only(self):
        import owner_rules_audit as audit

        self.assertIn("A45", audit.AUDIT_RULES)
        new = record(body="持ち出されたメールアドレスは約77百万件です。", generatedAt="2026-11-06T00:00:00+00:00", newsType="incident")
        old = {**new, "generatedAt": "2026-11-04T00:00:00+00:00"}
        self.assertTrue(any(x.startswith("[A45]") for x in audit.type_problems(new)))
        self.assertFalse(any(x.startswith("[A45]") for x in audit.type_problems(old)))


class FixedArticlesTest(unittest.TestCase):
    """とろいもの書き換え（題名・リード3文）を公式発表で確かめて入れた2本（slug は同じ）"""

    def test_fixed_articles_pass_the_gate(self):
        for slug in FIXED:
            rec = load(slug)
            with self.subTest(slug=slug):
                self.assertEqual(rec["slug"], slug)
                self.assertEqual(quality.every_path_problems(rec), [])
                self.assertEqual(hn.title_problems(rec["title"]), [])
                after = copy.deepcopy(rec)
                self.assertEqual(st.autofix(after), [])  # 直すところが残っていない
                self.assertEqual(len(st._sentences(rec["lede"])), 3)
                self.assertNotIn("百万", json.dumps({k: rec[k] for k in ("title", "lede", "body", "highlights", "faq", "easy")}, ensure_ascii=False))

    def test_arara_reader_order(self):
        rec = load("arara-message-data-leak-second-report")
        self.assertTrue(rec["title"].startswith("アララのメール配信で約7,700万件流出の恐れ"))
        self.assertIn("利用内容確認のご依頼", rec["title"])
        first = st.first_paragraph(rec["body"])
        self.assertIn("news@arara.com", first)  # 個人がすることが最初
        self.assertNotRegex(first, st.BUSINESS_STEP_RE)  # 企業向けの手続きは最初の段落に無い
        heads = st.headings(rec["body"])
        self.assertEqual(heads[-1], "アララメッセージを契約している企業へ")  # 企業向けは最後
        self.assertLess(heads.index("まだ分からないこと"), heads.index("アララメッセージを契約している企業へ"))
        self.assertNotRegex(" ".join(rec["todayActions"]), "契約企業の|社内で|APIキー")  # 今日やることは個人向け

    def test_yucho_reader_order(self):
        rec = load("yucho-bank-matsui-securities-alliance")
        self.assertIn("約2割", rec["title"])
        self.assertIn("1.2億口座", rec["title"])
        lede = st._sentences(rec["lede"])
        self.assertIn("約20%", lede[0])
        self.assertIn("まだ決まっておらず", lede[2])
        self.assertNotIn("丸六", rec["lede"])  # 専門的な名前はリードから下げた
        self.assertNotIn("持分法", rec["lede"])
        self.assertIn("19.99%", rec["body"])  # 正確な数字は本文に
        self.assertIn("5,148万9,700株", rec["body"])
        self.assertEqual(rec["body"].count("持分法適用関連会社（"), 1)  # 説明は1回だけ
        self.assertFalse(any("持分法" in r["a"] for r in rec["faq"]))


if __name__ == "__main__":
    unittest.main()
