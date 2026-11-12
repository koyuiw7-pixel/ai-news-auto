"""AdSense 再審査のあいだの記事の1日上限（scripts/ramp.py の REVIEW_PERIOD）。
2026-11-03〜11-05 は40本。2026-11-06 オーナー決定（台帳 A47）で 11/6 から100本に上げたので、40本の期間は 11/5 で終わり"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ramp  # noqa: E402


class ReviewPeriodCap(unittest.TestCase):
    def test_cap_was_40_until_nov_5(self):
        self.assertEqual(ramp.review_cap(80, "2026-11-03"), 40)
        self.assertEqual(ramp.review_cap(80, "2026-11-05"), 40)

    def test_ends_on_nov_6_owner_decision(self):
        self.assertEqual(ramp.review_cap(100, "2026-11-06"), 100)
        # 11/12〜11/26 は AdSense の2回目の審査の期間（別の決まり）。そのあとは元どおり
        self.assertEqual(ramp.review_cap(100, "2026-11-30"), 100)

    def test_never_raises_a_lower_cap(self):
        self.assertEqual(ramp.review_cap(25, "2026-11-04"), 25)


if __name__ == "__main__":
    unittest.main()
