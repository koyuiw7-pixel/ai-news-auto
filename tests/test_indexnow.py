"""IndexNowの対象選定だけ検証。実コンテンツ・キー・ネットワークは使わない。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import indexnow

BASE = "https://example.test"
NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
OLD = "2026-10-29T00:00:00+00:00"
NEW = "2026-10-31T06:00:00+00:00"


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)


class IndexNowFixture(unittest.TestCase):
    """記事・ガイド・道具・イベント・一覧・送った記録を一時フォルダに置く（実コンテンツ・ネットワークは使わない）"""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.guides, self.articles = self.root / "howto", self.root / "articles"
        self.guides.mkdir()
        self.articles.mkdir()
        self.tools, self.lib = self.root / "tools", self.root / "lib"
        self.tools.mkdir()
        self.lib.mkdir()
        for attribute, value in [("HOWTO_DIR", self.guides), ("ARTICLES_DIR", self.articles), ("datetime", FixedDatetime),
                                 ("TOOLS_DIR", self.tools), ("LIB_DIR", self.lib), ("EVENTS_PATH", self.root / "events.json"),
                                 ("DATES_PATH", self.root / "money-dates.json"),
                                 ("TOPIC_LISTS_PATH", self.root / "topic_lists.json"), ("STATE_PATH", self.root / "state" / "indexnow_sent.json")]:
            patcher = patch.object(indexnow, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        network = patch.object(indexnow.urllib.request, "urlopen", side_effect=AssertionError("network is forbidden"))
        self.urlopen = network.start()
        self.addCleanup(network.stop)

    def guide(self, slug="sample", **timestamps):
        (self.guides / f"{slug}.json").write_text(json.dumps({"slug": slug, **timestamps}))

    def selected(self, hours=12):
        result = indexnow.collect_urls(BASE, hours)
        self.urlopen.assert_not_called()
        return result


class IndexNowGuideSelectionTest(IndexNowFixture):
    def test_partial_update_is_selected_with_old_whole_guide_check(self):
        self.guide(checkedAt=OLD, updatedAt=NEW, createdAt=OLD)
        self.assertIn(BASE + "/guides/sample", self.selected())

    def test_new_check_is_selected_with_old_update(self):
        self.guide(checkedAt=NEW, updatedAt=OLD, createdAt=OLD)
        self.assertIn(BASE + "/guides/sample", self.selected())

    def test_mixed_timezones_use_instant_not_lexical_date(self):
        # 10/30 -05:00の方が、10/31 +09:00より実際には新しい。
        self.guide(checkedAt="2026-10-30T20:30:00-05:00", updatedAt="2026-10-31T03:30:00+09:00")
        self.assertIn(BASE + "/guides/sample", self.selected())
        actual = indexnow.latest_guide_timestamp({"checkedAt": "2026-10-31T10:30:00+09:00",
                                                "updatedAt": "2026-10-30T23:30:00-05:00"})
        self.assertEqual(actual, datetime(2026, 10, 31, 4, 30, tzinfo=timezone.utc))
        self.assertEqual(actual.tzinfo, timezone.utc)

    def test_utc_z_and_creation_fallback(self):
        self.guide(createdAt="2026-10-31T06:00:00Z")
        self.assertIn(BASE + "/guides/sample", self.selected())

    def test_invalid_fields_do_not_hide_another_valid_timestamp(self):
        for value in [None, "", "invalid", "2026-02-30T12:00:00+00:00", 123, [],
                      "2026-10-31T06:00:00", "0001-01-01T00:00:00+09:00"]:
            with self.subTest(value=value):
                self.guide(checkedAt=value, updatedAt=NEW)
                self.assertIn(BASE + "/guides/sample", self.selected())
                self.guide(checkedAt=NEW, updatedAt=value)
                self.assertIn(BASE + "/guides/sample", self.selected())

    def test_missing_invalid_or_timezone_free_dates_are_skipped_without_crash(self):
        for fields in [{}, {"checkedAt": None}, {"checkedAt": "invalid", "updatedAt": []},
                       {"checkedAt": "2026-10-31"}, {"createdAt": "2026-10-31T06:00:00"}]:
            with self.subTest(fields=fields):
                self.guide(**fields)
                # 2026-11-10（seo A2）: 変わったページが無ければ、トップ・一覧も送らない
                self.assertEqual(self.selected(), [])
        (self.guides / "bad-json.json").write_text("{broken")
        (self.guides / "not-object.json").write_text("[]")
        self.assertEqual(len(self.selected()), 0)

    def test_window_boundary_is_inclusive_and_older_dates_are_excluded(self):
        self.guide("boundary", checkedAt="2026-10-31T09:00:00+09:00", updatedAt=OLD)
        self.guide("expired", checkedAt="2026-10-30T23:59:59.999999+00:00", updatedAt=OLD)
        urls = self.selected()
        self.assertIn(BASE + "/guides/boundary", urls)
        self.assertNotIn(BASE + "/guides/expired", urls)
        self.assertEqual(urls.count(BASE + "/guides"), 1)

    def test_all_mode_keeps_old_valid_guides(self):
        self.guide(checkedAt=OLD, updatedAt=OLD)
        self.assertNotIn(BASE + "/guides/sample", self.selected())
        self.assertIn(BASE + "/guides/sample", self.selected(hours=None))

    def test_thin_offfocus_and_wire_are_excluded(self):
        long = "## 日本で使える？\n" + "a" * 2000
        cases = [
            {"slug": "ai-long", "genreSlug": "ai", "sourceType": "web", "body": long, "generatedAt": NEW},
            {"slug": "ai-short", "genreSlug": "ai", "sourceType": "web", "body": "a" * 1000, "generatedAt": NEW},
            {"slug": "noindex", "indexable": False, "generatedAt": NEW},
            {"slug": "game", "genreSlug": "entertainment", "title": "新作ゲームの体験版", "body": long, "generatedAt": NEW},
            {"slug": "wire", "sourceType": "web", "channelSlug": "prtimes", "body": long, "generatedAt": NEW},
            {"slug": "old", "indexable": True, "generatedAt": OLD},
        ]
        for article in cases:
            (self.articles / (article["slug"] + ".json")).write_text(json.dumps(article))
        # 2026-11-08（台帳 A61）: ai-short は題名の無い ai-long と同じ題名の重複として外れる。配信の題名の無いものも同じ重複で外れる。
        # 2026-11-13 オーナー「とにかく数字」: 公開した記事は題名の語・主題で検索から外さない（game も送る）
        # 2026-11-10（seo A2・LLMO-A3）: 入口は変わった記事のジャンル（ai-long は ai なので /genres/ai）
        self.assertEqual(self.selected(), [BASE, BASE + "/articles", BASE + "/genres/ai", BASE + "/genres/entertainment",
                                           BASE + "/articles/ai-long", BASE + "/articles/game"])

    def test_search_policy_reasons(self):
        long = "a" * 2000
        jp = "## 無料で使える？\n" + long
        cases = [
            ({"genreSlug": "ai", "body": jp}, None),
            ({"genreSlug": "ai", "body": long, "verdict": {"japan": "ok"}}, None),
            ({"genreSlug": "ai", "body": long}, "no-japan-value"),
            ({"genreSlug": "ai", "body": "a"}, "thin"),
            ({"genreSlug": "public", "title": "生成AIの指針", "body": jp}, None),
            ({"genreSlug": "public", "title": "道路の工事", "body": jp}, "off-focus"),
            # 読者像（scripts/persona.py）: お金・制度・日本のスポーツは対象、エンタメ・お金に関係しない話題・海外スポーツは外す
            ({"genreSlug": "business", "title": "財務省が10月の国債金利を公表", "body": jp}, None),
            ({"genreSlug": "investment", "title": "楽天証券の口座数", "body": jp}, None),
            ({"genreSlug": "public", "title": "国の教育ローン、世帯年収の上限と金利", "body": jp}, None),
            ({"genreSlug": "lifestyle", "title": "新作ラテが期間限定で発売", "body": jp}, "off-focus"),
            ({"genreSlug": "entertainment", "title": "新作ゲームの体験版", "body": jp}, "off-focus"),
            ({"genreSlug": "science", "title": "天文台の教授が褒章", "body": jp}, "off-focus"),
            ({"genreSlug": "sports", "title": "なでしこジャパンがブラジルと対戦", "body": jp}, None),
            ({"genreSlug": "sports", "title": "レイカーズが開幕戦に勝利", "body": jp}, "off-focus"),
            ({"genreSlug": "sports", "title": "世界陸上で海外選手が新記録", "body": jp}, None),
            ({"genreSlug": "business", "title": "国債金利", "body": "a" * 1499}, "thin"),
            ({"genreSlug": "ai", "body": "a", "channelSlug": "prtimes"}, "wire"),
            ({"body": "a", "indexable": True}, None),
            ({"body": jp, "genreSlug": "ai", "indexable": False}, "manual"),
            ({"type": "roundup", "body": "a"}, None),
        ]
        # 2026-11-08 までの基準（focus_reason。今は公開前の門が使う）。検索に出す基準は tests/test_index_relax_20261108.py（台帳 A61）
        for article, reason in cases:
            with self.subTest(article=article):
                self.assertEqual(indexnow.focus_reason(article), reason)

    def test_duplicates_keep_longest(self):
        arts = [{"slug": "a", "title": "同じ 題名", "body": "x" * 10},
                {"slug": "b", "title": "同じ題名", "body": "x" * 20},
                {"slug": "c", "title": "新しい料金プランを発表", "sourceUrl": "u", "body": "x"},
                {"slug": "d", "title": "新しい料金プランを発表へ", "sourceUrl": "u", "body": "xx"},
                # 2026-11-13: 出典が同じでも題名の切り口が違えば重複にしない
                {"slug": "e", "title": "社長が退任", "sourceUrl": "u", "body": "x"}]
        self.assertEqual(indexnow.duplicate_slugs(arts), {"a", "c"})

    def test_distribution_policy_unchanged(self):
        cases = [
            ({"sourceType": "web", "body": "a"}, False),
            ({"sourceType": "web", "body": "a" * 2000}, True),
            ({"sourceType": "web", "body": "a", "channelSlug": "prtimes", "indexable": True}, True),
            ({"sourceType": "video"}, True),
        ]
        for article, distribution in cases:
            with self.subTest(article=article):
                self.assertEqual(indexnow.is_distribution_eligible(article), distribution)

class IndexNowChangedOnlyTest(IndexNowFixture):
    """seo A2・LLMO-A3（2026-11-10）: 公開後に、変わったURLだけ送り、結果を state/indexnow_sent.json に残す"""

    def article(self, slug, **fields):
        article = {"slug": slug, "title": f"{slug} の料金が12月から変わる", "body": "本文" * 300, "generatedAt": NEW, **fields}
        (self.articles / f"{slug}.json").write_text(json.dumps(article, ensure_ascii=False))
        return article

    def sent_ok(self, urls, status=200):
        state = indexnow.load_state()
        changed = indexnow.changed_items(BASE, 12, state)
        indexnow.record_result(state, urls, {u: h for u, h, _ in changed}, status, now=NOW)
        indexnow.save_state(state)
        return indexnow.load_state()

    def test_hub_is_genre_of_changed_article_not_fixed_ai(self):
        self.article("denki", genre="暮らし・生活", genreSlug="lifestyle")
        urls = self.selected()
        self.assertEqual(urls, [BASE, BASE + "/articles", BASE + "/genres/lifestyle", BASE + "/articles/denki"])
        self.assertNotIn(BASE + "/genres/ai", urls)
        self.article("ai-news", genreSlug="ai")
        self.assertIn(BASE + "/genres/ai", self.selected())

    def test_unchanged_url_is_not_resubmitted(self):
        self.article("denki", genreSlug="lifestyle")
        first = self.selected()
        state = self.sent_ok(first)
        self.assertEqual(state["urls"][BASE + "/articles/denki"]["status"], 200)
        self.assertIn("hash", state["urls"][BASE + "/articles/denki"])
        self.assertEqual(indexnow.collect_urls(BASE, 12, state), [])
        # SNS の下書きだけが変わってもページは同じなので送らない
        self.article("denki", genreSlug="lifestyle", threadsPost="別の下書き")
        self.assertEqual(indexnow.collect_urls(BASE, 12, state), [])
        # 本文が変わったら送り直す（入口も一緒に）
        self.article("denki", genreSlug="lifestyle", body="新しい本文" * 300)
        self.assertEqual(indexnow.collect_urls(BASE, 12, state),
                         [BASE, BASE + "/articles", BASE + "/genres/lifestyle", BASE + "/articles/denki"])

    def test_tools_events_roundups_only_when_changed(self):
        (self.tools / "furusato-limit").mkdir()
        (self.tools / "furusato-limit" / "page.tsx").write_text("v1")
        (self.lib / "calc-math.ts").write_text("m1")
        (self.root / "events.json").write_text(json.dumps({"events": [{"slug": "ces-2027", "name": "CES"}]}))
        (self.root / "topic_lists.json").write_text(json.dumps({"lists": {"price-hikes": [{"slug": "a"}]}}))
        (self.root / "money-dates.json").write_text(json.dumps({"dates": [{"slug": "nenkin-december-2026", "name": "年金"}]}))
        urls = self.selected()
        self.assertEqual(urls, [BASE + "/events", BASE + "/dates", BASE + "/roundups", BASE + "/tools/furusato-limit",
                                BASE + "/events/ces-2027", BASE + "/dates/nenkin-december-2026", BASE + "/roundups/price-hikes"])
        state = self.sent_ok(urls, 202)
        self.assertEqual(indexnow.collect_urls(BASE, 12, state), [])
        # 計算の部品（lib/calc*）が変わったら道具を送り直す。イベント・一覧は変わっていないので送らない
        (self.lib / "calc-math.ts").write_text("m2")
        self.assertEqual(indexnow.collect_urls(BASE, 12, state), [BASE + "/tools/furusato-limit"])

    def test_rejected_submit_is_logged_and_retried_and_alerts(self):
        self.article("denki", genreSlug="lifestyle")
        state = self.sent_ok(self.selected(), 403)
        self.assertEqual(state["last"], {"time": NOW.isoformat(timespec="seconds"), "count": 4, "status": 403})
        self.assertEqual(state["log"][-1]["status"], 403)
        self.assertNotIn("hash", state["urls"][BASE + "/articles/denki"])
        self.assertIn(BASE + "/articles/denki", indexnow.collect_urls(BASE, 12, state))  # 次の回に送り直す
        import pipeline_health
        self.assertIn("HTTP 403", pipeline_health.indexnow_problem(indexnow.STATE_PATH))
        calls = []
        with patch.object(pipeline_health, "_gh", side_effect=lambda *a: calls.append(a) or ""), \
                patch.object(pipeline_health.subprocess, "run"):
            self.assertEqual(pipeline_health.indexnow_alert(indexnow.STATE_PATH), 0)
        self.assertTrue(any(c[:2] == ("issue", "create") for c in calls))
        # 受理に戻れば、開いている知らせを閉じる
        state = self.sent_ok(indexnow.collect_urls(BASE, 12, state), 200)
        self.assertIsNone(pipeline_health.indexnow_problem(indexnow.STATE_PATH))
        calls.clear()
        with patch.object(pipeline_health, "_gh", side_effect=lambda *a: calls.append(a) or ("12" if a[:2] == ("issue", "list") else "")):
            pipeline_health.indexnow_alert(indexnow.STATE_PATH)
        self.assertTrue(any(c[:3] == ("issue", "close", "12") for c in calls))

    def test_main_records_status_and_returns_nonzero_on_error(self):
        self.article("denki", genreSlug="lifestyle")
        out = self.root / "out.json"
        argv = ["indexnow.py", "--hours", "12", "--state-out", str(out)]
        site = patch.object(indexnow, "site_url", return_value=BASE)
        site.start()
        self.addCleanup(site.stop)
        with patch.object(indexnow, "find_key", return_value="k"), patch.object(indexnow, "rules_drift", return_value=False), \
                patch.object(indexnow, "submit", side_effect=OSError("down")), patch.object(sys, "argv", argv):
            self.assertEqual(indexnow.main(), 1)
        self.assertEqual(indexnow.load_state(out)["last"]["status"], "error")
        self.assertEqual(indexnow.merge_state(str(out)), 0)  # 最新の main の記録に足す（デプロイの記録の push と同じやり方）
        with patch.object(indexnow, "find_key", return_value="k"), patch.object(indexnow, "rules_drift", return_value=False), \
                patch.object(indexnow, "submit", return_value=202), patch.object(sys, "argv", argv):
            self.assertEqual(indexnow.main(), 0)
        self.assertEqual(indexnow.load_state(out)["last"]["status"], 202)
        self.assertEqual(indexnow.merge_state(str(out)), 0)
        merged = indexnow.load_state()
        self.assertEqual(merged["urls"][BASE + "/articles/denki"]["status"], 202)
        self.assertEqual([e["status"] for e in merged["log"]], ["error", 202])

    def test_nothing_changed_sends_nothing(self):
        argv = ["indexnow.py", "--hours", "12"]
        with patch.object(indexnow, "find_key", return_value="k"), patch.object(indexnow, "rules_drift", return_value=False), \
                patch.object(indexnow, "submit", side_effect=AssertionError("must not send")), patch.object(sys, "argv", argv):
            self.assertEqual(indexnow.main(), 0)
        self.assertFalse(indexnow.STATE_PATH.exists())


if __name__ == "__main__":
    unittest.main()
