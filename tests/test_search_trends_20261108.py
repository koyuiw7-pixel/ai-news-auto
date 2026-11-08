"""2026-11-08 オーナー（台帳 A63）: いま日本で検索されている暮らしとお金の話題を、公式の一次情報に当てて早く記事にする。

- Googleトレンドを約20分おき（記事づくりの回）＋30分おきの予約で集める
- 地震・停電・運休・情報流出・値上げ・宝くじなどの暮らしの話題を軸に入れる。芸能のうわさ・事件（犯罪）は除外のまま
- 「ドコモ 情報流出 確認方法」のような複数の語の検索も、公式の題名と発信元に語ごとに当てる
- 当たった記事は検索の言葉を題名に使い、すぐデプロイして Google ニュースのサイトマップに載せる
通信しない・API を使わない。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import public_interest as pi  # noqa: E402
import trends  # noqa: E402


def classify(keyword: str, titles: list[str]):
    return trends.classify({"title": keyword, "news": [{"title": t} for t in titles]})


class LifeAxisTest(unittest.TestCase):
    def test_safety_and_money_topics_are_kept(self):
        cases = [
            ("地震 南海トラフ", ["南海トラフ地震臨時情報の発表基準は"], "public"),
            ("停電", ["台風で停電、男性死亡", "停電で1人死亡", "停電の復旧見通し 死亡事故も"], "public"),
            ("大和路線", ["大和路線で人身事故 運転見合わせ", "JR大和路線 事故で遅れ", "大和路線が運転再開 事故の影響"], "public"),
            ("ドコモ 情報流出", ["ドコモ、顧客情報流出の可能性"], "public"),
            ("年末ジャンボ", ["年末ジャンボ宝くじ、発売開始"], "lifestyle"),
            ("コストコ スイーツ", ["コストコの新作スイーツ、価格は1,298円"], "lifestyle"),
        ]
        for kw, titles, want in cases:
            self.assertEqual(classify(kw, titles), want, kw)

    def test_gossip_and_crime_stay_out(self):
        self.assertIsNone(classify("maruzen&ジュンク堂書店梅田店", ["書店で男性が刺され", "男を逮捕", "容疑者を逮捕"]))
        self.assertIsNone(classify("馬場 徹", ["俳優の馬場徹さん出演", "ドラマに出演"]))
        self.assertIsNone(classify("宇賀なつみ", ["宇賀なつみアナが近況"]))
        # 安全の語があっても、見出しの半数以上が犯罪そのものなら落とす
        self.assertIsNone(classify("停電", ["停電中に強盗", "強盗の容疑者を逮捕", "容疑者を逮捕"]))

    def test_old_selftest_still_passes(self):
        self.assertEqual(trends._selftest(), 0)

    def test_signals_keep_axis_and_gossip_flag(self):
        raw = [
            {"title": "停電", "traffic": 200, "news": [{"title": "停電の復旧見通し"}]},
            {"title": "馬場 徹", "traffic": 1000, "news": [{"title": "俳優が出演"}, {"title": "ドラマに出演"}]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trend_signals.json"
            trends.save_signals(raw, path)
            items = {i["title"]: i for i in json.loads(path.read_text("utf-8"))["items"]}
            self.assertEqual(items["停電"]["axis"], "public")
            self.assertFalse(items["停電"]["gossip"])
            self.assertTrue(items["馬場 徹"]["gossip"])
            # 芸能のうわさは公式の候補の順番を上げる合図に使わない
            self.assertEqual([s["title"] for s in pi.load_signals(path)], ["停電"])


class TrendHitTest(unittest.TestCase):
    SIGNALS = [{"title": "ドコモ 情報流出 確認方法"}, {"title": "知多市 土砂災害"}, {"title": "jma"}]

    def test_multi_word_queries_match_official_titles(self):
        hit = pi.trend_hit("不正アクセスによるお客さま情報の流出について", self.SIGNALS, "NTTドコモ 重要なお知らせ")
        self.assertEqual((hit or {}).get("title"), "ドコモ 情報流出 確認方法")
        hit = pi.trend_hit("知多市の土砂災害警戒情報の発表基準を引き下げ", self.SIGNALS, "気象庁 報道発表")
        self.assertEqual((hit or {}).get("title"), "知多市 土砂災害")
        hit = pi.trend_hit("【地震】静岡県西部で最大震度5強、M5.7（気象庁）", self.SIGNALS)
        self.assertEqual((hit or {}).get("title"), "jma")

    def test_unrelated_titles_do_not_match(self):
        self.assertIsNone(pi.trend_hit("ドコモ、新しい料金プランを発表", self.SIGNALS, "NTTドコモ"))
        # 発信元の名前だけで当たる（題名に語が1つも無い）ものは数えない
        self.assertIsNone(pi.trend_hit("年末年始の営業時間のお知らせ", [{"title": "ドコモ"}], "NTTドコモ"))

    def test_old_exact_match_still_works(self):
        self.assertEqual(pi.trend_hit("ビックカメラの不正アクセス", [{"title": "ビックカメラ"}])["title"], "ビックカメラ")

    def test_query_terms_drop_how_to_words(self):
        self.assertEqual(pi.query_terms("ドコモ 情報流出 確認方法"), ["ドコモ", "情報流出"])
        self.assertEqual(pi.query_terms("熊本地震 2026"), ["熊本地震"])

    def test_title_note_uses_search_words_without_bar(self):
        note = pi.search_title_note("ドコモ 情報流出 確認方法")
        self.assertIn("ドコモ 情報流出 確認方法", note)
        self.assertIn("うそをつかない", note)
        self.assertNotIn("｜", note.replace("「｜」", ""))


class WiringTest(unittest.TestCase):
    def test_trends_are_collected_in_every_article_run(self):
        auto = (ROOT / ".github/workflows/auto_run.yml").read_text("utf-8")
        self.assertIn("python scripts/trends.py --enqueue", auto)
        self.assertIn("git add state/trend_signals.json", auto)
        # 検索で急上昇している話題の記事は待たずにデプロイ（Google ニュースのサイトマップ・IndexNow へすぐ）
        self.assertIn(".searchTrend", auto)
        collect = (ROOT / ".github/workflows/trends_collect.yml").read_text("utf-8")
        self.assertIn('cron: "17,47 * * * *"', collect)

    def test_web_articles_marks_and_prompts(self):
        src = (ROOT / "scripts/web_articles.py").read_text("utf-8")
        self.assertIn('rec["searchTrend"] = item["_trend_hit"]', src)
        self.assertIn("public_interest.search_title_note(item[\"_trend_hit\"])", src)
        # 新しい軸は「大きなニュース」（1日の上限の外）にしない＝今日の段の本数の内側で先に回すだけ
        self.assertIn('q.get("genre") in (None, "ai", "investment", "real-estate")', src)

    def test_ledger_entry(self):
        ledger = (ROOT / "docs/owner_rules.md").read_text("utf-8")
        self.assertIn("| A63 |", ledger)


if __name__ == "__main__":
    unittest.main()
