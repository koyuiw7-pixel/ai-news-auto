"""表示されない太字の記号（** と __）を公開前に消す（scripts/md_markers.py・scripts/main.py の write_article）。

2026-11-27、Muse の原稿から作ったガソリン補助の記事の本文に「**」だけの段落が残り、本番で生の「**」が読者に見えた。
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import main as m  # noqa: E402
import md_markers  # noqa: E402

PAIR = re.compile(r"(?<!\*)\*\*(?!\*)(?=\S)[^*\n]+?(?<=\S)(?<!\*)\*\*(?!\*)")


def lone_stars(text: str) -> list[str]:
    """対になっていない「**」（サイトで太字にならず、生のまま見えるもの）"""
    return [line for line in text.split("\n") if re.search(r"(?<!\*)\*\*(?!\*)", PAIR.sub("", line))]


def muse_draft() -> dict:
    """Muse の原稿から作った記事の形（2026-11-27 のガソリン補助の記事と同じ崩れ）"""
    return {
        "slug": "md-markers-test", "writer": "muse", "refreshMode": "editorial", "museFile": "x.md",
        "title": "ガソリン補助、**12月17日**から基準が175円に",
        "lede": "**補助の基準価格**が段階的に上がります。",
        "summaryLine": "12月17日に1リットル**175円**、灯油は**18リットル**で変わります。",
        "highlights": ["**175円**になる", "__灯油__も上がる"],
        "faq": [{"q": "**いつから**？", "a": "12月3日から**段階的**に。"}],
        "todayActions": ["**給油の時期**を見直す"],
        "workMoney": {"points": ["月に**500円**ほど増える"]},
        "body": "ガソリンは**x**円になります。\n\n**\n\n計算のもとは基準価格の差です。\n\n閉じていない**175円の行。\n\n"
                "品番 C05-*****-******1 は触らない。URL は https://example.com/a__b__c のまま。\n\n```\ncode **here\n```",
        "easy": "**\n\nやさしい説明です。",
        "category": "lifestyle", "tags": [], "publishedAt": "2026-11-27T00:00:00+00:00",
    }


class CleanTest(unittest.TestCase):
    def test_draft_with_bold_and_lone_marker_publishes_without_raw_stars(self):
        rec = muse_draft()
        changes = md_markers.apply(rec)
        self.assertTrue(changes)
        # 太字にならない欄には「**」「__」が1つも残らない
        plain = [rec["title"], rec["lede"], *rec["highlights"], rec["faq"][0]["q"], rec["faq"][0]["a"],
                 *rec["todayActions"], *rec["workMoney"]["points"]]
        for text in plain:
            self.assertNotIn("**", text)
            self.assertNotIn("__", text)
        self.assertEqual(rec["title"], "ガソリン補助、12月17日から基準が175円に")
        self.assertEqual(rec["highlights"], ["175円になる", "灯油も上がる"])
        # 本文: 「**」だけの段落・閉じていない「**」は消え、対の「**x**」だけが残る（サイトが <strong> にする。lib/leftover-bold.ts）
        body = rec["body"].split("```")[0]
        self.assertEqual(lone_stars(body), [])
        self.assertIn("ガソリンは**x**円になります。", body)
        self.assertNotIn("\n**\n", rec["body"])
        self.assertIn("閉じていない175円の行。", body)
        self.assertEqual(lone_stars(rec["easy"]), [])
        self.assertTrue(rec["easy"].startswith("やさしい説明です。"))
        # 太字の記号を全部取ると「**」は1つも残らない（＝読者に見える文字に「**」は無い）
        self.assertIsNone(re.search(r"(?<!\*)\*\*(?!\*)", PAIR.sub(lambda mm: mm.group(0)[2:-2], body)))
        # 要点の1文は最初の1組だけ（サイトの splitEmphasis と同じ）
        self.assertEqual(rec["summaryLine"], "12月17日に1リットル**175円**、灯油は18リットルで変わります。")

    def test_untouched(self):
        rec = muse_draft()
        md_markers.apply(rec)
        self.assertIn("C05-*****-******1", rec["body"])
        self.assertIn("https://example.com/a__b__c", rec["body"])
        self.assertIn("code **here", rec["body"])
        self.assertEqual(md_markers.clean_plain("__init__ と snake_case"), "__init__ と snake_case")
        clean = {"body": "ふつうの**太字**の文。", "summaryLine": "**3万円**が届く", "title": "題名"}
        self.assertEqual(md_markers.apply(dict(clean)), [])

    def test_write_article_runs_the_cleanup_for_every_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(m, "ARTICLES_DIR", Path(tmp)), \
                    mock.patch.object(m.headline_normalize, "apply", return_value=[]), \
                    mock.patch.object(m.headline_normalize, "title_problems", return_value=[]), \
                    mock.patch.object(m.headline_normalize, "click_problems", return_value=[]), \
                    mock.patch.object(m.section_gate, "apply", return_value=[]), \
                    mock.patch.object(m.article_style, "autofix", return_value=[]), \
                    mock.patch.object(m.public_interest, "autofix", return_value=[]), \
                    mock.patch("rewrite_titles.about_name_problems", return_value=[]), \
                    mock.patch("search_title.revalidate", return_value=None), \
                    mock.patch("search_title.attach", return_value=None), \
                    mock.patch.object(m.noir_layout, "attach", return_value=[]):
                path = m.write_article(muse_draft())
                saved = json.loads(path.read_text("utf-8"))
        self.assertNotIn("**", saved["title"])
        self.assertEqual(lone_stars(saved["body"].split("```")[0]), [])
        self.assertNotIn("\n**\n", saved["body"])

    def test_muse_and_followup_paths_use_it(self):
        self.assertIn("target = m.write_article(record)", (ROOT / "scripts" / "muse_articles.py").read_text("utf-8"))
        self.assertIn("md_markers.apply(record)", (ROOT / "scripts" / "main.py").read_text("utf-8"))
        self.assertIn("md_markers.apply(record)", (ROOT / "scripts" / "web_articles.py").read_text("utf-8"))

    def test_published_articles_have_no_lone_markers(self):
        bad = []
        for path in sorted((ROOT / "content" / "articles").glob("*.json")):
            if md_markers.apply(json.loads(path.read_text("utf-8"))):
                bad.append(path.name)
        self.assertEqual(bad, [], "python3 scripts/md_markers.py --apply で直す")


if __name__ == "__main__":
    unittest.main()
