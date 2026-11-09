"""2026-11-10 オーナー承認（台帳 A70）: 読まれた記事を夜に深掘りする・夜の穴埋めのガイドは手続きを先に・無料の取得の経路を主にする。
外部への通信なし（記事・ページは手元の例）。"""

import json
import re
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import deep_dive  # noqa: E402
import evergreen  # noqa: E402
import feeds  # noqa: E402
import pacing  # noqa: E402

JST = timezone(timedelta(hours=9))


def art(slug, genre="public", title="児童手当の第3子は月3万円", url="https://www.cfa.go.jp/a", **extra):
    return {"slug": slug, "genreSlug": genre, "title": title, "sourceUrl": url, **extra}


RICH = ("対象 該当 確認 条件 要件 家族 配偶者 子ども 扶養 世帯 申請 手続 届出 窓口 必要書類 期限 "
        "Q&A よくある 注意 場合 1万円 2万円 3万円 10% 5日 6か月 7年 8件 9時間")


class PickBasesTest(unittest.TestCase):
    def test_same_story_is_one_base_and_views_add_up(self):
        articles = {
            "docomo-a": art("docomo-a", "business", "ドコモ流出 対象の確かめ方", "https://www.docomo.ne.jp/n1"),
            "docomo-b": art("docomo-b", "business", "ドコモ流出 今やること", "https://www.ntt.com/x",
                            museSources=[{"url": "https://www.docomo.ne.jp/n1"}]),
            "kids": art("kids"),
        }
        popular = {"items": [{"slug": "docomo-a", "views": 60}, {"slug": "docomo-b", "views": 50}, {"slug": "kids", "views": 46}]}
        bases = deep_dive.pick_bases(popular, articles)
        self.assertEqual([(b["slug"], n) for b, n in bases], [("docomo-a", 110), ("kids", 46)])
        self.assertEqual(bases[0][0]["_siblings"], ["docomo-b"])

    def test_off_axis_and_unread_articles_are_skipped(self):
        articles = {"ai": art("ai", "ai", url="https://x/1"), "sport": art("sport", "sports", url="https://x/2"),
                    "few": art("few", url="https://x/3"), "ok": art("ok", url="https://x/4")}
        popular = {"items": [{"slug": "ai", "views": 99}, {"slug": "sport", "views": 50}, {"slug": "few", "views": 2},
                             {"slug": "ok", "views": 9}]}
        self.assertEqual([b["slug"] for b, _ in deep_dive.pick_bases(popular, articles)], ["ok"])

    def test_hit_angle_article_points_back_to_its_base(self):
        articles = {"base": art("base"), "child": art("child", angleOf="base", deepDive="family", url="https://x/9")}
        bases = deep_dive.pick_bases({"items": [{"slug": "child", "views": 30}]}, articles)
        self.assertEqual([b["slug"] for b, _ in bases], ["base"])


class PlanTest(unittest.TestCase):
    def test_only_supported_new_angles_round_robin(self):
        a = art("a", title="児童手当の第3子は月3万円", url="https://x/a")
        b = art("b", title="年金生活者支援給付金の対象は前年の所得で決まる", url="https://x/b")
        articles = {"a": a, "b": b, "a-fam": art("a-fam", angleOf="a", deepDive="family", url="https://x/c")}
        todo = deep_dive.plan([(a, 50), (b, 20)], articles, {"attempts": {}}, {"a": RICH, "b": RICH})
        keys = [(x["slug"], y["key"]) for x, y in todo]
        self.assertNotIn(("a", "family"), keys)  # すでにある型は作らない
        self.assertNotIn(("b", "check"), keys)  # 題名がすでに「対象」に答えている
        self.assertEqual(keys[0][0], "a")
        self.assertEqual(keys[1][0], "b")  # 元記事を交互に回す
        self.assertLessEqual(sum(1 for s, _ in keys if s == "a"), deep_dive.ANGLES_PER_BASE - 1)

    def test_thin_sources_make_no_angles(self):
        a = art("a")
        self.assertEqual(deep_dive.plan([(a, 50)], {"a": a}, {"attempts": {}}, {"a": "お知らせです。"}), [])

    def test_recent_rejection_waits_and_published_never_repeats(self):
        now = datetime.now(timezone.utc)
        state = {"attempts": {"a|qa": {"status": "rejected", "at": now.isoformat()},
                              "a|check": {"status": "published", "at": (now - timedelta(days=9)).isoformat()},
                              "a|family": {"status": "rejected", "at": (now - timedelta(days=4)).isoformat()}}}
        self.assertTrue(deep_dive.blocked_attempt(state, "a", "qa"))
        self.assertTrue(deep_dive.blocked_attempt(state, "a", "check"))
        self.assertIsNone(deep_dive.blocked_attempt(state, "a", "family"))

    def test_sources_drop_press_and_rss(self):
        base = art("a", url="https://www.cfa.go.jp/a", museSources=[{"url": "https://www.nikkei.com/article/x"},
                                                                      {"url": "https://www.docomo.ne.jp/info/rss/notice.rdf"},
                                                                      {"url": "http://old.example.go.jp/"}],
                   officialDesk=[{"url": "https://www.cfa.go.jp/a/"}, {"url": "https://www.cfa.go.jp/desk"}])
        self.assertEqual([s["url"] for s in deep_dive.source_urls(base)], ["https://www.cfa.go.jp/a", "https://www.cfa.go.jp/desk"])


