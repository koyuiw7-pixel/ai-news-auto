"""2026-11-05 夕方のオーナー決定（流入が目標に遠く、Threads からの訪問が1日2〜4に落ちた）。外部通信なし・何も投稿しない。

  S31 終了: 「すべて本文にリンクにしよう今後は」→ Threads の記事のリンクは本文だけ。変数 THREADS_LINK_AB は読まない。
           比べの間に返信にリンクを置いて作った予定・予約も、送る前・出る前に本文のリンクに直す。
  S13 置き換え: 「動画を待たない」「返信欄にリンクつけてみない人が多いのだから、動画も同じことになるでしょ。なら動画を作る記事を
           限定した方がいいかな。かなり人気なジャンルで、ビューを取れるような記事にしたいよね。」
           → ふつうの投稿は枠の時刻に記事の写真・カードで出す。動画はビューを取れる限られた記事（Muse に頼んだ記事・1日4本まで）だけで、
             その投稿だけ枠から1時間まで動画を待つ。動画が無いことでは投稿を落とさない。動画を返信で足す仕組みは作らない。

  python3 -m unittest tests.test_owner_decisions_20261105_evening
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import owner_rules_audit as audit  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules as r  # noqa: E402
import sns_video_followup as fu  # noqa: E402
import threads_post as tp  # noqa: E402
from test_sns_video_required import ART, CARD, FLAGS, GOOD, LINK, queued_rec, ready_video  # noqa: E402

JST = timezone(timedelta(hours=9))
DAY = datetime(2026, 11, 6, 0, 0, tzinfo=JST)
BODY_URL = f"{LINK}?utm_source=threads&utm_medium=social&utm_campaign=classic&utm_content=video_body"
REPLY_URL = BODY_URL.replace("video_body", "video_reply")


class LinkInBodyTest(unittest.TestCase):
    """S31 終了（2026-11-05 夕方 オーナー「すべて本文にリンクにしよう今後は」）"""

    def test_flag_is_ignored_and_position_is_always_body(self):
        for flag in ("1", "on", "0"):
            with patch.dict(os.environ, {"THREADS_LINK_AB": flag}):
                self.assertEqual(sns_plan.threads_link_position({"a": {"linkPosition": "body"}}), "body")
        self.assertFalse(hasattr(sns_plan, "link_ab_on"))  # 比べは終わった（2026-11-08 に仕組みごと外した）
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            self.assertNotIn("THREADS_LINK_AB", path.read_text("utf-8"), path.name)

    def test_buffer_input_never_gets_a_link_reply(self):
        article = {**ART, "description": "d", "seoTitle": ART["title"], "_linkPosition": "reply"}
        with patch.dict(os.environ, {"THREADS_LINK_AB": "1"}):
            inp = tp.publish_via_buffer("", "t", f"{GOOD}\n\n{BODY_URL}", LINK, article, DAY, build_only=True)["input"]
        thread = inp["metadata"]["threads"]["thread"]
        self.assertEqual(len(thread), 1)
        self.assertIn("/articles/acme-tool", thread[0]["text"])

    def test_gate_rejects_link_only_in_reply_on_threads(self):
        with patch.dict(os.environ, {"THREADS_LINK_AB": "1"}):
            self.assertTrue(r.check_link("threads", GOOD, REPLY_URL, [], ["/articles/acme-tool"]))
        self.assertEqual(r.check_link("threads", f"{GOOD}\n\n{BODY_URL}", "", [], ["/articles/acme-tool"]), [])

    def test_old_reply_link_input_is_moved_to_body_before_sending(self):
        """比べの間に作った「返信にリンク」の予定は、送る直前の門番（autofix）が本文のリンクに直してから通す"""
        inp = {"channelId": "t", "text": GOOD, "mode": "customScheduled", "dueAt": "2026-11-06T03:15:00Z",
               "metadata": {"threads": {"thread": [{"text": GOOD, "assets": [{"image": {"url": CARD[0]["url"]}}]},
                                                   {"text": REPLY_URL, "assets": []}]}}}
        with patch.dict(os.environ, {"SNS_RULES_NO_ISSUE": "1"}):
            r.enforce_buffer("threads", inp, ART, source="test", history=False, measurer=lambda u: (1200, 675))
        thread = inp["metadata"]["threads"]["thread"]
        self.assertEqual(len(thread), 1)
        self.assertTrue(thread[0]["text"].endswith(BODY_URL))
        self.assertEqual(inp["text"], thread[0]["text"])

    def test_rebuild_keeps_link_in_body_even_if_record_said_reply(self):
        rec = {"linkPosition": "reply", "pending": {"inputs": {"threads": {"channelId": "t"}}, "slot": DAY.isoformat(), "fmt": "classic"}}
        article = {**ART, "description": "d", "seoTitle": ART["title"], "lede": "Acmeが会議の内容を自動でまとめるAIを公開しました。"}
        with patch.object(tp, "compose", return_value=GOOD), patch.object(r, "enforce_buffer"):
            new = tp.rebuild_pending_inputs(rec, article)
        self.assertEqual(rec["linkPosition"], "body")
        thread = new["threads"]["metadata"]["threads"]["thread"]
        self.assertEqual(len(thread), 1)
        self.assertIn("/articles/acme-tool", thread[0]["text"])


class PictureInsteadOfWaitingTest(unittest.TestCase):
    """S13（2026-11-05 夕方）: 動画を待たない・動画は限られた記事だけ"""

    def publish(self, posted, videos, now, video_posts=()):
        sent = []

        def creator(service, inp, article):
            media = r.buffer_parts(service, inp)[2]
            self.assertTrue(media, "文字だけで出そうとした")
            sent.append((service, inp["dueAt"], r.has_video(media)))
            return f"id-{service}-{len(sent)}"

        state = {"videos": videos}
        with patch.object(fu, "article_of", lambda report: ART), patch.object(sns_plan, "video_post", side_effect=lambda s, *a: s in video_posts):
            fu.publish_queued(state, {"posted": posted}, now, FLAGS, creator=creator, issue=lambda s, w: self.fail(f"issue を立てない: {w}"),
                              eligible=lambda s: True, remote=lambda s: {})
        return state, sent

    def test_gate_accepts_picture_and_rejects_text_only(self):
        body = f"{GOOD}\n\n{BODY_URL}"
        self.assertFalse([v for v in r.check_post("threads", body, CARD, ART) if "ルール8" in v])
        self.assertTrue([v for v in r.check_post("threads", body, [], ART) if "ルール8" in v])

    def test_six_slots_all_go_out_on_time_without_any_video(self):
        """枠6つ（7:15〜21:45）の投稿は、動画が1本も無くてもすべて枠の時刻に出る（1日6本＋朝のまとめは別）"""
        slots = [DAY.replace(hour=h, minute=m) for h, m in sns_plan.slots_jst()]
        self.assertLessEqual(len(slots), sns_plan.daily_cap())  # 2026-11-06〜 4枠・上限5（速報1本分の空き。S39）
        posted = {f"s{i}": queued_rec(slot.astimezone(timezone.utc)) for i, slot in enumerate(slots)}
        state = {"videos": {}}
        sent: list = []
        for slot in slots:  # 毎時の回を枠ごとに（枠の60分前）
            st, out = self.publish(posted, {}, (slot - timedelta(minutes=60)).astimezone(timezone.utc))
            for k, q in st["queued"].items():
                if q.get("status") == "created":
                    state.setdefault("queued", {})[k] = q
                    posted[k]["status"] = "scheduled"
            sent += out
        self.assertEqual(sorted(state["queued"]), sorted(posted))
        threads_due = sorted(d for s, d, _v in sent if s == "threads")
        self.assertEqual(threads_due, [fu._iso(s.astimezone(timezone.utc)) for s in slots])  # 遅れずに枠の時刻
        self.assertFalse(any(v for _s, _d, v in sent))
        self.assertTrue(all(q["media"] == "card" for q in state["queued"].values()))

    def test_video_post_waits_at_most_one_hour_then_card(self):
        slot = datetime(2026, 11, 6, 3, 15, tzinfo=timezone.utc)
        posted = {"yucho": queued_rec(slot)}
        st, sent = self.publish(posted, {}, slot + timedelta(minutes=50), video_posts={"yucho"})
        self.assertEqual((st["queued"]["yucho"]["status"], sent), ("waiting", []))
        st, sent = self.publish(posted, {}, slot + timedelta(minutes=61), video_posts={"yucho"})
        self.assertEqual(st["queued"]["yucho"]["media"], "card")
        st, sent = self.publish(posted, {"yucho": ready_video("yucho")}, slot - timedelta(minutes=30), video_posts={"yucho"})
        self.assertEqual(st["queued"]["yucho"]["media"], "video")
        self.assertEqual(sent[0][1], fu._iso(slot))

    def test_breaking_goes_out_now_with_card(self):
        rec = queued_rec(datetime(2026, 11, 6, 3, 0, tzinfo=timezone.utc))
        rec["breaking"] = True
        st, sent = self.publish({"brk": rec}, {}, datetime(2026, 11, 6, 3, 1, tzinfo=timezone.utc), video_posts={"brk"})
        self.assertEqual(st["queued"]["brk"]["media"], "card")

    def test_only_limited_articles_are_video_posts(self):
        data = {"items": [{"slug": "a", "status": "queued", "score": 9}, {"slug": "b", "status": "queued", "score": 0},
                          {"slug": "c", "status": "delivered"}, {"slug": "d", "status": "expired", "score": 9}]}
        self.assertEqual([s for s in "abcde" if sns_plan.video_post(s, data)], ["a", "c"])
        self.assertEqual(sns_plan.plan()["muse"]["max_per_day"], 2)  # 2026-11-06〜（S39）
        self.assertEqual(sns_plan.video_wait_hours(), 1.0)
        with patch.dict(os.environ, {"MUSE_WAIT_HOURS": "6"}):
            self.assertEqual(sns_plan.video_wait_hours(), 1.0)
        posted = {"posted": {s: {"postedAt": datetime(2026, 11, 6, 2, tzinfo=timezone.utc).isoformat()} for s in "ab"}}
        with patch.object(sns_plan, "load_muse_queue", return_value=data):
            got = fu.candidates(posted, {"videos": {}}, datetime(2026, 11, 6, 3, tzinfo=timezone.utc), 12,
                                load_article=lambda s: {"slug": s}, eligible=lambda a: True, score=lambda a: 1)
        self.assertEqual(got, ["a"])  # 動画を作るのは限られた記事だけ

    def test_bluesky_and_instagram_post_with_card_when_no_video(self):
        import bluesky_post as bp

        s = datetime(2026, 11, 6, 3, 15, tzinfo=timezone.utc).isoformat()
        state = {"posted": {"acme-tool": {"status": "awaiting_video", "dueAt": s, "pending": {"slot": s, "inputs": {"threads": {"text": GOOD}}}}}}
        with patch.object(bp, "video_of", return_value={}), patch.object(sns_plan, "load_muse_queue", return_value={"items": []}):
            got = bp.pending(state, datetime(2026, 11, 6, 3, 40, tzinfo=timezone.utc))
        self.assertEqual([k for k, _ in got], ["acme-tool"])
        src = (ROOT / "scripts" / "bluesky_post.py").read_text("utf-8")
        self.assertNotIn("写真では出しません", src)

    def test_no_video_reply_mechanism(self):
        """オーナー判断（返信欄は見られない）: 動画を返信で足す仕組みは作らない"""
        for name in ("sns_video_followup.py", "bluesky_post.py", "instagram_post.py", "threads_post.py"):
            src = (ROOT / "scripts" / name).read_text("utf-8")
            self.assertNotIn("video_reply_", src, name)
            self.assertNotIn('"reply": {"root"', src, name)

    def test_audit_flags_text_only_posts_not_card_posts(self):
        now = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
        at = (now - timedelta(hours=1)).isoformat()
        posted = {"posted": {"card": {"id": "1", "status": "scheduled", "dueAt": at, "image": "card"},
                             "bare": {"id": "2", "status": "scheduled", "dueAt": at, "image": ""}}}
        out = audit.video_record_problems(posted, {}, {}, now)
        self.assertEqual(len(out), 1)
        self.assertIn("bare", out[0])

    def test_presend_fixes_picture_posts_too(self):
        """写真・カードの予約も、出る前の読み直し（S38）で直す（以前は動画の無い予約を触らなかった）"""
        due = datetime(2026, 11, 6, 5, 0, tzinfo=timezone.utc)
        now = due - timedelta(hours=2)
        n = {"id": "p1", "service": "threads", "status": "scheduled", "dueAt": due.isoformat(), "text": GOOD,
             "metadata": {"thread": [{"text": GOOD, "assets": [{"mimeType": "image/png", "source": CARD[0]["url"]}]}, {"text": REPLY_URL, "assets": []}]}}
        edits = []
        reader = lambda key, pid, raise_unavailable=False: {"status": "scheduled", "dueAt": due.isoformat(), "metadata": {}}  # noqa: E731
        with patch.object(fu, "node_problems", return_value=("acme-tool", False, ["[ルール1] 本文に記事のリンクがない"])), \
                patch.object(fu, "ARTICLES", Path("/nonexistent")):
            rows = fu.presend_recheck(apply=True, now=now, api_key="k", force=True, state={"videos": {}}, posted={"posted": {}}, nodes=[n],
                                      editor=lambda k, inp, a=None, s="threads": edits.append(inp) or {"status": "scheduled", "dueAt": due.isoformat()},
                                      reader=reader, pauser=lambda k, node: {"status": "draft"}, rebuild=lambda *a: [],
                                      issue=lambda s, w: None)
        self.assertNotEqual(rows[0]["action"], "left")

def setUpModule():
    __import__("sys").path.insert(0, __import__("os").path.dirname(__file__))
    import legacy_threads  # 以前の書き方の仕組みのテスト（台帳 S46 の新しい書き方・承認待ちの止めは外す）

    legacy_threads.start()


def tearDownModule():
    import legacy_threads

    legacy_threads.stop()


if __name__ == "__main__":
    unittest.main()
