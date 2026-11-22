"""検索で4〜20位の記事を厚くする（2026-11-22 オーナー決定・台帳 A68）: 選ぶ範囲・検索語が空の記事・人が確かめた記事を守る"""

import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import search_protected  # noqa: E402
import search_refresh  # noqa: E402

NOW = datetime(2026, 11, 23, tzinfo=timezone.utc)


class PickTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, slug, **fields):
        (self.dir / f"{slug}.json").write_text(json.dumps({"slug": slug, **fields}, ensure_ascii=False), "utf-8")

    def test_range_is_4_to_20(self):
        for s in ("p3", "p4", "p20", "p21"):
            self.write(s)
        pages = {"p3": {"position": 3.9, "impressions": 50}, "p4": {"position": 4.0, "impressions": 40},
                 "p20": {"position": 20.0, "impressions": 30}, "p21": {"position": 20.1, "impressions": 60}}
        self.assertEqual(["p4", "p20"], [s for s, _ in search_refresh.pick(pages, NOW, {}, self.dir)])

    def test_latest_data_comes_first_then_impressions(self):
        for s in ("old", "new_small", "new_big"):
            self.write(s)
        pages = {"old": {"position": 8, "impressions": 900},
                 "new_small": {"position": 8, "impressions": 20, "asOf": "2026-11-22"},
                 "new_big": {"position": 15, "impressions": 100, "asOf": "2026-11-22"}}
        self.assertEqual(["new_big", "new_small", "old"], [s for s, _ in search_refresh.pick(pages, NOW, {}, self.dir)])

    def test_human_checked_articles_are_never_picked_and_are_listed(self):
        self.write("muse", museFile="a.md")
        self.write("editorial", refreshMode="editorial")
        self.write("fixed", body="**編集部訂正（2026年10月31日）**：直しました")
        self.write("plain", body="本文")
        pages = {s: {"position": 8, "impressions": 50} for s in ("muse", "editorial", "fixed", "plain")}
        self.assertEqual(["plain"], [s for s, _ in search_refresh.pick(pages, NOW, {}, self.dir)])
        self.assertEqual({"muse", "editorial", "fixed"}, {s for s, _, _ in search_refresh.held_back(pages, self.dir)})

    def test_correction_pattern_matches_rewrite_types(self):
        source = (ROOT / "scripts" / "rewrite_types.py").read_text("utf-8")
        self.assertIn(f'CORRECTION_RE = re.compile(r"{search_refresh.CORRECTION_RE.pattern}")', source)


class FocusTest(unittest.TestCase):
    def test_empty_query_uses_title_and_invents_nothing(self):
        focus = search_refresh.focus_for({"query": "", "position": 6.9}, "ニコリの返金の手続き", "2026年11月23日")
        self.assertIn("題名「ニコリの返金の手続き」", focus)
        self.assertIn("言葉を推測して本文に入れない", focus)
        self.assertNotIn("と検索されて", focus)
        self.assertIn("資料に無いことは書かない", focus)

    def test_no_query_and_no_title_gives_no_instruction(self):
        self.assertEqual("", search_refresh.focus_for({"query": " ", "position": 6.9}))

    def test_past_deadlines_rule_and_no_padding(self):
        focus = search_refresh.focus_for({"query": "x 期限", "position": 12.0}, "題名", "2026年11月23日")
        self.assertIn("今日は 2026年11月23日", focus)
        self.assertIn("終わったこととして過去形", focus)
        self.assertIn("文字数を増やすためだけ", focus)


class RealDataTest(unittest.TestCase):
    def test_fresh_entries_are_marked_and_old_pages_stay_protected(self):
        data = search_protected.load_positions()
        pages = data["pages"]
        fresh = {s for s, r in pages.items() if r.get("asOf") == "2026-11-22"}
        self.assertEqual(12, len(fresh))
        self.assertIn("2026-11-22", data["window"])
        self.assertIn("2026-11-09", data["window"])
        self.assertGreaterEqual(len(pages), 68)
        self.assertEqual("", pages["nicorio-flavos-refund-process"]["query"])
        self.assertTrue(fresh <= search_protected.protected_slugs())

    def test_monday_stays_at_five_while_budget_is_stopped(self):
        wf = (ROOT / ".github" / "workflows" / "types_rewrite.yml").read_text("utf-8")
        self.assertTrue(re.search(r"search_refresh\.py --apply --weekly --max 5\b", wf))


if __name__ == "__main__":
    unittest.main()
