"""「自分は対象か」の事故（情報流出・回収・障害）の見張り（2026-11-14 オーナー「結果低すぎ」「全然最速でもない」・台帳 W44）。

無印良品（MUJI Card 約109万件・11/4 の第2報）を10日間、ほかにも同じ型の事故を8件取りこぼした。会社自身の「お知らせ」は
どの発信元の一覧にも無く、毎朝の見逃しチェックも一覧に並べるだけだった。ここでは次を確かめる（ネットには出ない）:
  - 見つけるための発信元の見出しから、会社の名前・事故の種類・規模を取り出す
  - 会社自身のお知らせ（公式の一次情報）を探す。報道・まとめの記事そのものは出典にしない
  - 同じ事故の記事がもうあれば作らない（muji-card-number-leak-2021 を二重に作らない）
  - 速報レーンに渡す形（登録外の会社のサイトでも受け付ける・SNS の【速報】にはしない・審査の期間の門の外・古さで落とさない）
  - 公式のお知らせが無いときは話題のレーン（報道2社以上の決まり）に回す
  - 発表 → 検知 → 公開の時間の記録（日付しか分からない発表では「発表から何分」を出さない）
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fast_lane  # noqa: E402
import incident_watch as iw  # noqa: E402
import news_mix  # noqa: E402
import web_articles  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)
CFG = iw.CONFIG

RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>x</title>
<item><title>「ネットマイル」に不正アクセス、最大約549万人の会員情報等が漏えいした可能性</title>
<link>https://scan.netsecurity.ne.jp/article/2026/11/13/56773.html</link><description><![CDATA[会員情報が漏えいした可能性。]]></description>
<pubDate>Fri, 13 Nov 2026 08:05:10 +0900</pubDate></item>
<item><title>「Chrome」が今週2度目の更新 - 脆弱性83件を修正</title><link>https://www.security-next.com/1</link>
<pubDate>Fri, 13 Nov 2026 08:00:00 +0900</pubDate></item>
<item><title>ＸＹＺ商会:不正アクセスによる個人情報流出に関するお知らせ</title>
<link>https://webapi.yanoshin.jp/rd.php?https://www.release.tdnet.info/inbs/140120261113500000.pdf</link>
<pubDate>Fri, 13 Nov 2026 15:00:00 +0900</pubDate></item>
</channel></rss>""".encode("utf-8")

NOTICE = ("「ネットマイル」における不正アクセスによる個人情報漏洩の可能性に関するお知らせ\n2026年11月2日\n株式会社ネットマイル\n"
          "当社が運営する「ネットマイル」において、第三者による不正アクセスがあり、会員情報 最大約549万人分が漏えいした可能性があります。" + "詳しい説明です。" * 170)


def page(text="", links=None, title="", published=""):
    return {"text": text, "links": links or [], "title": title, "published": published}


def article(slug, title, url, made="2026-11-14T00:36:07+00:00"):
    return {"slug": slug, "title": title, "seoTitle": "", "urls": [url], "publishedAt": iw.parse_time(made), "madeAt": iw.parse_time(made),
            "sourcePublishedAt": None, "detectedAt": None, "incident": None}


MUJI = article("muji-card-number-leak-2021", "無印良品のMUJI Card、2021年7月までの入会者109万件のカード番号が流出の可能性　対象かは入会時期で確認",
               "https://www.ryohin-keikaku.jp/news/articles/2026_1104_02")


