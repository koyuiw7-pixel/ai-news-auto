"""Threads の表示0からの立て直し（2026-11-06 22:40 オーナー承認・台帳 S44）の検査。外部通信なし・何も投稿しない。

  1. Threads の投稿どうしは30分あける（ずっと）。速報も数えるが、近ければ遅らせるだけで落とさない（S41 のまま）
  2. 今夜（11/6 22:00〜11/7 7:00）は通常の投稿を出さない。速報は出す
  3. 11/7 はまずいちばん強い1本だけ（7:15）。30分後の表示 > 0 なら再開、0 なら止めて issue。11/8 からは何もしない

  python3 -m unittest tests.test_threads_recovery_20261106
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sns_rules  # noqa: E402
import sns_video_followup as fu  # noqa: E402
import threads_gate as g  # noqa: E402
import threads_post as tp  # noqa: E402

JST = timezone(timedelta(hours=9))
CH = "threads-ch"


def jst(day: int, h: int, m: int = 0) -> datetime:
    return datetime(2026, 11, day, h, m, tzinfo=JST)


def z(when: datetime) -> str:
    return when.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


ART = {"slug": "acme-tool", "title": "Acme が新しいAIツールを公開", "genreSlug": "ai"}
NEWS = {"slug": "big-news", "title": "大手が値下げを発表", "genreSlug": "money", "breaking": True}
QUAKE = {"slug": "quake-1", "title": "震度5強の地震 津波の心配なし", "disaster": True}


class TempState(unittest.TestCase):
    """state/ の3つのファイルを一時フォルダに置き換える（本物の記録を読まない・書かない）"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.posted_path, self.video_path, self.rec_path = self.tmp / "p.json", self.tmp / "v.json", self.tmp / "r.json"
        self.write(posted={}, video={})
        self.patches = [patch.object(g, "POSTED_PATH", self.posted_path), patch.object(g, "VIDEO_PATH", self.video_path),
                        patch.object(g, "RECOVERY_PATH", self.rec_path)]
        for p in self.patches:
            p.start()
        tp._BUFFER_DUE.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        tp._BUFFER_DUE.clear()

    def write(self, posted=None, video=None, recovery=None):
        if posted is not None:
            self.posted_path.write_text(json.dumps({"posted": posted}), "utf-8")
        if video is not None:
            self.video_path.write_text(json.dumps(video), "utf-8")
        if recovery is not None:
            self.rec_path.write_text(json.dumps(recovery), "utf-8")


def probe_rec(slot: datetime, **extra) -> dict:
    return {"id": "", "status": "awaiting_video", "style": "standalone", "pending": {"slot": slot.isoformat()}, "dueAt": slot.isoformat(), **extra}


class GapTest(TempState):
    def test_gap_only_delays_never_moves_earlier(self):
        t = jst(7, 12, 15)
        self.assertEqual(g.gap_shift(t, [jst(7, 11, 0)]), t)  # 75分はなれていればそのまま
        self.assertEqual(g.gap_shift(t, [jst(7, 12, 0)]), jst(7, 12, 30))  # 15分前に投稿 → 30分あくまで遅らせる
        self.assertEqual(g.gap_shift(t, [jst(7, 12, 30)]), jst(7, 13, 0))  # 15分後に予約がある → その30分後へ（前には動かさない）
        self.assertEqual(g.gap_shift(t, [jst(7, 12, 0), jst(7, 12, 40)]), jst(7, 13, 10))  # 続けてぶつかれば、さらに後へ

    def test_breaking_within_30_min_is_delayed_not_dropped(self):
        now = jst(7, 9, 0)
        self.write(posted={"big-news": {"breaking": True, "status": "awaiting_video"}})
        inp = {"channelId": CH, "mode": "shareNow", "text": "x"}
        when = g.enforce("k", inp, NEWS, now=now, others=[jst(7, 8, 50)])
        self.assertEqual(when, jst(7, 9, 20))
        self.assertEqual((inp["mode"], inp["dueAt"]), ("customScheduled", z(jst(7, 9, 20))))

    def test_gap_is_permanent(self):
        now = jst(12, 15, 0)  # 計画の日付を過ぎても30分の間隔は続く
        inp = {"channelId": CH, "mode": "customScheduled", "dueAt": z(now)}
        self.assertEqual(g.enforce("k", inp, ART, now=now, others=[jst(12, 14, 45)]), jst(12, 15, 15))

    def test_urgent_safety_alert_is_never_delayed(self):
        now = jst(7, 9, 0)
        inp = {"channelId": CH, "mode": "shareNow"}
        self.assertEqual(g.enforce("k", inp, QUAKE, now=now, others=[jst(7, 8, 55)]), now)
        self.assertEqual(inp["mode"], "shareNow")


