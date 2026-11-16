#!/usr/bin/env python3
"""同じ会社の、日が違う障害は別の事故（2026-11-16・台帳 W45）。

NTTドコモの 5G SA の障害は 11/5・11/11・11/16 の3回。事故の鍵が「種類:会社」だけで日付が無く、公式の障害のお知らせ一覧も
直接は読んでいなかったので、11/16 の障害は発生から約1時間54分たって他社の記事で気づいた。ここで確かめること:

  (a) 同じ会社の別の日の障害は「記事あり」にならない（新しい事故として速報レーンに回る）
  (b) 同じ事故の続きのお知らせ（第二報・一部復旧・復旧）は、2本目の記事を作らない（同じ事故の記事への追記に回る）
  (c) ドコモの一覧の読み取りが【障害発生】【第N報】【復旧】と日付を取り出す
  (d) 障害の記事に、同じ会社の過去の障害（発生と復旧の時刻・かかった時間・公式が発表した原因）を渡す。過去の原因は今回の原因にしない
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import incident_watch as iw  # noqa: E402

JST = timezone(timedelta(hours=9))
CFG = iw.CONFIG
FIX = json.loads((ROOT / "tests" / "fixtures" / "docomo_outage_notices_20261116.json").read_text("utf-8"))
LIST_URL = "https://www.docomo.ne.jp/info/network/"
BASE = "https://www.docomo.ne.jp/info/network/kanto/pages/"
NOW = datetime(2026, 11, 16, 10, 20, tzinfo=JST)  # 第一報（障害発生）が出た直後


def listing(until: str = "") -> dict:
    """一覧のページ。until（例 "261116_00"）より新しい 11/16 のお知らせを消して「その時点の一覧」にする"""
    links = [l for l in FIX["list"]["links"] if not until or "/261116_" not in l["url"] or l["url"].rsplit("/", 1)[1][:9] <= until]
    return {**FIX["list"], "links": links}


def fetcher(until: str = ""):
    def fetch(url: str) -> dict:
        if url == LIST_URL:
            return listing(until)
        if url in FIX["pages"]:
            return FIX["pages"][url]
        raise RuntimeError(f"読めない: {url}")
    return fetch


def article(slug, title, url, made, incident=None):
    return {"slug": slug, "title": title, "seoTitle": "", "urls": [url], "publishedAt": iw.parse_time(made), "madeAt": iw.parse_time(made),
            "sourcePublishedAt": None, "detectedAt": None, "incident": incident}


# 11/11 の障害の記事（本番にあるもの）
OLD = [
    article("docomo-5g-sa-outage-4g-switch", "ドコモ障害は5G SA契約者だけが対象　4Gへの切り替え方と対象の確かめ方", BASE + "261111_04_m.html", "2026-11-11T07:01:59+00:00"),
    article("docomo-5g-sa-outage-recovery", "ドコモ5G SAの障害、一部を除き復旧　まだつながらないときは再起動か機内モード", BASE + "261111_07_m.html", "2026-11-11T08:40:18+00:00"),
    article("docomo-outage-press", "NTTドコモで通信障害　全国で通話とデータ通信がつながりにくい", "https://example.co.jp/news/1", "2026-11-11T03:00:00+00:00"),
]
TODAY = article("docomo-5g-sa-network-outage-2026", "ドコモ5G SAで全国障害　4Gへの切り替えと再起動で使える場合も", BASE + "261116_01_m.html", "2026-11-16T02:58:21+00:00")


def docomo_only(cfg=CFG):
    return {**cfg, "notices": [s for s in cfg["notices"] if s["name"] == "NTTドコモ"]}


def run_cycle(state: dict, articles: list[dict], until: str, now: datetime) -> list[str]:
    """見張りの1回分（一覧を読む → 新しい見出しだけ → 候補 → 記事の有無・公式のお知らせ）"""
    fetch = fetcher(until)
    items, sources, errors, days = iw.gather_notices(docomo_only(), fetch, now)
    assert not errors, errors
    fresh = [i for i in items if i["url"] not in state["seen"]]
    for i in fresh:
        state["seen"][i["url"]] = iw.iso(now)
    hits = iw.detect(fresh, sources, CFG, now, iw.open_days_of(state))
    return iw.step(state, hits, articles, fetch, CFG, now, notice_days=days)


class NoticeListTest(unittest.TestCase):
    """(c) ドコモの一覧の読み取り"""

    def rows(self):
        return iw.parse_notice_list(iw.notice_src("NTTドコモ"), listing(), datetime(2026, 11, 16, 17, 0, tzinfo=JST))

    def test_stages_and_dates(self):
        by_url = {r["url"].rsplit("/", 1)[1]: r for r in self.rows()}
        start = by_url["261116_00_m.html"]
        self.assertEqual((start["stage"], start["posted"].strftime("%Y-%m-%d")), ("start", "2026-11-16"))
        self.assertIn("障害発生", start["title"])
        second = by_url["261116_01_m.html"]
        self.assertEqual((second["stage"], second["no"], second["asOf"].strftime("%m-%d %H:%M")), ("report", 2, "11-16 10:30"))
        self.assertEqual((by_url["261116_02_m.html"]["stage"], by_url["261116_02_m.html"]["no"]), ("report", 3))
        partial = by_url["261116_06_m.html"]
        self.assertEqual((partial["stage"], partial["no"], partial["asOf"].strftime("%H:%M")), ("partial", 7, "15:30"))
        done = by_url["261111_13_m.html"]
        self.assertEqual((done["stage"], done["posted"].strftime("%m-%d"), done["asOf"].strftime("%H:%M")), ("recovered", "11-11", "20:45"))
        numbers = sorted(r["no"] for r in self.rows() if "/261111_" in r["url"] and r["stage"] == "report")
        self.assertEqual(numbers[-2:], [10, 11])  # 第十報・第十一報

    def test_stage_words(self):
        self.assertEqual(iw.notice_stage("【障害発生】携帯電話サービスがご利用しづらい状況について"), ("start", 1))
        self.assertEqual(iw.notice_stage("【第二報】携帯電話サービスがご利用しづらい状況について"), ("report", 2))
        self.assertEqual(iw.notice_stage("【第五報/一部復旧】携帯電話サービスがご利用しづらい状況について"), ("partial", 5))
        self.assertEqual(iw.notice_stage("【お詫び/復旧】携帯電話サービスがご利用しづらい状況について")[0], "recovered")
        self.assertEqual(iw.notice_stage("【第3報】通信障害について"), ("report", 3))

    def test_incidents_are_grouped_by_start_day(self):
        groups = iw.group_notices(self.rows())
        mobile = iw._subject("携帯電話サービスがご利用しづらい状況について")
        self.assertEqual(sorted(g["day"] for g in groups if g["subject"] == mobile), ["20261028", "20261105", "20261111", "20261116"])  # 日ごとに別の事故
        nov5 = next(g for g in groups if g["day"] == "20261105")
        self.assertEqual(nov5["rows"][-1]["url"].rsplit("/", 1)[1], "261106_00_m.html")  # 翌日に出た復旧のお知らせも 11/5 の事故
        self.assertEqual(nov5["stage"], "recovered")
        self.assertTrue(any(g["subject"] != mobile for g in groups))  # ドコモメールの障害は別の対象

    def test_only_milestones_and_recent_incidents_become_candidates(self):
        items, sources, errors, days = iw.gather_notices(docomo_only(), fetcher(), datetime(2026, 11, 16, 17, 0, tzinfo=JST))
        self.assertEqual(errors, [])
        self.assertEqual({i["day"] for i in items}, {"20261116"})  # 11/5・11/11 の終わった障害は今から記事にしない
        self.assertEqual(sorted(i["stage"] for i in items), ["partial", "report", "start"])  # 毎時の報は拾わない
        self.assertEqual(days[iw._url_key(BASE + "261106_00_m.html")], "20261105")
        self.assertTrue(sources["notice:NTTドコモ"]["official"])

    def test_disaster_and_local_notices_are_not_outages(self):
        src = iw.notice_src("NTTドコモ")
        page = {"text": "", "links": [
            {"url": BASE + "261023_00_m.html", "text": "【復旧】台風30号の影響により、携帯電話サービスがご利用できない、またはご利用しづらい状況について"},
            {"url": BASE + "260625_00_m.html", "text": "青森で発生した地震による携帯電話サービスの影響について（サービス影響なし）"},
            {"url": "https://www.docomo.ne.jp/info/news_release/2026/11/04_00.html", "text": "通信障害に関する報道発表"},
        ]}
        self.assertEqual(iw.parse_notice_list(src, page, NOW), [])

    def test_config_lists_carrier_pages(self):
        names = {s["name"]: s for s in CFG["notices"]}
        self.assertEqual(names["NTTドコモ"]["url"], LIST_URL)
        self.assertIn("楽天モバイル", names)
        self.assertEqual(iw.notice_src(BASE + "261116_00_m.html")["name"], "NTTドコモ")
        self.assertIsNone(iw.notice_src("https://www.docomo.ne.jp/info/news_release/2026/11/04_00.html"))


class RepeatOutageTest(unittest.TestCase):
    """(a) 別の日の障害は新しい事故"""

    def old_state(self):
        return {"seen": {}, "homes": {}, "items": {
            # 11/16 より前の形の鍵（日付なし）と、11/11 の事故
            "outage:nttドコモ": {"key": "outage:nttドコモ", "kind": "outage", "name": "NTTドコモ", "aliases": ["ドコモ"], "status": "covered",
                              "slug": "docomo-5g-sa-outage-recovery", "detectedAt": "2026-11-11T02:00:00+00:00", "discovery": []},
            "outage:nttドコモ@20261111": {"key": "outage:nttドコモ@20261111", "kind": "outage", "name": "NTTドコモ", "aliases": ["ドコモ"], "day": "20261111",
                                       "status": "published", "slug": "docomo-5g-sa-outage-recovery", "detectedAt": "2026-11-11T02:00:00+00:00",
                                       "discovery": [{"source": "notice:NTTドコモ", "url": BASE + "261111_00_m.html", "official": True}]},
        }}

    def test_key_has_the_incident_day(self):
        self.assertEqual(iw.hit_key("outage", "NTTドコモ", "20261116"), "outage:nttドコモ@20261116")
        self.assertEqual(iw.hit_key("breach", "NTTドコモ"), "breach:nttドコモ")
        self.assertEqual(iw.base_key("outage:nttドコモ@20261116#20261116ab12cd"), "outage:nttドコモ")
        self.assertIn("outage", CFG["dated_kinds"])

    def test_second_outage_on_another_day_is_not_covered(self):
        state = self.old_state()
        notes = run_cycle(state, OLD, "261116_00", NOW)
        entry = state["items"]["outage:nttドコモ@20261116"]
        self.assertEqual(entry["status"], "queued", (entry.get("reason"), notes))
        self.assertEqual(entry["officialUrl"], BASE + "261116_00_m.html")
        self.assertEqual(entry["day"], "20261116")
        self.assertFalse(entry.get("followup"))
        meta = iw.build_meta(entry, CFG, NOW)
        self.assertEqual(meta["incident"]["day"], "20261116")
        self.assertNotIn("followup", meta["incident"])
        self.assertNotEqual(meta["id"], iw.fast_id("outage:nttドコモ"))  # 速報レーンの結果の記録も前の事故と混ざらない
        self.assertEqual([e["key"] for e in iw.pick_dispatch(state, CFG, NOW)], ["outage:nttドコモ@20261116"])

    def test_old_articles_do_not_cover_a_new_day(self):
        hit = {"kind": "outage", "name": "NTTドコモ", "aliases": ["ドコモ", "docomo"], "day": "20261116"}
        self.assertIsNone(iw.covered(hit, OLD, cfg=CFG))
        self.assertIsNone(iw.covered(hit, OLD, BASE + "261116_00_m.html", datetime(2026, 11, 16, tzinfo=JST), CFG))
        self.assertEqual(iw.covered({**hit, "day": "20261111"}, OLD, cfg=CFG), "docomo-5g-sa-outage-4g-switch")
        # 同じ日の記事があれば「記事あり」（題名に「通信障害」の語が無くても、出典が同じ会社の障害のお知らせなら同じ事故）
        self.assertEqual(iw.covered(hit, [*OLD, TODAY], cfg=CFG), TODAY["slug"])
        # 日付の無い種類（情報流出）は今までどおり会社＋種類で見る
        leak = article("docomo-data-leak", "ドコモで不正アクセス　個人情報が流出の可能性", "https://www.docomo.ne.jp/info/notice/1.html", "2026-11-05T05:00:00+00:00")
        self.assertEqual(iw.covered({"kind": "breach", "name": "NTTドコモ", "aliases": ["ドコモ"]}, [leak], cfg=CFG), "docomo-data-leak")

    def test_press_headline_of_a_new_outage_gets_its_own_day(self):
        items = [{"title": "NTTドコモ、11月16日10時2分から全国で通信障害 5G SAの通話・データ通信・SMSに影響、今月3回目",
                  "url": "https://rocket-boys.co.jp/x/", "summary": "", "published": datetime(2026, 11, 16, 11, 52, tzinfo=JST), "source": "rocket-boys"}]
        hits = iw.detect(items, {"rocket-boys": {"slug": "rocket-boys"}}, CFG, datetime(2026, 11, 16, 11, 56, tzinfo=JST), {"outage:nttドコモ": ["20261111"]})
        self.assertEqual(list(hits), ["outage:nttドコモ@20261116"])
        self.assertIsNone(iw.covered(hits["outage:nttドコモ@20261116"], OLD, cfg=CFG))

    def test_undated_recovery_headline_joins_the_open_incident(self):
        late = [{"title": "ドコモの通信障害が復旧、全国で通話とデータ通信が元どおりに", "url": "https://example.co.jp/n/2", "summary": "",
                 "published": datetime(2026, 11, 17, 1, 30, tzinfo=JST), "source": "press"}]
        hits = iw.detect(late, {}, CFG, datetime(2026, 11, 17, 2, 0, tzinfo=JST), {"outage:nttドコモ": ["20261111", "20261116"]})
        self.assertEqual(list(hits), ["outage:nttドコモ@20261116"])  # 翌日の「復旧」の見出しは、新しい事故ではなく 11/16 の事故の続き
        fresh = [{"title": "ドコモで通信障害、全国でつながりにくい", "url": "https://example.co.jp/n/3", "summary": "",
                  "published": datetime(2026, 11, 20, 9, 30, tzinfo=JST), "source": "press"}]
        hits = iw.detect(fresh, {}, CFG, datetime(2026, 11, 20, 9, 40, tzinfo=JST), {"outage:nttドコモ": ["20261111", "20261116"]})
        self.assertEqual(list(hits), ["outage:nttドコモ@20261120"])

    def test_first_notice_under_600_chars_is_not_dropped(self):
        self.assertLess(len(FIX["pages"][BASE + "261116_00_m.html"]["text"]), iw.OUTAGE_SOURCE_FLOOR)  # 第一報は596字
        self.assertEqual(iw.source_floor("outage", CFG, BASE + "261116_00_m.html"), CFG["notice_min_source_chars"])
        self.assertEqual(iw.source_floor("outage", CFG, "https://www.example.co.jp/info/1.html"), iw.OUTAGE_SOURCE_FLOOR)
        self.assertEqual(iw.source_floor("outage", CFG), iw.OUTAGE_SOURCE_FLOOR)


class FollowupTest(unittest.TestCase):
    """(b) 同じ事故の続きのお知らせは2本目の記事を作らない"""

    def test_followup_notices_do_not_open_a_second_incident(self):
        state = {"seen": {}, "homes": {}, "items": {}}
        run_cycle(state, OLD, "261116_00", NOW)
        base = state["items"]["outage:nttドコモ@20261116"]
        self.assertEqual(base["status"], "queued")
        base.update(status="published", slug=TODAY["slug"])  # 速報レーンが記事を作った
        articles = [*OLD, {**TODAY, "urls": [BASE + "261116_00_m.html"], "incident": {"kind": "outage", "name": "NTTドコモ", "day": "20261116"}}]

        run_cycle(state, articles, "261116_01", datetime(2026, 11, 16, 10, 40, tzinfo=JST))  # 第二報
        run_cycle(state, articles, "261116_03", datetime(2026, 11, 16, 13, 10, tzinfo=JST))  # 第三報・第四報（節目ではない）
        run_cycle(state, articles, "261116_06", datetime(2026, 11, 16, 15, 40, tzinfo=JST))  # 一部復旧（第五〜七報）
        keys = sorted(state["items"])
        self.assertEqual([k for k in keys if "#" not in k], ["outage:nttドコモ@20261116"])  # 事故は1つのまま
        follow = sorted((state["items"][k] for k in keys if "#" in k), key=lambda f: f["officialUrl"])
        self.assertEqual([f["officialUrl"].rsplit("/", 1)[1] for f in follow], ["261116_01_m.html", "261116_04_m.html"])  # 第二報と最初の一部復旧だけ
        for f in follow:
            self.assertTrue(f["followup"])
            self.assertEqual((f["status"], f["day"]), ("queued", "20261116"), f.get("reason"))
            meta = iw.build_meta(f, CFG, NOW)
            self.assertEqual((meta["incident"]["day"], meta["incident"]["followup"]), ("20261116", True))
            # 速報レーンは、同じ日の同じ事故の記事を見つけてそこに足す（新しい記事にしない）
            self.assertEqual(iw.same_incident_slug(meta["incident"], articles, CFG), TODAY["slug"])

        again = sorted(state["items"])
        run_cycle(state, articles, "261116_06", datetime(2026, 11, 16, 15, 50, tzinfo=JST))
        self.assertEqual(sorted(state["items"]), again)  # 同じ一覧をもう一度読んでも増えない

    def test_notice_already_used_as_a_source_is_covered(self):
        state = {"seen": {}, "homes": {}, "items": {}}
        run_cycle(state, [*OLD, TODAY], "261116_01", datetime(2026, 11, 16, 12, 0, tzinfo=JST))
        entry = state["items"]["outage:nttドコモ@20261116"]
        self.assertEqual((entry["status"], entry["slug"]), ("covered", TODAY["slug"]))  # 話題のレーンなどが先に作っていたら作らない

    def test_same_incident_slug_ignores_other_days(self):
        inc = {"kind": "outage", "name": "NTTドコモ", "day": "20261116"}
        self.assertEqual(iw.same_incident_slug(inc, OLD, CFG), "")  # 11/11 の記事は 11/16 の事故の記事ではない
        self.assertEqual(iw.same_incident_slug(inc, [*OLD, TODAY], CFG), TODAY["slug"])
        self.assertEqual(iw.same_incident_slug({"kind": "outage", "name": "ドコモ", "day": "20261111"}, [*OLD, TODAY], CFG), "docomo-5g-sa-outage-recovery")
        self.assertEqual(iw.same_incident_slug({"kind": "breach", "name": "NTTドコモ"}, [*OLD, TODAY], CFG), "")  # 日付の無い種類は今までの判定に任せる

    def test_next_day_recovery_notice_belongs_to_the_earlier_day(self):
        state = {"seen": {}, "homes": {}, "items": {
            "outage:nttドコモ@20261106": {"key": "outage:nttドコモ@20261106", "kind": "outage", "name": "NTTドコモ", "aliases": ["ドコモ"], "day": "20261106",
                                       "status": "new", "tries": 0, "dispatches": 0, "detectedAt": "2026-11-06T00:30:00+00:00",
                                       "discoveredAt": "2026-11-06T00:20:00+00:00",
                                       "discovery": [{"source": "press", "url": "https://example.co.jp/n/9", "title": "ドコモの通信障害", "official": False}]}}}
        pages = {"https://example.co.jp/n/9": {"text": "記事", "links": [{"url": BASE + "261106_00_m.html", "text": "お知らせ"}]}, **FIX["pages"]}
        prior = article("docomo-outage-1105", "ドコモで通信障害　5G SAの通話とデータ通信に影響", BASE + "261105_02_m.html", "2026-11-05T03:00:00+00:00")
        iw.step(state, {}, [prior], lambda u: pages[u], CFG, datetime(2026, 11, 6, 9, 40, tzinfo=JST),
                notice_days={iw._url_key(BASE + "261106_00_m.html"): "20261105"})
        entry = state["items"]["outage:nttドコモ@20261106"]
        self.assertEqual((entry["day"], entry["followup"]), ("20261105", True))
        # 11/5 の事故の続き（復旧）。新しい事故の記事にはせず、速報レーンが 11/5 の記事に足す
        self.assertEqual(entry["status"], "queued")
        meta = iw.build_meta(entry, CFG, NOW)
        self.assertEqual((meta["incident"]["day"], meta["incident"]["followup"]), ("20261105", True))
        self.assertEqual(iw.same_incident_slug(meta["incident"], [prior, *OLD], CFG), "docomo-outage-1105")

    def test_fast_lane_routes_by_incident_day(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("incident_watch.same_incident_slug(inc)", src)
        self.assertIn('followup_for(same_slug, "同じ事故の続きのお知らせ")', src)
        self.assertIn('if item.get("_incident_same"):', src)
        self.assertIn('**({"day": str(inc["day"])} if inc.get("day") else {})', src)
        pick = src[src.index("def _pick("):src.index("def major_retry(")]
        # 発生日つきの事故の判定は、見出しの似た記事を探すふつうの続報・重複の判定より前にある
        self.assertLess(pick.index("incident_watch.same_incident_slug(inc)"), pick.index('followup_target(cand["title"], cand["url"])'))
        self.assertLess(pick.index('recent.has_url(cand["url"])'), pick.index("incident_watch.same_incident_slug(inc)"))


class HistoryTest(unittest.TestCase):
    """(d) 過去の障害の比較の材料"""

    URL = BASE + "261116_02_m.html"

    def test_notice_times_and_cause(self):
        facts = iw.parse_outage_notice(FIX["pages"][BASE + "261111_13_m.html"]["text"], 2026)
        self.assertEqual((facts["start"].strftime("%m-%d %H:%M"), facts["end"].strftime("%m-%d %H:%M")), ("11-11 10:34", "11-11 19:17"))
        self.assertEqual(facts["cause"], "5G SAをご契約のお客さまを収容する交換機の輻輳")
        facts = iw.parse_outage_notice(FIX["pages"][BASE + "261106_00_m.html"]["text"], 2026)
        self.assertEqual((facts["start"].strftime("%m-%d %H:%M"), facts["end"].strftime("%m-%d %H:%M"), facts["approx"]), ("11-05 11:18", "11-06 01:20", True))
        ongoing = iw.parse_outage_notice(FIX["pages"][self.URL]["text"], 2026)
        self.assertEqual((ongoing["start"].strftime("%H:%M"), ongoing["end"], ongoing["cause"]), ("10:02", None, "調査中"))
        rakuten = iw.parse_outage_notice("1. 日時\n2026年11月4日（水） 午前8時00分頃から午前8時25分頃\n2.影響エリア\n確認中\n5. 原因\n確認中\n", 2026)
        self.assertEqual((rakuten["start"].strftime("%H:%M"), rakuten["end"].strftime("%H:%M"), rakuten["cause"]), ("08:00", "08:25", "確認中"))

    def test_history_excludes_the_current_incident(self):
        now = datetime(2026, 11, 16, 12, 0, tzinfo=JST)
        cases = iw.outage_history("NTTドコモ", fetcher(), CFG, now, current_url=self.URL, day="20261116")
        self.assertEqual([c["day"] for c in cases], ["20261111", "20261105", "20261028"])
        self.assertTrue(all(c["url"].startswith(BASE) for c in cases))

    def test_block_given_to_the_writer(self):
        now = datetime(2026, 11, 16, 12, 0, tzinfo=JST)
        text = FIX["pages"][self.URL]["text"]
        block = iw.outage_context({"kind": "outage", "name": "NTTドコモ", "day": "20261116"}, self.URL, text, fetcher(), CFG, now)
        self.assertIn("11月11日午前10時34分に発生 → 11月11日午後7時17分に復旧", block)
        self.assertIn("8時間43分", block)
        self.assertIn("約14時間2分", block)  # 11/5 午前11時18分頃 → 11/6 午前1時20分頃
        self.assertIn("公式が発表した原因: 5G SAをご契約のお客さまを収容する交換機の輻輳", block)
        self.assertIn("復旧のお知らせの時点では「確認中」", block)  # 原因が出ていない過去の障害は、そのとおりに
        self.assertIn(BASE + "261111_13_m.html", block)
        self.assertIn("今回の障害の原因・復旧の見込みではない", block)
        self.assertIn("輻輳（ふくそう）", block)
        self.assertIn("5G SA（スタンドアローン）", block)
        self.assertNotIn("261116", block)  # 今回の事故は「過去」に入れない
        self.assertGreaterEqual(len(FIX["pages"][BASE + "261116_00_m.html"]["text"] + "\n\n" + block), iw.OUTAGE_SOURCE_FLOOR)
        self.assertEqual(iw.outage_context({"kind": "breach", "name": "NTTドコモ"}, self.URL, text, fetcher(), CFG, now), "")

    def test_unreadable_list_does_not_stop_the_article(self):
        def broken(url):
            raise RuntimeError("timeout")
        block = iw.outage_context({"kind": "outage", "name": "NTTドコモ", "day": "20261116"}, self.URL, "5G SAの障害", broken, CFG, NOW)
        self.assertNotIn("同じ会社の過去の障害", block)
        self.assertIn("言葉の説明", block)  # 言葉の説明だけは渡す

    def test_writer_rules(self):
        note = iw.prompt_note({"kind": "outage", "name": "NTTドコモ"})
        for phrase in ["過去の障害との比較の表", "仕組み", "今やること", "復旧までにかかった時間", "過去の原因を今回の原因として書かない", "調査中"]:
            self.assertIn(phrase, note)
        self.assertNotIn("過去の障害との比較の表", iw.prompt_note({"kind": "breach", "name": "X"}))
        self.assertEqual(iw.prompt_note(None), "")
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn('incident_watch.outage_context(item["_incident"], item["url"], text)', src)
        body = src[src.index("def process_web("):]
        self.assertLess(body.index("incident_watch.outage_context("), body.index("if len(text) < MIN_TEXT_CHARS:"))  # 資料の長さを確かめる前に足す


class WiringTest(unittest.TestCase):
    def test_watch_reads_the_carrier_pages_every_run(self):
        src = (ROOT / "scripts" / "incident_watch.py").read_text("utf-8")
        run = src[src.index("def run(args)"):]
        self.assertIn("gather_notices(cfg, _fetch_page, now)", run)
        self.assertIn("notice_days=notice_days", run)
        self.assertIn("open_days_of(state)", run)

    def test_rule_is_in_the_ledger(self):
        ledger = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        self.assertIn("| W45 |", ledger)
        self.assertIn("tests/test_incident_repeat_outage_20261116.py", ledger)


if __name__ == "__main__":
    unittest.main()
