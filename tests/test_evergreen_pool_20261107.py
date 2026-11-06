"""2026-11-07 オーナー指示（台帳 A55）: 使い方ガイドの予定表を150本以上に広げる（お金・手続き・行政サービス・AIツール）。
季節の近さ × 勝ちやすさの順に作る（上限は変えない）。外部への通信なし。"""

import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evergreen  # noqa: E402
import headline_normalize as hn  # noqa: E402

PLAN = json.loads((ROOT / "content" / "evergreen_plan.json").read_text("utf-8"))
TOPICS = PLAN["topics"]
OFFICIAL = re.compile(r"^https://(?:[a-z0-9-]+\.)*(?:go\.jp|lg\.jp|kojinbango-card\.go\.jp|smrj\.go\.jp|denkigas-gekihenkanwa\.go\.jp)/|^https://(?:support\.apple\.com|www\.apple\.com|support\.google\.com|gemini\.google|help\.openai\.com|www\.samsung\.com|support\.microsoft\.com|www\.microsoft\.com|support\.claude\.com|www\.canva\.com|manus\.im|www\.genspark\.ai)/")


class PoolTest(unittest.TestCase):
    def test_size_and_unique(self):
        self.assertGreaterEqual(len(TOPICS), 150)
        slugs = [t["slug"] for t in TOPICS]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertGreaterEqual(sum(1 for t in TOPICS if t.get("kind") == "procedure"), 60)

    def test_new_topics_have_official_sources_queries_and_a50_titles(self):
        for t in TOPICS:
            if t.get("kind") != "procedure" and t["slug"] not in {"apple-intelligence-japanese", "google-ai-mode", "galaxy-ai"}:
                continue
            self.assertTrue(t["sources"], t["slug"])
            for url in t["sources"]:
                self.assertRegex(url, OFFICIAL, t["slug"])
            self.assertGreaterEqual(len(t["queries"]), 3)
            self.assertFalse(re.search(r"とは[？?].*解説|を解説$", t["title"]), t["title"])
            self.assertEqual([p for p in hn.title_problems(t["title"]) if "決まり文句" in p], [], t["title"])
            season = t.get("season")
            if season:
                for k in ("from", "peak", "until"):
                    self.assertRegex(season[k], r"^\d{2}-\d{2}$")

    def test_queue_order_puts_year_end_first_in_november(self):
        ordered = evergreen.order_plan(TOPICS, date(2026, 11, 7))
        first = [t["slug"] for t in ordered[:20]]
        self.assertEqual(first[0], "nencho-how-to")
        self.assertIn("furusato-limit", first)
        self.assertNotIn("gakusei-tokurei", first)  # 春の手続きは後ろ
        spring = evergreen.order_plan(TOPICS, date(2027, 3, 1))
        self.assertIn("hikkoshi-online", [t["slug"] for t in spring[:25]])

    def test_season_urgency(self):
        t = {"season": {"from": "10-20", "peak": "11-20", "until": "12-25"}}
        self.assertEqual(evergreen.season_urgency(t, date(2026, 11, 7)), 3.0)
        self.assertEqual(evergreen.season_urgency(t, date(2026, 6, 1)), 1.0)
        self.assertEqual(evergreen.season_urgency({}, date(2026, 6, 1)), 1.5)

    def test_procedure_prompt_and_labels(self):
        src = (ROOT / "scripts" / "evergreen.py").read_text("utf-8")
        self.assertIn("SYSTEM_PROCEDURE if procedure else SYSTEM", src)
        self.assertIn('"kind": topic.get("kind", "ai-tool")', src)
        view = (ROOT / "components" / "HowtoGuideView.tsx").read_text("utf-8")
        self.assertIn('japanTitle: "対象になる人は？"', view)
        self.assertIn("{L.pricingTitle}", view)

    def test_daily_cap_unchanged(self):
        self.assertEqual(PLAN["dailyCap"], 4)

    def test_ledger(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        self.assertTrue(any(line.startswith("| A55 |") for line in rules.splitlines()))


if __name__ == "__main__":
    unittest.main()