class PauseTonightTest(TempState):
    def test_normal_posts_are_held_tonight(self):
        for when in (jst(6, 22, 0), jst(6, 23, 30), jst(7, 3, 0), jst(7, 6, 59)):
            inp = {"channelId": CH, "mode": "customScheduled", "dueAt": z(when)}
            with self.assertRaises(g.ThreadsHeld):
                g.enforce("k", inp, ART, now=when - timedelta(minutes=5), others=[])
        with self.assertRaises(g.ThreadsHeld):  # 朝のまとめ・比べの投稿も通常の投稿
            g.enforce("k", {"channelId": CH, "mode": "shareNow"}, {"link": "/digest/x"}, kind="digest", now=jst(6, 23, 0), others=[])

    def test_breaking_still_goes_tonight(self):
        self.write(posted={"big-news": {"breaking": True}})
        inp = {"channelId": CH, "mode": "shareNow"}
        self.assertEqual(g.enforce("k", inp, NEWS, now=jst(6, 23, 0), others=[]), jst(6, 23, 0))

    def test_breaking_article_planned_as_normal_slot_is_normal(self):
        self.write(posted={"big-news": probe_rec(jst(6, 23, 0))})  # 速報の記事でも、ふつうの枠に回した記録は通常の投稿
        with self.assertRaises(g.ThreadsHeld):
            g.enforce("k", {"channelId": CH, "mode": "shareNow"}, NEWS, now=jst(6, 23, 0), others=[])

    def test_no_normal_slot_planned_tonight(self):
        slots = tp.free_slots({"posted": {}}, jst(6, 22, 40).astimezone(timezone.utc))
        self.assertEqual(slots, [])  # 8時間先（6:40）まで、通常の枠は1つも取らない


