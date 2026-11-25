"""報道が出典の記事（press）と動画だけから作った記事（video-only）を検索に出さない（2026-11-25 AdSense の申請の前の点検）。

- 報道機関・ニュースの集約サイト（dメニューニュース・Yahoo!ニュース・NHK・日経・TBS など）を出典にした記事は noindex・サイトマップに入れない
- YouTube などの動画だけから作った記事も同じ
- どちらも記事は消さない（scripts/retire_articles.py の noindex の取り下げの対象にしない）
- サイト側（lib/indexing.ts）と同じ判定（lib/index-rules.json の pressHosts。ずれは tests/test_index_rules.py が見る）
ネットワーク・LLM は使わない。
"""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import retire_articles  # noqa: E402

BODY = "## 概要\n" + "本文の説明です。" * 200
BASE = {"slug": "x", "title": "題名", "body": BODY, "genreSlug": "public", "sourceType": "web", "videoId": "",
        "sourceUrl": "https://www.mhlw.go.jp/stf/houdou/0000.html", "channelSlug": "mhlw"}


class PressSourcedTest(unittest.TestCase):
    def test_news_hosts_are_press(self):
        for url in ("https://topics.smt.docomo.ne.jp/article/abc", "https://news.yahoo.co.jp/articles/1", "https://news.web.nhk/newsweb/na/1",
                    "https://www.nikkei.com/article/DGX", "https://business.nikkei.com/atcl/1", "https://newsdig.tbs.co.jp/articles/-/1",
                    "https://news.tv-asahi.co.jp/news_society/articles/1", "https://www.yomiuri.co.jp/national/1", "https://www.asahi.com/articles/1",
                    "https://www.nikkansports.com/general/news/1.html", "https://www3.nhk.or.jp/news/html/1.html"):
            self.assertTrue(indexnow.press_host(url), url)
            self.assertEqual(indexnow.noindex_reason({**BASE, "sourceUrl": url}), "press", url)

    def test_official_hosts_are_not_press(self):
        for url in ("https://www.mhlw.go.jp/stf/1.html", "https://www.docomo.ne.jp/info/notice/1.html", "https://www.nhk.or.jp/info/1.html",
                    "https://www.starbucks.co.jp/youkou/luckybag/", "https://about.yahoo.co.jp/pr/1", "", "not a url"):
            self.assertFalse(indexnow.press_host(url), url)
        self.assertIsNone(indexnow.noindex_reason(BASE))

    def test_press_marks(self):
        self.assertEqual(indexnow.noindex_reason({**BASE, "pressOnly": True}), "press")
        self.assertEqual(indexnow.noindex_reason({**BASE, "awaitingOfficial": True}), "press")
        self.assertEqual(indexnow.noindex_reason({**BASE, "pressReport": True}), "press")
        self.assertEqual(indexnow.noindex_reason({**BASE, "channelSlug": "radar-itmedia.co.jp"}), "press")
        # 報道から作り、あとで公式の発表で確かめ直した記事（scripts/trend_lane.py の mark_official_found）は検索に出す
        confirmed = {**BASE, "pressReport": True, "awaitingOfficial": False, "officialSourceUrl": "https://www.sony.jp/x/"}
        self.assertIsNone(indexnow.noindex_reason(confirmed))
        self.assertIsNone(indexnow.noindex_reason({**BASE, "channelSlug": "radar-official"}))
        # 手で決めた indexable が先
        self.assertIsNone(indexnow.noindex_reason({**BASE, "pressOnly": True, "indexable": True}))


class VideoOnlyTest(unittest.TestCase):
    def test_video_articles(self):
        video = {**BASE, "sourceType": None, "videoId": "abc", "sourceUrl": None}
        video.pop("sourceType")
        self.assertEqual(indexnow.noindex_reason(video), "video-only")
        self.assertIsNone(indexnow.noindex_reason({**video, "type": "roundup"}))
        self.assertIsNone(indexnow.noindex_reason({**BASE, "videoId": "abc"}))  # 公式の文章が出典（web）なら出す


class NotRetiredTest(unittest.TestCase):
    def test_noindex_plan_keeps_press_and_video_articles(self):
        press = {**BASE, "slug": "press-a", "title": "報道の記事", "sourceUrl": "https://news.yahoo.co.jp/articles/1"}
        video = {**BASE, "slug": "video-a", "title": "動画の記事", "sourceType": "video", "videoId": "abc", "sourceUrl": ""}
        picked, _ = retire_articles.plan_noindex([press, video], datetime(2026, 11, 25, tzinfo=timezone.utc))
        self.assertEqual(picked, {})


class RulesExportTest(unittest.TestCase):
    def test_press_hosts_are_exported_for_the_site(self):
        rules = json.loads((ROOT / "lib" / "index-rules.json").read_text("utf-8"))
        self.assertEqual(rules["pressHosts"], sorted(indexnow.PRESS_SOURCE_HOSTS))
        self.assertIn("topics.smt.docomo.ne.jp", rules["pressHosts"])
        self.assertIn("press", indexnow.NOINDEX_LABELS)
        self.assertIn("video-only", indexnow.NOINDEX_LABELS)


if __name__ == "__main__":
    unittest.main()
