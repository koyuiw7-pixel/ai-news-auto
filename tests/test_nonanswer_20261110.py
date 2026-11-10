"""2026-11-10 SEO A4・LLMO-A4: 答えの欄（よくある質問・不安・ガイドの結論）に「このページには載っていません」を出さない。
式は scripts/nonanswer.py が正本で、サイト側には lib/index-rules.json の notStated で同じ式を渡す。外部 API は呼ばない。"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import evergreen  # noqa: E402
import indexnow  # noqa: E402
import nonanswer  # noqa: E402
import owner_rules_audit  # noqa: E402
import quality  # noqa: E402
import sweep_not_stated  # noqa: E402

PASSPORT_FAQ = {"q": "パスポートの手数料はいくら？",
                "a": "金額は、このページには載っていません。外務省は「手数料改定関連情報」を令和8年3月26日付で掲載しています。申請前に、最新の金額をそのページで確認します。"}
ANSWERED = {"q": "どこで申請する？", "a": "住民登録をしている都道府県のパスポート申請窓口で申請します。"}


class PatternTest(unittest.TestCase):
    def test_one_pattern_for_site_and_gates(self):
        rules = json.loads((ROOT / "lib" / "index-rules.json").read_text("utf-8"))
        self.assertEqual(rules["notStated"]["source"], nonanswer.NOT_STATED_RE.pattern)
        self.assertEqual(indexnow.index_rules()["notStated"]["source"], nonanswer.NOT_STATED_RE.pattern)
        self.assertIn(nonanswer.NOT_STATED_RE.pattern, quality.FAQ_UNANSWERED_RE.pattern)

    def test_answer_or_none(self):
        self.assertIsNone(nonanswer.answer_or_none(PASSPORT_FAQ["a"]))
        self.assertEqual(nonanswer.answer_or_none(ANSWERED["a"]), ANSWERED["a"])
        self.assertEqual(nonanswer.answer_or_none("都道府県の窓口で申請します。受付時間はこのページには書かれていません。"), "都道府県の窓口で申請します。")
        for text in ("このページには載っていません。", "詳細は案内されていません。", "説明を控えます。", "料金は記載がありません。"):
            self.assertIsNone(nonanswer.answer_or_none(text), text)

    def test_quality_faq_gate_uses_the_lead_sentence(self):
        self.assertTrue(quality.FAQ_UNANSWERED_RE.search(PASSPORT_FAQ["a"]))
        self.assertIsNone(quality.FAQ_UNANSWERED_RE.search("窓口で申請します。受付時間は書かれていません。"))


class EvergreenTest(unittest.TestCase):
    def test_guide_drops_non_answers_and_queues_them(self):
        data = {"faq": [PASSPORT_FAQ, ANSWERED], "conclusion": ["都道府県の窓口で申請します。", "手数料はこのページには載っていません。"],
                "description": "申請の流れをまとめました。手数料はこのページには載っていません。"}
        faq, conclusion, description, open_q = evergreen.answer_slots(data, None, "2026-11-10T20:00:00+09:00")
        self.assertEqual(faq, [ANSWERED])
        self.assertEqual(conclusion, ["都道府県の窓口で申請します。"])
        self.assertEqual(description, "申請の流れをまとめました。")
        self.assertEqual(open_q, [{"q": PASSPORT_FAQ["q"], "since": "2026-11-10T20:00:00+09:00"}])

    def test_open_question_closes_when_answered_and_keeps_since(self):
        previous = {"openQuestions": [{"q": PASSPORT_FAQ["q"], "since": "2026-11-01T00:00:00+09:00"}, {"q": "代理で受け取れる？", "since": "2026-11-02T00:00:00+09:00"}]}
        answered = {"q": PASSPORT_FAQ["q"], "a": "手数料の金額は、外務省の手数料のページに有効期間ごとに載っています。"}
        faq, _, _, open_q = evergreen.answer_slots({"faq": [answered], "conclusion": [], "description": ""}, previous, "2026-11-10T00:00:00+09:00")
        self.assertEqual(faq, [answered])
        self.assertEqual(open_q, [{"q": "代理で受け取れる？", "since": "2026-11-02T00:00:00+09:00"}])

    def test_prompt_allows_zero_faq_and_lists_open_questions(self):
        self.assertIn("よくある質問を0〜6個", evergreen.PROMPT)
        self.assertIn("答えられない問いは作らない", evergreen.PROMPT)
        self.assertIn("代理で受け取れる？", evergreen.open_questions_block([{"q": "代理で受け取れる？"}]))
        self.assertEqual(evergreen.open_questions_block([]), "")


class SweepTest(unittest.TestCase):
    NOW = "2026-11-10T20:00:00+09:00"

    def test_article_worries_block_hidden_below_two(self):
        record = {"slug": "x", "updatedAt": "2026-11-02", "depthHeadings": {"worries": "料金の不安", "steps": "今日やること"},
                  "worries": [{"q": "料金は？", "a": "改定後の具体的な料金額は記載されていません。PDFで確認できます。", "source": "https://example.jp/"},
                              {"q": "開館時間は？", "a": "開館時間は10時から17時です。", "source": "https://example.jp/"}],
                  "faq": [ANSWERED]}
        fixed, removed, _ = sweep_not_stated.sweep_record("articles", record, self.NOW)
        self.assertEqual(removed, 1)
        self.assertNotIn("worries", fixed)
        self.assertEqual(fixed["depthHeadings"], {"steps": "今日やること"})
        self.assertEqual(fixed["updatedAt"], "2026-11-02")  # 更新日は変えない
        self.assertEqual(fixed["faq"], [ANSWERED])

    def test_howto_faq_moves_to_open_questions(self):
        fixed, removed, _ = sweep_not_stated.sweep_record("howto", {"faq": [PASSPORT_FAQ, ANSWERED]}, self.NOW)
        self.assertEqual(removed, 1)
        self.assertEqual(fixed["faq"], [ANSWERED])
        self.assertEqual(fixed["openQuestions"], [{"q": PASSPORT_FAQ["q"], "since": self.NOW}])

    def test_clean_record_is_unchanged(self):
        record = {"faq": [ANSWERED]}
        self.assertEqual(sweep_not_stated.sweep_record("howto", record, self.NOW)[0], record)


class AuditTest(unittest.TestCase):
    def test_audit_prints_the_counts(self):
        lines = owner_rules_audit.answer_slot_lines()
        self.assertIn("guide answers that are non-answers: 0", lines)
        self.assertIn("open questions waiting for a source: ", lines)


if __name__ == "__main__":
    unittest.main()
