"""2026-11-05 オーナー承認の決定（台帳 O2・O14・S30〜S33）。ネットワークは使わない。

O2  Buffer の呼び出し: 30日の合計（全部の書き手）・ソフトの上限を超えたら優先の投稿だけ・429 は Retry-After どおり＋6時間に1回の確かめ
S30 すべての投稿の動画を Muse で（Muse の受け渡し＝SNS の予定・6本/日・期限のあとは自動動画）
S31 Threads のリンクの位置の比べ（11/5〜11/12・既定 on・utm_content で分ける・決まるまで交互）
S32 Bluesky は SNS の予定から直接出す（Buffer・Threads を待たない）
S33 出せる時刻から6時間を過ぎた投稿は遅れて出さない
O14 コメントは偉そうに絡まない・具体的な一言を入れる
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import bluesky_post as bp  # noqa: E402
import buffer_budget as bb  # noqa: E402
import comment_tone  # noqa: E402
import owner_rules_audit as audit  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules  # noqa: E402
import sns_video_followup as fu  # noqa: E402
import threads_post as tp  # noqa: E402

NOW = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)
JST = timezone(timedelta(hours=9))


def headers(**values) -> Message:
    msg = Message()
    for k, v in values.items():
        msg[k.replace("_", "-")] = v
    return msg


class Response(io.BytesIO):
    def __init__(self, payload, hdrs=None):
        super().__init__(json.dumps(payload).encode())
        self.headers = hdrs or headers()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "buffer_calls"
        for target, attr, value in ((bb, "LEDGER_DIR", self.dir), (tp, "CHANNEL_CACHE", Path(self.tmp.name) / "buffer_channels.json")):
            p = patch.object(target, attr, value)
            p.start()
            self.addCleanup(p.stop)
        env = patch.dict(os.environ, {"BUFFER_LEDGER": "video"})
        env.start()
        self.addCleanup(env.stop)
        for name in ("BUFFER_DAILY_CAP", "BUFFER_MONITOR_CAP", "BUFFER_30D_CAP", "BUFFER_30D_MONITOR_SHARE"):
            os.environ.pop(name, None)
        bb.reset_memory()
        tp._account_memo.clear()
        self.addCleanup(bb.reset_memory)

    def write(self, name, data):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{name}.json").write_text(json.dumps(data))


class ThirtyDayBudgetTest(LedgerCase):
    def test_rolling_30_days_across_all_writers(self):
        self.write("pipeline", {"day": "2026-11-05", "calls": {"book": 1, "monitor": 0},
                                "days": {"2026-11-05": {"book": 1}, "2026-10-20": {"book": 100, "monitor": 50}, "2026-10-01": {"book": 999}}})
        self.write("monitor", {"day": "2026-11-04", "calls": {"book": 0, "monitor": 7}})  # 古い形の記録もその日の分として数える
        bb.record("book", now=NOW, kind="create")
        s = bb.status(NOW)
        self.assertEqual(s["used30"], 1 + 150 + 7 + 1)  # 10/01 は30日より前
        self.assertEqual(s["kinds30"].get("create"), 1)

    def test_soft_cap_lets_only_high_priority_creates_through(self):
        with patch.dict(os.environ, {"BUFFER_30D_CAP": "100"}):
            self.write("pipeline", {"days": {"2026-11-05": {"book": 100}}})
            with self.assertRaises(bb.BufferBudgetExceeded):
                bb.check("book", NOW)
            with self.assertRaises(bb.BufferBudgetExceeded):
                with bb.priority("high"):
                    bb.check("monitor", NOW)  # 読むだけは優先でも止める
            with bb.priority("high"):
                bb.check("book", NOW)  # 優先の枠の投稿は作れる
            self.write("pipeline", {"days": {"2026-11-05": {"book": 110}}})
            with self.assertRaises(bb.BufferBudgetExceeded):
                with bb.priority("high"):
                    bb.check("book", NOW)  # ハードの上限（110%）は何も通さない

    def test_cap_follows_plan_upgrade_and_env(self):
        self.assertEqual(bb.cap_30d({}), 7000)  # Essentials（2026-11-05 夜に変更）
        self.assertEqual(bb.cap_30d({"2592000": {"q": "15000", "r": "15000"}}), 12000)  # Buffer の30日の上限の8割
        with patch.dict(os.environ, {"BUFFER_30D_CAP": "2400"}):
            self.assertEqual(bb.cap_30d({"2592000": {"q": "15000"}}), 2400)

    def test_buffer_reported_usage_wins_when_higher(self):
        h = headers(RateLimit='"m";r=100;t=99999', RateLimit_Policy='"m";q=7500;w=2592000')
        bb.record("book", h, now=NOW)
        self.assertEqual(bb.status(NOW)["used30"], 7400)
        with self.assertRaises(bb.BufferBudgetExceeded):
            bb.check("book", NOW)

    def test_monitor_share(self):
        with patch.dict(os.environ, {"BUFFER_30D_CAP": "100"}):
            self.write("monitor", {"days": {"2026-11-04": {"monitor": 15}}})
            with self.assertRaises(bb.BufferBudgetExceeded):
                bb.check("monitor", NOW)
            bb.check("book", NOW)


class RetryAfterAndProbeTest(LedgerCase):
    BODY = '{"errors":[{"extensions":{"code":"RATE_LIMIT_EXCEEDED","window":"30d"}}]}'

    def test_30d_429_is_honored_in_full_and_probe_every_6h(self):
        until = bb.record_429(headers(Retry_After="1406281"), self.BODY, now=NOW)
        self.assertEqual(until, NOW + timedelta(seconds=1406281))  # 7日で切らない（約16日）
        self.assertFalse(bb.probe_due(NOW + timedelta(hours=5)))
        self.assertTrue(bb.probe_due(NOW + timedelta(hours=6)))
        with self.assertRaises(bb.BufferRateLimited):
            bb.check("book", NOW + timedelta(hours=7))  # ふつうの呼び出しは止めたまま
        bb.check("book", NOW + timedelta(hours=7), probe=True)  # 確かめの1回だけ通る
        bb.mark_probe(NOW + timedelta(hours=7))
        self.assertFalse(bb.probe_due(NOW + timedelta(hours=8)))
        self.assertEqual(bb.next_probe_at(NOW + timedelta(hours=8)), NOW + timedelta(hours=13))

    def test_successful_call_after_429_clears_every_writers_block(self):
        self.write("pipeline", {"blockedUntil": (NOW + timedelta(days=10)).isoformat(), "last429": {"at": NOW.isoformat(), "window": "30d"}})
        self.assertTrue(bb.status(NOW + timedelta(hours=7))["blockedUntil"])
        bb.record("book", now=NOW + timedelta(hours=7), kind="probe")  # 確かめが通った（プランを上げた）
        self.assertIsNone(bb.status(NOW + timedelta(hours=7, minutes=1))["blockedUntil"])
        self.assertEqual(bb.status(NOW + timedelta(hours=7, minutes=1))["kinds30"]["probe"], 1)  # 確かめも回数に数える
        self.assertEqual(bb.clear_blocks(NOW + timedelta(hours=7)), ["pipeline.json"])
        self.assertIsNone(json.loads((self.dir / "pipeline.json").read_text())["blockedUntil"])

    def test_probe_through_graphql(self):
        bb.record_429(headers(Retry_After="1406281"), self.BODY, now=datetime.now(timezone.utc) - timedelta(hours=7))
        err = urllib.error.HTTPError(tp.BUFFER_API, 429, "Too Many", headers(Retry_After="900000"), io.BytesIO(self.BODY.encode()))
        with patch.object(tp.urllib.request, "urlopen", side_effect=err) as opened:
            res = tp.buffer_probe("k")
            self.assertTrue(res["probed"] and not res["ok"])
            self.assertEqual(tp.buffer_probe("k"), {"probed": False, "ok": False, "detail": "確かめの時刻ではない"})
        self.assertEqual(opened.call_count, 1)
        saved = json.loads((self.dir / "video.json").read_text())
        self.assertEqual(saved["probe"]["result"], "429")
        self.assertEqual(saved["last429"]["retryAfter"], "900000")
        with patch.object(tp.urllib.request, "urlopen", side_effect=lambda *a, **k: Response({"data": {"account": {"organizations": []}}})):
            res = tp.buffer_probe("k", force=True)  # 手で頼んだ1回（6時間を待たない）
        self.assertTrue(res["ok"])
        self.assertIsNone(bb.status()["blockedUntil"])


class FewerCallsTest(LedgerCase):
    def test_duplicate_check_reads_all_channels_once(self):
        calls = []
        chans = {"threads": {"id": "t"}, "twitter": {"id": "x"}, "facebook": {"id": "f"}}

        def fake(key, query, variables=None):
            calls.append(query)
            return {"posts": {"edges": [{"node": {"id": "p1", "channelId": "x", "text": "https://ai-tech-express.jp/articles/a"}}]}}

        tp._BUFFER_RECENT.clear()
        with patch.object(tp, "buffer_channels", return_value=chans), patch.object(tp, "buffer_org_ids", return_value=["org"]):
            self.assertEqual(tp.recent_channel_posts("k", "t", fake), [])
            self.assertEqual(tp.recent_channel_posts("k", "x", fake)[0][0], "p1")
            tp.recent_channel_posts("k", "f", fake)
        self.assertEqual(len(calls), 1)  # 投稿1本・3つの SNS で1回（以前は3回）

    def test_stale_channel_cache_is_used_while_blocked(self):
        tp.CHANNEL_CACHE.write_text(json.dumps({"fetchedAt": "2026-09-01T00:00:00+00:00", "orgs": [{"id": "o", "channels": [{"id": "t", "service": "threads"}]}]}))
        bb.record_429(headers(Retry_After="99999"), "", now=datetime.now(timezone.utc))
        with patch.object(tp, "buffer_graphql", side_effect=AssertionError("呼ばない")):
            self.assertEqual(tp.buffer_channels("k")["threads"]["id"], "t")

    def test_monitor_runs_twice_a_day_and_every_buffer_workflow_saves_its_ledger(self):
        wf = ROOT / ".github" / "workflows"
        self.assertIn("'12 0,11 * * *'", (wf / "buffer_delivery_monitor.yml").read_text())
        for path in sorted(wf.glob("*.yml")):
            src = path.read_text("utf-8")
            for name in set(re.findall(r"BUFFER_LEDGER: ([\w-]+)", src)):
                if name == "post-now":
                    continue  # git add state（全部）
                self.assertTrue(f"state/buffer_calls/{name}.json" in src or "git add state\n" in src or "f=state/buffer_calls" in src,
                                f"{path.name}: 呼び出し回数 {name} を main に残していない")


# 2026-11-09 から投稿は動画を待たない（muse.wait_hours=0・台帳 S48）。待ちの仕組みそのものは前の1時間で確かめる
@__import__("unittest.mock").mock.patch.dict(__import__("sns_plan").plan()["muse"], {"wait_hours": 1, "max_wait_hours": 1})
class PublishQueuedTest(unittest.TestCase):
    SLOT = datetime(2026, 11, 5, 3, 15, tzinfo=timezone.utc)

    def rec(self):
        s = self.SLOT.isoformat()
        return {"id": "", "status": "awaiting_video", "dueAt": s, "pending": {"slot": s, "inputs": {"threads": {"channelId": "t", "text": "x"}}}}

    def video(self):
        return {"status": "ready", "urls": {"short": "https://ai-tech-express.jp/video/a.mp4"},
                "versions": {"short": {"ok": True, "post": {"url": "https://ai-tech-express.jp/articles/yucho"}}}}

    def run_publish(self, now, items, creator):
        with patch.object(sns_plan, "load_muse_queue", return_value={"items": items}), patch.object(fu, "qa_ok", return_value=True), \
                patch.object(fu, "probe_buffer", return_value={"probed": False}), patch.object(fu, "video_input", side_effect=lambda *a: {}):
            return fu.publish_queued({"videos": {"yucho": self.video()}}, {"posted": {"yucho": self.rec()}}, now,
                                     {"post": True, "ab_until": "", "after_ab": "short"}, creator=creator,
                                     issue=lambda *a: self.fail("issue を立てない"), eligible=lambda s: True, remote=lambda s: {})

    def test_waits_for_muse_even_if_auto_video_is_ready(self):
        # 2026-11-05 夕方〜: Muse を待つのは動画を作る限られた記事（点数のある項目）だけで、枠から1時間まで
        item = {"slug": "yucho", "status": "queued", "queuedAt": self.SLOT.isoformat(), "score": 9}
        out = self.run_publish(self.SLOT + timedelta(minutes=30), [item], lambda *a: self.fail("まだ送らない"))
        self.assertIn("Muse の動画", out[0]["why"])
        sent = []
        out = self.run_publish(self.SLOT + timedelta(hours=1, minutes=5), [item], lambda s, i, a: sent.append(s) or "id1")
        self.assertEqual(sent, ["threads"])  # 期限のあとは自動動画で出す（本数を減らさない）
        self.assertEqual(out[0]["media"], "video")

    def test_stale_post_is_dropped_not_posted_late(self):
        out = self.run_publish(self.SLOT + timedelta(hours=6, minutes=5), [], lambda *a: self.fail("遅れて出さない"))
        self.assertEqual(out[0]["status"], "skipped")
        self.assertTrue(out[0]["stale"])

    def test_priority_is_set_while_creating(self):
        seen = []
        self.run_publish(self.SLOT + timedelta(minutes=5), [], lambda s, i, a: seen.append(bb.current_priority()) or "id")
        self.assertEqual(seen, [sns_plan.slot_priority(self.SLOT, {}, False)])
        self.assertEqual(sns_plan.slot_priority(datetime(2026, 11, 5, 3, 15, tzinfo=timezone.utc), {}), "high")  # 12:15 JST
        self.assertEqual(sns_plan.slot_priority(datetime(2026, 11, 4, 23, 10, tzinfo=timezone.utc), {}), "normal")  # 8:10 JST
        self.assertEqual(sns_plan.slot_priority(None, {}, breaking=True), "high")


class BlueskyDirectTest(unittest.TestCase):
    SLOT = datetime(2026, 11, 5, 3, 15, tzinfo=timezone.utc)

    def state(self, **extra):
        s = self.SLOT.isoformat()
        return {"posted": {"yucho": {"status": "awaiting_video", "dueAt": s, "postedAt": s, "pending": {"slot": s, "inputs": {"threads": {
            "text": "ゆうちょ銀行を使う人に関係する話です。\n\n要約すると、松井証券と提携します。\n\n詳しくはこちら👇\nhttps://ai-tech-express.jp/articles/yucho?utm_source=threads"}}}, **extra}}}

    def test_posts_from_plan_without_waiting_for_buffer(self):
        with patch.object(bp, "video_of", return_value={"url": "u", "variant": "short"}), patch.object(bp, "muse_until", return_value=None), \
                patch.object(sns_plan, "load_muse_queue", return_value={"items": []}):
            self.assertEqual(bp.pending(self.state(), self.SLOT + timedelta(minutes=10)), [])  # 枠＋20分まで待つ
            got = bp.pending(self.state(), self.SLOT + timedelta(minutes=25))
            self.assertEqual([k for k, _ in got], ["yucho"])  # Buffer は止まったまま（Threads はまだ動画待ち）でも出す
            self.assertEqual(bp.pending(self.state(channels={"bluesky": "at://x"}), self.SLOT + timedelta(minutes=25)), [])  # 二重に出さない
            self.assertEqual(bp.pending(self.state(), self.SLOT + timedelta(hours=7)), [])  # 古いものは出さない

    def test_waits_for_muse_and_video(self):
        # 2026-11-05 夕方 オーナー「動画を待たない」: 動画が無くても枠＋20分に出す（記事の写真のリンクカード）
        with patch.object(bp, "video_of", return_value={}), patch.object(sns_plan, "load_muse_queue", return_value={"items": []}):
            self.assertEqual([k for k, _ in bp.pending(self.state(), self.SLOT + timedelta(minutes=25))], ["yucho"])
        # 動画を作る限られた記事だけ、Muse の待ちの期限（枠＋1時間）まで待つ
        with patch.object(bp, "video_of", return_value={"url": "u", "variant": "short"}), patch.object(bp, "muse_until", return_value=self.SLOT + timedelta(hours=1)):
            self.assertEqual(bp.pending(self.state(), self.SLOT + timedelta(minutes=25)), [])

    def test_text_is_the_planned_threads_text_without_link(self):
        text = bp.planned_text(self.state()["posted"]["yucho"])
        self.assertNotIn("http", text)
        self.assertNotIn("詳しくはこちら", text)
        self.assertTrue(text.startswith("ゆうちょ銀行を使う人"))

    def test_link_card_only_when_bluesky_rejects_the_video(self):
        art = {"slug": "acme", "title": "Acme が新しいAIツールを公開", "genreSlug": "ai"}
        img = [{"type": "image", "url": "https://ai-tech-express.jp/card/acme", "width": 1200, "height": 675}]
        rule8 = lambda v: [x for x in v if x.startswith("[ルール8]")]  # noqa: E731
        # 2026-11-05 夕方〜: どの SNS も記事の写真のカードで出してよい（文字だけは止める）
        for platform in ("bluesky", "threads"):
            self.assertFalse(rule8(sns_rules.check_post(platform, "x", img, art)), platform)
            self.assertTrue(rule8(sns_rules.check_post(platform, "x", [], art)), platform)


# 2026-11-09 から投稿は動画を待たない（muse.wait_hours=0・台帳 S48）。待ちの仕組みそのものは前の1時間で確かめる
@__import__("unittest.mock").mock.patch.dict(__import__("sns_plan").plan()["muse"], {"wait_hours": 1, "max_wait_hours": 1})
class FlagsTest(unittest.TestCase):
    def test_flags_default_on_in_every_workflow(self):
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            self.assertNotIn("THREADS_LINK_AB", path.read_text("utf-8"), path.name)  # S31 は 2026-11-05 夕方に終了（変数は読まない）
            for flag in ("SNS_HOOK_FORMAT",):
                for m in re.finditer(rf"{flag}: \$\{{\{{ vars\.{flag} \|\| '(\d)' \}}\}}", path.read_text("utf-8")):
                    self.assertEqual(m.group(1), "1", f"{path.name} {flag}")
        for name in ("auto_run.yml", "sns_video.yml", "bluesky.yml", "breaking_post.yml", "sns_recover.yml", "threads_publish.yml"):
            src = (ROOT / ".github" / "workflows" / name).read_text("utf-8")
            self.assertIn("SNS_HOOK_FORMAT: ${{ vars.SNS_HOOK_FORMAT || '1' }}", src, name)

    def test_x_keeps_the_classic_text_when_hook_format_is_on(self):
        # 2026-11-05: フラグを有効にした最初の回で、X に Muse の型の文面を渡して門番に止められ、記事ごと出せなくなった
        self.assertEqual(tp.x_root_text({"_hookFormat": True}, "型の3行", "今の形"), "今の形")
        self.assertEqual(tp.x_root_text({}, "今の形", "今の形"), "今の形")
        src = (ROOT / "scripts" / "threads_post.py").read_text("utf-8")
        self.assertIn("x_root_text(article, text, classic_text)", src)

    def test_link_ab_week_and_reminder(self):
        # 2026-11-05 夕方 オーナー決定「すべて本文にリンクにしよう今後は」で比べは終了（decided=body。変数が 1 でも本文）
        self.assertNotIn("link_ab", sns_plan.plan())  # 2026-11-08 に比べの記録ごと外した
        with patch.dict(os.environ, {"THREADS_LINK_AB": "1"}):
            self.assertEqual(sns_plan.threads_link_position({"a": {"linkPosition": "body"}}), "body")
        self.assertEqual(sns_plan.utm_content("video", "reply"), "video_reply")  # 2つの組を utm_content で分ける
        self.assertEqual(sns_plan.utm_content("video", "body"), "video_body")

    def test_muse_queue_is_the_sns_plan(self):
        m = sns_plan.plan()["muse"]
        self.assertEqual((m["max_per_day"], m["wait_hours"], m["max_wait_hours"]), (2, 1, 1))  # 2026-11-06 テストの日から2本（S39）  # 2026-11-05 夕方 オーナー「動画を作る記事を限定」
        self.assertIn("muse_queue.py", (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8"))


class CommentToneTest(unittest.TestCase):
    def test_condescending_or_empty_comments_are_flagged(self):
        self.assertEqual(comment_tone.problems("Claude の新しいプラン、公式の発表では上限が5倍とあって驚きました。個人の利用でも効きそうですね。"), [])
        self.assertTrue(comment_tone.problems("それは違います。正しくは API の話です"))
        self.assertTrue(comment_tone.problems("知らないんですか？常識ですよ"))
        self.assertTrue(comment_tone.problems("すごいです！"))  # 具体的な一言が無い
        self.assertTrue(comment_tone.problems("公式の数字は 20% だよ"))  # です・ます でない
        log = [{"date": "2026-11-05", "time": "12:00", "sns": "threads", "text": "勉強不足ですね。"}]
        self.assertTrue(any(p.startswith("[O14]") for p in audit.comment_log_problems(log)))


if __name__ == "__main__":
    unittest.main()
