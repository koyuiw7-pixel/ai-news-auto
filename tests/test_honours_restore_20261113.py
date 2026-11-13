"""2026-11-13 オーナー「とにかく数字」: 11/3 に「薄い」で取り下げた受章者の記事2本を、公式の一次情報で書き直して同じ URL に戻す
（台帳 A26・A46。褒章の受章者の記事は検索の流入の2位だった＝点検 audit_20261113）。外部への通信なし。"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import headline_normalize as hn  # noqa: E402
import indexnow  # noqa: E402
import notice_gate  # noqa: E402
import quality  # noqa: E402
import search_protected  # noqa: E402
import sns_plan  # noqa: E402

RESTORED = ("reiwa-8-autumn-shoubo-houshou", "reiwa-8-culture-merit-recipients")


def article(slug):
    return json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))


class HonoursRestoredTest(unittest.TestCase):
    def test_restored_like_the_1106_batch(self):
        retired = json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"]
        protected = search_protected.load()["articles"]
        for slug in RESTORED:
            a = article(slug)
            self.assertNotIn(slug, retired)
            self.assertIn(slug, protected)
            self.assertEqual(protected[slug]["title"], a["title"])
            self.assertTrue(a.get("restoredAt") and a.get("typesRewrittenAt") and a.get("titleHistory"))
            self.assertTrue(sns_plan.excluded(a), "書き直して戻した記事は SNS に出さない")
            self.assertGreaterEqual(len(a["body"]), 1500)
            self.assertEqual(quality.every_path_problems(a), [], slug)
            self.assertEqual(hn.title_problems(a["title"]) + hn.click_problems(a), [], slug)
            self.assertIn("出典：", a["body"])
            self.assertNotIn("｜", a["title"] + a["seoTitle"])
            self.assertFalse(a.get("videoUrl"))

    def test_indexable_by_the_rules_without_a_manual_override(self):
        """お知らせの門（c37c8b5a で受章者の一覧を通すようにした）も検索の基準も、手動の印なしで通る"""
        for slug in RESTORED:
            a = article(slug)
            self.assertNotIn("indexable", a, slug)
            self.assertFalse(notice_gate.is_notice(a), slug)
            self.assertIsNone(indexnow.publish_block_reason(a), slug)
            self.assertIsNone(indexnow.noindex_reason(a), slug)
            self.assertTrue(indexnow.is_indexable(a), slug)

    def test_fire_service_counts_match_the_official_release(self):
        a = article("reiwa-8-autumn-shoubo-houshou")
        for fact in ("110人", "藍綬褒章 | 102人", "黄綬褒章 | 7人", "紅綬褒章 | 1人", "10月20日の閣議", "11月17日（火）12時30分", "761人"):
            self.assertIn(fact, a["body"], fact)
        self.assertTrue(a["sourceUrl"].startswith("https://www.soumu.go.jp/"))
        # 都道府県別の表の合計が受章者の数と合う（表は「各N人」「N人」で書く）
        import re
        section = a["body"].split("## 都道府県別の人数")[1].split("## ")[0]
        total = 0
        for row in re.findall(r"^\| (.+?) \| (各)?(\d+)人", section, flags=re.M):
            total += int(row[2]) * (len(row[0].split("・")) if row[1] else 1)
        self.assertEqual(total, 110)

    def test_culture_lists_match_the_ministry_pages(self):
        a = article("reiwa-8-culture-merit-recipients")
        kunsho = a["body"].split("## 令和8年度の文化勲章は8人")[1].split("## ")[0]
        koro = a["body"].split("## 令和8年度の文化功労者は21人")[1].split("## ")[0]
        rows = lambda text: [line for line in text.splitlines() if line.startswith("| ") and "（" in line.split("|")[1]]  # noqa: E731
        self.assertEqual((len(rows(kunsho)), len(rows(koro))), (8, 21))
        for name in ("石井 幹子", "伊東 豊雄", "黒岩 常祥", "塩川 徹也", "硤合 憲三", "都倉 俊一", "長田 重一", "宮本 茂"):
            self.assertIn(name, kunsho)
        self.assertTrue(a["sourceUrl"].startswith("https://www.mext.go.jp/"))


if __name__ == "__main__":
    unittest.main()
