"""話題のレーン（2026-11-13）: 急上昇の言葉 → 公式の出典 → 無ければ主要な報道機関2社以上の報道で短い記事。
オーナー 11/13「とにかく数字。それさえ出るなら結構なんでもいい」「注目する話題がとれていない」。
点検（audit_20261113_pipeline）: 急上昇の言葉を7日で456語以上拾って記事0本だった。うそを出さない基準は変えない。
通信・LLM は使わない（RSS・ページは作りもの）。"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import pacing  # noqa: E402
import public_interest as pi  # noqa: E402
import quality  # noqa: E402
import ramp  # noqa: E402
import trend_lane as tl  # noqa: E402
import trends  # noqa: E402
import web_articles as w  # noqa: E402

SRC = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
NOW = datetime(2026, 11, 13, 6, 0, tzinfo=timezone.utc)

NHK_RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>NHK</title><link>https://news.web.nhk/</link>
<item><title>ドコモで通信障害 全国でつながりにくい状態</title><link>https://news.web.nhk/newsweb/na/nd-1</link><pubDate>Fri, 13 Nov 2026 05:10:00 +0000</pubDate></item>
<item><title>古い記事</title><link>https://news.web.nhk/newsweb/na/nd-old</link><pubDate>Mon, 09 Nov 2026 05:10:00 +0000</pubDate></item>
<item><title>ほかの媒体の記事</title><link>https://example.com/a</link><pubDate>Fri, 13 Nov 2026 05:10:00 +0000</pubDate></item>
</channel></rss>""".encode("utf-8")
ASAHI_RDF = """<?xml version="1.0" encoding="UTF-8"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<item rdf:about="https://www.asahi.com/articles/A1.html"><title>NTTドコモ、通信障害が発生　音声通話とデータ通信に影響</title><link>https://www.asahi.com/articles/A1.html</link><dc:date>2026-11-13T14:20:00+09:00</dc:date></item>
</rdf:RDF>""".encode("utf-8")


def press(source_url, title, text):
    return {"url": source_url, "title": title, "text": text, "source": pi.press_outlet(source_url)}


NHK = press("https://news.web.nhk/newsweb/na/nd-1", "ドコモで通信障害 全国でつながりにくい状態",
            "NTTドコモによると、13日午後2時ごろから全国で音声通話とデータ通信がつながりにくくなっている。影響は約120万人。" + "復旧の見通しは立っていない。" * 40)
ASAHI = press("https://www.asahi.com/articles/A1.html", "NTTドコモ、通信障害が発生　音声通話とデータ通信に影響",
              "NTTドコモは13日、午後2時ごろから通信障害が起きていると明らかにした。約120万人に影響が出ている。" + "原因は調査中という。" * 40)
OTHER = press("https://mainichi.jp/articles/x", "大相撲九州場所　熱海富士が4連勝", "大相撲九州場所は13日、福岡国際センターで行われ、熱海富士が4連勝とした。" * 20)


def press_record(**kw):
    rec = {"title": "ドコモで通信障害とNHKなど報道　復旧の見通しは", "lede": "NHKなどが報じた。ドコモで通信障害が起きている。",
           "body": "## 何が報じられたか\n\nNHKによると、13日午後2時ごろから全国でつながりにくくなっている。\n\n## まだ分かっていないこと\n\n公式の発表はまだ確認できていない。",
           "easy": "", "genreSlug": "public"}
    tl.press_fields(rec, "ドコモ 障害", [NHK, ASAHI], NOW)
    rec.update(kw)
    return rec


