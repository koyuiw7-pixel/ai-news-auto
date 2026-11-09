"""手動の速報（Actions で fast_url だけを入れて起動した回）が、登録外の公式の一次情報を受け付けること（2026-11-09）。

ニトリHDの不正アクセスのお知らせ（公式サイトの PDF）を手動で起動したら「[fast] 対象外の URL のため処理しません」で止まった。
速報レーンは登録した発信元・レーダーの一次情報・報道機関のホストしか受け付けなかったため。
手動（fast_meta が空）のときだけ、会社・官公庁・自治体・団体の日本のドメインと会社の .com/.jp（PDF も）を受け付ける。
報道機関・配信サービス・SNS・ブログ・blocked_hosts は手動でも受け付けない。Worker の自動の起動（fast_meta あり）は今までどおり。
あわせて、PDF の題名を本文から取り出す（PDF には見出しの欄が無く「見出しが取れない」で止まるため）。
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fast_lane  # noqa: E402
import feeds  # noqa: E402
import web_articles  # noqa: E402

NITORI_PDF = "https://www.nitorihd.co.jp/news/items/2b702dbe4d438f7fef74945d68e5bd27.pdf"
NITORI_TITLE = "当社システムへの不正アクセスによる個人情報漏えいの可能性に関するお詫びとお知らせ"
NITORI_TEXT = (
    "お客様各位\n2026 年 11 月 9 日\n株式会社ニトリホールディングス\n\n"
    "当社システムへの不正アクセスによる\n個人情報漏えいの可能性に関するお詫びとお知らせ\n\n"
    "平素より、当社グループをご愛顧いただき、誠にありがとうございます。" + "本文の説明です。" * 300
)


class ManualOfficialUrlTest(unittest.TestCase):
    def test_official_japanese_domains_pass_only_when_manual(self):
        for url in [
            NITORI_PDF,
            "https://www.city.yokohama.lg.jp/kurashi/notice.html",
            "https://www.jfc.or.jp/news/a.pdf",
            "https://www.u-tokyo.ac.jp/focus/ja/press/z0508.html",
            "https://global.toyota.com/jp/newsroom/corporate/12345.html",
            "https://www.example-maker.jp/news/2026/1109.pdf",
            "https://www.mhlw.go.jp/content/001234567.pdf",
        ]:
            self.assertTrue(fast_lane.allowed_url(url, manual=True), url)
        self.assertFalse(fast_lane.allowed_url(NITORI_PDF))  # Worker の自動の起動は今までどおり

    def test_wires_news_sns_blogs_are_rejected_even_when_manual(self):
        for url in [
            "https://prtimes.jp/main/html/rd/p/000000001.000000001.html",
            "https://www.atpress.ne.jp/news/1",
            "https://www3.nhk.or.jp/news/html/20261109/k1.html",
            "https://www.nikkei.com/article/DGXZQO1/",
            "https://news.yahoo.co.jp/articles/abc",
            "https://www.yomiuri.co.jp/national/1/",
            "https://toyokeizai.net/articles/-/1",
            "https://www.itmedia.co.jp/news/articles/1.html",
            "https://x.com/nitori_official/status/1",
            "https://www.youtube.com/watch?v=abc",
            "https://note.com/someone/n/abc",
            "https://ameblo.jp/someone/entry-1.html",
            "https://www.facebook.com/nitori",
        ]:
            self.assertFalse(fast_lane.manual_official_url(url), url)

    def test_blocked_hosts_are_rejected_when_manual(self):
        for host in fast_lane.rules()["radar"]["blocked_hosts"]:
            self.assertFalse(fast_lane.allowed_url(f"https://{host}/news/1", manual=True), host)

    def test_shape_rules(self):
        self.assertFalse(fast_lane.allowed_url("http://www.nitorihd.co.jp/a.pdf", manual=True))  # https だけ
        self.assertFalse(fast_lane.allowed_url("https://example.org/news", manual=True))  # 対象外のドメイン
        self.assertFalse(fast_lane.allowed_url("https://user@www.nitorihd.co.jp/a", manual=True))
        self.assertFalse(fast_lane.allowed_url("not a url", manual=True))


class BuildFastItemsTest(unittest.TestCase):
    def _run(self, meta_raw: str):
        page = {"text": NITORI_TEXT[: feeds.TEXT_CAP], "image": None, "title": feeds.pdf_title(NITORI_TEXT),
                "description": "", "published": "", "final_url": NITORI_PDF, "links": []}
        with patch.object(feeds, "fetch_article_text", return_value=page) as fetch, \
                patch.object(fast_lane, "load_acks", return_value={}):
            items, results = web_articles.build_fast_items(
                [NITORI_PDF], meta_raw, {"processed_web": {}}, datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc))
        return items, results, fetch

    def test_manual_dispatch_builds_the_official_pdf(self):
        items, results, _ = self._run("")
        self.assertEqual(results, {})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], NITORI_TITLE)
        self.assertEqual(items[0]["lang"], "ja")
        self.assertFalse(items[0].get("secondary"))

    def test_worker_dispatch_with_meta_stays_strict(self):
        meta = '[{"url": "%s", "detectedAt": "2026-11-09T10:00:00Z"}]' % NITORI_PDF
        items, results, fetch = self._run(meta)
        self.assertEqual(items, [])
        self.assertEqual([r["reason"] for r in results.values()], ["対象外のURL"])
        fetch.assert_not_called()

    def test_manual_news_site_is_still_skipped(self):
        with patch.object(fast_lane, "load_acks", return_value={}):
            items, results = web_articles.build_fast_items(
                ["https://www.nikkei.com/article/DGXZQO1/"], "", {"processed_web": {}}, datetime(2026, 11, 9, tzinfo=timezone.utc))
        self.assertEqual(items, [])
        self.assertEqual([r["reason"] for r in results.values()], ["対象外のURL"])


class PdfTitleTest(unittest.TestCase):
    def test_nitori_notice(self):
        self.assertEqual(feeds.pdf_title(NITORI_TEXT), NITORI_TITLE)

    def test_disclosure_header_lines_are_skipped(self):
        text = ("2026年11月9日\n各 位\n会 社 名 株式会社テスト\n代表者名 代表取締役社長 山田太郎\n"
                "（コード番号：1234 東証プライム）\n問合せ先 経理部長 鈴木\n業績予想の修正に関するお知らせ\n当社は、…")
        self.assertEqual(feeds.pdf_title(text), "業績予想の修正に関するお知らせ")

    def test_government_release(self):
        text = "報道関係者各位\n令和8年11月9日\n厚生労働省\n\n新しい制度の開始について\n\n本日、…"
        self.assertEqual(feeds.pdf_title(text), "新しい制度の開始について")

    def test_english_release(self):
        text = "NEWS RELEASE\nNovember 9, 2026\nAcme Announces New Battery Factory in Japan\nTOKYO — Acme said"
        self.assertEqual(feeds.pdf_title(text), "Acme Announces New Battery Factory in Japan")

    def test_empty(self):
        self.assertEqual(feeds.pdf_title(""), "")


class PdfFetchUserAgentTest(unittest.TestCase):
    def test_pdf_fetch_sends_a_browser_user_agent(self):
        """nitorihd.co.jp は curl の既定の UA には何も返さない。PDF を読む経路もブラウザの UA を送る"""
        seen = {}

        class Response:
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                return b"%PDF-1.7"

            def geturl(self):
                return NITORI_PDF

        def fake_urlopen(request, timeout=None, context=None):
            seen.update({k.lower(): v for k, v in request.header_items()})
            return Response()

        with patch.object(feeds.urllib.request, "urlopen", fake_urlopen):
            feeds.fetch(NITORI_PDF, accept="application/pdf,*/*;q=0.8")
        ua = seen["user-agent"]
        self.assertTrue(ua.startswith("Mozilla/5.0") and "Chrome/" in ua, ua)
        self.assertNotIn("curl", ua.lower())
        self.assertNotIn("python", ua.lower())


if __name__ == "__main__":
    unittest.main()
