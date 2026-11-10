"""質問ごとの答えのページ（docs/owner_rules.md「質問ごとの答えのページ」・SEO の作業の束 A7・2026-11-10）。

手で直した記事に updatedAt と generatedAt より新しい updates[] があること、
足した答え（支給日・届かない）が本文にあること、表を写さずに支払日のまとめへリンクしていることを確かめる。
"""
import json
import re
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
EDITED = ("child-allowance-december-payment", "pension-support-benefit-old-age-check")
BANNED = ("｜", "ざっくり")


def load(slug):
    return json.loads((ARTICLES / f"{slug}.json").read_text("utf-8"))


def when(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class EditedRecordTest(unittest.TestCase):
    def test_every_hand_edit_has_updated_at_and_a_newer_update_note(self):
        for slug in EDITED:
            data = load(slug)
            with self.subTest(slug=slug):
                self.assertTrue(data.get("updatedAt"))
                updates = data.get("updates") or []
                self.assertTrue(updates, "updates[] に手で直した記録が無い")
                generated = when(data["generatedAt"])
                self.assertTrue(any(when(u["at"]) > generated for u in updates), "updates[] が generatedAt より新しくない")
                self.assertGreaterEqual(when(data["updatedAt"]), max(when(u["at"]) for u in updates))
                for u in updates:
                    self.assertTrue(u.get("title") and u.get("sourceUrl", "").startswith("https://") and u.get("sourceName"))
                for word in BANNED:
                    self.assertNotIn(word, data["body"])

    def test_child_allowance_answers_payment_day_with_a_table(self):
        data = load("child-allowance-december-payment")
        body = data["body"]
        self.assertGreaterEqual(body.count("支給日"), 1)
        self.assertIn("早見表", data["seoTitle"])
        self.assertIn("早見表", body, "seoTitle が約束する早見表が本文に無い")
        self.assertIn("令和8年12月10日", body)
        self.assertRegex(body, r"\| 東京都文京区 \| 令和8年12月10日 \| \[文京区の児童手当のページ\]\(https://www\.city\.bunkyo\.lg\.jp/")
        # 市区町村の行は、その市区町村の公式のページ（lg.jp）を出どころにしたものだけ
        rows = [line for line in body.splitlines() if re.match(r"^\| (?:東京都|千葉県|横浜市)", line)]
        self.assertGreaterEqual(len(rows), 1)
        for line in rows:
            self.assertRegex(line, r"\(https://www\.city\.[a-z]+(?:\.[a-z]+)?\.(?:lg\.)?jp/")

    def test_pension_check_has_not_arrived_section_and_links_calendar(self):
        data = load("pension-support-benefit-old-age-check")
        body = data["body"]
        self.assertEqual(data.get("refreshMode"), "editorial")
        self.assertGreaterEqual(body.count("届かない"), 1)
        self.assertIn("0570-05-4092", body)
        self.assertIn("令和9年（2027年）1月4日", body)
        self.assertIn("(/articles/pension-child-allowance-payment-calendar)", body)
        # 支払日のまとめの表を写さない（支給月・対象月の表の見出しが無い）
        self.assertNotIn("| 支給月 | その回に入る対象月 |", body)


class LedgerRecordTest(unittest.TestCase):
    def test_owner_pages_are_recorded(self):
        ledger = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        self.assertIn("## 質問ごとの答えのページ", ledger)
        for href in ("/articles/child-allowance-december-payment", "/articles/pension-support-benefit-old-age-check",
                     "/articles/docomo-data-leak-what-to-do", "/tools/defense-tax"):
            self.assertIn(f"`{href}`", ledger)
        for slug in re.findall(r"`/articles/([a-z0-9-]+)`", ledger.split("## 質問ごとの答えのページ", 1)[1].split("\n## ", 1)[0]):
            self.assertTrue((ARTICLES / f"{slug}.json").exists(), slug)
        self.assertTrue((ROOT / "content" / "howto" / "jidou-teate.json").exists())


if __name__ == "__main__":
    unittest.main()
