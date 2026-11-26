"""scripts/aff_stats.py の押した割合の表示（通信しない）。2026-11-27 オーナー: 人のクリック率 15% 以上が続いて良い広告"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import aff_stats as a  # noqa: E402

RATE = {
    "total": {"seen": 329, "clicks": 5, "clickers": 4, "seenClickers": 4, "rate": 4 / 329},
    "byPos": [{"pos": "tool-result", "seen": 300, "clicks": 4, "clickers": 3, "seenClickers": 3, "rate": 0.01}, {"pos": "action-ad", "seen": 29, "clicks": 1, "clickers": 1, "seenClickers": 1, "rate": 1 / 29}],
    "byVariant": [{"pos": "tool-result", "ab": "b", "seen": 150, "clicks": 3, "clickers": 3, "seenClickers": 3, "rate": 0.02}, {"pos": "tool-result", "ab": "a", "seen": 150, "clicks": 0, "clickers": 0, "seenClickers": 0, "rate": 0.0}],
    "byArm": [],
    "byToolPath": [{"path": "/tools/child-allowance", "pos": "tool-result", "ab": "a", "seen": 150, "clicks": 0, "clickers": 0, "seenClickers": 0, "rate": 0.0}],
    "truncated": False,
}


class AdRateTest(unittest.TestCase):
    def test_headline_for_meetings(self):
        lines = a.ad_rate_lines(RATE)
        self.assertEqual(lines[0], "広告クリック（人） 4 ／ 広告を見た人 329 ／ 押した割合 1.2%（目標15%に届いていません）")

    def test_per_position_variant_and_tool_page(self):
        text = "\n".join(a.ad_rate_lines(RATE))
        self.assertIn("計算ツールの結果の下のPR（tool-result）: 押した人 3 ／ 見た人 300 ／ 1.0%", text)
        self.assertIn("A 今までの囲み: 押した人 0 ／ 見た人 150 ／ 0.0%", text)
        self.assertIn("B 新しい見た目: 押した人 3 ／ 見た人 150 ／ 2.0%", text)
        self.assertLess(text.index("A 今までの囲み"), text.index("B 新しい見た目"))
        self.assertIn("/tools/child-allowance A: 押した人 0 ／ 見た人 150 ／ 0.0%", text)

    def test_no_denominator_is_not_zero(self):
        lines = a.ad_rate_lines({"total": {"seen": 0, "clicks": 1, "clickers": 1, "seenClickers": 0, "rate": None}, "byPos": []})
        self.assertEqual(lines[0], "広告クリック（人） 1 ／ 広告を見た人 0 ／ 押した割合 見た人なし")
        self.assertIn("数えられませんでした", a.ad_rate_lines(None)[0])

    def test_goal_reached(self):
        lines = a.ad_rate_lines({"total": {"seen": 100, "clicks": 20, "clickers": 15, "seenClickers": 15, "rate": 0.15}})
        self.assertTrue(lines[0].endswith("（目標15%に届いています）"))


if __name__ == "__main__":
    unittest.main()