class ProbeDayTest(TempState):
    def test_probe_slot_is_715_and_only_from_0545(self):
        self.assertFalse(g.plan_slot_ok(jst(7, 7, 15), jst(7, 5, 0)))  # 夜のあいだの記事も候補に入れるため、まだ選ばない
        self.assertTrue(g.plan_slot_ok(jst(7, 7, 15), jst(7, 6, 0)))
        self.assertFalse(g.plan_slot_ok(jst(7, 12, 15), jst(7, 6, 0)))  # 様子見は1本だけ

    def test_free_slots_returns_only_the_probe(self):
        slots = tp.free_slots({"posted": {}}, jst(7, 6, 0).astimezone(timezone.utc))
        self.assertEqual([s.astimezone(JST) for s in slots], [jst(7, 7, 15)])  # 朝のまとめの枠でも、この日は様子見に使う

    def test_missed_715_moves_probe_to_next_slot(self):
        self.assertTrue(g.plan_slot_ok(jst(7, 12, 15), jst(7, 11, 0)))  # 7:15 を取り逃しても、その日が丸ごと空かない

    def test_nothing_else_until_result(self):
        posted = {"acme-tool": probe_rec(jst(7, 7, 15))}
        self.write(posted=posted)
        self.assertEqual(tp.free_slots({"posted": posted}, jst(7, 7, 30).astimezone(timezone.utc)), [])
        # 様子見の1本は通す・ほかの通常の投稿と朝のまとめは止める
        self.assertEqual(g.normal_hold(jst(7, 7, 15), ART), "")
        self.assertIn("様子見", g.normal_hold(jst(7, 12, 15), {"slug": "other"}))
        self.assertIn("様子見", g.normal_hold(jst(7, 7, 15), None))

    def test_recovered_resumes_and_not_recovered_holds_the_day(self):
        posted = {"acme-tool": probe_rec(jst(7, 7, 15))}
        self.write(posted=posted, recovery={"probe": {"day": "2026-11-07", "result": "recovered"}})
        slots = [s.astimezone(JST) for s in tp.free_slots({"posted": posted}, jst(7, 8, 0).astimezone(timezone.utc))]
        self.assertIn(jst(7, 12, 15), slots)
        self.assertEqual(g.normal_hold(jst(7, 12, 15), {"slug": "other"}), "")
        self.write(recovery={"probe": {"day": "2026-11-07", "result": "not_recovered"}})
        self.assertEqual(tp.free_slots({"posted": posted}, jst(7, 8, 0).astimezone(timezone.utc)), [])
        self.assertIn("0", g.normal_hold(jst(7, 18, 45), {"slug": "other"}))

    def test_plan_ends_after_probe_day(self):
        self.write(recovery={"probe": {"day": "2026-11-07", "result": "not_recovered"}})
        self.assertEqual(g.normal_hold(jst(8, 7, 15), ART), "")  # 11/8 からはいつもどおり（ずっと続く止めにしない）
        self.assertTrue(g.plan_slot_ok(jst(8, 12, 15), jst(8, 6, 0)))
        self.assertFalse(g.in_pause(jst(13, 23, 0)))

    def test_breaking_goes_on_probe_day_before_result(self):
        self.write(posted={"acme-tool": probe_rec(jst(7, 7, 15)), "big-news": {"breaking": True}})
        inp = {"channelId": CH, "mode": "shareNow"}
        self.assertEqual(g.enforce("k", inp, NEWS, now=jst(7, 7, 30), others=[jst(7, 7, 15)]), jst(7, 7, 45))  # 出す（30分あけて）

    def test_skipped_probe_frees_the_day_for_a_new_probe(self):
        posted = {"acme-tool": probe_rec(jst(7, 7, 15), status="skipped_plan")}
        self.write(posted=posted)
        self.assertEqual(g.probe_slug(), "")
        self.assertTrue(g.plan_slot_ok(jst(7, 12, 15), jst(7, 11, 0)))


