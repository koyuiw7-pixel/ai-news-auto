"""救済モードでは種類別・海外 AI の1日の上限で全部を見送らない（2026-11-07 朝、候補93件が全部上限で見送られ0本が続いた。台帳 A48）"""
import re
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "scripts" / "web_articles.py").read_text(encoding="utf-8")


class RescueCapsTest(unittest.TestCase):
    def test_mix_cap_skipped_in_rescue(self):
        self.assertRegex(SRC, r"news_mix\.over_cap\(cand, mix_counts\) and not rescue_mode")

    def test_foreign_ai_cap_skipped_in_rescue(self):
        self.assertRegex(SRC, r"foreign_left\[0\] <= 0 and not rescue_mode")


if __name__ == "__main__":
    unittest.main()