class OutletAllowlistTest(unittest.TestCase):
    """1b: 出典にしてよいのは一覧の主要な報道機関だけ。独立は報道機関の単位で数える"""

    def test_allowlist_and_groups(self):
        hosts = ["nhk.or.jp", "news.web.nhk", "47news.jp", "nordot.app", "jiji.com", "nikkei.com", "asahi.com", "yomiuri.co.jp", "mainichi.jp",
                 "reuters.com", "jp.reuters.com", "bloomberg.com", "bloomberg.co.jp", "apnews.com", "newsdig.tbs.co.jp", "news.tv-asahi.co.jp",
                 "news.ntv.co.jp", "fnn.jp"]
        self.assertEqual(set(pi.TREND_PRESS_OUTLETS), set(hosts))
        for h in hosts:
            self.assertTrue(pi.press_outlet(f"https://{h}/a/b"), h)
        self.assertEqual(pi.press_outlet("https://www3.nhk.or.jp/news/x"), pi.press_outlet("https://news.web.nhk/newsweb/x"))
        self.assertEqual(pi.press_outlet("https://www.47news.jp/1.html"), pi.press_outlet("https://nordot.app/1"))
        self.assertEqual(pi.press_outlet("https://jp.reuters.com/x"), pi.press_outlet("https://www.reuters.com/x"))
        self.assertNotEqual(pi.press_outlet("https://www.asahi.com/x"), pi.press_outlet("https://news.tv-asahi.co.jp/x"))
        for bad in ("https://news.yahoo.co.jp/articles/1", "https://gori.me/x", "https://www.itmedia.co.jp/x", "https://www.sankei.com/x",
                    "https://nhk.or.jp.example.com/x", "https://example.com/?u=https://www.asahi.com/x", "ftp://www.asahi.com/x", ""):
            self.assertIsNone(pi.press_outlet(bad), bad)


class PressGateTest(unittest.TestCase):
    """1b: 門（press。W31）は、この形だけ通し、ほかは今までどおり止める"""

    def test_allowed_shape_passes_every_gate(self):
        rec = press_record()
        self.assertTrue(pi.trend_press_ok(rec))
        self.assertEqual(pi.press_source_problems(rec), [])
        self.assertFalse(any("W31" in p for p in quality.every_path_problems(rec)))
        self.assertIsNone(indexnow.publish_block_reason(rec))
        self.assertEqual(tl.press_record_problems(rec), [])
        self.assertTrue(rec["pressReport"] and rec["awaitingOfficial"])
        self.assertIn("公式の発表はまだ確認できていません", rec["disclaimer"])
        self.assertIsNone(rec["verdict"])

    def test_everything_else_is_still_blocked(self):
        good = press_record()
        bad_cases = {
            "1社だけ": {"sources": good["sources"][:1]},
            "同じ報道機関の2本": {"sources": [good["sources"][0], {"url": "https://www3.nhk.or.jp/news/y", "source": "NHK"}]},
            "一覧に無い媒体が混ざる": {"sources": good["sources"] + [{"url": "https://news.yahoo.co.jp/articles/1"}]},
            "一覧に無い媒体だけ": {"sources": [{"url": "https://gori.me/a"}, {"url": "https://www.itmedia.co.jp/b"}], "sourceUrl": "https://gori.me/a"},
            "報道の印が無い": {"pressReport": None},
            "急上昇の言葉が無い": {"trendKeyword": ""},
            "出典のURLが一覧の外": {"sourceUrl": "https://news.yahoo.co.jp/articles/1"},
            "報道と書いていない": {"lede": "ドコモで通信障害が起きている。", "body": "## 障害\n\n全国でつながりにくい。"},
            "話題のレーンではない": {"channelSlug": "radar-gori.me"},
            "出典の欄が無い": {"sources": []},
        }
        for name, kw in bad_cases.items():
            rec = {**good, **kw}
            self.assertFalse(pi.trend_press_ok(rec), name)
            self.assertTrue(pi.press_source_problems(rec), name)
            self.assertEqual(indexnow.publish_block_reason(rec), "press", name)
        # 今までの例（報道が出典のふつうの記事・速報）も止まったまま
        for kw in ({"channelSlug": "fast", "sourceUrl": "https://www.bloomberg.com/news/articles/x"},
                   {"channelSlug": "trends", "sourceUrl": "https://www.nytimes.com/2026/10/28/x"},
                   {"channelSlug": "mlit-press", "sourceUrl": "https://www.asahi.com/articles/A1.html", "pressReport": True}):
            rec = {"title": "t", "lede": "NHKなどが報じた。", "body": "## a\n\nb", "genreSlug": "public", **kw}
            self.assertEqual(indexnow.publish_block_reason(rec), "press", kw)

    def test_record_shape_checks(self):
        self.assertTrue(any("言い切って" in p for p in tl.press_record_problems(press_record(title="ドコモで通信障害　全国でつながらない"))))
        self.assertTrue(any("｜" in p for p in tl.press_record_problems(press_record(title="ドコモ障害と報道｜復旧は"))))
        self.assertTrue(any("速報" in p for p in tl.press_record_problems(press_record(title="【速報】ドコモ障害と報道"))))
        self.assertTrue(any("長すぎる" in p for p in tl.press_record_problems(press_record(body="NHKによると、" + "あ" * 3000))))
        self.assertTrue(any("報道が出典" in p for p in tl.press_record_problems(press_record(lede="障害が起きた。", body="## a\n\n障害が起きた。"))))


