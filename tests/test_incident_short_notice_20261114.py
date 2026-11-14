"""事故の見張り（scripts/incident_watch.py・台帳 W44）の記事だけ、短い公式のお知らせから書けるようにする（2026-11-14 オーナー承認）。

モンテールの回収（公式のお知らせ 938字）と東京ガスの情報流出（1,098字）が、公共性の枠の資料の下限（1,200字）で書けなかった。
回収・流出のお知らせは短くても対象（製品・ロット）・窓口・やることがそろっている。ここでは次を確かめる（ネットには出ない）:
  - 事故の見張りの経路だけ、公式の資料は 700字から（scripts/incident_watch.json の min_source_chars）、記事の本文は 800字から
  - ほかの経路は今までどおり（資料 1,200字・本文 1,500字／速報などは 800字）
  - 起こす前の確かめ（6fa0fd4d）も速報レーンも同じ下限（incident_watch.source_floor）を使う
  - 書き方: 対象の表・窓口・今やることは必ず。数字は公式の資料だけ。水増ししない
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import incident_watch as iw  # noqa: E402
import indexnow  # noqa: E402
import public_interest  # noqa: E402
import retire_articles  # noqa: E402
import web_articles  # noqa: E402

NOW = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)
CFG = iw.CONFIG
HEAD = ("商品の回収に関するお詫びとお知らせ\n2026年11月9日\n株式会社モンテール\n"
        "当社が製造した一部の商品に、表示に無いアレルゲンが含まれていることが分かったため、対象の商品を自主回収いたします。")


def notice(chars: int) -> str:
    return (HEAD + "対象の商品と賞味期限、お問い合わせ窓口は次のとおりです。" * 60)[:chars]


def page(text="", links=None):
    return {"text": text, "links": links or [], "title": "", "published": ""}


def body(chars: int) -> str:
    text = "## 対象の商品\n\n| 商品 | 賞味期限 |\n|---|---|\n| シュークリーム | 11月12日 |\n\n## 日本の窓口と今やること\n\n"
    return (text + "対象の商品は食べずに、お客様相談室へ連絡してください。" * 80)[:chars]


def record(chars: int, **extra) -> dict:
    return {"slug": "x", "sourceType": "web", "channelSlug": "official", "genreSlug": "lifestyle",
            "title": "モンテールがシュークリームを自主回収　対象の賞味期限と返金の窓口", "body": body(chars), "verdict": None, **extra}


INCIDENT = {"key": "recall:モンテール", "kind": "recall", "name": "モンテール"}


class SourceFloorTest(unittest.TestCase):
    def test_config_sets_700_for_the_incident_lane(self):
        self.assertEqual(CFG["min_source_chars"], 700)
        self.assertEqual(iw.source_floor("recall"), 700)
        self.assertEqual(iw.source_floor("breach"), 700)
        self.assertEqual(iw.source_floor("outage"), web_articles.MIN_TEXT_CHARS)  # 障害は今までどおり

    def test_other_lanes_keep_1200(self):
        self.assertEqual(public_interest.MIN_SOURCE_CHARS, 1200)
        self.assertTrue(public_interest.source_too_short("recall", notice(938)))
        self.assertTrue(public_interest.source_too_short("breach", notice(1098)))

    def test_missing_or_larger_setting_falls_back_to_the_public_interest_floor(self):
        for cfg in ({}, {"min_source_chars": 0}, {"min_source_chars": "x"}, {"min_source_chars": 5000}):
            self.assertEqual(iw.source_floor("recall", cfg), public_interest.MIN_SOURCE_CHARS, cfg)
        self.assertEqual(iw.source_floor("recall", {"min_source_chars": 900}), 900)

    def step(self, chars: int) -> dict:
        url = "https://www.monteur.co.jp/information/4189"
        hit = {"key": "recall:モンテール", "kind": "recall", "name": "モンテール", "aliases": [], "scale": 0, "scaleText": "",
               "title": "モンテール（取りこぼしの拾い直し）", "home": "", "official": url, "backfill": True, "majorOnly": False, "discovery": []}
        state = {"items": {}, "seen": {}}
        iw.step(state, {hit["key"]: hit}, [], lambda u: {url: page(notice(chars))}[u], CFG, NOW)
        return state["items"][hit["key"]]

    def test_precheck_lets_a_938_char_recall_notice_through(self):
        entry = self.step(938)
        self.assertEqual(entry["status"], "queued", entry.get("reason"))
        self.assertEqual(iw.build_meta(entry, CFG, NOW)["incident"]["kind"], "recall")

    def test_precheck_still_stops_notices_under_700(self):
        entry = self.step(690)
        self.assertEqual(entry["status"], "skipped")
        self.assertIn("下限 700字", entry["reason"])

    def test_fast_lane_uses_the_same_floor_only_for_incident_items(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn('incident_watch.source_floor(item["_incident"].get("kind") or "") if item.get("_incident")', src)
        self.assertIn("else public_interest.MIN_SOURCE_CHARS)", src)
        self.assertIn('public_interest.source_too_short(item["_public_interest"], text) and len(text) < source_floor', src)

    def test_backfill_retries_the_two_blocked_incidents(self):
        rows = {b["name"]: b for b in CFG["backfill"]}
        self.assertEqual(rows["モンテール"]["kind"], "recall")
        self.assertEqual(rows["東京ガス"]["official"], "https://www.tokyo-gas.co.jp/news/press/20261112-02.html")
        self.assertTrue(iw.official_candidate(rows["東京ガス"]["official"]))


class BodyFloorTest(unittest.TestCase):
    def test_incident_article_publishes_from_800(self):
        r = record(900, incident=INCIDENT)
        self.assertTrue(public_interest.short_ok(r))
        self.assertIsNone(indexnow.focus_reason(r))
        self.assertIsNone(indexnow.publish_block_reason(r))
        self.assertFalse(retire_articles.is_thin(r))

    def test_incident_article_under_800_is_still_thin(self):
        self.assertEqual(indexnow.focus_reason(record(790, incident=INCIDENT)), "thin")

    def test_same_article_without_the_mark_keeps_1500(self):
        for extra in ({}, {"incident": None}, {"incident": {}}, {"incident": {"key": "k"}}, {"publicInterest": "recall"}):
            r = record(900, **extra)
            self.assertFalse(public_interest.short_ok(r), extra)
            self.assertEqual(indexnow.focus_reason(r), "thin", extra)
        self.assertEqual((indexnow.THIN_BODY, public_interest.SHORT_BODY), (1500, 800))

    def test_only_the_fast_lane_sets_the_mark_from_the_watch_request(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertEqual(src.count('rec["incident"] ='), 1)
        self.assertIn('if incident and not incident_watch.official_candidate(url):', src)  # 報道・まとめの URL には印を付けない


class PromptTest(unittest.TestCase):
    def test_short_notice_is_written_without_padding(self):
        note = iw.prompt_note(INCIDENT)
        for word in ["対象の条件の表", "連絡の届き方・窓口", "今やること", "公式の資料に書かれた数字だけ", "800字以上",
                     "資料に無い背景や数字", "対象の表・窓口・今やること"]:
            self.assertIn(word, note)


if __name__ == "__main__":
    unittest.main()
