"""話題のレーンの報道の記事を、公式の資料の事実で 800字以上にする（2026-11-21 オーナー承認・AdSense の3回目の申請の準備）。
原因: 報道が出典の記事の指示が「本文は600〜1,100字・章は2〜3つ・サイソクの見方は書かない」で、報道2社の共通の事実だけを使うので、
11/20 の報道の記事17本が 800字未満（検索に出ない・台帳 A72）。公開中の 800字未満の話題の記事 79本のうち 69本が報道の記事だった。
直し方: ①話題の公式のページ（自治体・官公庁・会社。support_pages）を探して読み、窓口・やること・制度の説明の事実を足す
②長さの目安を 900〜1,600字にし、「サイソクの見方」の章（予測なし）を書く ③書き足し（own_view.ensure）を報道の記事にも1回する（保留はしない）。
出典（sources）は報道のまま（W31 の例外の形）。通信・LLM は使わない。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import own_view  # noqa: E402
import public_interest as pi  # noqa: E402
import quality  # noqa: E402
import trend_lane as tl  # noqa: E402
import web_articles as w  # noqa: E402

SRC = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
TERM = "前橋市 熊 出没 今日"
CITY_URL = "https://www.city.maebashi.gunma.jp/kurashi/bousai/kuma.html"
CITY_PAGE = {"title": "クマの出没情報｜前橋市", "final_url": CITY_URL,
             "text": "前橋市内でのクマの出没情報をお知らせします。" + "クマを見かけたら近づかず、農林課（電話027-000-0000）か警察に連絡してください。" * 6}


class LocalGovHostTest(unittest.TestCase):
    def test_local_government_domains_are_official(self):
        for url in (CITY_URL, "https://www.pref.gunma.jp/page/1234.html", "https://www.city.osaka.lg.jp/x/y.html",
                    "https://www.town.example.hokkaido.jp/a/b.html"):
            self.assertTrue(tl.is_official_url(url, set()), url)

    def test_other_domains_are_not(self):
        for url in ("https://city.example.co.jp/news/1.html", "https://www.city-news.jp/a/1.html", "https://www.yomiuri.co.jp/local/gunma/1/",
                    "https://www.city.maebashi.gunma.jp/", "http://www.city.maebashi.gunma.jp/kuma.html"):
            self.assertFalse(tl.is_official_url(url, set()), url)


class SupportPagesTest(unittest.TestCase):
    def test_pages_already_read_come_first_then_search(self):
        searched = []

        def search(q):
            searched.append(q)
            return ["https://www.yomiuri.co.jp/x/1.html", "https://www.pref.gunma.jp/page/kuma.html", "https://example.com/kuma"]

        def fetch(url):
            return {"title": "ツキノワグマの出没に注意｜群馬県", "text": "前橋市など県内でクマの出没が増えています。" * 20, "final_url": url}

        got = tl.support_pages(TERM, set(), pages=[{"url": CITY_URL, "page": CITY_PAGE}], search=search, fetch=fetch)
        self.assertEqual([p["url"] for p in got], [CITY_URL, "https://www.pref.gunma.jp/page/kuma.html"])
        self.assertEqual(got[0]["name"], "前橋市")
        self.assertEqual(searched, ["前橋市 熊 出没 公式"])  # 2本そろったら2回目の検索はしない
        self.assertNotIn("今日", tl.support_queries(TERM)[1])

    def test_unrelated_short_or_press_pages_are_dropped(self):
        pages = [{"url": "https://www.city.maebashi.gunma.jp/kosodate/1.html", "page": {"title": "子育て", "text": "保育園の案内。" * 60}},
                 {"url": "https://www.city.maebashi.gunma.jp/kuma2.html", "page": {"title": "前橋市 クマ", "text": "出没。"}},
                 {"url": "https://www.asahi.com/articles/A1.html", "page": {**CITY_PAGE, "final_url": ""}}]
        self.assertEqual(tl.support_pages(TERM, set(), pages=pages), [])

    def test_search_failure_does_not_raise(self):
        def boom(_q):
            raise TimeoutError("x")
        self.assertEqual(tl.support_pages(TERM, set(), search=boom, fetch=lambda u: {}), [])

    def test_fact_sources_and_source_text(self):
        got = tl.support_pages(TERM, set(), pages=[{"url": CITY_URL, "page": CITY_PAGE}])
        fs = tl.support_fact_sources(got)
        self.assertEqual(fs[0]["label"], "公式の資料")
        self.assertEqual(fs[0]["url"], CITY_URL)
        self.assertEqual(set(fs[0]), {"label", "name", "url", "checkedAt"})  # lib/articles.ts の FactSource
        self.assertIn("027-000-0000", tl.support_source_text(got))


class PressNoteTest(unittest.TestCase):
    NHK = {"source": "NHK", "url": "https://news.web.nhk/newsweb/na/nd-1"}
    ASAHI = {"source": "朝日新聞", "url": "https://www.asahi.com/articles/A1.html"}

    def test_length_view_and_no_padding(self):
        note = tl.press_note([self.NHK, self.ASAHI])
        for needle in ("900〜1,600字", "水増ししない", "## サイソクの見方", "見込まれる", "2社以上の報道が共通して伝えていること",
                       "窓口・電話番号・URL は書かない"):
            self.assertIn(needle, note)
        self.assertNotIn("600〜1,100字", note)
        self.assertNotIn("「サイソクの見方」の章は書かない", note)
        self.assertNotIn("｜", tl.PRESS_NOTE + tl.PRESS_SUPPORT_NOTE + tl.PRESS_NO_SUPPORT_NOTE + tl.PRESS_EXPAND_NOTE)

    def test_support_block_is_in_the_note(self):
        got = tl.support_pages(TERM, set(), pages=[{"url": CITY_URL, "page": CITY_PAGE}])
        note = tl.press_note([self.NHK, self.ASAHI], got)
        self.assertIn("# 公式の資料", note)
        self.assertIn(CITY_URL, note)
        self.assertIn("古い日付・数字を今回のことのように書かない", note)
        self.assertNotIn("窓口・電話番号・URL は書かない", note)

    def test_longer_body_is_not_a_shape_problem(self):
        rec = {"title": "前橋市のクマ出没、20日朝も目撃と報道", "lede": "NHKなどが報じた。", "body": "NHKによると、" + "あ" * 2400,
               "channelSlug": "trends", "pressReport": True, "trendKeyword": TERM, "sourceUrl": self.NHK["url"],
               "sources": [self.NHK, self.ASAHI], "factSources": tl.support_fact_sources([{"name": "前橋市", "url": CITY_URL}])}
        self.assertEqual(tl.press_record_problems(rec), [])
        self.assertTrue(pi.trend_press_ok(rec))  # 公式の資料を添えても W31 の例外の形のまま
        self.assertEqual(pi.press_source_problems(rec), [])
        self.assertEqual(quality.source_cap(rec), quality.MULTI_SOURCE_CAP)  # 報道3社＋公式の資料が事実確認に全部入る
        self.assertEqual(quality.source_cap({"pressReport": True}), quality.SOURCE_CAP)


class ExpandTest(unittest.TestCase):
    def test_press_articles_are_expanded_but_never_held(self):
        press_item = {"_press_report": True}
        self.assertTrue(w.view_urgent(press_item))  # 保留はしない（今までどおり）
        self.assertFalse(w.expand_urgent(press_item))  # 書き足しと章の追加は1回する
        self.assertTrue(w.expand_urgent({"fast": True}))

    def test_ensure_adds_the_press_note(self):
        prompts = []

        def fake(system, prompt, schema, **kw):
            prompts.append(prompt)
            return ({"body_markdown": "NHKによると、" + "い" * 1200} if "body_markdown" in str(schema) else {"view_markdown": ""}), "fake"

        rec = {"title": "t", "body": "NHKによると、短い本文。", "genreSlug": "public", "newsType": "policy"}
        own_view.ensure(rec, "資料", log=lambda _: None, generate=fake, note=tl.PRESS_EXPAND_NOTE)
        self.assertTrue(prompts)
        self.assertTrue(all(tl.PRESS_EXPAND_NOTE in p for p in prompts))
        prompts.clear()
        own_view.ensure({"title": "t", "body": "短い。", "genreSlug": "public"}, "資料", log=lambda _: None, generate=fake)
        self.assertTrue(prompts and not any("報道が出典" in p for p in prompts))

    def test_wiring(self):
        self.assertIn("urgent=expand_urgent(item)", SRC)
        self.assertIn('note=trend_lane.PRESS_EXPAND_NOTE if item.get("_press_report") else ""', SRC)
        seg = SRC[SRC.index("# 3) 公式の発表が見つからない"):SRC.index("[OK trend 報道]")]
        self.assertIn("trend_lane.support_pages(", seg)
        self.assertIn("search=research.search_links", seg)
        self.assertIn('rec["factSources"] = trend_lane.support_fact_sources(support)', seg)
        self.assertIn("trend_lane.support_source_text(support)", seg)
        self.assertIn("off_read.append(", SRC)


if __name__ == "__main__":
    unittest.main()
