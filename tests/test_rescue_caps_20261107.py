"""救済モードと1日の上限（2026-11-07 朝 台帳 A48 → 2026-11-08 台帳 A58 で改定）。
11/7 朝は上限で全部見送って0本が続いたので救済モードで上限を外したが、夜・週末に海外の開発者向けの発表が1日13本まで出た。
A58 からは救済モードでも種類別・海外 AI の上限を守り、空いた枠は使い方・手続きのガイド（evergreen.yml）で埋める"""
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "scripts" / "web_articles.py").read_text(encoding="utf-8")


class RescueCapsTest(unittest.TestCase):
    def test_mix_cap_kept_in_rescue(self):
        self.assertIn("if news_mix.over_cap(cand, mix_counts):", SRC)
        self.assertNotRegex(SRC, r"news_mix\.over_cap\(cand, mix_counts\) and not rescue_mode")

    def test_foreign_ai_cap_kept_in_rescue(self):
        self.assertNotRegex(SRC, r"foreign_left\[0\] <= 0 and not rescue_mode")

    def test_zero_runs_ask_for_a_guide(self):
        self.assertIn('fh.write("rescue_evergreen=1\\n")', SRC)
        self.assertNotIn("if rescue_mode and total_created() == 0:", SRC)


if __name__ == "__main__":
    unittest.main()
