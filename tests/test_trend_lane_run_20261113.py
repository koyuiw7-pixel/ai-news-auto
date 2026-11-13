"""話題のレーンを、記事づくりの本体（web_articles.main）ごと動かして確かめる（2026-11-13）。
通信・LLM・書き込みは全部作りもの。確かめること:
  - 公式のフィードに発表がある言葉 → 公式が出典の記事（trendKeyword・trendLane の印。1日の上限に数えない）
  - 公式が無く、主要な報道機関の独立した2社が同じ事実を伝えている言葉 → 報道と明記した短い記事（pressReport・awaitingOfficial）
  - 1社しか無い言葉・別の話題の2社 → 作らない（次の回にもう一度だけ探す）
  - 扱わない話題（事件）→ 作らない"""
import contextlib
import io
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dedupe  # noqa: E402
import facts_bundle  # noqa: E402
import public_interest as pi  # noqa: E402
import trend_lane as tl  # noqa: E402
import web_articles as w  # noqa: E402

NOW = datetime.now(timezone.utc)
NHK_URL, ASAHI_URL, MAINICHI_URL = "https://news.web.nhk/newsweb/na/nd-1", "https://www.asahi.com/articles/A1.html", "https://mainichi.jp/articles/x"
PAGES = {
    NHK_URL: "NTTドコモによると、13日午後2時ごろから全国で音声通話とデータ通信がつながりにくくなっている。影響は約120万人。" + "復旧の見通しは立っていない。" * 40,
    ASAHI_URL: "NTTドコモは13日、午後2時ごろから通信障害が起きていると明らかにした。約120万人に影響が出ている。" + "原因は調査中という。" * 40,
    MAINICHI_URL: "大相撲九州場所は13日、福岡国際センターで行われ、熱海富士が4連勝とした。" * 20,
}
INDEX = [
    {"title": "ドコモで通信障害 全国でつながりにくい状態", "url": NHK_URL, "source": "NHK", "published": None},
    {"title": "NTTドコモ、通信障害が発生　音声通話とデータ通信に影響", "url": ASAHI_URL, "source": "朝日新聞", "published": None},
    {"title": "熱海富士が4連勝　大相撲九州場所", "url": MAINICHI_URL, "source": "毎日新聞", "published": None},
]


def queue_item(qid, title, genre="public", traffic=1000, sources=()):
    return {"id": qid, "kind": "trend", "url": "https://news.google.com/x", "title": title, "summary": "Googleトレンド急上昇",
            "published_at": NOW - timedelta(hours=1), "source_name": "Googleトレンド", "source_slug": "trends", "lang": "ja",
            "genre": genre, "sources": list(sources), "traffic": traffic}


def llm_data(title, body):
    return {"is_relevant": True, "title": title, "seo_title": title[:28], "threads_post": "", "lede": body[:60], "description": "説明" * 40,
            "keywords": ["ドコモ", "通信障害"], "tags": ["ドコモ"], "highlights": ["a" * 45, "b" * 45, "c" * 45], "timetable": [], "verdict": None,
            "body_markdown": body, "easy_markdown": "## かんたんに\n\nやさしい説明です。", "slug_en": "docomo-outage-report", "genre": "public",
            "mentioned_tools": [], "faq": [], "today_actions": []}


class FakeStory:
    stories: list = []

    def __init__(self, *_a, **_k):
        pass

    def match(self, *_a, **_k):
        return None

    def add(self, *_a, **_k):
        return None


class FakeArchive:
    rows: list = []

    def related(self, *_a, **_k):
        return []


