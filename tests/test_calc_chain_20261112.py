"""2段の計算と、前の式の答えを使う計算（2026-11-12 障害基礎年金の記事が正しい計算で落ちていた）"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import calc_facts as c  # noqa: E402

FACTS = "1級は年1,059,125円、2級は年847,300円。子の加算額は第1子・第2子は各243,800円、第3子以降は各81,300円。"


def unsupported(text):
    allowed = c.values(FACTS)
    found = [q for q in c.extract(text) if c.checkable(q)]
    return [q.text for q in found if not c.supported(q, allowed) and not c.derived(q, allowed, text)]


class CalcChainTest(unittest.TestCase):
    def test_two_step_expression(self):
        self.assertEqual(unsupported("1級で子2人なら、1,059,125円 + 243,800円 × 2 = 1,546,725円です（サイソク編集部の計算）。"), [])

    def test_chained_expression(self):
        t = ("1級で子2人なら1,059,125円 + 243,800円 × 2 = 1,546,725円です（サイソク編集部の計算）。"
             "3人目がいれば1,546,725円 + 81,300円 = 1,628,025円です（サイソク編集部の計算）。")
        self.assertEqual(unsupported(t), [])

    def test_wrong_answer_still_rejected(self):
        self.assertTrue(unsupported("1級で子2人なら、1,059,125円 + 243,800円 × 2 = 1,600,000円です（サイソク編集部の計算）。"))

    def test_unverified_operand_still_rejected(self):
        self.assertTrue(unsupported("1級で子2人なら、1,111,111円 + 243,800円 × 2 = 1,598,711円です（サイソク編集部の計算）。"))

    def test_needs_calc_label(self):
        self.assertTrue(unsupported("1級で子2人なら、1,059,125円 + 243,800円 × 2 = 1,546,725円です。"))

    def test_chain_cannot_start_from_wrong_answer(self):
        t = ("1級で子2人なら1,059,125円 + 243,800円 × 2 = 1,600,000円です（サイソク編集部の計算）。"
             "3人目がいれば1,600,000円 + 81,300円 = 1,681,300円です（サイソク編集部の計算）。")
        bad = unsupported(t)
        self.assertIn("1,681,300円", bad)


if __name__ == "__main__":
    unittest.main()
