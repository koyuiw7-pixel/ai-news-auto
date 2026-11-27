"""ニュースアプリ向けの汎用フィード（/feeds/partner.xml）とグノシー用（/feeds/gunosy.xml）が XML として正しく読めるか（2026-11-28）。

実際の記事でフィードを作り、XML として読み、RSS 2.0 の必須の要素（channel の title・link・description、
item の title・link・guid・pubDate・content:encoded）と、配信先の決まり（広告・紹介リンクなし、AI 利用の開示）を確かめる。
細かい中身は tests/test_partner_feeds.cjs が見る。
"""
import email.utils
import os
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = {"content": "http://purl.org/rss/1.0/modules/content/", "media": "http://search.yahoo.com/mrss/", "atom": "http://www.w3.org/2005/Atom"}
RENDER = """
const path = require("node:path");
const { createJiti } = require("jiti");
const root = process.cwd();
const jiti = createJiti(path.join(root, "x.js"), { alias: { "@": root }, interopDefault: true });
const which = process.argv[1];
const run = which === "partner"
  ? jiti.import(path.join(root, "lib/partner-xml.ts")).then((m) => m.partnerFeedXml("/feeds/partner.xml")).then((r) => r.xml)
  : jiti.import(path.join(root, "app/feeds/gunosy.xml/route.ts")).then((m) => m.GET()).then((r) => r.text());
run.then((xml) => process.stdout.write(xml));
"""
FORBIDDEN = ["a8.net", "/api/aff/", 'rel="sponsored"', "【PR】", "afl.rakuten", "<script"]
DISCLOSURE = "この記事は生成AIで下書きを作成し、元の発表と自動で照合してから公開しています。"


def render(which):
    env = {**os.environ, "NEXT_PUBLIC_SITE_URL": "https://ai-tech-express.jp"}
    out = subprocess.run(["node", "-e", RENDER, which], cwd=ROOT, env=env, capture_output=True, check=True, timeout=180)
    return out.stdout


@unittest.skipUnless(shutil.which("node") and (ROOT / "node_modules" / "jiti").exists(), "node と npm ci が必要")
class PartnerFeedsXml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = {w: render(w) for w in ("partner", "gunosy")}
        cls.root = {w: ET.fromstring(raw) for w, raw in cls.raw.items()}

    def test_channel(self):
        for w, root in self.root.items():
            self.assertEqual(root.tag, "rss", w)
            self.assertEqual(root.get("version"), "2.0", w)
            ch = root.find("channel")
            self.assertEqual(ch.findtext("title"), "サイソクニュース", w)
            self.assertEqual(ch.findtext("link"), "https://ai-tech-express.jp", w)
            self.assertTrue(ch.findtext("description"), w)
            self.assertEqual(ch.findtext("language"), "ja", w)
        self.assertEqual(self.root["partner"].find("channel/atom:link", NS).get("href"), "https://ai-tech-express.jp/feeds/partner.xml")

    def test_items(self):
        for w, root in self.root.items():
            items = root.find("channel").findall("item")
            self.assertGreaterEqual(len(items), 5, w)
            guids = [it.findtext("guid") for it in items]
            self.assertEqual(len(guids), len(set(guids)), f"{w}: 同じ記事を2回載せない")
            for it in items:
                for tag in ("title", "link", "guid", "pubDate"):
                    self.assertTrue((it.findtext(tag) or "").strip(), f"{w}: {tag}")
                self.assertIsNotNone(email.utils.parsedate_to_datetime(it.findtext("pubDate")))
                body = it.findtext("content:encoded", namespaces=NS) or ""
                self.assertIn(DISCLOSURE, body, w)
                if w == "gunosy":
                    self.assertFalse(it.findtext("guid").startswith("http"), "グノシーの guid は URL 形式にしない")

    def test_no_ads(self):
        for w, raw in self.raw.items():
            text = raw.decode()
            for bad in FORBIDDEN:
                self.assertNotIn(bad, text, f"{w}: {bad}")


if __name__ == "__main__":
    unittest.main()
