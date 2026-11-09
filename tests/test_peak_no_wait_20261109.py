"""2026-11-09 オーナー承認: 人の多い時間帯（朝7〜10時台・夜18〜23時台）の枠は Muse の動画を待たない"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sns_plan  # noqa: E402
import sns_video_followup as f  # noqa: E402

JST = timezone(timedelta(hours=9))


class PeakNoWait(unittest.TestCase):
    def test_peak_hours(self):
        for h, m, want in [(7, 15, True), (8, 30, True), (10, 0, True), (10, 59, True), (11, 30, False), (13, 45, False),
                           (17, 0, False), (18, 0, True), (21, 45, True), (23, 45, True)]:
            self.assertEqual(sns_plan.peak_no_wait(datetime(2026, 11, 9, h, m, tzinfo=JST)), want, (h, m))

    def test_wait_hours_zero_in_peak(self):
        rec = {"pending": {"slot": datetime(2026, 11, 9, 8, 30, tzinfo=JST).isoformat()}}
        self.assertEqual(f.video_wait_h(rec), 0.0)
        rec = {"pending": {"slot": datetime(2026, 11, 9, 13, 45, tzinfo=JST).isoformat()}}
        self.assertEqual(f.video_wait_h(rec), sns_plan.video_wait_hours())

    def test_muse_wait_none_in_peak(self):
        self.assertIsNone(sns_plan.muse_wait_until("x", datetime(2026, 11, 9, 10, 0, tzinfo=JST)))


if __name__ == "__main__":
    unittest.main()