class DetectTest(unittest.TestCase):
    def test_kind_and_exclusions(self):
        self.assertEqual(iw.classify("「ノジマオンライン」に不正アクセス、約700万件の会員情報が漏えい"), "breach")
        self.assertEqual(iw.classify("商品の回収に関するお詫びとお知らせ"), "recall")
        self.assertEqual(iw.classify("複数の信金でATM利用・振り込みできず──共同システムで障害が発生"), "outage")
        for title in ["「FortiMail」に深刻な脆弱性 - 10月の更新で対応", "【無料ウェビナー開催】相次ぐ情報漏洩の裏にある脅威",
                      "上場企業の個人情報漏えい事故 過去最多更新 ～ 東京商工リサーチ調査", "ザ・ギンザ誕生25周年を記念して新たに登場"]:
            self.assertIsNone(iw.classify(title), title)

    def test_company_name(self):
        cases = {
            "「ネットマイル」に不正アクセス、最大約549万人の会員情報等が漏えいした可能性": "ネットマイル",
            "ブックオフグループホールディングス子会社の会員管理システムに不正アクセス、638万3,279人の会員情報が漏えい": "ブックオフ",
            "肌測定システムで個人情報や測定結果が流出 - 資生堂": "資生堂",
            "良品計画への不正アクセスについてまとめてみた": "良品計画",
            "マネックス証券、最大113万件のメールアドレスに漏えいのおそれ": "マネックス証券",
            "ネット印刷「ラクスル」に不正アクセス　入稿データ一部漏えいか": "ラクスル",
            "東京ガスで委託先アララへの不正アクセスにより利用者メール8万5,565件が流出": "東京ガス",
            "FABRIC TOKYOの検証用システムに不正アクセス 予約者699名の情報が流出した恐れ": "FABRIC TOKYO",
            "複数の信金でATM利用できず、障害が発生": "",
        }
        for title, want in cases.items():
            self.assertEqual(iw.extract_company(title), want, title)
        self.assertEqual(iw.extract_company("Ｇ－プレイド:当社サービスへの不正アクセスに関するお知らせ", {"title_split": ":"}), "プレイド")
        self.assertEqual(iw.extract_company("神戸物産「砂糖不使用デーツバー」 - 返金／回収", {"type": "html"}), "神戸物産")

    def test_scale(self):
        self.assertEqual(iw.parse_scale("638万3,279人の会員情報が漏えい")[0], 6_383_279)
        self.assertEqual(iw.parse_scale("最大約549万人の会員情報")[0], 5_490_000)
        self.assertEqual(iw.parse_scale("最大228,734件")[0], 228_734)
        self.assertEqual(iw.parse_scale("約1.09億件")[0], 109_000_000)
        self.assertIsNone(iw.parse_scale("2026年11月4日に発表した"))

    def test_same_company_is_one_key(self):
        self.assertEqual(iw.canonical("無印良品")[0], "良品計画")
        self.assertEqual(iw.canonical("MUJIアプリ")[0], "良品計画")
        self.assertEqual(iw.canonical("ノジマオンライン")[0], "ノジマ")
        self.assertTrue(iw.is_major_name("au"))
        self.assertFalse(iw.is_major_name("autobahn"))  # 英字の名前は語の区切りで当てる

    def test_feed_to_hits(self):
        srcs = {s["slug"]: s for s in CFG["discovery"]}
        items = iw.parse_source(srcs["scan-netsecurity"], RSS)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[2]["url"], "https://www.release.tdnet.info/inbs/140120261113500000.pdf")  # 中継の URL は本当の URL に戻す
        self.assertEqual(items[0]["published"].astimezone(JST).hour, 8)
        items[2]["source"] = "tdnet-recent"  # 適時開示の見出しは「会社:題名」
        hits = iw.detect(items, srcs, CFG, NOW)
        self.assertEqual(set(hits), {"breach:ネットマイル", "breach:xyz商会"})
        self.assertTrue(hits["breach:xyz商会"]["discovery"][0]["official"])
        hit = hits["breach:ネットマイル"]
        self.assertEqual(hit["scale"], 5_490_000)
        self.assertTrue(iw.significant(hit)[0])

    def test_small_or_unknown_single_source_is_not_taken(self):
        base = {"kind": "breach", "aliases": [], "discovery": [{"source": "a", "url": "https://a.example/1"}]}
        self.assertFalse(iw.significant({**base, "name": "四條畷市", "scale": 26, "scaleText": "26人"})[0])
        self.assertFalse(iw.significant({**base, "name": "東急不動産", "scale": 0})[0])
        self.assertTrue(iw.significant({**base, "name": "資生堂", "scale": 0})[0])  # 全国で知られた名前
        two = [{"source": "a", "url": "https://a.example/1"}, {"source": "b", "url": "https://b.example/1"}]
        self.assertTrue(iw.significant({**base, "name": "東急不動産", "scale": 0, "discovery": two})[0])
        # 消費者庁の一覧だけの小さな回収は拾わない（全国で知られた名前だけ）
        self.assertFalse(iw.significant({**base, "kind": "recall", "name": "旭トラストフーズ", "scale": 0, "majorOnly": True, "discovery": two})[0])

    def test_old_items_are_dropped(self):
        srcs = {"x": {"slug": "x"}}
        old = [{"title": "「ネットマイル」に不正アクセス、最大約549万人", "url": "https://x.example/1", "summary": "",
                "published": NOW - timedelta(days=20), "source": "x"}]
        self.assertEqual(iw.detect(old, srcs, CFG, NOW), {})


class CoveredTest(unittest.TestCase):
    def test_muji_is_covered_by_name_url_and_site(self):
        hit = {"kind": "breach", "name": "良品計画", "aliases": ["無印良品", "MUJI"]}
        self.assertEqual(iw.covered(hit, [MUJI]), "muji-card-number-leak-2021")
        self.assertEqual(iw.covered({"kind": "breach", "name": "別の名前"}, [MUJI], "https://www.ryohin-keikaku.jp/news/articles/2026_1104_02/"),
                         "muji-card-number-leak-2021")
        # 同じ会社のサイトの別のお知らせ（第1報 10/30）でも、記事より前の日付なら同じ事故
        self.assertEqual(iw.covered({"kind": "breach", "name": "別の名前"}, [MUJI], "https://www.ryohin-keikaku.jp/news/articles/2026_1030_01",
                                    datetime(2026, 10, 30, tzinfo=JST)), "muji-card-number-leak-2021")

    def test_other_company_and_other_kind_are_not_covered(self):
        self.assertIsNone(iw.covered({"kind": "breach", "name": "ネットマイル"}, [MUJI], "https://www.netmile.co.jp/info/1"))
        self.assertIsNone(iw.covered({"kind": "recall", "name": "良品計画", "aliases": ["無印良品"]}, [MUJI]))

    def test_shared_hosts_do_not_count_as_same_company(self):
        a = article("a-leak", "A社の情報流出、対象は会員10万件", "https://www.release.tdnet.info/inbs/1.pdf")
        self.assertIsNone(iw.covered({"kind": "breach", "name": "B社"}, [a], "https://www.release.tdnet.info/inbs/2.pdf"))

    def test_newer_notice_is_left_to_the_fast_lane(self):
        hit = {"kind": "breach", "name": "良品計画", "aliases": ["無印良品"], "followup": True}
        self.assertIsNone(iw.covered(hit, [MUJI]))  # 続きの知らせは URL と日付が分かるまで決めない
        newer = datetime(2026, 11, 16, tzinfo=JST)
        self.assertIsNone(iw.covered(hit, [MUJI], "https://www.ryohin-keikaku.jp/news/articles/2026_1116_01", newer))
        older = datetime(2026, 11, 9, tzinfo=JST)
        self.assertEqual(iw.covered(hit, [MUJI], "https://www.ryohin-keikaku.jp/news/articles/2026_1109_01", older), "muji-card-number-leak-2021")