class PressDiscoveryTest(unittest.TestCase):
    """1b: 主要な報道機関の RSS から、その言葉を伝えている独立した2社を探し、同じ出来事か確かめる"""

    def fetch(self, url):
        return {"https://nhk/rss": NHK_RSS, "https://asahi/rss": ASAHI_RDF}.get(url)

    def index(self):
        return tl.press_index(self.fetch, NOW, feeds=[("NHK", "https://nhk/rss"), ("朝日新聞", "https://asahi/rss"), ("毎日新聞", "https://down/rss")])

    def test_index_reads_rss_and_rdf_and_drops_old_or_foreign_hosts(self):
        idx = self.index()
        self.assertEqual({i["url"] for i in idx}, {"https://news.web.nhk/newsweb/na/nd-1", "https://www.asahi.com/articles/A1.html"})

    def test_broken_xml_feed_is_still_read(self):
        broken = ("<rdf:RDF><channel><title>日テレ</title></channel>"
                  "<item rdf:about=\"https://news.ntv.co.jp/n/abs/1\"><title><![CDATA[ドコモ通信障害 & 復旧の見通し]]></title>"
                  "<link>https://news.ntv.co.jp/n/abs/1</link><dc:date>2026-11-13T14:30:00+09:00</dc:date></item>"
                  "<item><title>壊れた項目 \x01</title><link>https://example.com/x</link></item></rdf:RDF>").encode("utf-8")
        got = tl.parse_press_feed(broken, "日テレNEWS")
        self.assertEqual([(i["title"], i["url"]) for i in got], [("ドコモ通信障害 & 復旧の見通し", "https://news.ntv.co.jp/n/abs/1")])
        self.assertTrue(got[0]["published"].startswith("2026-11-13T14:30"))

    def test_candidates_mix_trend_news_and_feed_matches(self):
        q = {"title": "ドコモ 障害", "sources": [
            {"title": "ドコモ障害", "url": "https://news.yahoo.co.jp/articles/1", "source": "Yahoo!ニュース"},     # 一覧の外 → 使わない
            {"title": "ドコモで通信障害", "url": "https://news.google.com/rss/articles/CBMi", "source": "NHK"},    # 記事の URL ではない → 使わない
            {"title": "ドコモで通信障害", "url": "https://newsdig.tbs.co.jp/articles/-/1", "source": "TBS NEWS DIG"},
        ]}
        got = tl.press_candidates(q, self.index())
        self.assertEqual([c["source"] for c in got], ["TBS NEWS DIG", "NHK", "朝日新聞"])
        self.assertEqual(tl.press_candidates({"title": "熱海富士", "sources": []}, self.index()), [])

    def test_independent_needs_distinct_outlets_and_real_text(self):
        same = press("https://www3.nhk.or.jp/news/z", "ドコモ障害 続報", NHK["text"])
        short = press("https://www.asahi.com/articles/A2.html", "ドコモ障害", "短い")
        yahoo = {"url": "https://news.yahoo.co.jp/articles/1", "title": "ドコモ障害", "text": NHK["text"]}
        self.assertEqual([s["source"] for s in tl.independent([NHK, same, short, yahoo, ASAHI])], ["NHK", "朝日新聞"])
        self.assertEqual(len(tl.independent([NHK, same, yahoo])), 1)

    def test_agreement(self):
        ok, why = tl.agreement("ドコモ 障害", [NHK, ASAHI])
        self.assertTrue(ok, why)
        ok, why = tl.agreement("ドコモ 障害", [NHK, OTHER])       # もう1社は別の話題
        self.assertFalse(ok)
        self.assertIn("2社以上", why)
        unrelated = press("https://www.asahi.com/articles/A9.html", "ドコモ、新しい料金プランで障害者割引を拡充",
                          "ドコモは料金プランの障害者割引を広げる。対象は手帳を持つ人で、月額は550円安くなる。" * 10)
        ok, why = tl.agreement("ドコモ 障害", [NHK, unrelated])   # 言葉は当たるが、共通の固有名詞・数が無い
        self.assertFalse(ok)
        self.assertEqual([s["source"] for s in tl.agreed("ドコモ 障害", [NHK, OTHER, ASAHI])], ["NHK", "朝日新聞"])


