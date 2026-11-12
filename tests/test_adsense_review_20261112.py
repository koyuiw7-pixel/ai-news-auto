"""2026-11-12 AdSense 2回目の不承認のあとのオーナー決定: 申し込み直しまでは自動のニュースを1日30本・暮らしとお金だけ"""
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import news_mix  # noqa: E402
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


class ReviewLaneTest(unittest.TestCase):
    """審査の期間は、自動のニュースを暮らしとお金の種類だけにする（11/12 夕方にスポーツの記事が出ていた）"""

    DAY = "2026-11-13"

    def item(self, title, section):
        return {"title": title, "summary": "", "source_slug": "x", "section": section, "lang": "ja"}

    def test_sports_and_science_are_not_made(self):
        self.assertTrue(news_mix.review_blocks(self.item("サッカー日本代表対ブラジル戦、11月14日開催　若手主体の王国に挑む", "sports"), self.DAY))
        self.assertTrue(news_mix.review_blocks(self.item("マウス受精卵の発生、鍵は「核の軟らかさ」　遺伝子が働く仕組みを解明", "science"), self.DAY))

    def test_money_life_and_alerts_are_made(self):
        self.assertFalse(news_mix.review_blocks(self.item("九州電力、2027年1月分から電気・都市ガスを割引　2・3月は割引拡大", "lifestyle"), self.DAY))
        self.assertFalse(news_mix.review_blocks(self.item("アルファード・ヴェルファイアPHEV 3,026台リコール　11月13日から無料修理", "business"), self.DAY))
        self.assertFalse(news_mix.review_blocks(self.item("JFA STOREの「GMO後払い」利用者11人のメールアドレスが漏えい", "sports"), self.DAY))

    def test_back_to_normal_after_review(self):
        self.assertFalse(news_mix.review_blocks(self.item("サッカー日本代表対ブラジル戦、11月14日開催", "sports"), "2026-11-27"))

    def test_web_articles_checks_the_lane(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("news_mix.review_blocks(cand)", src)


if __name__ == "__main__":
    unittest.main()
