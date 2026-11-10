"""提携先の配信ファイル（グノシー・スマートニュース）のサイトの説明が、サイトの軸に合っているか（2026-11-10 オーナー承認）。

昔の「海外AIの新発表を最速で…」のままだった。軸は台帳 A61「暮らしとお金の『自分ごと』ニュース」。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PartnerFeedDescriptionTest(unittest.TestCase):
    def test_feeds_use_site_feed_description(self):
        for rel, key in (("app/feeds/gunosy.xml/route.ts", "feedDescription"), ("lib/smartnews-feed.ts", "feedShortDescription")):
            text = (ROOT / rel).read_text("utf-8")
            self.assertIn("<description>${escapeXml(siteConfig.%s)}</description>" % key, text, rel)
            self.assertNotIn("海外AIの新発表", text, rel)

    def test_feed_description_matches_axis(self):
        config = (ROOT / "site.config.ts").read_text("utf-8")
        m = re.search(r'feedDescription:\s*"([^"]+)"', config)
        self.assertIsNotNone(m)
        text = m.group(1)
        self.assertIn("暮らしとお金の「自分ごと」ニュース", text)
        self.assertIn("公式発表", text)
        self.assertNotIn("海外AI", text)
        self.assertNotIn("｜", text)
        self.assertLessEqual(len(text), 100)
        short = re.search(r'feedShortDescription:\s*"([^"]+)"', config).group(1)
        self.assertIn("暮らしとお金", short)
        self.assertLessEqual(len(short), 15)  # スマートニュースの仕様


if __name__ == "__main__":
    unittest.main()