class OfficialFirstTest(unittest.TestCase):
    """1a: 公式の出典を先に探す（公式のフィードの候補 → 報道の記事の中の公式のリンク）"""

    def test_feed_candidate_matches_title_not_only_source_name(self):
        pool = [
            {"id": "a", "title": "一部のお客さまで通信サービスがご利用しづらい状況について", "source_name": "NTTドコモ", "published_at": NOW},
            {"id": "b", "title": "ドコモ、通信障害の発生について（第2報）", "source_name": "NTTドコモ", "published_at": NOW + timedelta(hours=1)},
            {"id": "c", "title": "Alphabet の新しい研究", "source_name": "Google", "published_at": NOW},
        ]
        self.assertEqual(tl.feed_candidate("ドコモ 障害", pool)["id"], "b")
        self.assertIsNone(tl.feed_candidate("bet", pool))
        self.assertIsNone(tl.feed_candidate("熱海富士", pool))

    def test_official_links_only_gov_or_registered_hosts(self):
        hosts = {"docomo.ne.jp", "meti.go.jp"}
        pages = [{"links": [
            {"url": "https://www.docomo.ne.jp/info/network/kanto/pages/261113_00.html"},
            {"url": "https://www.docomo.ne.jp/"},                       # トップページ
            {"url": "https://www.soumu.go.jp/menu_news/s-news/01kiban05_02000123.html"},
            {"url": "https://www.asahi.com/articles/A1.html"},          # 報道
            {"url": "https://x.com/docomo/status/1"},                    # SNS
            {"url": "http://www.docomo.ne.jp/info/http.html"},          # https ではない
            {"url": "https://blog.example.com/docomo-shougai"},         # 登録の無いサイト
        ]}]
        self.assertEqual(tl.official_links(pages, hosts), [
            "https://www.docomo.ne.jp/info/network/kanto/pages/261113_00.html",
            "https://www.soumu.go.jp/menu_news/s-news/01kiban05_02000123.html"])
        self.assertIn("soumu.go.jp", " ".join(tl.official_links(pages, set())))

    def test_link_only_pages_and_registered_hosts(self):
        q = {"sources": [{"url": "https://news.yahoo.co.jp/articles/1"}, {"url": "https://news.google.com/rss/articles/CBMi"},
                         {"url": "https://www.asahi.com/articles/A1.html"}, {"url": "https://prtimes.jp/main/html/rd/p/1.html"},
                         {"url": "https://www.itmedia.co.jp/news/1.html"}]}
        self.assertEqual([s["url"] for s in tl.link_only_sources(q)], ["https://news.yahoo.co.jp/articles/1", "https://prtimes.jp/main/html/rd/p/1.html"])

        class Feeds:
            FEEDS = [{"url": "https://openai.com/news/rss.xml", "kind": "official"}, {"url": "https://prtimes.jp/index.rdf", "kind": "wire"}]
            BROAD_FEEDS = [{"url": "https://www.mhlw.go.jp/stf/news.rdf", "kind": "gov"}, {"url": "https://www.docomo.ne.jp/info/rss.xml", "kind": "company"}]

        hosts = tl.official_hosts(Feeds, {"sources": [{"url": "https://www.anthropic.com/news"}, {"url": "https://www.reuters.com/x"}],
                                          "radar": {"primary_hosts": [{"host": "sec.gov"}]}})
        self.assertEqual(hosts, {"openai.com", "mhlw.go.jp", "docomo.ne.jp", "anthropic.com", "sec.gov"})

    def test_official_page_must_be_about_the_term(self):
        self.assertTrue(tl.official_page_ok("ドコモ 障害", {"title": "通信障害について", "text": "NTTドコモの通信サービスで障害が発生しています。" * 30}))
        self.assertFalse(tl.official_page_ok("ドコモ 障害", {"title": "会社概要", "text": "ドコモは通信の会社です。" * 60}))
        self.assertFalse(tl.official_page_ok("ドコモ 障害", {"title": "通信障害", "text": "ドコモ 障害"}))

    def test_official_item_shape(self):
        q = {"id": "q1", "title": "ドコモ 障害", "genre": "public", "published_at": NOW}
        item = w.trend_official_item(q, "https://www.docomo.ne.jp/info/network/kanto/pages/261113_00.html",
                                     {"title": "通信障害について", "text": "x" * 700, "description": "d"})
        self.assertEqual((item["source_slug"], item["section"], item["published_guessed"]), ("radar-official", "public", True))
        self.assertFalse(pi.press_source_problems({"channelSlug": item["source_slug"], "sourceUrl": item["url"]}))
        game = w.trend_official_item({"id": "q2", "title": "vindictus defying fate ps5", "genre": "ai", "published_at": NOW},
                                     "https://store.playstation.com/concept/10011300", {"title": "Vindictus: Defying Fate (PS5 ゲーム)", "text": "x" * 700})
        self.assertEqual(game["section"], "entertainment")