class RecordTest(unittest.TestCase):
    def test_base_link_is_kept(self):
        record = {"body": "本文です。", "relatedSlugs": ["x"]}
        deep_dive.ensure_base_link(record, {"slug": "base", "title": "元の記事"})
        self.assertIn("(/articles/base)", record["body"])
        self.assertEqual(record["relatedSlugs"][0], "base")
        before = record["body"]
        deep_dive.ensure_base_link(record, {"slug": "base", "title": "元の記事"})
        self.assertEqual(record["body"], before)

    def test_counts_toward_todays_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "deep-slug.json").write_text("{}", "utf-8")
            state = {"processed_web": {}}
            deep_dive.register_today(state, {"slug": "base"}, deep_dive.ANGLE_BY_KEY["procedure"],
                                     {"slug": "deep-slug", "title": "児童手当の申請の手順", "qualityScore": 90})
            self.assertEqual(pacing.live_today(state, articles_dir=Path(tmp)), 1)
            entry = next(iter(state["processed_web"].values()))
            self.assertEqual((entry["writer"], entry["angleOf"], entry["deepDive"]), ("deep_dive", "base", "procedure"))

    def test_daily_cap_counts_only_today(self):
        now = datetime.now(timezone.utc)
        state = {"attempts": {"a|qa": {"status": "published", "at": now.isoformat()},
                              "b|qa": {"status": "published", "at": (now - timedelta(days=2)).isoformat()},
                              "c|qa": {"status": "rejected", "at": now.isoformat()}}}
        self.assertEqual(deep_dive.made_today(state), 1)

    def test_angles_ask_for_skip_when_sources_lack_answers(self):
        self.assertIn("is_relevant を false", deep_dive.DEEP_NOTE)
        self.assertEqual({a["key"] for a in deep_dive.ANGLES}, {"check", "family", "procedure", "qa", "compare"})
        self.assertGreaterEqual(deep_dive.PASS_SCORE, 80)  # 門は緩めない（Muse と同じ）


class WorkflowTest(unittest.TestCase):
    def test_runs_through_the_night_and_twice_by_day(self):
        wf = (ROOT / ".github" / "workflows" / "deep_dive.yml").read_text("utf-8")
        cron = re.search(r'cron: "(\d+) ([^ ]+) \* \* \*"', wf).group(2)
        hours = set()
        for part in cron.split(","):
            lo, _, hi = part.partition("-")
            hours |= set(range(int(lo), int(hi or lo) + 1))
        jst = {(h + 9) % 24 for h in hours}
        self.assertTrue(set(range(20, 24)) | set(range(0, 9)) <= jst, sorted(jst))
        self.assertTrue({12, 16} <= jst)
        self.assertIn("scripts/deep_dive.py", wf)
        self.assertIn("git_safe_push.py", wf)
        self.assertIn("FETCH_CACHE_DIR", wf)

    def test_rescue_asks_for_procedure_guides(self):
        wf = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("evergreen.yml --ref main -f max=1 -f prefer=procedure", wf)
        self.assertIn("EVERGREEN_PREFER_KIND", (ROOT / ".github" / "workflows" / "evergreen.yml").read_text("utf-8"))


class EvergreenOrderTest(unittest.TestCase):
    PLAN = [{"slug": "chatgpt", "kind": "ai-tool", "accuracy": 5, "demand": 5, "rank": 1},
            {"slug": "jidou-teate", "kind": "procedure", "accuracy": 3, "demand": 3, "rank": 9}]

    def test_procedure_first_when_preferred(self):
        today = datetime(2026, 11, 10).date()
        self.assertEqual(evergreen.order_plan(self.PLAN, today)[0]["slug"], "chatgpt")
        self.assertEqual(evergreen.order_plan(self.PLAN, today, prefer_kind="procedure")[0]["slug"], "jidou-teate")

    def test_night_hours(self):
        self.assertTrue(evergreen.is_night(datetime(2026, 11, 10, 21, 0, tzinfo=JST)))
        self.assertTrue(evergreen.is_night(datetime(2026, 11, 10, 3, 0, tzinfo=JST)))
        self.assertFalse(evergreen.is_night(datetime(2026, 11, 10, 13, 0, tzinfo=JST)))


