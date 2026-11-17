"""2026-11-18 オーナー「他にもあなたが勝手に作ったルールで公式の画像使えていないの多いんじゃない？そういうの本当に勿体無いからさ」
「放送の切り抜きはOK、権利表記つけて使って」（台帳 I11）。

AI が作った決まりで公式の画像を落としていたところを外し、公式の画像を先に使う。オーナーの決まり（ニュースサイトの写真は使わない＝I1、
調査会社の画像は使わない＝A37、官公庁のロゴの使い回しをしない＝S49）は今までどおり守る（通信しない）。
"""

import io
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import images  # noqa: E402


def web(channel_slug: str, url: str, name: str, **extra) -> dict:
    return {"sourceType": "web", "channelSlug": channel_slug, "sourceUrl": url, "sourceName": name, "channel": name, **extra}


def png(size=(1200, 630), box=True) -> bytes:
    image = images.Image.new("RGB", size, (255, 255, 255))
    if box:
        image.paste((200, 20, 30), (size[0] // 3, size[1] // 3, size[0] * 2 // 3, size[1] * 2 // 3))
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def collector(html: str):
    parser = images._PageCollector()
    parser.feed(html)
    return parser


class OfficialByHostTest(unittest.TestCase):
    def test_go_jp_source_is_official_without_registered_feed(self):
        self.assertEqual(images.official_source(web("nta-go-jp", "https://www.nta.go.jp/information/release/2026/x.htm", "国税庁")), {"wire": ""})
        self.assertEqual(images.official_source(web("fast", "https://www.city.yokohama.lg.jp/kurashi/x.html", "横浜市")), {"wire": ""})
        self.assertEqual(images.official_source(web("fast", "https://www.boj.or.jp/statistics/x.htm", "日本銀行")), {"wire": ""})

    def test_tdnet_is_official(self):
        self.assertEqual(images.official_source(web("fast", "https://www.release.tdnet.info/inbs/140120261118500000.pdf", "TDnet")), {"wire": ""})

    def test_company_own_site_is_official(self):
        # 会社のサイトの発表のページ・ホストから作ったフィードの記事
        self.assertEqual(images.official_source(web("fast", "https://www.mcdonalds.co.jp/company/news/2026/1118a/", "日本マクドナルド")), {"wire": ""})
        self.assertEqual(images.official_source(web("starbucks-co-jp", "https://www.starbucks.co.jp/beverage/x", "スターバックス")), {"wire": ""})
        self.assertEqual(images.official_source(web("fast", "https://www.jleague.jp/news/article/1234/", "Jリーグ")), {"wire": ""})

    def test_news_outlet_is_still_not_official(self):
        # 台帳 I1: ニュースサイト・放送局の写真は使わない
        for url in ("https://news.web.nhk/newsweb/na/na-k10014990001000", "https://newsdig.tbs.co.jp/articles/-/1234",
                    "https://www.okinawatimes.co.jp/articles/-/1234", "https://www.nikkei.com/article/DGXZQO1/",
                    "https://www.asahi.com/articles/ASV1.html", "https://www.nikkansports.com/baseball/news/2026.html",
                    "https://news.yahoo.co.jp/articles/abc"):
            self.assertIsNone(images.official_source(web("fast", url, "報道")), url)
            self.assertIsNone(images.official_source(web("trends", url, "報道")), url)

    def test_research_firm_is_still_not_official(self):
        # 台帳 A37: 調査会社・情報会社のサイトの写真は使わない
        self.assertIsNone(images.official_source(web("tsr", "https://www.tsr-net.co.jp/data/detail/1.html", "東京商工リサーチ")))
        self.assertIsNone(images.official_source(web("nli-research", "https://www.nli-research.co.jp/report/detail/id=1?site=nli", "ニッセイ基礎研究所")))
        self.assertIsNone(images.official_source(web("fast", "https://www.tdb.co.jp/report/economic/20261118/", "帝国データバンク")))

    def test_platforms_and_unknown_pages_are_not_official(self):
        self.assertIsNone(images.official_source(web("fast", "https://note.com/someone/n/n123", "誰か")))
        self.assertIsNone(images.official_source(web("some-new-feed", "https://example.com/x", "例")))
        self.assertIsNone(images.official_source(web("radar-techcrunch.com", "https://techcrunch.com/x", "TechCrunch")))


class SocialImageTest(unittest.TestCase):
    def test_official_account_images_allowed_random_users_blocked(self):
        img = "https://pbs.twimg.com/media/abc.jpg"
        official = web("nvidia-blog", "https://x.com/nvidia/status/1", "NVIDIA")
        self.assertIsNone(images.agency_problem(img, "", official))
        self.assertIsNotNone(images.agency_problem(img, "", web("fast", "https://www.example-corp.co.jp/news/1/", "例")))
        self.assertIsNotNone(images.agency_problem(img))
        self.assertIsNotNone(images.agency_problem("https://www.reuters.com/x.jpg", "", official))


class SizeTest(unittest.TestCase):
    def test_portrait_and_small_official_photos_are_used(self):
        self.assertIsNone(images.size_ok("photo", 600, 900))  # 縦長の製品写真
        self.assertIsNone(images.size_ok("photo", 420, 300))
        self.assertIsNotNone(images.size_ok("photo", 300, 200))
        self.assertIsNone(images.size_ok("dense", 720, 400))
        self.assertGreaterEqual(images.VISION_BUDGET, 12)
        self.assertGreaterEqual(images.FETCH_BUDGET, 20)

    def test_portrait_is_blur_filled_not_cropped(self):
        tall = images.Image.new("RGB", (600, 900), (10, 120, 200))
        out = images.blur_fill(tall)
        self.assertEqual(out.size, (images.OUT_W, images.OUT_H))


class HeroTest(unittest.TestCase):
    def test_ogp_filename_is_no_longer_rejected(self):
        photo = images.Image.new("RGB", (1200, 675), (40, 90, 140))
        ok, _ = images.hero_ok(photo, "photo", "https://corp.example.co.jp/uploads/ogp_eyecatch.jpg", vision=lambda *a, **k: "no")
        self.assertTrue(ok)
        ok, _ = images.hero_ok(photo, "banner", "https://corp.example.co.jp/img/kv.jpg", vision=lambda *a, **k: None)
        self.assertTrue(ok)  # 判定できないときは出す
        ok, _ = images.hero_ok(photo, "photo", "https://corp.example.co.jp/img/a.jpg", vision=lambda *a, **k: "yes")
        self.assertFalse(ok)  # 画像判定が「ほとんど文字」と答えたものだけ落とす


class OfficialBeforeAiTest(unittest.TestCase):
    def ctx(self):
        return {"repeats": Counter(), "used_stock": set(), "credit_by_thumb": {}, "official_by_original": {}, "dry_run": True,
                "fast": False, "ai_only": False, "defer_hours": 3, "retry_ai": False, "repick": True, "scene": "",
                "previous_credit": {}, "previous_thumb": {}}

    def test_official_banner_beats_ai_for_any_article(self):
        # 発表ではない記事（値上げのお知らせ）でも、公式のバナーは AI の作り物・素材より先
        article = web("fast", "https://www.example-corp.co.jp/news/2026/1118.html", "株式会社例",
                      slug="example-price-up", title="例の主力商品、12月から値上げ　対象と今やること", publishedAt="2026-11-18T00:00:00Z")
        image = images.Image.new("RGB", (1200, 630), (180, 60, 40))
        best = {"kind": "banner", "url": "https://www.example-corp.co.jp/news/img/banner.jpg", "image": image,
                "rank": images.OFFICIAL_RANK["banner"], "where": "body"}
        with mock.patch.object(images, "pick_official", return_value={"best": best, "found": [best], "reasons": []}), \
                mock.patch.object(images, "store", return_value=("https://ai-tech-express.jp/img/example-price-up-1a2b3c4d.jpg", (1200, 630))), \
                mock.patch.object(images, "generate_ai", side_effect=AssertionError("AI を作らない")), \
                mock.patch.object(images, "find_stock", side_effect=AssertionError("素材を探さない")):
            self.assertEqual(images.process(Path("/nonexistent/example-price-up.json"), article, self.ctx()), "official")
        self.assertEqual(article["imageCredit"]["imageKind"], "banner")


class LogoTest(unittest.TestCase):
    LOGO = "https://www.example-corp.co.jp/common/img/logo.png"

    def pick(self, page: str, others: set[str]):
        html = f'<html><head><meta property="og:image" content="{self.LOGO}"></head><body><article><p>本文</p></article></body></html>'
        article = web("fast", page, "株式会社例", slug="x", title="例が新サービス", publishedAt="2026-11-18T00:00:00Z")
        with mock.patch.dict(images.PARSE_CACHE, {page: (collector(html), page)}), \
                mock.patch.dict(images.PAGES_BY_IMAGE, {self.LOGO: set(others)} if others else {}, clear=True), \
                mock.patch.object(images, "http_get", return_value=(png(), "image/png", self.LOGO)), \
                mock.patch.object(images, "cf_vision", return_value=None), \
                mock.patch.object(images, "youtube_official", return_value=None):
            return images.pick_official(article, Counter())

    def test_company_own_og_logo_is_allowed(self):
        result = self.pick("https://www.example-corp.co.jp/news/2026/1118.html", set())
        self.assertTrue(result["best"] and result["best"].get("ownOg"))
        self.assertTrue(images.cover_worthy(result["best"]))

    def test_unrelated_reused_logo_is_still_rejected(self):
        # 台帳 S49: ほかの発表（別のページ）でも使われている画像はサイト共通のロゴ。記事の画像にしない
        result = self.pick("https://www.example-corp.co.jp/news/2026/1118.html", {"https://www.example-corp.co.jp/news/2026/0901.html"})
        self.assertFalse(images.cover_worthy(result["best"]))

    def test_ministry_logo_is_still_rejected(self):
        page = "https://www.mhlw.go.jp/stf/newpage_1.html"
        logo = "https://www.mhlw.go.jp/common/img/logo.png"
        html = f'<html><head><meta property="og:image" content="{logo}"></head><body><article><p>本文</p></article></body></html>'
        article = web("mhlw-go-jp", page, "厚生労働省", slug="y", title="防じんマスクの回収", publishedAt="2026-11-18T00:00:00Z")
        with mock.patch.dict(images.PARSE_CACHE, {page: (collector(html), page)}), \
                mock.patch.object(images, "http_get", return_value=(png(), "image/png", logo)), \
                mock.patch.object(images, "cf_vision", return_value=None):
            result = images.pick_official(article, Counter())
        self.assertFalse(images.cover_worthy(result["best"]))


class YoutubeTest(unittest.TestCase):
    def test_channel_linked_from_company_site_is_official(self):
        article = web("fast", "https://www.example-corp.co.jp/news/2026/1118.html", "株式会社例", title="例が新型を発表")
        data = {"author_name": "Brand Films", "author_url": "https://www.youtube.com/@brandfilms", "title": "Brand Story"}
        with mock.patch.object(images, "http_json", return_value=data):
            self.assertIsNone(images.youtube_official("abcdefghijk", article, []))
            links = [("https://www.youtube.com/@brandfilms", "YouTube", True)]
            self.assertIsNotNone(images.youtube_official("abcdefghijk", article, links))

    def test_company_name_without_corporate_words_matches(self):
        article = web("fast", "https://global.toyota/jp/newsroom/x.html", "トヨタ自動車株式会社", title="トヨタが新型車")
        data = {"author_name": "トヨタ自動車 公式チャンネル", "author_url": "https://www.youtube.com/@toyota", "title": "x"}
        with mock.patch.object(images, "http_json", return_value=data):
            self.assertIsNotNone(images.youtube_official("abcdefghijk", article, []))

    def test_body_video_skips_title_keyword_check(self):
        html = '<html><body><article><iframe src="https://www.youtube.com/embed/abcdefghijk"></iframe></article></body></html>'
        self.assertIn("abcdefghijk", collector(html).youtube_body)
        side = '<html><body><aside><iframe src="https://www.youtube.com/embed/abcdefghijk"></iframe></aside></body></html>'
        self.assertNotIn("abcdefghijk", collector(side).youtube_body)


class RepickTargetTest(unittest.TestCase):
    def test_ai_cover_on_official_source_is_a_target(self):
        a = web("nta-go-jp", "https://www.nta.go.jp/x.htm", "国税庁", thumbnail="https://ai-tech-express.jp/img/x.jpg", imageCredit={"kind": "ai"})
        self.assertTrue(images.official_repick_target(a))
        self.assertFalse(images.official_repick_target({**a, "imageCredit": {"kind": "official"}}))
        self.assertFalse(images.official_repick_target({**a, "sourceUrl": "https://news.web.nhk/x"}))
        self.assertFalse(images.official_repick_target({**a, "noPhoto": True}))


if __name__ == "__main__":
    unittest.main()