class ResolveTest(unittest.TestCase):
    HIT = {"key": "breach:ネットマイル", "kind": "breach", "name": "ネットマイル", "aliases": [],
           "discovery": [{"source": "scan-netsecurity", "url": "https://scan.netsecurity.ne.jp/article/2026/11/13/56773.html", "official": False}]}
    PDF = "https://global-assets.irdirect.jp/pdf/menu_file/4482/20261102152018_7983.pdf"

    def test_official_notice_from_links_in_the_article(self):
        pages = {
            self.HIT["discovery"][0]["url"]: page("記事の本文", [{"url": "https://bit.ly/x", "text": "広告"}, {"url": "https://www.nikkei.com/article/1", "text": "日経"},
                                                             {"url": self.PDF, "text": "リリース"}]),
            self.PDF: page(NOTICE, title="「ネットマイル」における不正アクセスによる個人情報漏洩の可能性に関するお知らせ"),
        }
        asked = []

        def fetch(url):
            asked.append(url)
            return pages[url]

        found = iw.resolve_official(self.HIT, fetch, CFG, NOW)
        self.assertEqual(found["url"], self.PDF)
        self.assertEqual(found["precision"], "date")
        self.assertEqual(iw.parse_time(found["announcedAt"]).astimezone(JST).strftime("%m-%d %H:%M"), "11-02 00:00")
        self.assertNotIn("https://www.nikkei.com/article/1", asked)  # 報道・短縮 URL は読みにも行かない
        self.assertNotIn("https://bit.ly/x", asked)

    def test_page_about_another_company_is_rejected(self):
        pages = {self.HIT["discovery"][0]["url"]: page("記事", [{"url": "https://www.example.co.jp/news/123", "text": "x"}]),
                 "https://www.example.co.jp/news/123": page("別の会社の不正アクセスのお知らせ。" * 60)}
        self.assertIsNone(iw.resolve_official(self.HIT, lambda u: pages[u], CFG, NOW))

    def test_third_party_blog_about_the_company_is_not_official(self):
        """ほかの会社のブログ・ニュース（「キユーピーは…と発表した」）は、会社の名前と事故の語があっても公式のお知らせではない"""
        hit = {"key": "breach:キユーピー", "kind": "breach", "name": "キユーピー", "aliases": [],
               "discovery": [{"source": "cybersecurity-jp", "url": "https://cybersecurity-jp.com/news/1", "official": False}]}
        blog = "https://act1.co.jp/2026-11-12-07/"
        own = "https://www.kewpie.com/newsrelease/2026/1112.html"
        third = ("公開日: 2026年11月12日\nキユーピーは2026年11月12日、委託先で第三者による不正アクセスが発生し、顧客のメールアドレス12万5,788件が"
                 "外部へ流出したと発表した。" + "当社のサービスなら防げます。" * 40)
        official = "お客様各位\n2026年11月12日\nキユーピー株式会社\n当社が利用するメール配信サービスへの不正アクセスにより、お客様のメールアドレスが流出しました。" + "お詫び申し上げます。" * 40
        pages = {"https://cybersecurity-jp.com/news/1": page("記事", [{"url": blog, "text": "解説"}, {"url": own, "text": "発表"}]),
                 blog: page(third), own: page(official)}
        self.assertFalse(iw.first_party(page(third), blog))
        self.assertTrue(iw.first_party(page(official), own))
        self.assertEqual(iw.resolve_official(hit, lambda u: pages[u], CFG, NOW)["url"], own)
        del pages[own]
        pages["https://cybersecurity-jp.com/news/1"] = page("記事", [{"url": blog, "text": "解説"}])
        self.assertIsNone(iw.resolve_official(hit, lambda u: pages[u], CFG, NOW))

    def test_date_in_url_wins_over_dates_in_the_body(self):
        body = "ここから本文です\n不正アクセスと対応について\n2026年10月23日、委託先から報告を受けました。11月13日までにご連絡します。"
        when, precision = iw.announced_of(page(body), NOW, "https://www.jal.co.jp/ja-jp/news/general/2026/other/261028.html")
        self.assertEqual((precision, when.astimezone(JST).strftime("%m-%d")), ("date", "10-28"))
        self.assertEqual(iw.url_date("https://www.ryohin-keikaku.jp/news/articles/2026_1104_02", NOW).astimezone(JST).strftime("%m-%d"), "11-04")
        self.assertEqual(iw.url_date("https://www.tokyo-gas.co.jp/news/press/20261112-02.html", NOW).astimezone(JST).strftime("%m-%d"), "11-12")
        self.assertIsNone(iw.url_date("https://www.monteur.co.jp/information/4189", NOW))
        when, _ = iw.announced_of(page("2026年11月2日(月)\nお詫びとお知らせ\n2026年11月1日に不正アクセスを確認し、11月10日に対応しました"), NOW,
                                  "https://www.nojima.co.jp/wp-content/uploads/2026/11/fa47.pdf")
        self.assertEqual(when.astimezone(JST).strftime("%m-%d"), "11-02")  # いちばん上の日付

    def test_company_top_page_is_followed_not_used(self):
        hit = {"key": "breach:資生堂", "kind": "breach", "name": "資生堂", "aliases": [], "home": "https://corp.shiseido.com/jp/", "discovery": []}
        notice = "https://corp.shiseido.com/jp/notice/20261106.html"
        pages = {"https://corp.shiseido.com/jp/": page("資生堂 企業情報 不正アクセスのお知らせ" * 30,
                                                       [{"url": "http://corp.shiseido.com/jp/notice/20261106.html", "text": "2026/11/06 当社肌測定システムへの不正アクセスによる個人情報漏えい"},
                                                        {"url": "https://corp.shiseido.com/jp/news/detail.html?n=1", "text": "新商品のお知らせ"}]),
                 notice: page("当社肌測定システムへの不正アクセスによる個人情報漏えいに関するお詫びとお知らせ\n2026/11/06\n" + "このたび当社は…" * 60)}
        found = iw.resolve_official(hit, lambda u: pages[u], CFG, NOW)
        self.assertEqual(found["url"], notice)  # トップページそのものは出典にしない。http のリンクは https に直す
        self.assertTrue(iw.is_home("https://corp.shiseido.com/jp/"))
        self.assertTrue(iw.is_home("https://www.monteur.co.jp/"))
        self.assertFalse(iw.is_home("https://www.monteur.co.jp/information/4189"))

    def test_press_wire_sns_are_never_official(self):
        for url in ["https://scan.netsecurity.ne.jp/article/1.html", "https://www.security-next.com/1", "https://prtimes.jp/main/html/rd/p/1.html",
                    "https://www.itmedia.co.jp/news/articles/1.html", "https://piyolog.hatenadiary.jp/entry/1", "https://x.com/a/status/1",
                    "https://news.yahoo.co.jp/articles/1", "http://www.example.co.jp/news/1"]:
            self.assertFalse(iw.official_candidate(url), url)
        self.assertTrue(iw.official_candidate("https://www.nojima.co.jp/wp-content/uploads/2026/11/a.pdf"))

    def test_announced_time(self):
        when, precision = iw.announced_of(page("本文", published="2026-11-13T15:30:00+09:00"), NOW)
        self.assertEqual((precision, when.astimezone(JST).hour), ("time", 15))
        when, precision = iw.announced_of(page("2026年11月9日\n第2報 11月8日に販売した商品を回収します。再開は2026年12月1日の予定"), NOW)
        self.assertEqual((precision, when.astimezone(JST).strftime("%m-%d")), ("date", "11-09"))  # 先の日付は発表の日にしない
        self.assertEqual(iw.announced_of(page("日付のない文"), NOW), (None, ""))


