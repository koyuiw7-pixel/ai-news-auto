"""scripts/reading_report.py の表示（通信しない）。python3 -m unittest tests/test_reading_report.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import reading_report as r  # noqa: E402

ROW = {
    "views": 4, "reached": {"d25": 3, "d50": 2, "d75": 1, "d100": 1}, "engaged": {"s10": 3, "s30": 2, "s60": 1, "s180": 0},
    "medianSecondsBucket": 20, "nextReadSeen": 1, "internalClicks": 1, "exits": {"nextread": 1}, "adSeen": {"action-ad": 3, "ranking-end": 1},
}
DATA = {"date": "2026-11-10", "total": ROW, "bySource": [{"source": "threads", **ROW}, {"source": "internal", **ROW}],
        "byPage": [{"page": "no-such-article-for-test", **ROW}], "truncated": False}


class ReadingReportTest(unittest.TestCase):
    def test_line_uses_shares(self):
        text = r.line(ROW)
        self.assertIn("4件", text)
        self.assertIn("半分まで読んだ 50%", text)
        self.assertIn("最後まで 25%", text)
        self.assertIn("30秒以上 50%", text)
        self.assertIn("中央値 20秒台", text)
        self.assertIn("次に読む記事が見えた 25%", text)
        self.assertIn("action-ad 75%、ranking-end 25%", text)

    def test_render_sections(self):
        text = r.render(DATA)
        self.assertIn("2026-11-10", text)
        self.assertIn("次に読む記事 1", text)
        self.assertIn("Threads:", text)
        self.assertIn("サイト内の移動:", text)
        self.assertIn("「no-such-article-for-test」", text)
        self.assertNotIn("途中まで", text)

    def test_empty_day(self):
        text = r.render({"date": "2026-11-10", "total": {"views": 0}})
        self.assertIn("0件", text)
        self.assertIn("-", text)


if __name__ == "__main__":
    unittest.main()
