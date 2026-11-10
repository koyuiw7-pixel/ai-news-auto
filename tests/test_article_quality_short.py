"""短い速報を字数で落とさず、事実・有用性の判定を迂回しないことを検証。外部 API は呼ばない。"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quality
import web_articles


def article():
    return {
        "sourceType": "web",
        "title": "新しい機能を日本から使えるか公式発表を確認",
        "lede": "新機能の提供対象を公式発表から整理します。",
        "highlights": ["日本の利用者も対象です"],
        "body": "公式発表によると、日本でも新機能を使えます。\n\n## 日本での提供と料金の発表\n料金は発表されていません。",
        "easy": "## ひとことで言うと\n新機能は日本でも使えます。料金はまだ不明です。",
        "workMoney": {"relevance": "medium", "points": ["日本の利用者は今日から試せます。料金は発表を待ってから判断しましょう。"]},
    }


class ShortNewsGateTests(unittest.TestCase):
    def result(self, **kwargs):
        return {"grounded": True, "score": 90, "problems": [], "fatal": False, "useful": True, **kwargs}

    def check(self, response):
        with patch.object(quality.llm, "generate_json", return_value=(response, "mock")) as call:
            verdict = quality.evaluate(article(), "日本で新機能を提供する公式発表", "ai")
        self.assertEqual(call.call_count, 1)
        self.assertIn("useful", call.call_args.args[2]["required"])
        return verdict

    def test_under_2000_and_short_easy_accepted_when_useful(self):
        self.assertLess(len(article()["body"]), 2000)
        self.assertLess(len(article()["easy"]), 400)
        self.assertTrue(self.check(self.result())["ok"])

    def test_unhelpful_cannot_bypass_via_major_surgical_path(self):
        verdict = self.check(self.result(useful=False))
        self.assertFalse(verdict["ok"])
        self.assertFalse(verdict["soft"])
        self.assertFalse(quality.surgical_ok(verdict))

    def test_missing_usefulness_fails_closed(self):
        data = self.result()
        del data["useful"]
        self.assertFalse(self.check(data)["ok"])
        self.assertFalse(self.check(self.result(useful="true"))["ok"])

    def test_invented_fact_and_checker_error_fail_closed(self):
        self.assertFalse(self.check(self.result(grounded=False, fatal=True))["ok"])
        with patch.object(quality.llm, "generate_json", side_effect=RuntimeError("unavailable")):
            verdict = quality.evaluate(article(), "公式発表", "ai")
        self.assertTrue(verdict["unavailable"])
        self.assertFalse(verdict["ok"])

    def test_empty_text_is_rejected_before_api(self):
        for changes in ({"body": "## 見出し\n"}, {"easy": "## ひとことで言うと\n"}):
            with self.subTest(changes=changes), patch.object(quality.llm, "generate_json") as call:
                self.assertFalse(quality.evaluate({**article(), **changes}, "公式発表", "ai")["ok"])
                call.assert_not_called()

    def test_existing_fact_check_callers_keep_old_schema(self):
        with patch.object(quality.llm, "generate_json", return_value=(self.result(), "mock")) as call:
            result = quality.fact_check(article(), "公式発表")
        self.assertNotIn("useful", result)
        self.assertNotIn("useful", call.call_args.args[2]["required"])

    def test_builder_accepts_short_body_but_still_rejects_empty(self):
        item = {"id": "test1234", "url": "https://example.test/news", "source_name": "公式",
                "title": "新機能の発表", "source_slug": "example", "published_at": datetime.now(timezone.utc)}
        data = {"title": article()["title"], "description": "公式発表を確認", "body_markdown": article()["body"],
                "easy_markdown": article()["easy"], "slug_en": "test-news"}
        with patch.object(web_articles.m, "unique_slug", return_value="test-news"), \
             patch.object(web_articles.m, "match_affiliates", return_value=[]):
            record = web_articles.build_web_record(item, data, {}, "mock", "test")
            self.assertLess(len(record["body"]), 800)
            with self.assertRaises(ValueError):
                web_articles.build_web_record(item, {**data, "body_markdown": ""}, {}, "mock", "test")


class PricePromiseTests(unittest.TestCase):
    """2026-11-10 SEO A4: 「月\\d」が「3月1日」に当たって、金額の無い料金の記事を通していた"""

    KYOTO = {
        "title": "京都鉄道博物館の入館料金が2027年3月1日から改定へ　JR西日本が案内を公開",
        "seoTitle": "京都鉄道博物館の入館料金が2027年3月1日から改定　JR西日本",
        "lede": "京都鉄道博物館の入館料金などが、2027年3月1日から改定されます。改定後の金額や対象区分は、ニュースリリースに掲載されたPDFで確認できます。",
        "body": "## 入館料金などの改定は2027年3月1日から\n\nJR西日本は2026年11月2日、京都鉄道博物館の入館料金などを2027年3月1日から改定すると発表しました。",
    }
    HOUSE = {
        "title": "うまかっちゃんやマロニーちゃんが7.4%〜24.2%値上げへ　ハウス食品、2027年2月から",
        "seoTitle": "ハウス食品、うまかっちゃんやマロニーちゃんを2027年2月に値上げ",
        "lede": "ハウス食品は、即席袋麺やマロニー製品など20品目の希望小売価格を、2027年2月1日納品分から引き上げます。",
        "body": "## うまかっちゃん5個パックは680円から730円に\n\n- うまかっちゃん 5個パック：680円から730円\n- マロニーちゃん 180g：371円から427円",
    }

    def test_date_is_not_a_price(self):
        self.assertIsNone(quality.PRICE_ANSWER_RE.search("2027年3月1日から改定"))
        self.assertTrue(quality.PRICE_ANSWER_RE.search("月額980円で使えます"))
        self.assertTrue(quality.PRICE_ANSWER_RE.search("月々 500から"))

    def test_kyoto_fee_change_without_amounts_is_a_broken_promise(self):
        self.assertTrue(quality.promise_problems(self.KYOTO))

    def test_price_change_with_old_and_new_amounts_passes(self):
        self.assertEqual(quality.promise_problems(self.HOUSE), [])
        self.assertEqual(quality.promise_problems({"title": "新プランの料金", "body": "料金は月額980円です。"}), [])

    def test_price_change_needs_two_amounts_or_old_to_new(self):
        one = {"title": "入館料を値上げ", "lede": "", "body": "大人は1,500円になります。"}
        self.assertTrue(quality.promise_problems(one))
        self.assertEqual(quality.promise_problems({**one, "body": "大人は1,200円から1,500円になります。"}), [])
        self.assertEqual(quality.promise_problems({**one, "body": "運賃を平均14.1%引き上げます。"}), [])

    def test_price_words_that_promise_no_price_are_left_alone(self):
        self.assertEqual(quality.price_change_problem("主食用米の取引で19事業者に指導　農水省、価格協議への対応などで", "農水省が指導しました。"), "")
        self.assertEqual(quality.price_change_problem("豆腐店の約4割が赤字、値上げも追いつかず倒産増える", "帝国データバンクの調査です。"), "")


if __name__ == "__main__":
    unittest.main()