class StepTest(unittest.TestCase):
    def hit(self, name="ネットマイル", **extra):
        key = iw.hit_key("breach", name)
        return {key: {"key": key, "kind": "breach", "name": name, "aliases": [], "scale": 5_490_000, "scaleText": "最大約549万人",
                      "title": f"「{name}」に不正アクセス", "majorOnly": False,
                      "discovery": [{"source": "scan-netsecurity", "url": "https://scan.netsecurity.ne.jp/article/1.html", "title": "t",
                                     "publishedAt": "2026-11-12T23:05:10+00:00", "official": False}], **extra}}

    def pages(self):
        return {"https://scan.netsecurity.ne.jp/article/1.html": page("記事", [{"url": ResolveTest.PDF, "text": "リリース"}]),
                ResolveTest.PDF: page(NOTICE, title="お知らせ")}

    def test_new_incident_is_queued_and_dispatched_once(self):
        state = {"items": {}, "seen": {}}
        pages = self.pages()
        iw.step(state, self.hit(), [MUJI], lambda u: pages[u], CFG, NOW)
        entry = state["items"]["breach:ネットマイル"]
        self.assertEqual((entry["status"], entry["officialUrl"]), ("queued", ResolveTest.PDF))
        batch = iw.pick_dispatch(state, CFG, NOW)
        self.assertEqual([e["name"] for e in batch], ["ネットマイル"])
        meta = iw.build_meta(entry, CFG, NOW)
        self.assertEqual(meta["url"], ResolveTest.PDF)
        self.assertEqual(meta["incident"]["kind"], "breach")
        self.assertTrue(meta["incident"]["dateOnly"])
        self.assertNotIn("549", json.dumps(meta, ensure_ascii=False))  # 見つけた記事（報道）の件数は渡さない
        entry.update(status="dispatched", dispatchedAt=iw.iso(NOW), firstDispatchedAt=iw.iso(NOW), dispatches=1)
        self.assertEqual(iw.pick_dispatch(state, CFG, NOW + timedelta(minutes=10)), [])  # 結果を待つ
        self.assertEqual(len(iw.pick_dispatch(state, CFG, NOW + timedelta(minutes=50))), 1)  # 結果が無ければ起こし直す
        entry["dispatches"] = CFG["max_dispatches"]
        self.assertEqual(iw.pick_dispatch(state, CFG, NOW + timedelta(minutes=50)), [])
        self.assertEqual(entry["status"], "failed")

    def test_muji_is_not_made_twice(self):
        state = {"items": {}, "seen": {}}
        hits = iw.backfill_hits(CFG)
        muji = {k: v for k, v in hits.items() if v["name"] == "良品計画"}
        self.assertEqual(len(muji), 1)

        def fetch(url):
            raise AssertionError(f"記事がある事故は公式のページを読みにも行かない: {url}")

        notes = iw.step(state, muji, [MUJI], fetch, CFG, NOW)
        entry = next(iter(state["items"].values()))
        self.assertEqual((entry["status"], entry["slug"]), ("covered", "muji-card-number-leak-2021"))
        self.assertEqual(iw.pick_dispatch(state, CFG, NOW), [])
        self.assertTrue(any("記事あり" in n for n in notes))

    def test_backfill_keeps_its_mark_when_a_feed_reports_the_same_company(self):
        merged = iw.merge_backfill(iw.backfill_hits(CFG), self.hit())
        entry = merged["breach:ネットマイル"]
        self.assertTrue(entry["backfill"])
        self.assertEqual(entry["scale"], 5_490_000)
        self.assertEqual(entry["home"], "https://www.netmile.co.jp/")
        self.assertEqual(len(entry["discovery"]), 2)
        state = {"seen": {}, "items": {
            "a": {"key": "a", "kind": "breach", "name": "大きい会社", "status": "queued", "scale": 9_000_000, "detectedAt": iw.iso(NOW)},
            "b": {"key": "b", "kind": "recall", "name": "拾い直し", "status": "queued", "scale": 0, "backfill": True, "detectedAt": iw.iso(NOW)}}}
        self.assertEqual([e["name"] for e in iw.pick_dispatch(state, CFG, NOW)], ["拾い直し", "大きい会社"])  # 拾い直しを先に

    def test_no_official_notice_goes_to_the_press_rule(self):
        state = {"items": {}, "seen": {}}
        pages = {"https://scan.netsecurity.ne.jp/article/1.html": page("記事", [])}
        iw.step(state, self.hit(), [], lambda u: pages[u], CFG, NOW)
        entry = state["items"]["breach:ネットマイル"]
        self.assertEqual(entry["status"], "press")
        item = iw.press_queue_item(entry, CFG, NOW)
        self.assertEqual((item["kind"], item["title"], item["source_slug"]), ("trend", "ネットマイル 情報流出", "trends"))
        self.assertEqual(item["traffic"], iw.PRESS_TRAFFIC)
        self.assertEqual(iw.pick_dispatch(state, CFG, NOW), [])  # 報道の記事を速報レーンに渡さない（W31）

    def test_short_official_notice_is_not_dispatched(self):
        """モンテールの回収のお知らせ（938字）・東京ガス（1,098字）は、速報レーンの資料の下限（1,200字）で見送りになった。起こす前に止めて理由を残す"""
        state = {"items": {}, "seen": {}}
        url = "https://www.netmile.co.jp/info/notice-b.html"
        short = NOTICE[:900]
        pages = {"https://scan.netsecurity.ne.jp/article/1.html": page("記事", [{"url": url, "text": "リリース"}]), url: page(short)}
        notes = iw.step(state, self.hit(), [], lambda u: pages[u], CFG, NOW)
        entry = state["items"]["breach:ネットマイル"]
        self.assertEqual(entry["status"], "skipped")
        self.assertIn("短い", entry["reason"])
        self.assertTrue(any("公式が短い" in n for n in notes))
        self.assertEqual(iw.source_floor("breach"), iw.public_interest.MIN_SOURCE_CHARS)
        self.assertEqual(iw.source_floor("outage"), web_articles.MIN_TEXT_CHARS)

    def test_backfill_only_within_14_days(self):
        state = {"items": {}, "seen": {}}
        old = NOTICE.replace("2026年11月2日", "2026年10月20日")
        url = "https://www.netmile.co.jp/info/notice-a.html"
        pages = {"https://scan.netsecurity.ne.jp/article/1.html": page("記事", [{"url": url, "text": "リリース"}]), url: page(old)}
        iw.step(state, self.hit(), [], lambda u: pages[u], CFG, NOW)
        entry = state["items"]["breach:ネットマイル"]
        self.assertEqual(entry["status"], "skipped")
        self.assertIn("古い", entry["reason"])

    def test_followup_notice_after_the_article(self):
        state = {"items": {}, "seen": {}}
        pages = self.pages()
        iw.step(state, self.hit(), [], lambda u: pages[u], CFG, NOW)
        entry = state["items"]["breach:ネットマイル"]
        entry.update(status="published", slug="netmile-leak")
        later = NOW + timedelta(days=2)
        made = article("netmile-leak", "ネットマイルの情報流出、最大約549万人が対象か", ResolveTest.PDF, made=iw.iso(NOW))
        second = "https://www.netmile.co.jp/info/20261116.html"
        new_hit = self.hit()
        new_hit["breach:ネットマイル"]["discovery"] = [{"source": "security-next", "url": "https://www.security-next.com/2", "title": "続報",
                                                    "publishedAt": iw.iso(later - timedelta(hours=1)), "official": False}]
        pages["https://www.security-next.com/2"] = page("記事", [{"url": second, "text": "第2報"}])
        pages[second] = page(NOTICE.replace("2026年11月2日", "2026年11月16日"))
        iw.step(state, new_hit, [made], lambda u: pages[u], CFG, later)
        follow = [e for k, e in state["items"].items() if "#" in k]
        self.assertEqual(len(follow), 1)
        self.assertEqual((follow[0]["status"], follow[0]["officialUrl"]), ("queued", second))
        self.assertEqual(state["items"]["breach:ネットマイル"]["status"], "published")

    def test_undated_list_item_is_not_taken(self):
        state = {"items": {}, "seen": {}}
        key = "recall:小林製薬"
        hits = {key: {"key": key, "kind": "recall", "name": "小林製薬", "aliases": [], "scale": 0, "scaleText": "", "title": "小林製薬「紅麹」 - 回収命令",
                      "majorOnly": True, "discovery": [{"source": "caa-recall-all", "url": "https://www.recall.caa.go.jp/result/detail.php?rcl=1",
                                                       "title": "t", "publishedAt": "", "official": False}]}}
        pages = {"https://www.recall.caa.go.jp/result/detail.php?rcl=1": page("対応開始日 2024年3月22日 回収命令")}
        iw.step(state, hits, [], lambda u: pages[u], CFG, NOW)
        self.assertEqual(state["items"][key]["status"], "skipped")


