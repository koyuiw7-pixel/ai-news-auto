"""スマートニュース（SmartFormat）のフィードが XML として正しく読めるか（2026-11-07 オーナー承認）。

実際の記事から lib/smartnews-feed.ts でフィードを作り、XML として読み、仕様書の必須の要素
（channel の title・link・description・pubDate、item の title・link・pubDate・content:encoded）を確かめる。
細かい中身（リンク・写真・日時）は tests/test_smartnews_feed.cjs が見る。
"""
import email.utils
import os
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
    "snf": "http://www.smartnews.be/snf",
    "dc": "http://purl.org/dc/elements/1.1/",
}
RENDER = """
const path = require("node:path");
const { createJiti } = require("jiti");
const root = process.cwd();
const jiti = createJiti(path.join(root, "x.js"), { alias: { "@": root }, interopDefault: true });
jiti.import(path.join(root, "lib/smartnews-feed.ts")).then((m) => m.smartnewsFeedXml()).then(({ xml }) => process.stdout.write(xml));
"""


@unittest.skipUnless(shutil.which("node") and (ROOT / "node_modules" / "jiti").exists(), "node と npm ci が必要")
class SmartnewsFeedXml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = {**os.environ, "NEXT_PUBLIC_SITE_URL": "https://ai-tech-express.jp"}
        out = subprocess.run(["node", "-e", RENDER], cwd=ROOT, env=env, capture_output=True, check=True, timeout=120)
        cls.raw = out.stdout
        cls.root = ET.fromstring(cls.raw)

    def test_channel(self):
        self.assertEqual(self.root.tag, "rss")
        self.assertEqual(self.root.get("version"), "2.0")
        ch = self.root.find("channel")
        self.assertEqual(ch.findtext("title"), "サイソクニュース")
        self.assertEqual(ch.findtext("link"), "https://ai-tech-express.jp")
        self.assertTrue(0 < len(ch.findtext("description")) <= 15)
        self.assertIsNotNone(email.utils.parsedate_to_datetime(ch.findtext("pubDate")))
        self.assertEqual(ch.findtext("language"), "ja")
        self.assertTrue(1 <= int(ch.findtext("ttl")) <= 15)
        self.assertTrue(ch.findtext("snf:logo/url", namespaces=NS).startswith("https://ai-tech-express.jp/"))
        self.assertLessEqual(len(self.raw), 1_000_000)

    def test_items(self):
        items = self.root.find("channel").findall("item")
        self.assertGreaterEqual(len(items), 5)
        links = [it.findtext("link") for it in items]
        self.assertEqual(len(links), len(set(links)), "同じ記事を2回載せない")
        for it in items:
            for tag in ("title", "link", "pubDate", "description"):
                self.assertTrue((it.findtext(tag) or "").strip(), tag)
            self.assertIsNotNone(email.utils.parsedate_to_datetime(it.findtext("pubDate")))
            self.assertTrue((it.findtext("content:encoded", namespaces=NS) or "").strip())
            self.assertTrue(it.find("media:thumbnail", NS).get("url").startswith("https://"))
            self.assertEqual(it.findtext("media:status", namespaces=NS), "active")


if __name__ == "__main__":
    unittest.main()