class CheckTest(TempState):
    def setUp(self):
        super().setUp()
        self.write(posted={"acme-tool": probe_rec(jst(7, 7, 15))},
                   video={"queued": {"acme-tool": {"status": "created", "id": "B1", "dueAt": jst(7, 7, 15).isoformat()}}})
        self.issues = []

    def run_check(self, now, node):
        return g.check("k", now, fetch=lambda key, pid: dict(node), issue=lambda probe, why: self.issues.append(why) or "https://issue/1")

    def test_waits_until_30_minutes_after(self):
        data = self.run_check(jst(7, 7, 30), {"metrics": {"views": 5}})
        self.assertEqual(data["probe"]["status"], "waiting")
        self.assertNotIn("result", data["probe"])

    def test_views_above_zero_means_recovered(self):
        data = self.run_check(jst(7, 7, 46), {"status": "sent", "sentAt": z(jst(7, 7, 15)), "metrics": {"views": 3}})
        self.assertEqual(data["probe"]["result"], "recovered")
        self.assertEqual(json.loads(self.rec_path.read_text())["probe"]["result"], "recovered")  # state に残る
        self.assertEqual(self.issues, [])

    def test_zero_views_holds_and_opens_one_issue(self):
        node = {"status": "sent", "sentAt": z(jst(7, 7, 15)), "metricsUpdatedAt": z(jst(7, 7, 45)), "metrics": {"views": 0}}
        data = self.run_check(jst(7, 7, 46), node)
        self.assertEqual(data["probe"]["result"], "not_recovered")
        self.run_check(jst(7, 8, 6), node)  # 次の回も何もしない（issue は1つだけ）
        self.assertEqual(len(self.issues), 1)
        self.assertIn("0", g.normal_hold(jst(7, 12, 15), {"slug": "other"}))

    def test_stale_zero_never_halts_the_day(self):
        node = {"status": "sent", "sentAt": z(jst(7, 7, 15)), "metricsUpdatedAt": None, "metrics": {"views": 0}}
        self.assertNotIn("result", self.run_check(jst(7, 7, 46), node)["probe"])  # 数字がまだ更新されていない 0 では決めない
        stale = dict(node, metricsUpdatedAt=z(jst(7, 7, 20)))  # 出てから5分の更新 → 新しい数字ではない
        self.assertNotIn("result", self.run_check(jst(7, 8, 6), stale)["probe"])
        data = self.run_check(jst(7, 10, 16), stale)  # 3時間たっても確かめられない → 止めない（締めすぎない）
        self.assertEqual(data["probe"]["result"], "unconfirmed")
        self.assertEqual(json.loads(self.rec_path.read_text())["probe"]["result"], "unconfirmed")
        self.assertEqual(self.issues, [])  # issue は立てない
        self.assertEqual(g.normal_hold(jst(7, 12, 15), {"slug": "other"}), "")  # いつもの予定に戻る
        posted = json.loads(self.posted_path.read_text())["posted"]
        slots = [s.astimezone(JST) for s in tp.free_slots({"posted": posted}, jst(7, 10, 20).astimezone(timezone.utc))]
        self.assertIn(jst(7, 12, 15), slots)

    def test_unreadable_metrics_never_halt(self):
        def boom(key, pid):
            raise RuntimeError("Buffer down")

        data = g.check("k", jst(7, 10, 16), fetch=boom, issue=lambda p, w: self.issues.append(w))
        self.assertEqual(data["probe"]["result"], "unconfirmed")
        self.assertEqual(self.issues, [])

    def test_issue_is_plain_japanese(self):
        body = g.issue_body({"slug": "acme-tool", "dueAt": jst(7, 7, 15).isoformat()}, "表示 0")
        for words in ("Threads はまだ元に戻っていません", "速報は今までどおり出します", "11月08日 からは、いつもの予定に自動で戻ります"):
            self.assertIn(words, body)

    def test_does_nothing_on_other_days(self):
        data = self.run_check(jst(6, 23, 0), {"metrics": {"views": 0}})
        self.assertNotIn("result", data["probe"])
        self.assertEqual(self.issues, [])


