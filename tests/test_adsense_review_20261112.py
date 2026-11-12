"""2026-11-12 AdSense 2回目の不承認のあとのオーナー決定: 申し込み直しまでは自動のニュースを1日30本・暮らしとお金だけ"""
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ramp  # noqa: E402


class AdsenseReviewTest(unittest.TestCase):
    def test_cap_during_review(self):
        self.assertEqual(ramp.review_cap(200, "2026-11-12"), 30)
        self.assertEqual(ramp.review_cap(200, "2026-11-26"), 30)

    def test_cap_after_review(self):
        self.assertEqual(ramp.review_cap(200, "2026-11-27"), 200)

    def test_outputs_stop_ai_lane(self):
        env = dict(os.environ, GITHUB_OUTPUT=str(ROOT / "tests" / ".ramp_out_tmp"))
        try:
            code = (
                "import ramp, datetime\n"
                "ramp.datetime = type('D', (), {'now': staticmethod(lambda tz=None: datetime.datetime(2026, 11, 13, 9, tzinfo=tz))})\n"
                "ramp.main()\n"
            )
            subprocess.run([sys.executable, "-c", code], cwd=ROOT / "scripts", env=env, check=True, capture_output=True)
            out = dict(line.split("=", 1) for line in (ROOT / "tests" / ".ramp_out_tmp").read_text().split())
        finally:
            (ROOT / "tests" / ".ramp_out_tmp").unlink(missing_ok=True)
        self.assertEqual(out["web_daily_cap"], "30")
        self.assertEqual(out["ai_per_run"], "0")
        self.assertEqual(out["foreign_ai_cap"], "0")
        self.assertLessEqual(int(out["broad_per_run"]), 2)
        self.assertEqual(out["muse_daily_cap"], str(ramp.MUSE_DAILY_CAP))

    def test_workflows_wired(self):
        auto = (ROOT / ".github/workflows/auto_run.yml").read_text()
        self.assertIn("FOREIGN_AI_DAILY_CAP: ${{ steps.ramp.outputs.foreign_ai_cap", auto)
        muse = (ROOT / ".github/workflows/muse_inbox.yml").read_text()
        self.assertIn("steps.ramp.outputs.muse_daily_cap", muse)


if __name__ == "__main__":
    unittest.main()