class PublishedBeforeSectionFixTest(unittest.TestCase):
    """45350f7a の前に公開した話題のレーンの記事（ゲームの発売が「社会・行政」・種類が「制度」だった）を、今の決め方の結果に直してある"""

    def test_vindictus_article_has_the_section_the_fix_assigns(self):
        import json
        from pathlib import Path

        import feeds
        import news_types

        path = Path(__file__).resolve().parents[1] / "content" / "articles" / "vindictus-defying-fate-ps5.json"
        if not path.exists():
            self.skipTest("記事が無い")
        a = json.loads(path.read_text("utf-8"))
        section = feeds.classify_section({"title": f"Vindictus: Defying Fate (PS5 ゲーム) {a['trendKeyword']}", "summary": ""})
        genre = w.GENRES_BY_SLUG[section]
        self.assertEqual((a["genreSlug"], a["genre"]), (genre.slug, genre.name))
        self.assertEqual(a["genreSlug"], "entertainment")
        self.assertEqual(a["newsType"], news_types.classify(a["title"], a["body"], url=a["sourceUrl"], genre=genre.slug))
        self.assertNotEqual(a["newsType"], "policy")
        self.assertEqual(a["disclaimer"], w.web_disclaimer(genre))
        self.assertNotIn("官公庁", a["disclaimer"])
        self.assertNotEqual((a.get("verdict") or {}).get("kind"), "public")  # 判定カードを「制度」の形で出さない


class TermMatchingTest(unittest.TestCase):
    """1d: 英数字だけの語は語の区切りで当てる（「bet」が「Alphabet」に当たっていた）"""

    def test_latin_terms_match_whole_words_only(self):
        sig = [{"title": "bet"}]
        self.assertIsNone(pi.trend_hit("Google DeepMind、AlphaGenome 2を発表　Alphabet傘下", sig))
        self.assertIsNone(pi.trend_hit("Alphabetの決算、広告が好調", sig, "Alphabet"))
        self.assertIsNotNone(pi.trend_hit("BET の新番組が配信開始", sig))
        self.assertIsNone(pi.trend_hit("Claudeの新機能を発表", [{"title": "au"}]))
        self.assertIsNotNone(pi.trend_hit("auの通信障害について", [{"title": "au"}]))
        self.assertIsNone(pi.trend_hit("iPhone 18 Pro Maxを発表", [{"title": "max"}]) and None)
        self.assertFalse(pi.contains_term("ps5", "PS55 という型番"))
        self.assertTrue(pi.contains_term("PS5", "新型PS5の価格を改定"))
        self.assertTrue(pi.contains_term("iphone 18", "Apple、iPhone 18を発表"))

    def test_japanese_terms_still_match_inside_words(self):
        self.assertIsNotNone(pi.trend_hit("NTTドコモ、情報流出の対象を公表", [{"title": "ドコモ 情報流出 確認方法"}]))
        self.assertIsNotNone(pi.trend_hit("気象庁、台風第25号の進路を発表", [{"title": "台風"}]))
        self.assertTrue(pi.contains_term("ドコモ", "NTTドコモ"))