class AllPathsTest(TempState):
    """Threads に作る経路はすべて threads_post.create_post（Buffer）を通る。そこで止める・遅らせる"""

    def fake(self, existing: list[datetime]):
        created = []

        def gql(key, query, variables=None, gated=False, **kw):
            if "createPost" in query:
                created.append(variables["input"])
                return {"createPost": {"post": {"id": f"N{len(created)}"}}}
            raise AssertionError(query[:60])

        def recent(key, channel_id, gql_=None):
            tp._BUFFER_DUE.setdefault(channel_id, [(f"E{i}", t) for i, t in enumerate(existing)])  # 実行の中では1回だけ読む（キャッシュ）
            return []

        return gql, recent, created

    def test_create_post_holds_normal_and_delays_breaking(self):
        gql, recent, created = self.fake([jst(6, 23, 50)])
        self.write(posted={"big-news": {"breaking": True}})
        with patch.object(tp, "buffer_graphql", gql), patch.object(tp, "recent_channel_posts", recent), \
                patch.object(tp, "ensure_not_duplicate"), patch.object(sns_rules, "enforce_buffer"):
            with self.assertRaises(g.ThreadsHeld):
                tp.create_post("k", {"channelId": CH, "mode": "customScheduled", "dueAt": z(jst(7, 1, 0))}, service="threads",
                               article=ART, source="test")
            self.assertEqual(created, [])  # Buffer に作らない
            tp.create_post("k", {"channelId": CH, "mode": "customScheduled", "dueAt": z(jst(7, 0, 0))}, service="threads",
                           article=NEWS, source="breaking")
            self.assertEqual(created[-1]["dueAt"], z(jst(7, 0, 20)))  # 23:50 から30分あける（落とさない）
            # 同じ実行の次の Threads の投稿は、いま作った投稿からも30分あける
            tp.create_post("k", {"channelId": CH, "mode": "customScheduled", "dueAt": z(jst(7, 0, 25))}, service="threads",
                           article={**NEWS, "slug": "big-news-2"}, source="breaking")
            self.assertEqual(created[-1]["dueAt"], z(jst(7, 0, 50)))

    def test_other_platforms_are_not_affected(self):
        gql, recent, created = self.fake([])
        with patch.object(tp, "buffer_graphql", gql), patch.object(tp, "ensure_not_duplicate"), patch.object(sns_rules, "enforce_buffer"), \
                patch.object(tp.sns_plan, "x_on", return_value=False):
            tp.create_post("k", {"channelId": "tw", "mode": "shareNow"}, service="twitter", article=ART, source="x_post")
        self.assertEqual(len(created), 1)

    def test_publish_queued_keeps_held_post_waiting(self):
        slot = jst(7, 12, 15)
        posted = {"acme-tool": probe_rec(slot, pending={"slot": slot.isoformat(), "inputs": {"threads": {"channelId": CH, "text": "x"}}})}
        issues = []

        def creator(svc, inp, art):
            raise g.ThreadsHeld("様子見の結果待ち")

        import sns_plan

        with patch.object(fu, "probe_buffer", return_value={}), patch.object(fu, "stale_post", return_value=False), \
                patch.object(fu, "muse_waiting", return_value=None), patch.object(sns_plan, "video_post", return_value=False):
            out = fu.publish_queued({"videos": {}}, {"posted": posted}, slot - timedelta(minutes=30),
                                    {"post": True, "ab_until": "", "after_ab": "short"}, creator=creator,
                                    issue=lambda s, w: issues.append(w), eligible=lambda s: True, remote=lambda s: {})
        self.assertEqual(out[0]["status"], "waiting")  # 出さなかった扱い（skipped）にしない
        self.assertEqual(issues, [])

    def test_every_threads_create_goes_through_create_post(self):
        # Buffer の createPost は gated=True でしか呼べない（create_post だけが付ける）。create_post の中で Threads は門番を通る
        src = (ROOT / "scripts" / "threads_post.py").read_text("utf-8")
        body = src[src.index("def create_post("):src.index("def publish_via_buffer(")]
        self.assertIn("threads_gate.enforce(", body)
        self.assertIn("threads_gate.enforce_direct(", src[src.index("def publish("):src.index("# 投稿の中身を作る・変える")])
        with self.assertRaises(sns_rules.SnsRuleViolation):
            tp.buffer_graphql("k", "mutation { createPost(input: {}) { __typename } }")

    def test_owner_rule_row_exists(self):
        ledger = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next(line for line in ledger.splitlines() if line.startswith("| S44 "))
        for words in ("30分", "速報", "遅らせ", "11/7", "scripts/threads_gate.py"):
            self.assertIn(words, row)

def setUpModule():
    __import__("sys").path.insert(0, __import__("os").path.dirname(__file__))
    import legacy_threads  # 以前の書き方の仕組みのテスト（台帳 S46 の新しい書き方・承認待ちの止めは外す）

    legacy_threads.start()


def tearDownModule():
    import legacy_threads

    legacy_threads.stop()


if __name__ == "__main__":
    unittest.main()
