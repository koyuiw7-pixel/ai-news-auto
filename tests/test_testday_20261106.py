"""2026-11-06 テストの日（台帳 S39）。外部通信なし・何も投稿しない。

オーナー承認（2026-11-06 01:00 JST）「外してもいいよ。ただし郵貯の時のように動画の質はかなりこだわってほしい。…
明日はそういったテストをして分析をする日にするんだね。それならとにかく法則を見つけるため奔走して」

  1. Threads のリンクの位置はリポジトリの変数 THREADS_LINK_POS（reply / body。空なら body）。すべての経路（通常・動画・速報・朝のまとめ・
     門番・送る前の autofix・出る前の読み直し・作り直し）で同じ。切り替えたら次の送信で効く（予約中の投稿も直す）
  2. 決まった動画の案内の行（「◯秒の動画で解説しています。」）を足さない・予約中の文面からも外す（音声のクレジットは残す）
  3. 通常の枠は 07:15（朝のまとめ）・12:15・18:45・20:30、1日5本まで（速報1本分の空き）
  4. Muse の動画は1日2本まで
  5. 決算・株の話題は Threads に1日2本まで

  python3 -m unittest tests.test_testday_20261106
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

import morning_digest as md  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules as r  # noqa: E402
import sns_video_followup as fu  # noqa: E402
import threads_post as tp  # noqa: E402
from test_sns_video_required import ART, CARD, GOOD, LINK  # noqa: E402

JST = timezone(timedelta(hours=9))
DAY = datetime(2026, 11, 6, 3, 15, tzinfo=timezone.utc)
BODY_URL = f"{LINK}?utm_source=threads&utm_medium=social&utm_campaign=classic&utm_content=video_body"
REPLY_URL = BODY_URL.replace("video_body", "video_reply")
PATHS = ["/articles/acme-tool"]
REPLY = {"THREADS_LINK_POS": "reply", "SNS_RULES_NO_ISSUE": "1"}
BODY = {"THREADS_LINK_POS": "body", "SNS_RULES_NO_ISSUE": "1"}
POSTING_WORKFLOWS = ("auto_run", "breaking_post", "sns_video", "sns_recover", "threads_publish", "post_now", "release_watch", "sns_extra")


def body_input(text: str = "") -> dict:
    text = text or f"{GOOD}\n\n{BODY_URL}"
    return {"channelId": "t", "text": text, "mode": "customScheduled", "dueAt": "2026-11-06T03:15:00Z",
            "metadata": {"threads": {"thread": [{"text": text, "assets": [{"image": {"url": CARD[0]["url"]}}]}]}}}


def reply_input() -> dict:
    return {"channelId": "t", "text": GOOD, "mode": "customScheduled", "dueAt": "2026-11-06T03:15:00Z",
            "metadata": {"threads": {"thread": [{"text": GOOD, "assets": [{"image": {"url": CARD[0]["url"]}}]},
                                                {"text": REPLY_URL, "assets": []}]}}}


class LinkPositionVariableTest(unittest.TestCase):
    def test_variable_values_and_default(self):
        with patch.dict(os.environ, {"THREADS_LINK_POS": ""}):
            self.assertEqual(sns_plan.threads_link_position(), "body")  # 空なら 11/5 の決まり（本文）
        for raw, want in (("reply", "reply"), ("REPLY ", "reply"), ("body", "body"), ("both", "body")):
            with patch.dict(os.environ, {"THREADS_LINK_POS": raw}):
                self.assertEqual(sns_plan.threads_link_position(), want)

    def test_every_posting_workflow_passes_the_variable(self):
        for name in POSTING_WORKFLOWS:
            text = (ROOT / ".github" / "workflows" / f"{name}.yml").read_text("utf-8")
            self.assertIn("THREADS_LINK_POS: ${{ vars.THREADS_LINK_POS || 'body' }}", text, name)

    def test_reply_mode_moves_body_link_to_one_reply_before_sending(self):
        inp = body_input()
        with patch.dict(os.environ, REPLY):
            r.enforce_buffer("threads", inp, ART, source="test", history=False, measurer=lambda u: (1200, 675))
        thread = inp["metadata"]["threads"]["thread"]
        self.assertEqual(len(thread), 2)
        self.assertNotIn("http", thread[0]["text"])
        self.assertEqual(thread[1]["text"], REPLY_URL)  # utm_content は video_reply
        self.assertEqual(inp["text"], thread[0]["text"])
        self.assertTrue(thread[0]["assets"])  # 写真・動画は本文のまま

    def test_body_mode_moves_reply_link_back_to_body(self):
        inp = reply_input()
        with patch.dict(os.environ, BODY):
            r.enforce_buffer("threads", inp, ART, source="test", history=False, measurer=lambda u: (1200, 675))
        thread = inp["metadata"]["threads"]["thread"]
        self.assertEqual(len(thread), 1)
        self.assertTrue(thread[0]["text"].endswith(BODY_URL))

    def test_gate_accepts_reply_only_link_only_in_reply_mode(self):
        with patch.dict(os.environ, REPLY):
            self.assertEqual(r.check_link("threads", GOOD, REPLY_URL, [], PATHS), [])
            self.assertTrue(r.check_link("threads", GOOD, "", [], PATHS))  # どこにもリンクが無いのは止める
            self.assertTrue(r.reply_counted("threads"))
        with patch.dict(os.environ, BODY):
            self.assertTrue(r.check_link("threads", GOOD, REPLY_URL, [], PATHS))
            self.assertFalse(r.reply_counted("threads"))
        self.assertTrue(r.reply_counted("x"))

    def test_x_and_facebook_are_not_reshaped(self):
        with patch.dict(os.environ, REPLY):
            self.assertEqual(r.reshape_threads_link("facebook", body_input()), "")
            self.assertEqual(r.reshape_threads_link("twitter", body_input()), "")

    def test_link_inside_a_sentence_is_left_alone(self):
        text = f"{GOOD}\n\n記事 {BODY_URL} を読んでください"
        self.assertEqual(r.split_body_link_texts([text]), [text])

    def test_queue_for_video_stores_the_current_shape(self):
        article = {**ART, "description": "d", "seoTitle": ART["title"]}
        with patch.dict(os.environ, REPLY), patch.object(r, "enforce_buffer"):
            out = tp.queue_for_video("", {"threads": {"id": "t"}}, f"{GOOD}\n\n{BODY_URL}", GOOD, LINK, article, DAY)
        thread = out["pending"]["inputs"]["threads"]["metadata"]["threads"]["thread"]
        self.assertEqual(len(thread), 2)
        self.assertIn("utm_content=video_reply", thread[1]["text"])

    def test_rebuild_records_current_position(self):
        rec = {"linkPosition": "body", "pending": {"inputs": {"threads": {"channelId": "t"}}, "slot": DAY.isoformat(), "fmt": "classic"}}
        article = {**ART, "description": "d", "seoTitle": ART["title"], "lede": "Acmeが会議の内容を自動でまとめるAIを公開しました。"}
        with patch.dict(os.environ, REPLY), patch.object(tp, "compose", return_value=GOOD), patch.object(r, "enforce_buffer"):
            new = tp.rebuild_pending_inputs(rec, article)
        self.assertEqual(rec["linkPosition"], "reply")
        self.assertEqual(len(new["threads"]["metadata"]["threads"]["thread"]), 2)

    def test_video_input_swaps_reply_link_to_video_version(self):
        inp = reply_input()
        report = {"url": LINK, "total": 40, "level": "MUSE"}
        out = fu.video_input("threads", inp, report, "short", "https://v.example/x.mp4")
        thread = out["metadata"]["threads"]["thread"]
        self.assertIn("utm_campaign=sns_video_short&utm_content=video_reply", thread[1]["text"])
        self.assertNotIn("動画で解説", thread[0]["text"])


class PresendFlipTest(unittest.TestCase):
    """変数を切り替えたら、予約中の Threads の投稿は次の出る前の読み直しで今の位置に直る（消さない・時刻はそのまま）"""

    def node(self, texts):
        return {"id": "p1", "service": "threads", "status": "scheduled", "dueAt": "2026-11-06T03:15:00Z", "channelId": "t",
                "text": texts[0], "assets": [], "metadata": {"thread": [{"text": t, "assets": []} for t in texts]}}

    def setUp(self):
        import json
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.arts = Path(tmp.name)
        (self.arts / "acme-tool.json").write_text(json.dumps({**ART, "description": "d"}, ensure_ascii=False), "utf-8")

    def run_presend(self, node, env):
        edits = []
        now = datetime(2026, 11, 6, 1, 0, tzinfo=timezone.utc)
        with patch.dict(os.environ, env), patch.object(fu, "ARTICLES", self.arts), patch.object(r, "ARTICLES_DIR", self.arts):
            rows = fu.presend_recheck(apply=True, now=now, api_key="k", force=True, state={"videos": {}}, posted={"posted": {}},
                                      nodes=[node], editor=lambda k, inp, *a: edits.append(inp) or {"status": "scheduled", "dueAt": node["dueAt"]},
                                      reader=lambda k, i, **kw: {"status": "scheduled", "metadata": {}},
                                      pauser=lambda *a: self.fail("下書きに戻さない"), issue=lambda s, w: None,
                                      rebuild=lambda *a: self.fail("作り直さない"))
        return rows, edits

    def test_body_to_reply(self):
        rows, edits = self.run_presend(self.node([f"{GOOD}\n\n{BODY_URL}"]), REPLY)
        self.assertEqual(len(edits), 1, rows)
        thread = edits[0]["metadata"]["threads"]["thread"]
        self.assertEqual([t["text"] for t in thread], [GOOD, REPLY_URL])
        self.assertNotIn("dueAt", edits[0])

    def test_reply_to_body(self):
        rows, edits = self.run_presend(self.node([GOOD, REPLY_URL]), BODY)
        self.assertEqual(len(edits), 1, rows)
        thread = edits[0]["metadata"]["threads"]["thread"]
        self.assertEqual(len(thread), 1)
        self.assertTrue(thread[0]["text"].endswith(BODY_URL))

    def test_already_right_shape_is_not_edited(self):
        _rows, edits = self.run_presend(self.node([GOOD, REPLY_URL]), REPLY)
        self.assertEqual(edits, [])

    def test_rules_version_changes_with_the_variable(self):
        with patch.dict(os.environ, REPLY):
            a = fu.rules_version()
        with patch.dict(os.environ, BODY):
            b = fu.rules_version()
        self.assertNotEqual(a, b)  # 読み直し済みの予約も、切り替えたらもう一度見る

    def test_old_video_line_is_removed_from_scheduled_post(self):
        text = f"{GOOD}\n40秒の動画で解説しています。\n\n{BODY_URL}"
        _rows, edits = self.run_presend(self.node([text]), BODY)
        self.assertEqual(len(edits), 1)
        self.assertNotIn("動画で解説", edits[0]["metadata"]["threads"]["thread"][0]["text"])


class DigestThreadTest(unittest.TestCase):
    POST = {"text": "今朝のAIニュース3本（2026/11/06）\n\n・OpenAIが新しい音声モデルを公開\n・ソニーがAI機能付きの新型カメラを発表\n・トヨタがAIの会社と提携",
            "link": "https://ai-tech-express.jp/digest/20261106", "items": ["a", "b", "c"], "reply": md.REPLY_LINES[0],
            "image": "https://ai-tech-express.jp/digest/20261106/share.png"}

    def test_reply_mode_is_a_short_thread_with_link_last(self):
        with patch.dict(os.environ, REPLY):
            inp = md.threads_input("t", self.POST, {"mode": "customScheduled"})
            text, reply, media, _ = r.buffer_parts("threads", inp)
            self.assertEqual(r.check_post("threads", text, media, md.gate_article(self.POST), kind="digest", reply_text=reply), [])
        thread = inp["metadata"]["threads"]["thread"]
        self.assertGreaterEqual(len(thread), 3)
        self.assertNotIn("http", thread[0]["text"])
        self.assertTrue(thread[0]["text"].endswith("、"))  # 文の途中で終えて続きを開いてもらう
        self.assertNotIn("！", thread[0]["text"])
        self.assertIn("utm_content=digest_reply", thread[-1]["text"])
        self.assertTrue(all("http" not in t["text"] for t in thread[:-1]))

    def test_body_mode_keeps_link_in_body(self):
        with patch.dict(os.environ, BODY):
            inp = md.threads_input("t", self.POST, {"mode": "customScheduled"})
        thread = inp["metadata"]["threads"]["thread"]
        self.assertEqual(len(thread), 1)
        self.assertIn("utm_content=digest_body", thread[0]["text"])


class VideoLineTest(unittest.TestCase):
    def test_merged_text_adds_no_video_line_but_keeps_credit(self):
        report = {"url": LINK, "total": 40, "level": "L1", "voice": {"credit": "VOICEVOX:九州そら"}}
        new, notes = fu.merged_text(f"{GOOD}\n\n{BODY_URL}", report, "short")
        self.assertNotIn("動画で解説", new)
        self.assertFalse(notes["line"])
        self.assertTrue(new.endswith("音声：VOICEVOX:九州そら"))

    def test_autofix_strips_old_line_on_every_service(self):
        for service in ("threads", "twitter", "facebook"):
            inp = body_input(f"{GOOD}\n公式ページの画面を見ながら、35秒の動画で解説しています。\n\n{BODY_URL}")
            with patch.dict(os.environ, BODY):
                r.autofix_buffer_input(service, inp, ART)
            self.assertNotIn("動画で解説", inp["text"], service)


class SlotsCapMuseTest(unittest.TestCase):
    def test_plan_numbers(self):
        self.assertEqual(sns_plan.slots_jst(), [(7, 15), (12, 15), (18, 45), (20, 30)])
        self.assertEqual(sns_plan.digest_slot_jst(), (7, 15))
        self.assertEqual(sns_plan.daily_cap(), 5)
        self.assertEqual(sns_plan.plan()["muse"]["max_per_day"], 2)

    def test_breaking_still_has_room_after_full_normal_day(self):
        """朝のまとめ＋3枠＝4本を予約しても、08:30 の速報（毎月勤労統計など）1本分の空きがある"""
        day = datetime(2026, 11, 6, tzinfo=JST).date()
        posted = {"digest-20261106": {"id": "d", "style": "digest", "dueAt": "2026-11-05T22:15:00+00:00"}}
        posted.update({f"s{h}": {"id": f"s{h}", "dueAt": datetime(2026, 11, 6, h, m, tzinfo=JST).isoformat()} for h, m in ((12, 15), (18, 45), (20, 30))})
        self.assertEqual(sns_plan.cap_left(posted, day, set()), 1)


class FinanceCapTest(unittest.TestCase):
    def test_topic(self):
        self.assertTrue(sns_plan.finance_topic({"title": "トヨタが決算を発表、純利益は過去最高"}))
        self.assertTrue(sns_plan.finance_topic({"title": "ソニーが自社株買いを発表"}))
        self.assertTrue(sns_plan.finance_topic({"title": "A社がB社にTOB"}))
        self.assertFalse(sns_plan.finance_topic({"title": "株式会社ACMEが新しいAIを公開"}))
        self.assertFalse(sns_plan.finance_topic({"title": "毎月勤労統計 9月の実質賃金"}))
        self.assertEqual(sns_plan.finance_cap(), 2)

    def test_third_finance_post_of_the_day_is_skipped(self):
        day = datetime(2026, 11, 6, tzinfo=JST).date()
        posted = {f"f{i}": {"id": f"f{i}", "title": f"会社{i}の決算", "dueAt": datetime(2026, 11, 6, 9 + i, tzinfo=JST).isoformat()} for i in range(2)}
        art = {"slug": "f3", "title": "会社3の決算、営業利益が増加"}
        self.assertTrue(sns_plan.finance_full(art, posted, day))
        self.assertFalse(sns_plan.finance_full({"slug": "n", "title": "新しいスマホ"}, posted, day))
        self.assertFalse(sns_plan.finance_full(art, {"f0": posted["f0"]}, day))
        self.assertFalse(sns_plan.finance_full(art, posted, day.replace(day=7)))  # 次の日はまた出せる


class ControlPostTest(unittest.TestCase):
    """リンク無しの比べの投稿（オーナー・Muse 案 11/6 01:35。scripts/threads_control_post.py）"""

    SPEC = {"nolink": True, "slug": "acme-tool", "at": "2026-11-06T07:20+09:00", "text": GOOD, "ownerApproved": "test"}

    def test_gate_allows_only_linkless_threads(self):
        self.assertFalse([v for v in r.check_post("threads", GOOD, CARD, ART, kind="control") if "ルール1" in v])
        self.assertTrue([v for v in r.check_post("threads", f"{GOOD}\n\n{BODY_URL}", CARD, ART, kind="control") if "ルール1" in v])
        self.assertTrue([v for v in r.check_post("x", GOOD, CARD, ART, kind="control") if "ルール1" in v])
        self.assertTrue([v for v in r.check_post("threads", GOOD, [], ART, kind="control") if "ルール8" in v])  # 画像は要る

    def test_control_is_not_a_duplicate_of_the_article_post(self):
        self.assertEqual(tp.post_needle(ART, "control"), "")
        self.assertFalse(r.already_posted("threads", ART, "control", state={"posted": {"acme-tool": {"id": "x"}}}))

    def test_build_input_and_spec_check(self):
        import threads_control_post as tc

        inp = tc.build_input(self.SPEC, "t", ART)
        self.assertEqual(inp["dueAt"], "2026-11-05T22:20:00Z")
        self.assertEqual(len(inp["metadata"]["threads"]["thread"]), 1)
        self.assertNotIn("http", inp["text"])
        with self.assertRaises(SystemExit):
            tc.load_spec_dict({**self.SPEC, "nolink": False})


if __name__ == "__main__":
    unittest.main()
