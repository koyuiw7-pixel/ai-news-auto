"""2026-11-12 オーナー「記事を少しずつ増やす」: 上限（1日200本）ではなく、暮らし・お金の公式の候補の数が足りていなかった
（1回 1〜6件・暮らし・お金の記事は 18%／めやす 60%）。値上げ・料金・手数料・金利・情報流出・リコールを公式に出す大手ブランドを足し、
読めなくなっていたりそなの RSS（題名の「M&A」）を読めるようにし、題名の末尾のファイルの大きさを外す（外部への通信なし）。"""

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import feeds  # noqa: E402
import genres  # noqa: E402
import news_mix  # noqa: E402

NEW = {"docomo-news-release", "povo", "miraiz-chuden", "tepco-pg", "netbk", "smtb", "nitori", "ppih", "kfc",
       "nippn", "nissui", "yokohama-rubber", "mitsubishi-motors"}


class LifeBrandSourcesTest(unittest.TestCase):
    def test_new_feeds_are_registered_and_valid(self):
        by_slug = {f["slug"]: f for f in feeds.BROAD_FEEDS}
        self.assertTrue(NEW <= set(by_slug), sorted(NEW - set(by_slug)))
        sections = {g.slug for g in genres.WEB_GENRES} | {"auto"}
        for slug in NEW:
            f = by_slug[slug]
            self.assertEqual(f["lang"], "ja", slug)
            self.assertIn(f["section"], sections, slug)
            self.assertEqual(f["kind"], "company", slug)
            self.assertTrue(f["url"].startswith("https://"), slug)
            for key in ("link_re", "include_re", "exclude_re"):
                if f.get(key):
                    re.compile(f[key])
        slugs = [f["slug"] for f in feeds.FEEDS + feeds.BROAD_FEEDS]
        self.assertEqual(len(slugs), len(set(slugs)), "slug が重なっている")

    def test_no_excluded_ad_categories(self):
        # 化粧品・健康食品・宝くじなどの賭け事・成人向け・高リスクの投資・ローン・MLM の発信元は足さない
        banned = re.compile(r"コスメ|化粧品|サプリ|健康食品|宝くじ|競馬|競輪|パチンコ|カジノ|FX|暗号資産|ローン|キャッシング|消費者金融")
        for slug in NEW:
            self.assertNotRegex(feeds.FEEDS_BY_SLUG[slug]["name"], banned, slug)
        for slug in ("netbk", "smtb"):
            self.assertRegex("カードローンの金利", feeds.FEEDS_BY_SLUG[slug]["exclude_re"])

    def test_big_brand_items_count_as_life_or_brand(self):
        for slug in ("docomo-news-release", "povo", "nitori", "ppih"):
            self.assertIn(slug, news_mix.SOURCES["brand"], slug)
        self.assertEqual(news_mix.classify({"title": "2026年メンバーズカードポイント有効期限のお知らせ", "source_slug": "nitori"}), "money")
        self.assertEqual(news_mix.classify({"title": "家庭用製品価格改定のお知らせ", "source_slug": "nippn"}), "money")
        self.assertIn(news_mix.classify({"title": "引き出し収納に新たに3サイズが登場", "source_slug": "nitori"}), ("brand",))

    def test_nitori_list_title_drops_file_size(self):
        page = """<dl>
          <dt><em class="icon06">重要なお知らせ</em>2026/11/09</dt>
          <dd><a href="https://www.nitorihd.co.jp/news/items/abc_3.pdf" target="_blank">当社システムへの不正アクセスによる個人情報漏えいの可能性に関するお詫びとお知らせ[<img src="/blank.gif" alt="PDFファイルを開きます">419.0 KB]</a></dd>
          <dt>2026/11/09</dt>
          <dd><a href="https://www.nitorihd.co.jp/news/items/def.pdf">フィリピンへの8店舗目出店に関するお知らせ[ 854.5 KB]</a></dd>
          <dt>2026/11/09</dt>
          <dd><a href="https://www.nitorihd.co.jp/company/">会社情報</a></dd>
        </dl>"""
        feed = feeds.FEEDS_BY_SLUG["nitori"]
        items = feeds.parse_html_list(feed, page.encode())
        titles = [i["title"] for i in items]
        self.assertEqual(titles[0], "当社システムへの不正アクセスによる個人情報漏えいの可能性に関するお詫びとお知らせ")
        self.assertEqual(len(items), 2)  # 会社情報のリンクは link_re で外れる
        self.assertRegex(titles[1], feed["exclude_re"])  # 出店の告知は取らない

    def test_clean_title_keeps_plan_sizes(self):
        self.assertEqual(feeds.clean_title("円預金金利の改定について （103KB）"), "円預金金利の改定について")
        self.assertEqual(feeds.clean_title("家庭用製品価格改定のお知らせ 82 KB"), "家庭用製品価格改定のお知らせ")
        self.assertEqual(feeds.clean_title("上半期決算を発表 （別ウィンドウで開く）"), "上半期決算を発表")
        self.assertEqual(feeds.clean_title("供給停止状況などについて[PDF : 86KB]"), "供給停止状況などについて")
        self.assertEqual(feeds.clean_title("ギフト2種を新発売[ 2.4 MB]"), "ギフト2種を新発売")
        # 料金プランの容量は題名の中身なので外さない
        self.assertEqual(feeds.clean_title("ahamo 大盛り（110GB）を値下げ"), "ahamo 大盛り（110GB）を値下げ")
        self.assertEqual(feeds.clean_title("データ追加（500MB）"), "データ追加（500MB）")

    def test_rss_with_bare_ampersand_is_read(self):
        xml = ("<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>りそな</title>"
               "<item><title>M&Aキャピタルパートナーズとの資本業務提携について(331.9 KB)</title>"
               "<link>https://www.resona-gr.co.jp/holdings/news/a.pdf</link><pubDate>Tue, 10 Nov 2026 16:00:05 +0900</pubDate></item>"
               "<item><title>預金金利の改定 &amp; 手数料</title><link>https://www.resona-gr.co.jp/holdings/news/b.pdf</link>"
               "<pubDate>Tue, 10 Nov 2026 16:00:00 +0900</pubDate></item></channel></rss>").encode()
        with patch.object(feeds, "fetch", return_value=(xml, "https://example.invalid/rss.xml")):
            items = feeds.parse_feed({"slug": "resona", "name": "りそな", "url": "https://example.invalid/rss.xml", "lang": "ja"})
        self.assertEqual([i["title"] for i in items], ["M&Aキャピタルパートナーズとの資本業務提携について", "預金金利の改定 & 手数料"])

    def test_broken_xml_still_fails(self):
        with patch.object(feeds, "fetch", return_value=(b"<rss><channel><item><title>x</title></channel>", "https://example.invalid/")):
            with self.assertRaises(Exception):
                feeds.parse_feed({"slug": "x", "name": "x", "url": "https://example.invalid/", "lang": "ja"})


class FeedErrorLogTest(unittest.TestCase):
    def test_failed_feeds_are_named_without_error_text(self):
        import web_articles  # noqa: PLC0415
        lines = []
        report = {"ok": {"error": ""}, "capcom-ir": {"error": "ParseError: no element found: line 1"},
                  "nitori": {"error": "HTTPError: HTTP Error 403: Forbidden"}}
        with patch.object(web_articles, "log", lines.append):
            web_articles.log_feed_errors("broad", report)
        self.assertEqual(lines, ["[feed-health] broad 読めなかった発信元: capcom-ir(ParseError), nitori(HTTPError)"])
        lines.clear()
        with patch.object(web_articles, "log", lines.append):
            web_articles.log_feed_errors("AI", {"ok": {"error": ""}})
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()
