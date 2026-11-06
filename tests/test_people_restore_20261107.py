"""2026-11-07 オーナー指示: 検索の需要がある取り下げた記事の書き直し（php・褒章）と、人物のまとめページ（台帳 A53）。外部への通信なし。"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import headline_normalize as hn  # noqa: E402
import indexnow  # noqa: E402
import quality  # noqa: E402
import sns_plan  # noqa: E402

RESTORED = ("php-vulnerabilities-jpcert-alert-2026", "mlit-autumn-2026-medals-of-honor")
OFFICIAL = re.compile(r"^https://(?:openai\.com|blog\.samaltman\.com)/")


def article(slug):
    return json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))


class RestoredTest(unittest.TestCase):
    def test_restored_like_the_1106_batch(self):
        retired = json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"]
        protected = json.loads((ROOT / "content" / "search_protected.json").read_text("utf-8"))["articles"]
        for slug in RESTORED:
            a = article(slug)
            self.assertNotIn(slug, retired)
            self.assertIn(slug, protected)
            self.assertTrue(a.get("restoredAt"))
            self.assertTrue(sns_plan.excluded(a), "書き直して戻した記事は SNS に出さない")
            self.assertGreaterEqual(len(a["body"]), 1500)
            self.assertEqual(quality.every_path_problems(a), [], slug)
            self.assertEqual(hn.title_problems(a["title"]) + hn.click_problems(a), [], slug)
            self.assertIsNone(indexnow.publish_block_reason(a), slug)
            self.assertIn("出典：", a["body"])
            self.assertFalse(a.get("videoUrl"))

    def test_php_versions(self):
        body = article("php-vulnerabilities-jpcert-alert-2026")["body"]
        for v in ("8.5.12", "8.4.27", "8.3.36", "8.2.35", "CVE-2026-109618", "session.upload_progress.enabled=0"):
            self.assertIn(v, body)

    def test_medals_counts_from_cabinet_office(self):
        a = article("mlit-autumn-2026-medals-of-honor")
        for n in ("761人（160人）", "443人（132人）", "264人（17人）"):
            self.assertIn(n, a["body"])
        self.assertIn("meibo_hosho.html", a["body"])
        self.assertTrue(a.get("indexable") and a.get("indexableReason"))


class PeopleTest(unittest.TestCase):
    def test_sam_altman_profile_is_official_only(self):
        people = json.loads((ROOT / "content" / "people.json").read_text("utf-8"))["people"]
        sam = next(p for p in people if p["slug"] == "sam-altman")
        self.assertTrue(sam["facts"])
        for f in sam["facts"]:
            self.assertRegex(f["source"]["url"], OFFICIAL)
        for url in sam["sameAs"]:
            self.assertRegex(url, OFFICIAL)
        self.assertRegex("OpenAIのサム・アルトマンCEO", sam["match"])
        self.assertRegex("サムアルトマン氏", r"サム・?アルトマン")

    def test_wiring(self):
        page = (ROOT / "app" / "people" / "[slug]" / "page.tsx").read_text("utf-8")
        self.assertIn('"@type": "Person"', page)
        self.assertIn("/people/", (ROOT / "lib" / "sitemap.ts").read_text("utf-8"))
        self.assertIn("peopleOfCompany", (ROOT / "app" / "companies" / "[company]" / "view.tsx").read_text("utf-8"))
        self.assertIn("PeopleInArticle", (ROOT / "app" / "articles" / "[slug]" / "page.tsx").read_text("utf-8"))

    def test_old_video_article_redirects_to_person_page(self):
        retired = json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"]
        entry = retired["sam-altman-ai-advice-human-centric"]
        self.assertEqual(entry["redirectPath"], "/people/sam-altman")
        self.assertNotIn("redirect", entry)
        self.assertFalse((ROOT / "content" / "articles" / "sam-altman-ai-advice-human-centric.json").exists())
        worker = (ROOT / "cloudflare" / "worker.ts").read_text("utf-8")
        self.assertIn("entry.redirectPath", worker)

    def test_ledger(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        self.assertTrue(any(line.startswith("| A53 |") for line in rules.splitlines()))


if __name__ == "__main__":
    unittest.main()