class _Resp:
    def __init__(self, body: bytes, headers: dict | None = None, url: str = "https://www.example.go.jp/p"):
        self.body, self.headers, self.url = body, headers or {}, url

    def read(self, n=-1):
        return self.body

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Headers(dict):
    def get(self, k, d=None):
        return super().get(k, d)


class FreePathTest(unittest.TestCase):
    PAGE = ("<html><body><article>" + "児童手当は高校生年代まで支給されます。" * 60 + "</article></body></html>").encode()

    def setUp(self):
        feeds._article_memo.clear()

    def test_same_url_is_read_once_per_run(self):
        calls = []

        def fake(url, timeout=25):
            calls.append(url)
            return {"text": "本文" * 400, "links": [{"url": "u"}], "image": None, "title": "t", "description": "",
                    "final_url": url, "published": ""}

        with patch.object(feeds, "_fetch_direct", side_effect=fake):
            first = feeds.fetch_article_text("https://www.example.go.jp/p")
            first["text"] = "書き換え"
            again = feeds.fetch_article_text("https://www.example.go.jp/p")
        self.assertEqual(len(calls), 1)
        self.assertNotEqual(again["text"], "書き換え")  # 呼び出し側が書き換えても覚えた中身は変わらない

    def test_busy_server_is_retried_once(self):
        busy = urllib.error.HTTPError("https://www.example.go.jp/p", 503, "busy", _Headers({"Retry-After": "1"}), None)
        with patch.object(feeds.urllib.request, "urlopen", side_effect=[busy, _Resp(self.PAGE, _Headers())]), \
                patch.object(feeds.time, "sleep") as slept:
            data, _ = feeds._fetch_cached("https://www.example.go.jp/p")
        self.assertEqual(data, self.PAGE)
        slept.assert_called_once()

    def test_not_modified_reuses_cached_page(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"FETCH_CACHE_DIR": tmp}), \
                patch.object(feeds, "CACHE_FRESH_SEC", 0):
            with patch.object(feeds.urllib.request, "urlopen", return_value=_Resp(self.PAGE, _Headers({"ETag": '"v1"'}))):
                feeds._fetch_cached("https://www.example.go.jp/p")
            seen = {}

            def not_modified(request, timeout=25, **kw):
                seen.update(dict(request.header_items()))
                raise urllib.error.HTTPError(request.full_url, 304, "not modified", _Headers(), None)

            with patch.object(feeds.urllib.request, "urlopen", side_effect=not_modified):
                data, _ = feeds._fetch_cached("https://www.example.go.jp/p")
        self.assertEqual(data, self.PAGE)
        self.assertEqual(seen.get("If-none-match"), '"v1"')

    def test_reader_is_only_a_fallback(self):
        direct = {"text": "本文" * 400, "links": [], "image": None, "title": "", "description": "", "final_url": "u", "published": ""}
        with patch.object(feeds, "_fetch_direct", return_value=direct), \
                patch.object(feeds, "_fetch_via_reader", side_effect=AssertionError("読まない")):
            self.assertEqual(feeds.fetch_article_text("https://www.example.go.jp/q")["text"], direct["text"])


    def test_empty_reader_answer_moves_on_to_the_next_route(self):
        """11/9: 直接読めず読み取りサービスが空の本文を返すと、'NoneType' の例外で止まり、次の経路を試していなかった"""
        empty = {"text": "", "links": [], "image": None, "title": "", "description": "", "final_url": "u", "published": ""}
        good = dict(empty, text="公式の本文" * 200)
        with patch.object(feeds, "_fetch_direct", side_effect=ValueError("PDF の文字を取り出せない")), \
                patch.object(feeds, "_fetch_via_reader", return_value=empty), \
                patch.object(feeds, "_fetch_via_api", return_value=good):
            self.assertEqual(feeds.fetch_article_text("https://www.example.go.jp/x.pdf")["text"], good["text"])
        feeds._article_memo.clear()
        with patch.object(feeds, "_fetch_direct", side_effect=ValueError("PDF の文字を取り出せない")), \
                patch.object(feeds, "_fetch_via_reader", return_value=empty), \
                patch.object(feeds, "_fetch_via_api", side_effect=RuntimeError("API なし")):
            with self.assertRaises(RuntimeError) as ctx:
                feeds.fetch_article_text("https://www.example.go.jp/y.pdf")
        self.assertIn("本文を取得できません", str(ctx.exception))


class LedgerTest(unittest.TestCase):
    def test_ledger_row(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next((line for line in rules.splitlines() if line.startswith("| A70 |")), "")
        self.assertIn("2026-11-10", row)
        self.assertIn("深掘り", row)
        self.assertIn("無料", row)


if __name__ == "__main__":
    unittest.main()
