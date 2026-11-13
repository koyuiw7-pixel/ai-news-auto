"""2026-11-13: 確かめた数字どうしの簡単な計算（割合・かっこ・「≒」「＝月」）は、機械で検算して合っていれば数字の門を通す。

きっかけ（Muse の見送り20本）: 「3,000万円×0.7%＝21万円」「46万円×5%＝23,000円」は正しいのに「計算の式が合っていない」で落ちていた
（割合を 0.7 倍・5 倍と読んでいた）。「÷ 12 = 月88,260円」「28万円÷30≒9,330円」は式として読めていなかった。
変えないこと: 式が合わないもの・材料が資料に無い式・「計算」と書いていない数字は、今までどおり落とす。
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import calc_facts as c  # noqa: E402
import quality  # noqa: E402

LABEL = "（サイソク編集部の計算）"


def unsupported(text: str, facts: str) -> list[str]:
    allowed = c.values(facts)
    found = [q for q in c.extract(text) if c.checkable(q)]
    return [q.text for q in found if not c.supported(q, allowed) and not c.derived(q, allowed, text)]


class PercentExpressionTest(unittest.TestCase):
    def test_correct_percent_products_are_not_bad(self):
        for text in ("3,000万円×0.7%=21万円", "46万円×5%=23,000円", "50万円×0.5％＝2,500円", "2億円×1.5%＝300万円",
                     "1億2,000万円×10%＝1,200万円", "5%×46万円＝2万3,000円", "30万円×67%＝201,000円"):
            self.assertEqual(c.bad_expressions(text), [], text)

    def test_wrong_percent_products_are_bad(self):
        for text in ("46万円×5%=2,300円", "46万円×5%=230,000円", "3,000万円×0.7%=210万円", "100円×50%=5,000円",
                     "2億円×1.5%＝3,000万円", "30万円×67%＝211,000円"):
            self.assertTrue(c.bad_expressions(text), text)

    def test_ratio_results_and_percent_sums(self):
        self.assertEqual(c.bad_expressions("2,500円÷50万円＝0.5%"), [])
        self.assertEqual(c.bad_expressions("11件÷56件＝19.6%"), [])
        self.assertEqual(c.bad_expressions("10%＋5%＝15%"), [])
        self.assertTrue(c.bad_expressions("2,500円÷50万円＝5%"))
        self.assertTrue(c.bad_expressions("10%＋5%＝16%"))

    def test_plain_arithmetic_is_unchanged(self):
        self.assertEqual(c.bad_expressions("1人50万円×2人＝100万円"), [])
        self.assertEqual(c.bad_expressions("月額1,200円×12か月＝1万5,000円の計算"), ["1,200円×12か月=1万5,000円"])
        self.assertEqual(c.bad_expressions("10,000円 × 2/3 = 6,667円"), [])
        self.assertEqual(c.bad_expressions("1億2,000万円÷4＝3,000万円"), [])
        self.assertTrue(c.bad_expressions("1億2,000万円÷4＝4,000万円"))


class WiderExpressionFormsTest(unittest.TestCase):
    def test_parentheses(self):
        self.assertEqual(c.bad_expressions("80,100円＋（1,000,000円−267,000円）×1％＝87,430円"), [])
        self.assertTrue(c.bad_expressions("80,100円＋（1,000,000円−267,000円）×1％＝97,430円"))

    def test_approx_sign_and_prefix_words(self):
        self.assertEqual(c.bad_expressions("28万円÷30≒9,330円"), [])
        self.assertTrue(c.bad_expressions("28万円÷30≒9,000円"))
        self.assertEqual(c.bad_expressions("1,059,125円 ÷ 12 = 月88,260円"), [])
        self.assertTrue(c.bad_expressions("1,059,125円 ÷ 12 = 月98,260円"))
        self.assertEqual(c.bad_expressions("月400円×12か月＝年4,800円"), [])
        self.assertEqual(c.bad_expressions("月400円×12か月＝約4,800円"), [])

    def test_per_unit_suffix_is_not_a_division(self):
        self.assertEqual(c.bad_expressions("400kWh×1.0円/kWh＝400円"), [])
        self.assertTrue(c.bad_expressions("400kWh×1.0円/kWh＝4,000円"))

    def test_equation_chain_checks_the_second_step(self):
        self.assertEqual(c.bad_expressions("合計は1,000円＋200円＝1,200円＋300円＝1,500円"), [])
        self.assertEqual(c.bad_expressions("合計は1,000円＋200円＝1,200円＋300円＝1,600円"), ["1,200円+300円=1,600円"])


class MiddleStepTest(unittest.TestCase):
    """「左辺＝途中の式＝答え」（公開中の高額療養費の記事の書き方）。途中の式の最初の数字を答えと読まない"""

    FACTS = "自己負担の上限は85,800円＋（総医療費−286,000円）×1%です。総医療費が1,000,000円の例。"
    TEXT = f"85,800円＋（1,000,000円−286,000円）×1%＝85,800円＋7,140円＝92,940円です{LABEL}。"

    def test_middle_step_is_not_a_wrong_answer(self):
        self.assertEqual(c.bad_expressions(self.TEXT), [])
        self.assertEqual(c.bad_expressions("179,100円+(2,000,000円-597,000円)×1%=179,100円+14,030円=193,130円"), [])

    def test_wrong_middle_or_final_step_is_bad(self):
        self.assertTrue(c.bad_expressions(self.TEXT.replace("7,140円", "9,140円")))
        self.assertTrue(c.bad_expressions(self.TEXT.replace("92,940円", "95,940円")))
        # 数字の門（式の答えとして認めるか）は1円までしか許さない
        self.assertEqual(unsupported(self.TEXT.replace("7,140円", "7,240円"), self.FACTS), ["7,240円", "92,940円"])

    def test_the_computed_part_and_total_pass_the_gate(self):
        self.assertEqual(unsupported(self.TEXT, self.FACTS), [])
        self.assertEqual(unsupported(self.TEXT.replace("92,940円", "93,940円"), self.FACTS), ["93,940円"])
        # 材料（総医療費の例）が資料に無ければ、途中の答えも認めない
        self.assertEqual(unsupported(self.TEXT, "自己負担の上限は85,800円＋（総医療費−286,000円）×1%です。"),
                         ["1,000,000円", "7,140円", "92,940円"])


class NumberGateTest(unittest.TestCase):
    """quality.number_problems（数字の門）を通して確かめる"""

    def problems(self, body: str, source: str) -> list[str]:
        return quality.number_problems({"title": "住宅ローン控除の2年目", "body": body}, source)

    def test_percent_of_a_source_amount_passes(self):
        source = "年末残高の0.7%を控除します。借入限度額は3,000万円です。"
        self.assertEqual(self.problems(f"上限いっぱいなら3,000万円×0.7%＝21万円です{LABEL}。", source), [])
        self.assertEqual(self.problems(f"上限いっぱいなら3,000万円×0.7%＝210,000円です{LABEL}。", source), [])

    def test_wrong_result_fails(self):
        source = "年末残高の0.7%を控除します。借入限度額は3,000万円です。"
        got = self.problems(f"上限いっぱいなら3,000万円×0.7%＝25万円です{LABEL}。", source)
        self.assertTrue(any("計算の式が合っていない" in p for p in got), got)
        self.assertTrue(any("どれにも無い数字" in p for p in got), got)

    def test_unverified_operand_fails(self):
        """式が合っていても、材料の金額・割合が資料に無ければ通さない"""
        source = "年末残高の0.7%を控除します。"
        self.assertTrue(self.problems(f"3,000万円×0.7%＝21万円です{LABEL}。", source))
        source2 = "借入限度額は3,000万円です。"
        self.assertTrue(self.problems(f"3,000万円×0.7%＝21万円です{LABEL}。", source2))

    def test_unlabelled_calculation_still_fails(self):
        source = "年末残高の0.7%を控除します。借入限度額は3,000万円です。"
        self.assertTrue(self.problems("上限いっぱいなら3,000万円×0.7%＝21万円です。", source))

    def test_division_with_month_prefix(self):
        facts = "1級は年1,059,125円、2級は年847,300円です。"
        self.assertEqual(unsupported(f"1級は1,059,125円 ÷ 12 = 月88,260円です{LABEL}。", facts), [])
        self.assertEqual(unsupported(f"2級は847,300円÷12≒70,608円です{LABEL}。", facts), [])
        self.assertEqual(unsupported(f"1級は1,059,125円 ÷ 12 = 月89,260円です{LABEL}。", facts), ["89,260円"])

    def test_unit_formats_man_oku(self):
        facts = "予算は2億円、対象は400世帯、補助率は50%、上限は1世帯5万円です。"
        self.assertEqual(unsupported(f"2億円÷400世帯＝50万円です{LABEL}。", facts), [])
        self.assertEqual(unsupported(f"2億円×50%＝1億円です{LABEL}。", facts), [])
        self.assertEqual(unsupported(f"5万円×400世帯＝2,000万円です{LABEL}。", facts), [])
        self.assertEqual(unsupported(f"5万円×400世帯＝2億円÷10＝2,000万円です{LABEL}。", facts), [])
        self.assertEqual(unsupported(f"2億円÷400世帯＝5万円です{LABEL}。", facts), [])  # 5万円は資料にある数字（式の誤りは bad_expressions が見る）
        self.assertTrue(c.bad_expressions("2億円÷400世帯＝5万円"))
        self.assertEqual(unsupported(f"2億円×50%＝1,000万円です{LABEL}。", facts), ["1,000万円"])

    def test_percent_result_from_two_source_amounts(self):
        facts = "保険料は2,500円、賞与は50万円でした。"
        self.assertEqual(unsupported(f"2,500円÷50万円＝0.5%です{LABEL}。", facts), [])
        self.assertEqual(unsupported(f"2,500円÷50万円＝0.9%です{LABEL}。", facts), ["0.9%"])

    def test_percent_operand_is_not_a_free_small_number(self):
        """「2人」「12か月」は文にあれば材料にしてよいが、割合・1単位あたりの金額は資料に無ければだめ"""
        facts = "賞与は50万円でした。"
        self.assertEqual(unsupported(f"50万円×0.5%＝2,500円です{LABEL}。", facts), ["0.5%", "2,500円"])
        self.assertEqual(unsupported(f"使用量350kWh×2.5円/kWh＝875円です{LABEL}。", "使用量の例は350kWhです。"), ["2.5円", "875円"])
        self.assertEqual(unsupported(f"使用量350kWh×2.5円/kWh＝875円です{LABEL}。", "値引きは1kWhあたり2.5円です。"), [])

    def test_label_once_for_a_block_of_expressions(self):
        facts = "1級は年1,059,125円、2級は年847,300円。子の加算額は各243,800円。"
        block = ("- 1級で子1人: 1,059,125円 + 243,800円 = 1,302,925円\n"
                 "- 2級で子1人: 847,300円 + 243,800円 = 1,091,100円\n"
                 f"{LABEL}\n\n別の段落です。")
        self.assertEqual(unsupported(block, facts), [])
        table = ("| 家族 | 年額 |\n|---|---|\n| 2級で子1人 | 847,300円 + 243,800円 = 1,091,100円 |\n\n"
                 f"表の年額は足し算です{LABEL}。")
        self.assertEqual(unsupported(table, facts), [])
        # 「計算」と書いていない段落の式は今までどおり認めない。式の無い数字も認めない
        self.assertEqual(unsupported("2級で子1人なら847,300円 + 243,800円 = 1,091,100円です。\n\n次の段落の計算。", facts), ["1,091,100円"])
        self.assertEqual(unsupported(f"2級で子1人なら1,091,100円です。\n式は省きます{LABEL}。", facts), ["1,091,100円"])
        wrong = f"- 2級で子1人: 847,300円 + 243,800円 = 1,191,100円\n{LABEL}"
        self.assertEqual(unsupported(wrong, facts), ["1,191,100円"])


if __name__ == "__main__":
    unittest.main()