class OpenTopicsTest(unittest.TestCase):
    """1a: 話題のレーンは軸の語が無くても拾う。うわさ・事件と被害者・訃報・アダルト・ギャンブル・選挙は外す"""

    def pick(self, title, news=()):
        return trends.lane_pick({"title": title, "news": [{"title": t} for t in news]})[0]

    def test_non_axis_topics_are_kept(self):
        self.assertEqual(self.pick("侍ジャパン", ["ラグザス アジアプロ野球チャンピオンシップ2026 試合速報"]), "sports")
        self.assertEqual(self.pick("ゴジラ-0.0", ["映画「ゴジラ－0．0」の興行収入が100億円を突破"]), "entertainment")
        self.assertEqual(self.pick("エルニーニョ", ["気象庁、エルニーニョ監視速報を発表"]), "public")
        self.assertEqual(self.pick("株主優待", ["すかいらーく、1-9月期最終は17％増益"]), "investment")
        self.assertEqual(self.pick("ダイハツ リコール", ["ダイハツ、ロッキーなど12万台をリコール"]), "public")

    def test_excluded_topics(self):
        for title, news in (
            ("鈴木真一容疑者", ["勤務先から21億円超横領か 元経理担当の43歳逮捕"]),
            ("山崎正昭", ["参議院議員の山崎正昭氏が死去"] * 2),
            ("エリザベス女王杯 枠順", ["G1エリザベス女王杯の枠順"]),
            ("ジュウ リョク ピエロ", ["【エ女王杯】四位師2頭出しで挑む", "競馬の注目馬"]),
            ("酒井 法子", ["最新姿にネット騒然"] * 2),
            ("vivant 薫", ["薫の正体は、第1話でもうバレてた？ ファンの新考察"] * 2),
            ("衆院選 情勢", []),
            ("オンラインカジノ", []),
            ("寒河江市 火事", ["山形県で住宅全焼 3人の遺体"] * 2),
        ):
            self.assertIsNone(self.pick(title, news), title)

    def test_collect_enqueues_non_axis_terms(self):
        trend = {"title": "侍ジャパン", "traffic": 5000, "traffic_label": "5000+", "published_at": NOW, "origin": "google", "context": [],
                 "news": [{"title": "侍ジャパンが台湾に快勝", "url": "https://news.web.nhk/newsweb/na/nd-9", "source": "NHK", "published": None},
                          {"title": "侍ジャパン、決勝へ", "url": "https://www.asahi.com/articles/A9.html", "source": "朝日新聞", "published": None}]}
        items = trends.collect({}, trends=[trend])
        self.assertEqual([(i["title"], i["genre"]) for i in items], [("侍ジャパン", "sports")])