class TrendLaneRunTest(unittest.TestCase):
    def run_main(self, queue, pool=(), generated=None, argv=("--trends", "3")):
        state = {"processed_web": {}, "failed_web": {}, "major_tries": {}}
        written, removed, prompts = [], [], []

        def fake_fetch_sources(item):
            return [{**s, "text": PAGES[s["url"]], "image": None, "links": [], "page_title": s.get("title", "")}
                    for s in item.get("sources") or [] if s.get("url") in PAGES]

        def fake_generate(system, prompt, schema, **_kw):
            prompts.append(prompt)
            return (generated or llm_data("ドコモで通信障害とNHKなど報道　復旧の見通しは",
                                          "NHKなどが報じた。NHKによると、13日午後2時ごろから全国でつながりにくくなっている。\n\n## まだ分かっていないこと\n\n"
                                          "公式の発表はまだ確認できていない。")), "stub-model"

        def fake_write(record):
            written.append(record)
            return w.m.ROOT / "content" / "articles" / f"{record['slug']}.json"

        def fake_compose(item, text, lane, related, voice_text, page=None, **_kw):
            return w.GENRES_BY_SLUG[lane], "system", "prompt", w.TREND_SCHEMA, "broad", "", facts_bundle.Bundle()

        patches = [
            mock.patch.object(sys, "argv", ["web_articles.py", *argv, "--max", "0", "--max-broad", "0", "--max-major", "0", "--max-updates", "0",
                                             "--daily-cap", "30"]),
            mock.patch.object(w.llm, "_load_env_local", lambda: None),
            mock.patch.object(w.m, "load_state", lambda: state),
            mock.patch.object(w.m, "save_state", lambda _s: None),
            mock.patch.object(w.m, "write_article", fake_write),
            mock.patch.object(w.pipeline_health, "load", lambda: {}),
            mock.patch.object(w.pipeline_health, "record", lambda *a, **k: {}),
            mock.patch.object(w.dedupe, "load_recent", lambda *a, **k: dedupe.Index()),
            mock.patch.object(w.story, "Recent", FakeStory),
            mock.patch.object(w.archive, "Archive", FakeArchive),
            mock.patch.object(w.trends, "load_queue", lambda: list(queue)),
            mock.patch.object(w.trends, "remove_from_queue", lambda ids: removed.extend(sorted(ids))),
            mock.patch.object(w.public_interest, "load_signals", lambda *a, **k: []),
            mock.patch.object(w.feeds, "collect", lambda *a, **k: [dict(i) for i in pool]),
            mock.patch.object(w.feeds, "fetch_article_text", lambda url: {"text": "NTTドコモの通信サービスで障害が発生しています。" * 60, "image": None,
                                                                           "title": "通信障害について", "links": []}),
            mock.patch.object(w.trend_lane, "covered_terms", lambda *a, **k: {}),
            mock.patch.object(w.trend_lane, "awaiting_official", lambda *a, **k: []),
            mock.patch.object(w.trend_lane, "press_index", lambda *a, **k: list(INDEX)),
            mock.patch.object(w, "fetch_trend_sources", fake_fetch_sources),
            mock.patch.object(w, "compose_with_facts", fake_compose),
            mock.patch.object(w, "fill_faq_actions", lambda *a, **k: []),
            mock.patch.object(w, "attach_rivals", lambda *a, **k: None),
            mock.patch.object(w, "attach_charts", lambda record: record),
            mock.patch.object(w, "finalize_facts", lambda record, text: record),
            mock.patch.object(w.quality, "pre_gate_repair", lambda *a, **k: None),
            mock.patch.object(w.quality, "evaluate", lambda *a, **k: {"ok": True, "score": 95, "problems": [], "readability": {}}),
            mock.patch.object(w.own_view, "ensure", lambda *a, **k: []),
            mock.patch.object(w.own_view, "hold_reason", lambda *a, **k: None),
            mock.patch.object(w.quality_bar, "ensure", lambda *a, **k: []),
            mock.patch.object(w.quality_bar, "hold_reason", lambda *a, **k: None),
            mock.patch.object(w.llm, "generate_json", fake_generate),
            mock.patch.object(w.llm, "all_exhausted", lambda *a, **k: False),
            mock.patch.object(w.llm, "api_block_reason", lambda *a, **k: None),
            mock.patch.object(w.llm, "run_cost_mark", lambda: (0.0, 0)),
            mock.patch.object(w.llm, "cost_since", lambda _m: (0.0, "")),
            mock.patch.object(w.llm, "usage_today", lambda: {}),
            mock.patch.object(w.fast_lane, "fast_waiting", lambda *a, **k: False),
            mock.patch.dict("os.environ", {"GITHUB_OUTPUT": ""}),
        ]
        out = io.StringIO()
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with contextlib.redirect_stdout(out):
                self.assertEqual(w.main(), 0)
        return state, written, removed, out.getvalue(), prompts

    def test_press_article_from_two_independent_outlets(self):
        queue = [queue_item("q-docomo", "ドコモ 障害", traffic=9000,
                            sources=[{"title": "ドコモ障害", "url": "https://news.yahoo.co.jp/articles/1", "source": "Yahoo!ニュース"}]),
                 queue_item("q-sumo", "熱海富士", genre="sports", traffic=5000),
                 queue_item("q-crime", "鈴木容疑者", traffic=4000)]
        state, written, removed, log, prompts = self.run_main(queue)
        self.assertEqual(len(written), 1, log)
        rec = written[0]
        self.assertEqual((rec["channelSlug"], rec["trendKeyword"], rec["pressReport"], rec["awaitingOfficial"]), ("trends", "ドコモ 障害", True, True))
        self.assertEqual([pi.press_outlet(s["url"]) for s in rec["sources"]], ["NHK", "朝日新聞"])  # Yahoo!ニュースは出典にならない
        self.assertEqual(pi.press_source_problems(rec), [])
        self.assertIn("公式の発表はまだ確認できていません", rec["disclaimer"])
        self.assertNotIn("｜", rec["title"])
        self.assertNotIn("indexable", rec)  # 既定は検索に出す（TREND_PRESS_NOINDEX=1 で出さない）
        # 指示文に、報道の書き方・題名の書き方・分野で落とさない決まりが入っている
        self.assertIn("NHKなどが報じた", prompts[0])
        self.assertIn("題名の書き方（話題のレーン", prompts[0])
        self.assertIn("分野を理由に対象外にしない", prompts[0])
        # 記録: 話題のレーンの印（1日の上限に数えない）
        done = state["processed_web"]["q-docomo"]
        self.assertTrue(done["trendLane"] and done["pressReport"] and done["slug"] == rec["slug"])
        self.assertEqual(tl.done_today(state), 1)
        # 1社しか無い話題は作らず、もう一度だけ探す（processed にしない）。扱わない話題は見送りで確定
        self.assertNotIn("q-sumo", state["processed_web"])
        self.assertEqual(state["failed_web"].get("q-sumo"), 1)
        self.assertIn("扱わない話題", state["processed_web"]["q-crime"]["reason"])
        self.assertIn("q-docomo", removed)
        self.assertIn("[trend] まとめ: キュー 3 語 / 調べた 3 語 → 記事 1 本（公式が出典 0 / 主要な報道機関2社以上 1）", log)

    def test_press_article_that_states_report_as_fact_is_not_published(self):
        queue = [queue_item("q-docomo", "ドコモ 障害", traffic=9000)]
        bad = llm_data("ドコモで通信障害　全国でつながらない", "ドコモで通信障害が起きている。全国でつながりにくい。")  # 報道と書かず、題名で言い切る
        state, written, _removed, log, _p = self.run_main(queue, generated=bad)
        self.assertEqual(written, [], log)
        self.assertTrue(state["processed_web"]["q-docomo"]["skipped"])

    def test_official_feed_candidate_is_used_first(self):
        queue = [queue_item("q-docomo", "ドコモ 障害", traffic=9000)]
        pool = [{"id": "feed-1", "url": "https://www.docomo.ne.jp/info/network/kanto/pages/261113_00.html",
                 "title": "ドコモ、通信障害の発生について（第2報）", "summary": "", "content": "", "published_at": NOW - timedelta(hours=1),
                 "source_name": "NTTドコモ", "source_slug": "docomo-notice", "lang": "ja", "image": None, "priority": 1}]
        official = llm_data("ドコモの通信障害、復旧の見通しと自分の回線の確かめ方", "NTTドコモは13日、通信障害が発生したと発表した。\n\n## 対象\n\n全国の回線。")
        wire = {**pool[0], "id": "wire-1", "url": "https://prtimes.jp/main/html/rd/p/1.html", "source_slug": "prtimes",
                "title": "ドコモの通信障害に備える新サービス", "source_name": "PR TIMES"}  # 配信は公式の候補にしない
        state, written, removed, log, prompts = self.run_main(queue, pool=[wire, *pool], generated=official)
        self.assertEqual(len(written), 1, log)
        rec = written[0]
        self.assertEqual((rec["sourceUrl"], rec["channelSlug"], rec["trendKeyword"], rec["searchTrend"]),
                         (pool[0]["url"], "docomo-notice", "ドコモ 障害", "ドコモ 障害"))
        self.assertNotIn("pressReport", rec)            # 公式が出典。報道の印は付かない
        self.assertEqual(pi.press_source_problems(rec), [])
        done = state["processed_web"]["feed-1"]
        self.assertTrue(done["trendLane"] and done["kind"] == "trend" and not done["mix"])  # 1日の上限・種類別の配分に数えない
        self.assertIn("公式の発表で記事にした", state["processed_web"]["q-docomo"]["reason"])
        self.assertEqual(tl.done_today(state), 1)
        self.assertEqual(w.pacing.live_today(state, articles_dir=ROOT / "tests"), 0)
        self.assertIn("→ 記事 1 本（公式が出典 1 / 主要な報道機関2社以上 0）", log)

    def test_press_only_switch_and_daily_cap(self):
        queue = [queue_item("q-docomo", "ドコモ 障害", traffic=9000)]
        with mock.patch.object(w, "TREND_FROM_PRESS", False):
            state, written, _r, log, _p = self.run_main(queue)
        self.assertEqual(written, [], log)
        self.assertIn("報道だけの話題は作らない設定", log)
        with mock.patch.object(w, "TREND_PRESS_NOINDEX", True):
            state, written, _r, log, _p = self.run_main(queue)
        self.assertIs(written[0]["indexable"], False)
        with mock.patch.object(w.trend_lane, "done_today", lambda *_a, **_k: w.ramp.TREND_DAILY_CAP):
            state, written, _r, log, _p = self.run_main(queue)
        self.assertEqual(written, [], log)
        self.assertIn("この回 0 本まで", log)


if __name__ == "__main__":
    unittest.main()
