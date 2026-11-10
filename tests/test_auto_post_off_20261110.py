"""2026-11-10 オーナー決定「自動投稿は伸びない。今後は全て手投稿にしよう」: 記事の自動投稿を SNS ごとのスイッチ（sns_plan.json の auto_post）で止める。
本物の設定（本番の sns_plan.json）で、Threads・X・Bluesky・Facebook のすべてが止まっていて、手で出す経路（図の投稿）は止まらないことを確かめる。"""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import conftest  # noqa: E402
import sns_plan  # noqa: E402
import threads_gate  # noqa: E402
import threads_post as tp  # noqa: E402


class RealSwitch(unittest.TestCase):
    def setUp(self):
        conftest.AUTO_POST_REAL["on"] = True

    def tearDown(self):
        conftest.AUTO_POST_REAL["on"] = False

    def test_config_is_off_for_every_service(self):
        block = json.loads((ROOT / "scripts" / "sns_plan.json").read_text("utf-8"))["auto_post"]
        for key in ("threads", "x", "bluesky", "facebook", "instagram", "alerts"):
            self.assertIs(block[key], False, key)
        for service in ("threads", "twitter", "x", "bluesky", "facebook", "instagram"):
            self.assertFalse(sns_plan.auto_post_on(service), service)
            self.assertIn("auto_post", sns_plan.auto_post_off_reason(service, None, "x_post"))
        self.assertFalse(sns_plan.auto_post_on("threads", {"disaster": True, "title": "地震"}))  # 急ぎの知らせも alerts が false なら出さない

    def test_manual_figure_posts_are_not_stopped(self):
        self.assertEqual(sns_plan.auto_post_off_reason("threads", None, "threads_figure_queue"), "")
        self.assertEqual(sns_plan.auto_post_off_reason("threads", None, "threads_control_post"), "")

    def test_switch_back_on_per_service(self):
        real = conftest._REAL_PLAN()
        on = {**real, "auto_post": {**real["auto_post"], "x": True}}
        with patch.object(sns_plan, "plan", lambda: on):
            self.assertTrue(sns_plan.auto_post_on("twitter"))
            self.assertFalse(sns_plan.auto_post_on("threads"))
            self.assertFalse(sns_plan.auto_post_on("bluesky"))

    def test_create_post_refuses_without_calling_buffer(self):
        for service, source in (("threads", "threads_post.publish_via_buffer"), ("twitter", "x_post"), ("facebook", "facebook_post"),
                                ("threads", "sns_video_followup.publish_queued"), ("threads", "morning_digest")):
            with patch.object(tp, "buffer_graphql", side_effect=AssertionError("Buffer を呼んだ")):
                with self.assertRaises(threads_gate.AutoPostOff):
                    tp.create_post("key", {"channelId": "c", "text": "x"}, service=service, article={"slug": "a"}, source=source)

    def test_publish_queued_skips_pending_without_sending(self):
        import sns_video_followup as fu

        posted = {"posted": {"kirin": {"status": "awaiting_video", "id": "", "dueAt": "2026-11-10T10:45:00+00:00",
                                       "pending": {"slot": "2026-11-10T10:45:00+00:00", "inputs": {"threads": {"channelId": "c", "text": "t"}}}}}}
        state = {}
        sent = []
        with patch.object(fu, "probe_buffer", return_value={}):
            out = fu.publish_queued(state, posted, datetime(2026, 11, 10, 9, 30, tzinfo=timezone.utc), {"post": True},
                                    creator=lambda *a, **k: sent.append(a) or "id", issue=lambda *a, **k: None,
                                    eligible=lambda *a, **k: True, remote=lambda *a, **k: [])
        self.assertEqual(sent, [])
        self.assertEqual(state["queued"]["kirin"]["status"], "skipped")
        self.assertTrue(state["queued"]["kirin"]["autoPostOff"])
        self.assertEqual(out[0]["slug"], "kirin")


if __name__ == "__main__":
    unittest.main()