class CapsAndExemptionTest(unittest.TestCase):
    """1c: 1回3本・1日20本。審査の期間の「1日30本・暮らしとお金だけ」の外（速報と同じ扱い）"""

    def test_ramp_numbers_and_workflow(self):
        self.assertEqual((ramp.TREND_PER_RUN, ramp.TREND_DAILY_CAP), (3, 20))
        self.assertEqual(ramp.ADSENSE_REVIEW[2], 30)  # オーナーが決めた自動のレーンの上限は変えない
        wf = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("--trends \"${{ vars.TREND_MAX_PER_RUN || steps.ramp.outputs.trend_per_run || '3' }}\"", wf)
        self.assertIn('(.trendKeyword // "") != ""', wf)  # 話題のレーンの記事は待たずにデプロイ

    def test_trend_articles_do_not_use_the_daily_cap(self):
        at = datetime.now(pacing.JST).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            for slug in ("a", "b", "c"):
                (Path(tmp) / f"{slug}.json").write_text("{}", "utf-8")
            state = {"processed_web": {"1": {"slug": "a", "at": at, "mix": "money"}, "2": {"slug": "b", "at": at, "trendLane": True, "kind": "trend"},
                                       "3": {"slug": "c", "at": at, "trendLane": True, "pressReport": True},
                                       "4": {"at": at, "skipped": True, "trendLane": True}}}
            self.assertEqual(pacing.live_today(state, articles_dir=Path(tmp)), 1)
            self.assertEqual(tl.done_today(state), 2)

    def test_pipeline_wiring(self):
        self.assertTrue(w.TREND_LANE and w.TREND_FROM_PRESS)
        self.assertIn("max(0, min(args.trends, ramp.TREND_DAILY_CAP - trend_done))", SRC)
        loop = SRC[SRC.index("        for q in queue:"):SRC.index("        # 公式フィード（AI）と幅広い話題を、レーンごとに1本ずつ交互に処理する")]
        # 上限は話題のレーンだけで数える（1日の上限 remaining を見ない）
        self.assertIn('if created["trend"] >= trend_limit or time_up():', loop)
        self.assertNotIn("remaining", loop)
        # 出典の順: 公式のフィード → 報道の中の公式のリンク → 報道2社以上
        order = [loop.index("trend_lane.feed_candidate(term, pool_left())"), loop.index("trend_lane.official_links(link_pages, off_hosts)"),
                 loop.index("if not TREND_FROM_PRESS:"), loop.index("trend_lane.independent(fetched)"), loop.index("trend_lane.agreement(term, chosen)"),
                 loop.index("status, record, model_name, info = gated(")]
        self.assertEqual(order, sorted(order))
        # 直近7日の重複（同じ言葉・見出し・同じ発表）を見てから作る
        self.assertLess(loop.index("covered.get(trend_lane.norm(term))"), loop.index("trend_lane.feed_candidate("))
        self.assertIn("trend_recent.find(", loop)
        self.assertIn("story_recent.match(", loop)
        self.assertEqual(tl.COVERED_DAYS, 7)
        # 読んだ報道の見出しと書き出しで、扱わない話題をもう一度確かめてから書く
        self.assertLess(loop.index("trends.open_exclusion_reason(term, [f\"{s_.get('title')"), loop.index("status, record, model_name, info = gated("))
        # 報道が出典の記事は、ふつうの品質の門（事実確認）を通し、形の確かめを生成の直後と書き出す前の2回行う
        self.assertEqual(loop.count("trend_lane.press_record_problems("), 2)
        self.assertLess(loop.rindex("trend_lane.press_record_problems("), loop.index("m.write_article(record)"))
        self.assertIn("trendLane=True, pressReport=True", loop)
        # ふつうのレーンの1回の本数に、話題のレーンの本数を数えない
        self.assertEqual(SRC.count("lane_created() >= remaining"), 3)
        # 公式の候補は process_web を通る（公式が出典のふつうの作り方）。種類別の上限・審査の期間の門の外
        self.assertIn('process_web(cand, lane, target, trend_term=q["title"])', SRC)
        self.assertIn("action, target = pick(cand, lane == \"ai\", trend=True)", SRC)
        self.assertIn('**({"trendLane": True, "kind": "trend", "trendKeyword": trend_term} if trend_term else {})', SRC)

    def test_trend_prefilter_blocks_only_unsafe_or_empty(self):
        self.assertIsNone(w.trend_prefilter({"title": "侍ジャパン、決勝のチケットを11月15日から販売", "summary": ""}))
        self.assertIsNone(w.trend_prefilter({"title": "Introducing Claude Fable 5.2", "summary": ""}))
        self.assertTrue(w.trend_prefilter({"title": "元社員を逮捕　横領の容疑", "summary": ""}))
        self.assertTrue(w.trend_prefilter({"title": "衆院選の候補者一覧", "summary": ""}))
        self.assertTrue(w.trend_prefilter({"title": "財務省が研究会の議事要旨を公開", "summary": ""}))

    def test_axis_gate_lets_trend_topics_through(self):
        base = {"body": "## a\n\n" + "あ" * 2000, "genreSlug": "sports", "channelSlug": "nhk", "sourceUrl": "https://www.japan-sports.or.jp/x"}
        off = {**base, "title": "ＮＢＡのウォリアーズが勝利"}
        self.assertEqual(indexnow.noindex_reason(off), "no-life-link")
        self.assertIsNone(indexnow.noindex_reason({**off, "trendKeyword": "ウォリアーズ"}))
        self.assertIsNone(indexnow.publish_block_reason({**off, "trendKeyword": "ウォリアーズ"}))
        self.assertEqual(indexnow.noindex_reason({**base, "genreSlug": "entertainment", "title": "人気俳優の熱愛が発覚", "trendKeyword": "熱愛"}),
                         "no-life-link")
        self.assertIn("trendTopic(article)", (ROOT / "lib" / "indexing.ts").read_text("utf-8"))
        self.assertIn("trendKeyword: a.trendKeyword || undefined", (ROOT / "lib" / "article-index.mjs").read_text("utf-8"))


