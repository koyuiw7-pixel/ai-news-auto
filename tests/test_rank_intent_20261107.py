"""2026-11-07 オーナー承認（Muse の5つの条件・台帳 A54）: 検索で上位に出やすい話題を先に作る並びの手がかり。上限は付けない。外部への通信なし。"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rank_intent as ri  # noqa: E402

NOW = datetime(2026, 11, 7, 3, 0, tzinfo=timezone.utc)


def item(title, **extra):
    return {"title": title, "url": "https://example.go.jp/x.html", **extra}


class RankIntentTest(unittest.TestCase):
    def test_first_mover_incident_within_an_hour(self):
        fresh = item("楽天モバイルで通信障害", published_at=NOW - timedelta(minutes=20))
        old = item("楽天モバイルで通信障害", published_at=NOW - timedelta(hours=3))
        self.assertEqual(ri.rank_of(fresh, NOW), 0)
        self.assertEqual(ri.rank_of(old, NOW), 1)  # 一覧に載る形なので query のまま
        self.assertEqual(ri.intent_of(item("新型スマホの発売", published_at=NOW - timedelta(minutes=10)), NOW), "breaking")

    def test_longtail_official_table_and_roundup_feed(self):
        for title in ("児童手当の申請期限は11月30日", "RTX 5090の価格と発売日", "PHPの脆弱性、8.5.12へ更新を"):
            self.assertIn("longtail", ri.signals(item(title), NOW), title)
            self.assertEqual(ri.intent_of(item(title), NOW), "query")
        self.assertIn("official-table", ri.signals(item("資料", url="https://www.mhlw.go.jp/a.pdf"), NOW))
        self.assertIn("official-table", ri.signals(item("令和8年秋の褒章の受章者数の内訳", kind="gov"), NOW))
        self.assertIn("roundup-feed", ri.signals(item("サントリーが「響」など値上げへ"), NOW))

    def test_head_terms_go_last_and_years_are_not_model_numbers(self):
        self.assertEqual(ri.rank_of(item("OpenAI、新モデルを発表"), NOW), 3)
        self.assertEqual(ri.signals(item("Java Annotated Monthly – November 2026"), NOW), [])
        self.assertEqual(ri.signals(item("Our Q1 FY27 letter to shareholders"), NOW), [])

    def test_mix_prefers_the_short_side_without_capping(self):
        q, b = item("児童手当の申請期限は11月30日"), item("新型スマホの発売", published_at=NOW - timedelta(minutes=5))
        self.assertLess(ri.mix_order(q, {"query": 1, "breaking": 5}, NOW), ri.mix_order(b, {"query": 1, "breaking": 5}, NOW))
        self.assertLess(ri.mix_order(b, {"query": 9, "breaking": 1}, NOW), ri.mix_order(q, {"query": 9, "breaking": 1}, NOW))
        rows = sorted([item("OpenAI、新モデルを発表"), q, b, item("ふつうの話題")], key=lambda i: ri.sort_key(i, {}, NOW))
        self.assertEqual([r["title"] for r in rows][0], b["title"])
        self.assertEqual(rows[-1]["title"], "OpenAI、新モデルを発表")

    def test_wired_as_ordering_only(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("rank_intent.sort_key(i, intent_counts)", src)
        self.assertIn("intent=rank_intent.intent_of(item)", src)
        self.assertNotIn("rank_intent.over_cap", src)

    def test_ledger(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        self.assertTrue(any(line.startswith("| A54 |") for line in rules.splitlines()))


class SpeedTest(unittest.TestCase):
    def test_cold_start_does_not_load_full_pipeline_state(self):
        src = (ROOT / "scripts" / "cf_content.mjs").read_text("utf-8")
        self.assertIn('processed: state.processed ?? {}, failed: state.failed ?? {}', src)
        self.assertNotIn('"content/state.json", "affiliate_links.json"', src)


if __name__ == "__main__":
    unittest.main()
