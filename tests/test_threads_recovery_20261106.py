"""Threads の投稿どうしの間隔（台帳 S47。2026-11-08 の台帳の見直しで旧 S44 の止め・様子見・30分を外し、45分に一本化）の検査。
外部通信なし・何も投稿しない。

  Threads の投稿どうしは45分あける（ずっと）。速報も数えるが、近ければ遅らせるだけで落とさない（S41 のまま）。
  ミサイル・地震・津波などの急ぎの安全の知らせは遅らせない。

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
        self.posted_path, self.video_path = self.tmp / "p.json", self.tmp / "v.json"
        self.write(posted={}, video={})
        self.patches = [patch.object(g, "POSTED_PATH", self.posted_path), patch.object(g, "VIDEO_PATH", self.video_path)]
        for p in self.patches:
            p.start()
        tp._BUFFER_DUE.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        tp._BUFFER_DUE.clear()

    def write(self, posted=None, video=None):
        if posted is not None:
            self.posted_path.write_text(json.dumps({"posted": posted}), "utf-8")
        if video is not None:
            self.video_path.write_text(json.dumps(video), "utf-8")


class GapTest(TempState):
    def test_gap_is_45_minutes_from_the_plan(self):
        self.assertEqual(g.min_gap(), timedelta(minutes=45))
        self.assertFalse(hasattr(g, "normal_hold"))  # 旧 S44 の止め・様子見は外した

    def test_gap_only_delays_never_moves_earlier(self):
        t = jst(7, 12, 15)
        self.assertEqual(g.gap_shift(t, [jst(7, 11, 0)]), t)  # 75分はなれていればそのまま
        self.assertEqual(g.gap_shift(t, [jst(7, 12, 0)]), jst(7, 12, 45))  # 15分前に投稿 → 45分あくまで遅らせる
        self.assertEqual(g.gap_shift(t, [jst(7, 12, 30)]), jst(7, 13, 15))  # 15分後に予約がある → その45分後へ（前には動かさない）

    def test_breaking_within_45_min_is_delayed_not_dropped(self):
        now = jst(7, 9, 0)
        self.write(posted={"big-news": {"breaking": True, "status": "awaiting_video"}})
        inp = {"channelId": CH, "mode": "shareNow", "text": "x"}
        when = g.enforce("k", inp, NEWS, now=now, others=[jst(7, 8, 50)])
        self.assertEqual(when, jst(7, 9, 35))
        self.assertEqual((inp["mode"], inp["dueAt"]), ("customScheduled", z(jst(7, 9, 35))))

    def test_normal_posts_are_never_held_by_date(self):
        now = jst(6, 23, 0)  # 旧 S44 の「11/6 夜の止め」の時間でも止めない
        inp = {"channelId": CH, "mode": "customScheduled", "dueAt": z(now)}
        self.assertEqual(g.enforce("k", inp, ART, now=now, others=[]), now)

    def test_urgent_safety_alert_is_never_delayed(self):
        now = jst(7, 9, 0)
        inp = {"channelId": CH, "mode": "shareNow"}
        self.assertEqual(g.enforce("k", inp, QUAKE, now=now, others=[jst(7, 8, 55)]), now)
        self.assertEqual(inp["mode"], "shareNow")


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

    def test_create_post_delays_by_45_minutes(self):
        gql, recent, created = self.fake([jst(6, 23, 50)])
        self.write(posted={"big-news": {"breaking": True}})
        with patch.object(tp, "buffer_graphql", gql), patch.object(tp, "recent_channel_posts", recent), \
                patch.object(tp, "ensure_not_duplicate"), patch.object(sns_rules, "enforce_buffer"):
            tp.create_post("k", {"channelId": CH, "mode": "customScheduled", "dueAt": z(jst(7, 0, 0))}, service="threads",
                           article=NEWS, source="breaking")
            self.assertEqual(created[-1]["dueAt"], z(jst(7, 0, 35)))  # 23:50 から45分あける（落とさない）
            # 同じ実行の次の Threads の投稿は、いま作った投稿からも45分あける
            tp.create_post("k", {"channelId": CH, "mode": "customScheduled", "dueAt": z(jst(7, 0, 40))}, service="threads",
                           article={**NEWS, "slug": "big-news-2"}, source="breaking")
            self.assertEqual(created[-1]["dueAt"], z(jst(7, 1, 20)))

    def test_other_platforms_are_not_affected(self):
        gql, recent, created = self.fake([])
        with patch.object(tp, "buffer_graphql", gql), patch.object(tp, "ensure_not_duplicate"), patch.object(sns_rules, "enforce_buffer"), \
                patch.object(tp.sns_plan, "x_on", return_value=False):
            tp.create_post("k", {"channelId": "tw", "mode": "shareNow"}, service="twitter", article=ART, source="x_post")
        self.assertEqual(len(created), 1)

    def test_publish_queued_keeps_held_post_waiting(self):
        slot = jst(7, 12, 15)
        posted = {"acme-tool": {"id": "", "status": "awaiting_video", "style": "standalone", "dueAt": slot.isoformat(),
                                "pending": {"slot": slot.isoformat(), "inputs": {"threads": {"channelId": CH, "text": "x"}}}}}
        issues = []

        def creator(svc, inp, art):
            raise g.ThreadsHeld("新しい書き方の承認待ち")

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
        row = next(line for line in ledger.splitlines() if line.startswith("| S47 "))
        for words in ("45分", "速報", "遅らせ", "scripts/threads_gate.py"):
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
