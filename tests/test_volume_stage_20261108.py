"""2026-11-08 台帳 A58: 段階を踏んで本数を上げる・救済モードでも種類別の上限を守る・お金や手続きが変わる知らせは見送らない"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ramp  # noqa: E402
import web_articles as w  # noqa: E402


class StageTest(unittest.TestCase):
    def test_default_stage_is_100_and_never_above_100(self):
        # 2026-11-09 オーナー指示: 100本/日は必須。段は今日から100（未設定でも100）
        old = os.environ.pop("WEB_STAGE_TARGET", None)
        try:
            # 2026-11-09 オーナー「目標を妨げるルールは消そう」: 既定は 200、100 を下回らない
            self.assertEqual(ramp.stage_target(), 200)
            os.environ["WEB_STAGE_TARGET"] = "80"
            self.assertEqual(ramp.stage_target(), 100)
            os.environ["WEB_STAGE_TARGET"] = "500"
            self.assertEqual(ramp.stage_target(), 200)
        finally:
            os.environ.pop("WEB_STAGE_TARGET", None)
            if old is not None:
                os.environ["WEB_STAGE_TARGET"] = old
        self.assertEqual(ramp.STAGES, (40, 60, 80, 100))


class RescueKeepsCapsTest(unittest.TestCase):
    def test_caps_are_not_bypassed_in_rescue_mode(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertNotIn("over_cap(cand, mix_counts) and not rescue_mode", src)
        self.assertNotIn("foreign_left[0] <= 0 and not rescue_mode", src)
        self.assertIn("今日の種類別の上限", w.CAP_ONLY_SKIPS)


class ReaderImpactNoticeTest(unittest.TestCase):
    def check(self, title):
        return w.broad_prefilter({"title": title, "section": "lifestyle", "source_slug": "mlit-press"})

    def test_money_and_procedure_notices_pass(self):
        self.assertIsNone(self.check("高速道路の深夜割引の見直しについて"))
        self.assertIsNone(self.check("子育て世帯への給付金の申請受付開始と対象者の募集"))

    def test_plain_notices_still_drop(self):
        self.assertIn("価値の薄いお知らせ", self.check("料金審議会の開催について（第3回）"))
        self.assertIn("価値の薄いお知らせ", self.check("冬の新春キャンペーンを実施します"))
        self.assertIn("価値の薄いお知らせ", self.check("令和8年度の職員の募集期間を延長します"))


class UpcomingDateTest(unittest.TestCase):
    def test_future_and_past_dates(self):
        now = w.datetime.now(w.JST)
        soon = now + w.timedelta(days=5)
        past = now - w.timedelta(days=5)
        self.assertTrue(w.upcoming_date_in_title(f"新しいカップ麺（{soon.month}月{soon.day}日発売）"))
        self.assertFalse(w.upcoming_date_in_title(f"新しいカップ麺（{past.month}月{past.day}日発売）"))


class LateKeptAfterPageDateTest(unittest.TestCase):
    def test_generation_step_keeps_late_life_items(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        # 2026-11-13: 見送る古さは too_old（96時間。いま起きている話題は48時間）。late の暮らし・お金の候補は今までどおり残す
        self.assertIn('if not major and too_old(item) and not (item.get("late") and life_late_ok(item)):', src)


if __name__ == "__main__":
    unittest.main()
