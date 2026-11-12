"""もう始まった変更を「これから」と書いた Muse の記事を止める（2026-11-12 夜の取り下げ7本。scripts/source_date.past_change）"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import source_date as sd  # noqa: E402

TODAY = date(2026, 11, 12)


class PastChangeTest(unittest.TestCase):
    def test_finished_price_hikes_written_as_upcoming_are_stopped(self):
        for text in [
            "ハーゲンダッツ ジャパンは、2026年3月1日出荷分から6カテゴリーの希望小売価格を改定します。",
            "マクドナルドが2026年2月25日から標準店舗の約6割の商品を10円〜50円値上げします。",
            "2026年10月1日から、ゆうパックの基本運賃が平均約10%上がります。",
            "75品が、2026年10月1日納品分から順次値上げされます。",
            "ロッテのガムは9月1日出荷分から、アイスは10月の出荷分から変わります。",  # 年の無い月日（今年・150日以内）
            "改定は2026年3月2日に実施予定です。",
        ]:
            with self.subTest(text=text):
                problems = sd.past_change([text], TODAY)
                self.assertTrue(problems, text)
                self.assertIn("今の状態として書き直し", problems[0])

    def test_advice_for_the_time_before_a_past_change_is_stopped(self):
        texts = ["実施は2026年3月1日の出荷分から値上げされました。", "買い置きをするなら、2月中に済ませる手があります。"]
        problems = sd.past_change(texts, TODAY)
        self.assertEqual(len(problems), 1)
        self.assertIn("もう過ぎた時期", problems[0])

    def test_upcoming_changes_and_current_state_pass(self):
        for text in [
            "三菱UFJ銀行からauじぶん銀行への振込が2027年4月1日から他行あて扱いになり、ATMは275円に改定されます（2026年10月1日の案内）。",
            "iDeCoの掛金の上限が2026年12月分から引き上げられます。",
            "2027年1月から防衛特別所得税が創設されます。",
            "最低賃金が、10月1日から12月2日までの間に、都道府県ごとに順次上がる予定です。",
            "自転車の青切符が2026年4月1日から適用されました。",
            "2026年4月から、年金が減り始める基準が月51万円から65万円に上がりました。",
            "2026年11月10日時点の公式表示で比べました。",
            "東京電力エリアの4つのプランを、2026年11月1日以降の基本料金で比較します。",
            "ヨコハマタイヤの無償交換は2027年1月5日から始まります。",
            "第45週（11月2日〜11月8日）分の数字は、2026年11月13日に公表される予定です。",
            "前回の2023年4月の改定では、ミニカップが295円から325円に上がります。",  # 前回・過去と分かる文は見ない
            "交換は1月5日から始まります。",  # 年の無い月日で150日より前は来年の意味
        ]:
            with self.subTest(text=text):
                self.assertEqual(sd.past_change([text], TODAY), [], text)

    def test_muse_pipeline_uses_the_check_on_the_draft_and_the_record(self):
        src = (Path(__file__).resolve().parent.parent / "scripts" / "muse_articles.py").read_text(encoding="utf-8")
        self.assertIn("source_date.past_change([data[\"title\"], data[\"body\"]], today)", src)
        self.assertIn("source_date.past_change(texts, today)", src)
        self.assertIn('record.get("todayActions")', src)


if __name__ == "__main__":
    unittest.main()