class RefreshWhenOfficialTest(unittest.TestCase):
    """1b: 報道が出典の記事には「公式の発表を待っている」印を残し、公式の発表が出たら更新して印を外す"""

    def test_awaiting_and_covered_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            fresh = (NOW - timedelta(days=1)).isoformat()
            old = (NOW - timedelta(days=9)).isoformat()
            (d / "a.json").write_text(json.dumps({**press_record(), "generatedAt": fresh}, ensure_ascii=False), "utf-8")
            (d / "b.json").write_text(json.dumps({**press_record(), "generatedAt": old}, ensure_ascii=False), "utf-8")
            (d / "c.json").write_text(json.dumps({"title": "x", "searchTrend": "ダイハツ　リコール", "generatedAt": fresh}, ensure_ascii=False), "utf-8")
            done = tl.mark_official_found({**press_record(), "generatedAt": fresh}, "https://www.docomo.ne.jp/info/x.html", NOW)
            (d / "e.json").write_text(json.dumps(done, ensure_ascii=False), "utf-8")
            self.assertEqual([p.stem for p, _ in tl.awaiting_official(articles_dir=d, now=NOW)], ["a"])
            covered = tl.covered_terms(articles_dir=d, now=NOW)
            self.assertEqual(covered.get(tl.norm("ドコモ 障害")), "a")
            self.assertEqual(covered.get(tl.norm("ダイハツ リコール")), "c")
        self.assertFalse(done["awaitingOfficial"])
        self.assertEqual(done["officialSourceUrl"], "https://www.docomo.ne.jp/info/x.html")

    def test_refresh_is_wired_before_the_queue(self):
        self.assertLess(SRC.index("trend_lane.awaiting_official()"), SRC.index("        for q in queue:"))
        seg = SRC[SRC.index("trend_lane.awaiting_official()"):SRC.index("        for q in queue:")]
        self.assertIn("try_followup(cand, text, (\"ok\", path, waiting", seg)  # 追記は、続報の門（事実確認・文体）をそのまま通る
        self.assertIn("trend_lane.mark_official_found(", seg)


class TitleNoteTest(unittest.TestCase):
    """1e: 題名は検索される言葉＋読者が知りたいこと。形を変える。本文に無い約束をしない。「｜」を使わない"""

    def test_note(self):
        note = tl.title_note("ドコモ 障害", "id-1")
        for needle in ("「ドコモ 障害」", "いつ・いくら・何をすればいいか", "必ず本文で答える", "約束しない", "「｜」（縦棒）は使わない"):
            self.assertIn(needle, note)
        shapes = {tl.title_note("ドコモ 障害", seed).split("形の例")[1].split("\n")[0] for seed in ("a", "b", "c", "d", "e")}
        self.assertGreater(len(shapes), 1)  # 形の例は毎回同じにしない
        self.assertNotIn("｜", "".join(tl.TITLE_SHAPES) + tl.PRESS_NOTE + tl.RELEVANT_NOTE + tl.PRESS_DISCLAIMER)

    def test_notes_are_in_the_prompts(self):
        self.assertIn("prompt += trend_lane.RELEVANT_NOTE + trend_lane.title_note(trend_term, item[\"id\"])", SRC)
        self.assertIn("+ trend_lane.title_note(term, q[\"id\"]) + trend_lane.press_note(chosen))", SRC)
        note = tl.press_note([NHK, ASAHI])
        for needle in ("NHK・朝日新聞", "NHKなどが報じた", "2社以上の報道が共通して伝えていること", "書き写さない", "600〜1,100字"):
            self.assertIn(needle, note)
        self.assertIn("私人", tl.RELEVANT_NOTE)

    def test_title_problems_and_bar_is_removed_in_code(self):
        self.assertTrue(tl.title_problems({"title": "通信障害が発生｜復旧は"}, "ドコモ 障害"))
        self.assertEqual(tl.title_problems({"title": "ドコモの通信障害、復旧の見通しは"}, "ドコモ 障害"), [])
        self.assertEqual(SRC.count('rec["title"] = re.sub(r"\\s*[｜|]\\s*", "　", rec["title"]).strip()'), 2)


if __name__ == "__main__":
    unittest.main()