class OwnSiteTest(unittest.TestCase):
    """会社自身のお知らせの欄を直接見る（他社が伝えるのを待たない）"""

    HOME = "https://www.monteur.co.jp/"
    NOTICE_URL = "https://www.monteur.co.jp/information/5001"
    CFG1 = {**CFG, "homes": [{"name": "モンテール", "url": HOME}]}

    def pages(self, date="2026年11月14日"):
        body = f"商品の回収に関するお詫びとお知らせ\n{date}\n弊社が製造した商品の一部を自主回収いたします。" + "対象の商品と連絡先は次のとおりです。" * 80
        return {self.HOME: page("トップ", [{"url": self.NOTICE_URL, "text": "商品の回収に関するお詫びとお知らせ"},
                                         {"url": "https://www.monteur.co.jp/information/4177", "text": "11月新商品のお知らせ"},
                                         {"url": "https://www.monteur.co.jp/sustainability/", "text": "回収キャップを再資源化する取り組み"}]),
                self.NOTICE_URL: page(body)}

    def test_new_notice_on_the_company_site_is_queued_with_an_upper_bound(self):
        pages = self.pages()
        checked = {"モンテール": "2026-11-14T02:45:00+00:00"}
        items, sources, errors = iw.gather_homes(self.CFG1, lambda u: pages[u], checked, NOW)
        self.assertEqual([i["url"] for i in items], [self.NOTICE_URL])  # 新商品・取り組みのリンクは拾わない
        self.assertEqual(errors, [])
        self.assertEqual(checked["モンテール"], iw.iso(NOW))
        hits = iw.detect(items, sources, self.CFG1, NOW)
        self.assertEqual(set(hits), {"recall:モンテール"})
        self.assertTrue(iw.significant(hits["recall:モンテール"], self.CFG1)[0])
        state = {"items": {}, "seen": {}, "homes": checked}
        iw.step(state, hits, [], lambda u: pages[u], self.CFG1, NOW)
        entry = state["items"]["recall:モンテール"]
        self.assertEqual((entry["status"], entry["officialUrl"]), ("queued", self.NOTICE_URL))
        self.assertEqual(entry["appearedAfter"], "2026-11-14T02:45:00+00:00")
        entry.update(status="published", slug="monteur-recall", publishedAt="2026-11-14T03:10:00+00:00")
        row = iw.latency_rows(state)[0]
        self.assertIsNone(row["announceToPublish"])          # 発表の時刻は日付しか分からない
        self.assertEqual(row["announceToPublishMax"], 25.0)  # 前の確認（11:45）より後に出たので、長くても25分
        self.assertIn("長くても25分", iw.report_markdown(state, self.CFG1))

    def test_old_notice_on_the_first_look_is_not_made(self):
        pages = self.pages(date="2026年10月1日")
        checked = {}
        items, sources, _ = iw.gather_homes(self.CFG1, lambda u: pages[u], checked, NOW)
        state = {"items": {}, "seen": {}, "homes": checked}
        iw.step(state, iw.detect(items, sources, self.CFG1, NOW), [], lambda u: pages[u], self.CFG1, NOW)
        self.assertEqual(state["items"]["recall:モンテール"]["status"], "skipped")

    def test_second_notice_from_the_company_is_checked_at_once(self):
        pages = self.pages(date="2026年11月15日")
        made = article("monteur-recall", "モンテールのシュークリーム回収、対象の商品と連絡先", "https://www.monteur.co.jp/information/4189", made="2026-11-14T04:00:00+00:00")
        state = {"seen": {}, "homes": {}, "items": {"recall:モンテール": {
            "key": "recall:モンテール", "kind": "recall", "name": "モンテール", "status": "published", "slug": "monteur-recall",
            "detectedAt": "2026-11-14T03:00:00+00:00", "discovery": [{"source": "home:モンテール", "url": "https://www.monteur.co.jp/information/4189", "official": True}]}}}
        later = NOW + timedelta(hours=30)
        items, sources, _ = iw.gather_homes(self.CFG1, lambda u: pages[u], state["homes"], later)
        iw.step(state, iw.detect(items, sources, self.CFG1, later), [made], lambda u: pages[u], self.CFG1, later)
        follow = [e for k, e in state["items"].items() if "#" in k]
        self.assertEqual(len(follow), 1)
        self.assertEqual((follow[0]["status"], follow[0]["officialUrl"]), ("queued", self.NOTICE_URL))  # 記事より新しい第2報は速報レーンが続報か決める

    def test_unreadable_site_does_not_stop_the_others(self):
        def fetch(url):
            raise RuntimeError("HTTP Error 403")

        checked = {"モンテール": "x"}
        items, _sources, errors = iw.gather_homes(self.CFG1, fetch, checked, NOW)
        self.assertEqual(items, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(checked["モンテール"], "x")  # 読めなかった回は「前回の確認」を進めない

    def test_listed_homes(self):
        names = [h["name"] for h in CFG["homes"]]
        self.assertEqual(len(names), len(set(names)))
        for want in ["良品計画", "ノジマ", "クラブツーリズム", "アイスタイル", "ソラシドエア", "SUBARU", "シェアフル", "モンテール", "資生堂"]:
            self.assertIn(want, names)
        for h in CFG["homes"]:
            self.assertTrue(iw.official_candidate(h["url"]), h["name"])


class FastLaneTest(unittest.TestCase):
    """速報レーン（scripts/web_articles.py）: 事故の見張りの依頼を受け付け、門・上限・古さの決まりの外で作る"""

    URL = "https://www.monteur.co.jp/information/4189"

    def build(self, meta):
        state = {"processed_web": {}, "failed_web": {}, "major_tries": {}}
        with patch.object(fast_lane, "load_acks", return_value={"items": {}}), \
                patch.object(web_articles.feeds, "fetch_article_text", side_effect=AssertionError("ネットに出ない")):
            return web_articles.build_fast_items([meta["url"]], json.dumps([meta], ensure_ascii=False), state, NOW)

    def meta(self, **extra):
        return {"id": "incident-abc", "url": self.URL, "title": "商品の回収に関するお詫びとお知らせ", "sourceName": "モンテール", "lang": "ja",
                "publishedAt": "2026-11-08T15:00:00+00:00", "detectedAt": "2026-11-14T03:00:00+00:00", "genre": "lifestyle",
                "text": "商品の回収に関するお詫びとお知らせ。" + "本文の説明です。" * 300, **extra}

    def test_incident_request_is_accepted_for_unregistered_company_site(self):
        self.assertFalse(fast_lane.allowed_url(self.URL))  # 登録外の会社のサイト
        items, results = self.build(self.meta(incident={"key": "recall:モンテール", "kind": "recall", "name": "モンテール", "dateOnly": True}))
        self.assertEqual(results, {})
        item = items[0]
        self.assertEqual(item["_incident"]["kind"], "recall")
        self.assertEqual(item["_public_interest"], "recall")
        self.assertEqual(item["section"], "lifestyle")
        self.assertTrue(item["fast"])
        self.assertFalse(item["published_guessed"])
        # 発表から5日たっていても落とさない（速報ではない形 late で作る）。審査の期間の門・1日の上限の外（速報と同じ扱い）
        self.assertTrue(web_articles.is_stale(item))
        self.assertTrue(web_articles.breaking_candidate(item))
        self.assertFalse(news_mix.review_ai_blocks({**item, "section": web_articles.major_lane(item)},
                                                   breaking=web_articles.breaking_candidate(item), today="2026-11-14"))
        # SNS の【速報】にはしない（公共性の枠の決まり: 速報の投稿はミサイル・災害だけ）
        fresh = {**item, "published_at": datetime.now(timezone.utc) - timedelta(minutes=5)}
        self.assertFalse(web_articles.breaking_record(fresh))
        self.assertEqual(web_articles.article_purpose(item, "lifestyle", major=True), "sns")

    def test_without_incident_the_same_url_is_still_rejected(self):
        items, results = self.build(self.meta())
        self.assertEqual(items, [])
        self.assertEqual(next(iter(results.values()))["reason"], "対象外のURL")

    def test_press_url_is_rejected_even_with_incident(self):
        meta = self.meta(incident={"key": "k", "kind": "breach", "name": "X"})
        meta["url"] = "https://scan.netsecurity.ne.jp/article/2026/11/13/56773.html"
        items, results = self.build(meta)
        self.assertEqual(items, [])

    def test_stale_and_cap_gates_stay_outside_the_fast_lane(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn('if is_stale(cand) and not cand.get("fast"):', src)  # 候補の段の古さの見送りは速報レーンに当てない
        self.assertIn("if not major and too_old(item)", src)               # 本文を読んだあとの古さの見送りも大きなニュースの外
        self.assertIn("incident_watch.prompt_note(item[\"_incident\"])", src)
        note = iw.prompt_note({"kind": "breach"})
        for word in ["対象の条件の表", "連絡の届き方・窓口", "今やること", "経緯", "公式の資料に書かれた数字だけ"]:
            self.assertIn(word, note)
        self.assertEqual(iw.prompt_note(None), "")

    def test_fast_run_deploys_at_once(self):
        wf = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertRegex(wf, r"FORCE_DEPLOY: .*\(inputs\.fast_url \|\| ''\) != ''")


class RecordTest(unittest.TestCase):
    def state(self):
        return {"seen": {}, "items": {
            "breach:a": {"key": "breach:a", "kind": "breach", "name": "A社", "status": "dispatched", "officialUrl": "https://www.a.co.jp/n/1",
                         "announcedAt": "2026-11-14T01:00:00+00:00", "precision": "time", "discoveredAt": "2026-11-14T01:40:00+00:00",
                         "detectedAt": "2026-11-14T01:50:00+00:00", "dispatchedAt": "2026-11-14T01:51:00+00:00", "firstDispatchedAt": "2026-11-14T01:51:00+00:00"},
            "recall:b": {"key": "recall:b", "kind": "recall", "name": "B社", "status": "dispatched", "officialUrl": "https://www.b.co.jp/n/1",
                         "announcedAt": "2026-11-08T15:00:00+00:00", "precision": "date", "discoveredAt": "", "detectedAt": "2026-11-14T01:50:00+00:00",
                         "dispatchedAt": "2026-11-14T01:51:00+00:00", "firstDispatchedAt": "2026-11-14T01:51:00+00:00", "backfill": True},
            "breach:c": {"key": "breach:c", "kind": "breach", "name": "C社", "status": "dispatched", "officialUrl": "https://www.c.co.jp/n/1",
                         "detectedAt": "2026-11-14T01:50:00+00:00", "dispatchedAt": "2026-11-14T01:51:00+00:00"},
        }}

    def test_settle_and_latency(self):
        state = self.state()
        acks = {"items": {
            iw.fast_id("breach:a"): {"outcome": "created", "slug": "a-leak", "finishedAt": "2026-11-14T02:05:00+00:00"},
            iw.fast_id("recall:b"): {"outcome": "created", "slug": "b-recall", "finishedAt": "2026-11-14T02:06:00+00:00"},
            iw.fast_id("breach:c"): {"outcome": "skipped", "reason": "public-interest: 資料が短い 900字", "finishedAt": "2026-11-14T02:07:00+00:00"},
        }}
        arts = [article("a-leak", "A社の情報流出", "https://www.a.co.jp/n/1", made="2026-11-14T02:03:00+00:00"),
                article("b-recall", "B社の回収", "https://www.b.co.jp/n/1", made="2026-11-14T02:04:00+00:00")]
        live = {"live": {"a-leak": {"liveAt": "2026-11-14T02:10:00+00:00"}}}
        iw.settle(state, acks, arts, live, NOW, CFG)
        self.assertEqual([state["items"][k]["status"] for k in ("breach:a", "recall:b", "breach:c")], ["published", "published", "failed"])
        self.assertIn("資料が短い", state["items"]["breach:c"]["reason"])
        rows = {r["name"]: r for r in iw.latency_rows(state)}
        self.assertEqual(rows["A社"]["announceToPublish"], 70.0)   # 発表 10:00 → 本番で開けた 11:10
        self.assertEqual(rows["A社"]["detectToPublish"], 20.0)
        self.assertEqual(rows["A社"]["pressToDetect"], 10.0)
        self.assertIsNone(rows["B社"]["announceToPublish"])        # 日付しか分からない発表では「発表から何分」を出さない
        md = iw.report_markdown(state, CFG)
        self.assertIn("（日付のみ）", md)
        self.assertIn("C社", md)

    def test_old_ack_does_not_settle_a_new_dispatch(self):
        state = self.state()
        acks = {"items": {iw.fast_id("breach:a"): {"outcome": "retry", "finishedAt": "2026-11-14T02:05:00+00:00"}}}
        iw.settle(state, acks, [], {}, NOW, CFG)
        self.assertEqual(state["items"]["breach:a"]["status"], "dispatched")

    def test_state_roundtrip_and_press_queue(self):
        import trends

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "incident_watch.json"
            state = {"seen": {"x": iw.iso(NOW - timedelta(days=60))}, "items": {
                "breach:n": {"key": "breach:n", "kind": "breach", "name": "ネットマイル", "status": "press", "detectedAt": iw.iso(NOW), "title": "t",
                             "discovery": [{"source": "scan-netsecurity", "url": "https://scan.netsecurity.ne.jp/article/1.html", "title": "t", "publishedAt": ""}]}}}
            iw.save_state(state, NOW, path)
            again = iw.load_state(path)
            self.assertEqual(again["seen"], {})  # 古い印は消す
            self.assertEqual(again["items"]["breach:n"]["status"], "press")
            real_now = datetime.now(timezone.utc)
            again["items"]["breach:n"]["detectedAt"] = iw.iso(real_now)
            with patch.object(trends, "QUEUE_PATH", Path(tmp) / "trend_queue.json"):
                self.assertEqual(iw.apply_press(again, CFG, real_now), 1)
                self.assertEqual(iw.apply_press(again, CFG, real_now), 0)  # 二重に足さない
                queue = json.loads((Path(tmp) / "trend_queue.json").read_text("utf-8"))["items"]
            self.assertEqual(queue[0]["title"], "ネットマイル 情報流出")
            self.assertEqual(queue[0]["sources"][0]["url"], "https://scan.netsecurity.ne.jp/article/1.html")


class ConfigTest(unittest.TestCase):
    def test_sources(self):
        slugs = [s["slug"] for s in CFG["discovery"]]
        self.assertEqual(len(slugs), len(set(slugs)))
        for s in CFG["discovery"]:
            self.assertTrue(s["url"].startswith("https://"), s["slug"])
        for want in ("scan-netsecurity", "security-next", "piyolog", "tdnet-recent", "caa-recall-all"):
            self.assertIn(want, slugs)
        # 見つけるための発信元は、公式の一次情報としては受け付けない（適時開示の PDF を除く）
        for s in CFG["discovery"]:
            if not s.get("official") and ".go.jp" not in s["url"]:
                self.assertFalse(iw.official_candidate(s["url"].rstrip("/") + "/article/1.html"), s["slug"])

    def test_backfill_lists_the_missed_incidents(self):
        names = [b["name"] for b in CFG["backfill"]]
        for want in ["良品計画", "クラブツーリズム", "アイスタイル", "ソラシドエア", "SUBARU", "シェアフル", "ノジマ", "ネットマイル", "モンテール", "資生堂"]:
            self.assertIn(want, names)
        self.assertEqual(CFG["max_age_days"], 14)

    def test_workflow(self):
        wf = (ROOT / ".github" / "workflows" / "incident_watch.yml").read_text("utf-8")
        self.assertIn('workflows: ["Auto Article Pipeline", "Deploy to Cloudflare Workers"]', wf)  # schedule が遅れても確かに動く
        self.assertIn("actions: write", wf)
        self.assertIn("cancel-in-progress: false", wf)
        self.assertIn("python scripts/incident_watch.py run", wf)
        self.assertIn("--backfill", wf)

    def test_daily_guard(self):
        state = {"seen": {}, "items": {f"breach:{i}": {"key": f"breach:{i}", "kind": "breach", "name": str(i), "status": "queued", "scale": i,
                                                       "detectedAt": iw.iso(NOW)} for i in range(5)}}
        batch = iw.pick_dispatch(state, CFG, NOW)
        self.assertEqual([e["name"] for e in batch], ["4", "3", "2"])  # 大きい順に、1回3件まで
        cfg = {**CFG, "daily_max": 1}
        self.assertEqual(len(iw.pick_dispatch(state, cfg, NOW)), 1)


if __name__ == "__main__":
    unittest.main()
