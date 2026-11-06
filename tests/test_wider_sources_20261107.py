"""2026-11-07 オーナー「テーマが狭い。日本で注目のニュースを拾えていない。監視する場所を増やす。Yahooニュースに勝つつもりで」（台帳 A51）。
公式の一次情報の発信元を増やす（RSS の無いものは公式のお知らせ一覧のページを読む）。外部への通信なし（HTML は手元の例）。"""

import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import feeds  # noqa: E402
import genres  # noqa: E402
import public_interest  # noqa: E402

JST = timezone(timedelta(hours=9))
NEW = {
    "jma-press", "env-press", "mlit-bousai", "nta-news", "cfa-news", "nenkin", "kokusen", "tepco", "tepco-ep", "tokyo-gas", "osaka-gas",
    "japanpost", "nissin", "kewpie", "house-foods", "nipponham", "rakuten-mobile-info", "jrwest", "jrcentral", "e-nexco", "caa-recall",
    "pmda-safety", "lawson", "familymart", "sharp", "mazda", "subaru", "usj", "jleague", "bleague", "pref-aichi",
}
# 報道機関・事件事故・芸能の発信元は足さない（W31・オーナーの判断待ち）
PRESS_HOSTS = re.compile(r"nhk\.or\.jp|yahoo\.co\.jp|asahi\.com|yomiuri|mainichi|nikkei\.com|sankei|kyodo|jiji\.com|oricon|sponichi|nikkansports")


class WiderSourcesTest(unittest.TestCase):
    def test_new_feeds_are_registered_and_valid(self):
        by_slug = {f["slug"]: f for f in feeds.BROAD_FEEDS}
        self.assertTrue(NEW <= set(by_slug), sorted(NEW - set(by_slug)))
        sections = {g.slug for g in genres.WEB_GENRES} | {"auto"}
        for slug in NEW:
            f = by_slug[slug]
            self.assertEqual(f["lang"], "ja", slug)
            self.assertIn(f["section"], sections, slug)
            self.assertIn(f["kind"], ("gov", "company"), slug)
            self.assertNotRegex(f["url"], PRESS_HOSTS, slug)
            if f.get("include_re"):
                re.compile(f["include_re"])
        slugs = [f["slug"] for f in feeds.FEEDS + feeds.BROAD_FEEDS]
        self.assertEqual(len(slugs), len(set(slugs)), "slug が重なっている")

    def test_html_list_parser_reads_dated_rows(self):
        page = """<ul>
          <li><span class="date">2026年11月5日</span><a href="/oshirase/2026/1105.html">大津年金事務所における電話の復旧について</a></li>
          <li><time>2026/11/02</time><p><a href="/news/2026_11_02_1">SUBARU サンバーバンの一部改良モデルを発表</a></p></li>
          <li><a href="/about/">機構について（日付なし）</a></li>
          <li><span>2099年1月1日</span><a href="/event.html">先の日付の工事のお知らせです</a></li>
          <li><span>令和8年10月30日</span><a href="https://other.example.com/x">別のホストへのリンクです</a></li>
        </ul>"""
        items = feeds.parse_html_list({"slug": "t", "name": "t", "url": "https://www.example.go.jp/"}, page.encode())
        self.assertEqual([i["title"] for i in items], ["大津年金事務所における電話の復旧について", "SUBARU サンバーバンの一部改良モデルを発表"])
        self.assertEqual(items[0]["published_at"], datetime(2026, 11, 5, tzinfo=JST))
        self.assertEqual(items[0]["url"], "https://www.example.go.jp/oshirase/2026/1105.html")

    def test_html_list_carry_mode_uses_heading_date(self):
        page = """<summary>2026年11月06日発表</summary><ul><li><a href="/press/press_05804.html">電力専門委員会の開催について</a></li></ul>
                  <summary>2026年11月05日発表</summary><ul><li><a href="/press/press_05790.html">熱中症の発生状況の取りまとめについて</a></li></ul>"""
        feed = {"slug": "env", "name": "環境省", "url": "https://www.env.go.jp/press/", "date_mode": "carry", "link_re": r"/press/press_"}
        items = feeds.parse_html_list(feed, page.encode())
        self.assertEqual([(i["title"][:6], i["published_at"].day) for i in items], [("電力専門委員", 6), ("熱中症の発生", 5)])

    def test_jma_press_list(self):
        js = ("array[num++] = ['1','/jma/press/2611/04a/meakandake_20261104.html','8','11','4','雌阿寒岳の噴火警戒レベルを１へ引下げ']\n"
              "array[num++] = ['0','https://www.wxbc.jp/x/','8','11','2','セミナーを開催します']\n")
        with patch.object(feeds, "fetch", return_value=(js.encode(), "")):
            items = feeds.parse_feed({"slug": "jma-press", "name": "気象庁", "url": "https://www.jma.go.jp/jma/press_list.js", "type": "jma_press"})
        self.assertEqual(len(items), 1)  # お知らせ（種類 0）は外し、報道発表だけ
        self.assertEqual(items[0]["published_at"], datetime(2026, 11, 4, tzinfo=JST))
        self.assertTrue(items[0]["url"].startswith("https://www.jma.go.jp/jma/press/2611/"))

    def test_recall_titles_from_new_sources_are_public_interest(self):
        for title in ("食料品 いとめん本店「伊勢うどん のたれ」 - 返金／回収", "[医療]クラスI回収 該当回収品目 ARROW PICカテーテルキット HP"):
            self.assertEqual(public_interest.category(title), "recall", title)

    def test_ledger_row(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next((line for line in rules.splitlines() if line.startswith("| A51 |")), "")
        self.assertIn("監視する場所を増やす", row)
        self.assertIn("2026-11-07", row)


if __name__ == "__main__":
    unittest.main()
