"""2026-11-22 オーナー決定（台帳 A74）: ふだんの自動の記事は1日30本。速報・安全情報・Muse とオーナーの指示の記事は数えず、止めない。"""
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pacing  # noqa: E402
import ramp  # noqa: E402
import rank_intent  # noqa: E402
import web_articles as w  # noqa: E402

NOW = datetime(2026, 11, 23, 12, tzinfo=pacing.JST)
AT = NOW.isoformat()


class CapTest(unittest.TestCase):
    def test_cap_is_30_with_no_end_date(self):
        for day in ("2026-11-22", "2026-11-27", "2026-12-31", "2027-06-01"):
            self.assertEqual(ramp.routine_cap(day), 30, day)
            self.assertEqual(ramp.review_cap(200, day), 30, day)
        self.assertEqual(ramp.review_cap(10, "2026-12-31"), 10)  # 変数で下げるのは効く

    def _count(self, entries, articles=None):
        articles = articles or {}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            state = {"processed_web": {}}
            for n, entry in enumerate(entries):
                slug = f"s{n}"
                (folder / f"{slug}.json").write_text(json.dumps(articles.get(n, {})), "utf-8")
                state["processed_web"][slug] = {"slug": slug, "at": AT, **entry}
            return pacing.live_today(state, NOW, folder)

    def test_routine_paths_are_counted(self):
        entries = [{"mix": "money"}, {"trendLane": True}, {"offPersona": True}, {"writer": "deep_dive"}, {"writer": "video"}, {"writer": "roundup"}]
        self.assertEqual(self._count(entries), 6)

    def test_safety_breaking_and_ordered_are_not_counted(self):
        entries = [{"ordered": True}, {"major": True}, {"safetyLane": True}, {"writer": "muse"}, {}, {}, {}, {}]
        articles = {1: {"title": "会員情報が流出"}, 4: {"fastLane": True, "title": "ドコモで通信障害"}, 5: {"disaster": True},
                    6: {"safetyAlert": True}, 7: {"museFile": "a.md"}}
        self.assertEqual(self._count(entries, articles), 0)

    def test_safety_titles(self):
        for title in ("個人情報流出のお知らせ", "電気ケトルの自主回収", "フィッシング詐欺に注意", "台風10号 避難指示", "ドコモで通信障害"):
            self.assertTrue(w.is_safety_item({"title": title}), title)
        self.assertFalse(w.is_safety_item({"title": "新社長の就任について"}))

    def test_every_path_is_wired(self):
        web = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("trend_limit = min(trend_limit, max(by_cap, 0))", web)
        self.assertIn('return created["ai"] + created["broad"] + created["trend"] + created_off[0]', web)
        self.assertIn("safety_items = [i for i in broad_items if is_safety_item(i)]", web)
        self.assertIn("pacing.routine_full(state)", (ROOT / "scripts" / "main.py").read_text("utf-8"))
        self.assertIn("pacing.routine_full(web_state)", (ROOT / "scripts" / "roundup.py").read_text("utf-8"))
        self.assertIn("pacing.live_today(web_state) >= args.daily_cap", (ROOT / "scripts" / "deep_dive.py").read_text("utf-8"))


class PriorityTest(unittest.TestCase):
    def rank(self, title, **kw):
        return rank_intent.reader_action_rank({"title": title}, **kw)

    def test_order(self):
        self.assertEqual(self.rank("電気料金の値上げ 12月1日から"), 0)
        self.assertEqual(self.rank("児童手当の申請方法"), 1)
        self.assertEqual(self.rank("新型スマホを発表"), 2)
        self.assertEqual(self.rank("春の叙勲の伝達式典を開催"), 3)

    def test_trending_ceremony_is_not_pushed_back(self):
        self.assertEqual(self.rank("新社長の就任について", trending=True), 2)


if __name__ == "__main__":
    unittest.main()
