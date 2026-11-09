"""2026-11-10 7:50 オーナー決定（台帳 S54）: 投稿の時間を朝6時から夜1時台（1:59）までにする（Threads・X・Bluesky）。外部通信なし・何も投稿しない。

  1. 枠: 6時台の朝の枠と、夜0時・1時台の枠。1日15本はそのまま（S47）・投稿どうしは45分以上あける。0時・1時台は前の日の夜の続き
  2. X・Bluesky の枠の窓: 6:00〜翌1:59。2:00〜5:59 は出さない
  3. 速報の静かな時間は 2:00〜5:59（1時台は出す）。その間に作った速報（1:30〜6:00 に作ったもの）は朝6時に出す
  4. 動画の後追いも 2〜5時台だけ出さない
  5. ワークフローは朝6:33・夜0時台にも動く（UTC で書く）
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sns_plan  # noqa: E402
import sns_video_followup as fu  # noqa: E402
import threads_post as tp  # noqa: E402

JST = timezone(timedelta(hours=9))


def jst(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=JST)


class SlotsTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"SNS_PER_DAY": "", "X_PER_DAY": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_each_sns_has_six_oclock_and_late_night_slots(self):
        for name, slots in (("threads", sns_plan.slots_jst()), ("x", sns_plan.x_slots_jst()), ("bluesky", sns_plan.bluesky_slots_jst())):
            self.assertEqual(len(slots), 15, name)
            self.assertEqual(slots[0][0], 6, name)  # 朝6時台が最初の枠
            self.assertIn(slots[-1][0], (0, 1), name)  # 夜0時・1時台が最後の枠
            order = [sns_plan.day_order(s) for s in slots]
            self.assertTrue(all(b - a >= 45 for a, b in zip(order, order[1:])), name)
        self.assertIn((7, 15), sns_plan.slots_jst())  # 朝のまとめ
        self.assertEqual(sns_plan.bluesky_slots_jst(), sns_plan.slots_jst())  # Bluesky は Threads と同じ枠（2026-11-08 夜）

    def test_x_window_runs_from_six_to_one_fifty_nine(self):
        self.assertIsNone(sns_plan.x_slot_window(jst(10, 5, 59)))
        first = sns_plan.x_slot_window(jst(10, 6, 35))
        self.assertEqual((first[0], first[1].hour, first[1].minute), (0, 6, 30))
        late = sns_plan.x_slot_window(jst(11, 0, 40))  # 11/10 の夜の続き
        self.assertEqual(late[1], jst(11, 0, 30))
        self.assertEqual(late[2], jst(11, 2, 0))
        self.assertEqual(late[0], len(sns_plan.x_slots_jst()) - 1)
        self.assertIsNotNone(sns_plan.x_slot_window(jst(11, 1, 59)))
        self.assertIsNone(sns_plan.x_slot_window(jst(11, 2, 0)))
        before = sns_plan.x_slot_window(jst(10, 23, 50))  # 23:00 の枠は 0:30 の枠の前まで
        self.assertEqual(before[2], jst(11, 0, 30))

    def test_bluesky_window_and_digest_slot(self):
        self.assertIsNone(sns_plan.bluesky_slot_window(jst(10, 4, 0)))
        self.assertIsNotNone(sns_plan.bluesky_slot_window(jst(11, 1, 40)))
        self.assertEqual(sns_plan.bluesky_slot_window(jst(10, 7, 20))[0], 1)  # 7:15 は2つ目の枠（朝のまとめを写す）
        import bluesky_post as bp  # noqa: PLC0415

        slot = sns_plan.bluesky_slot_window(jst(10, 7, 20))
        with patch.object(bp, "digest_today", return_value=("digest-20261110", {"text": "t"})):
            self.assertEqual(bp.slot_pick(slot, {"posted": {}}, {}, jst(10, 7, 20), [])[2], "mirror")

    def test_facebook_unchanged(self):
        self.assertEqual(sns_plan.fb_slots_jst()[0], (7, 30))
        self.assertIsNone(sns_plan.fb_slot_window(jst(11, 0, 40)))

    def test_threads_free_slots_include_new_hours(self):
        state = {"posted": {}}
        with patch.object(tp, "DIGEST_ON", False):
            got = {s.astimezone(JST).strftime("%H:%M") for s in tp.free_slots(state, jst(10, 22, 0).astimezone(timezone.utc))}
            self.assertTrue({"00:45", "01:30"} <= got, got)
            got = {s.astimezone(JST).strftime("%H:%M") for s in tp.free_slots(state, jst(11, 2, 30).astimezone(timezone.utc))}
            self.assertIn("06:30", got)


class QuietHoursTest(unittest.TestCase):
    def test_breaking_until_one_fifty_nine(self):
        state = {"posted": {}}
        self.assertTrue(tp.breaking_allowed(state, jst(11, 1, 30)))
        self.assertFalse(tp.breaking_allowed(state, jst(11, 2, 5)))
        self.assertFalse(tp.breaking_allowed(state, jst(11, 5, 59)))
        self.assertTrue(tp.breaking_allowed(state, jst(11, 6, 0)))

    def test_morning_queue_covers_the_quiet_hours(self):
        def art(h, m):
            return {"slug": "b", "breaking": True, "generatedAt": jst(11, h, m).isoformat()}

        at6 = jst(11, 6, 5)
        self.assertTrue(tp.queued_for_morning(art(3, 0), at6))
        self.assertTrue(tp.queued_for_morning(art(1, 45), at6))  # 静かな時間の直前（デプロイ待ち）
        self.assertFalse(tp.queued_for_morning(art(0, 30), at6))  # 0時台は即時投稿で出ている
        self.assertFalse(tp.queued_for_morning(art(3, 0), jst(11, 9, 30)))  # 朝の分は9時まで
        self.assertFalse(tp.queued_for_morning(art(3, 0), jst(11, 1, 30)))

    def test_video_followup_quiet(self):
        self.assertTrue(fu.can_post_now({}, jst(11, 1, 30))[0])
        self.assertFalse(fu.can_post_now({}, jst(11, 3, 0))[0])
        self.assertTrue(fu.can_post_now({}, jst(11, 6, 30))[0])


class WorkflowTest(unittest.TestCase):
    def test_crons_cover_new_slots(self):
        for name in ("x_post", "bluesky"):
            text = (ROOT / ".github" / "workflows" / f"{name}.yml").read_text("utf-8")
            crons = re.findall(r'cron: "([^"]+)"', text)
            self.assertIn("*/10 * * * *", crons, name)
            self.assertIn("33 21 * * *", crons, name)  # 6:33 日本時間
            self.assertTrue(any(c.split()[1] in ("15", "16") for c in crons), name)  # 0時・1時台


if __name__ == "__main__":
    unittest.main()
