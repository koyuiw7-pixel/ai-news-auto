"""夜の図つき Threads 投稿の予約の道具（scripts/threads_figure_queue.py・2026-11-10 ops O2）。外部通信なし・何も投稿しない。

  1. 枠: 19:00〜23:30・間隔 max(40分, min_gap)・手で出した時刻をよける・入らなければ「枠なし」
  2. 決まり: 全角の縦棒・同じ話題の群れの連続・会社員向けのない3本・同じ書き出しの型・直近と同じ書き出し
  3. 下見は Buffer を呼ばず台帳も書かない。--live は ownerApproved と THREADS_MODE=live が無ければ Buffer の前に止まる
  4. 台帳にある key は二重に予約しない
  5. 送る入力は publish_via_buffer の形（図は1つ目・返信に utm_content=reader_reply のリンク）で、門番（kind="reader"）を通る

  python3 -m pytest tests/test_threads_figure_queue.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.request
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sns_rules  # noqa: E402
import threads_figure_queue as fq  # noqa: E402
import threads_gate  # noqa: E402
import threads_post as tp  # noqa: E402

JST = timezone(timedelta(hours=9))
DAY = date(2026, 11, 10)
VBAR = "\uff5c"

# 門番を通る文面（tests/test_threads_reader_20261108.py と同じ形の、架空の記事）
ARTICLE = {
    "slug": "smbc-mail-leak-test",
    "title": "三井住友銀行のメール配信の委託先からアドレス22万7,216件が流出",
    "description": "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。",
    "body": "対象は7月1日〜10月31日に同行が送ったメールの宛先です。問い合わせ窓口と対象の見分け方を案内しています。",
    "_virtual": True,
}
MAIN = (
    "三井住友銀行からメールを受け取っていた法人・個人事業主の人へ。\n\n"
    "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。\n"
    "対象は7月1日〜10月31日に同行が送ったメールの宛先です。\n\n"
    "自分が対象かどうかの見分け方と問い合わせ先は記事にまとめています。"
)
IMAGE = "https://ai-tech-express.jp/img/smbc-mail-leak-test-figure-1.jpg"


def hm(h: int, m: int = 0) -> datetime:
    return datetime(2026, 11, 10, h, m, tzinfo=JST)


def post(key: str, cluster: str, audience: str = "general", opener: str = "number", text1: str = "", **kw) -> dict:
    return {"key": key, "slug": ARTICLE["slug"], "image": IMAGE, "text1": text1 or f"{key} の人へ。本文です。", "text2": "続き（対象の見分け方）→",
            "opener": opener, "cluster": cluster, "audience": audience, **kw}


def no_network(*_a, **_k):
    raise AssertionError("通信してはいけない")


class Isolated(unittest.TestCase):
    """手元の記録・Buffer・通信を切り離す"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.ledger = tmp / "threads_figure.json"
        patches = [
            patch.object(fq, "LEDGER", self.ledger),
            patch.object(fq, "CONTROL_LEDGER", tmp / "threads_control.json"),
            patch.object(fq, "READER_STATE", tmp / "threads_reader.json"),
            patch.object(tp, "STATE_PATH", tmp / "threads_posted.json"),
            patch.object(tp, "buffer_graphql", side_effect=AssertionError("Buffer を呼んではいけない")),
            patch.object(urllib.request, "urlopen", side_effect=no_network),
            patch.object(sns_rules, "fetch_size", return_value=(1200, 675)),  # 画像の縦横は通信せずに決める
            patch.object(sns_rules, "STATE_PATH", tmp / "threads_posted.json"),
            patch.object(threads_gate, "min_gap", return_value=timedelta(minutes=45)),
            patch.object(fq, "load_article", side_effect=lambda slug: dict(ARTICLE) if slug == ARTICLE["slug"] else None),
            patch.dict(os.environ, {"THREADS_MODE": "", "BUFFER_API_KEY": "", "GITHUB_ACTIONS": "", "SNS_RULES_NO_ISSUE": "1"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def plan(self, posts: list[dict], **kw) -> list[dict]:
        kw.setdefault("offline", True)
        kw.setdefault("last_opener", "")
        kw.setdefault("measurer", lambda url: (1200, 675))
        return fq.make_plan({"date": "2026-11-10", "ownerApproved": "", "posts": posts}, **kw)


class SlotTest(Isolated):
    def slots(self, n: int, taken=()):
        return [s.astimezone(JST).strftime("%H:%M") if s else None for s in fq.plan_slots(n, DAY, list(taken))]

    def test_empty_evening_four_posts(self):
        self.assertEqual(self.slots(4), ["19:00", "19:45", "20:30", "21:15"])

    def test_manual_post_pushes_first_slot(self):
        self.assertEqual(self.slots(2, [fq.parse_hm(DAY, "19:20")]), ["20:05", "20:50"])

    def test_eighth_post_has_no_slot_and_window_kept(self):
        got = self.slots(8)
        self.assertEqual(got[:7], ["19:00", "19:45", "20:30", "21:15", "22:00", "22:45", "23:30"])
        self.assertIsNone(got[7])
        for s in fq.plan_slots(8, DAY, []):
            if s:
                self.assertTrue(hm(19) <= s <= hm(23, 30))

    def test_forty_minute_floor_when_min_gap_is_smaller(self):
        with patch.object(threads_gate, "min_gap", return_value=timedelta(minutes=30)):
            self.assertEqual(self.slots(4), ["19:00", "19:40", "20:20", "21:00"])

    def test_taken_from_local_records_and_after_midnight(self):
        tp.STATE_PATH.write_text(json.dumps({"posted": {"a": {"id": "x", "dueAt": "2026-11-10T10:00:00Z"}}}), "utf-8")  # 19:00 JST
        self.assertEqual(fq.local_taken(DAY), [hm(19)])
        self.assertEqual(fq.parse_hm(DAY, "00:30"), hm(0, 30) + timedelta(days=1))

    def test_close_slots_are_skipped(self):
        got = fq.plan_slots(1, DAY, [], now=hm(19, 55))
        self.assertGreaterEqual(got[0], hm(19, 55) + timedelta(minutes=10))

    def test_quiet_hours(self):
        self.assertFalse(fq.in_posting_hours(hm(3)))
        self.assertTrue(fq.in_posting_hours(hm(1, 59) + timedelta(days=1)))


class RuleTest(Isolated):
    def problems(self, rows, i):
        return " / ".join(rows[i]["problems"])

    def test_vertical_bar_in_text2_blocks(self):
        p = post("a", "年金")
        p["text2"] = f"続き（対象{VBAR}見分け方）→"
        rows = self.plan([p])
        self.assertIn("U+FF5C", self.problems(rows, 0))

    def test_same_cluster_twice_blocks_second(self):
        rows = self.plan([post("a", "年金", "employee"), post("b", "年金", opener="money")])
        self.assertNotIn("決まり3", self.problems(rows, 0))
        self.assertIn("[決まり3]", self.problems(rows, 1))

    def test_last_manual_cluster_counts(self):
        rows = self.plan([post("a", "年金", "employee")], last_cluster="年金")
        self.assertIn("[決まり3]", self.problems(rows, 0))

    def test_three_general_in_a_row_blocks(self):
        rows = self.plan([post("a", "年金"), post("b", "相続", opener="money"), post("c", "税・控除")])
        self.assertIn("[決まり4]", self.problems(rows, 2))
        ok = self.plan([post("a", "年金"), post("b", "相続", "employee", opener="money"), post("c", "税・控除")])
        self.assertNotIn("決まり4", self.problems(ok, 2))

    def test_same_opener_twice_blocks(self):
        rows = self.plan([post("a", "年金", "employee"), post("b", "相続")])
        self.assertIn("書き出しの型が直前", self.problems(rows, 1))
        first = self.plan([post("a", "年金", "employee")], last_opener="number")
        self.assertIn("書き出しの型が直前", self.problems(first, 0))

    def test_first_twelve_chars_equal_recent_opener_blocks(self):
        fq.READER_STATE.write_text(json.dumps({"posts": {"x": {"status": "posted", "at": "2026-11-10T05:00:00+00:00", "main": MAIN}}},
                                              ensure_ascii=False), "utf-8")
        rows = self.plan([post("a", "年金", "employee", text1=MAIN)])
        self.assertIn("最初の12字", self.problems(rows, 0))

    def test_unknown_opener_and_missing_article(self):
        p = post("a", "年金", "employee", opener="nope")
        p["slug"] = "no-such-article"
        rows = self.plan([p])
        self.assertIn("threads_hooks の型にない", self.problems(rows, 0))
        self.assertIn("[決まり5]", self.problems(rows, 0))

    def test_local_image_needs_public_url(self):
        rows = self.plan([post("a", "年金", "employee", image="/Users/me/Downloads/saisoku-images/fig.png")])
        self.assertIn("公開の URL", self.problems(rows, 0))


class InputTest(Isolated):
    def test_input_shape_and_gate_pass(self):
        rows = self.plan([post("a", "年金", "employee", text1=MAIN)])
        inp = rows[0]["input"]
        self.assertEqual(inp["mode"], "customScheduled")
        self.assertEqual(inp["dueAt"], "2026-11-10T10:00:00Z")
        thread = inp["metadata"]["threads"]["thread"]
        self.assertEqual(thread[0]["assets"], [{"image": {"url": IMAGE}}])
        self.assertEqual(thread[1]["assets"], [])
        self.assertIn("utm_campaign=smbc-mail-leak-test&utm_content=reader_reply", thread[1]["text"])
        self.assertTrue(thread[1]["text"].startswith("続き（対象の見分け方）→ https://"))
        self.assertEqual(rows[0]["problems"], [])  # 門番（kind="reader"）を通る

    def test_gate_rejection_is_reported_not_sent(self):
        p = post("a", "年金", "employee", text1="年金の話です。")
        rows = self.plan([p])
        self.assertTrue(any(x.startswith("[門番]") for x in rows[0]["problems"]))
        self.assertEqual(fq.book(rows, {"ownerApproved": "x"}, "k", "c", {"posts": {}}, hm(12)), 0)  # Buffer を呼ばない

    def test_create_post_keeps_prepared_text_for_reader_kind(self):
        """kind="reader" は threads_reader.apply_input で書き換えない（門番は通す）"""
        import threads_reader

        inp = fq.build_input(post("a", "年金", text1=MAIN), ARTICLE, hm(19))
        with patch.object(threads_reader, "apply_input", side_effect=AssertionError("書き換えてはいけない")), \
                patch.object(threads_gate, "style_hold", return_value=""), \
                patch.object(sns_rules, "enforce_buffer", side_effect=sns_rules.SnsRuleViolation(["止めた"], "threads", "t")):
            with self.assertRaises(sns_rules.SnsRuleViolation):
                tp.create_post("k", inp, service="threads", article=ARTICLE, source="test", kind="reader")
        self.assertEqual(inp["text"], MAIN)


class ModeTest(Isolated):
    def write_spec(self, approved: str = "") -> Path:
        path = Path(self.tmp.name) / "figure-20261110.json"
        path.write_text(json.dumps({"date": "2026-11-10", "ownerApproved": approved,
                                    "posts": [post("a", "年金", "employee", text1=MAIN)]}, ensure_ascii=False), "utf-8")
        return path

    def run_main(self, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = fq.main(list(args))
        return code, out.getvalue()

    def test_dry_run_never_calls_buffer_or_writes(self):
        code, out = self.run_main("--spec", str(self.write_spec("ok")), "--offline", "--taken", "19:20")
        self.assertEqual(code, 0)
        self.assertIn("下見だけ", out)
        self.assertFalse(self.ledger.exists())
        tp.buffer_graphql.assert_not_called()

    def test_live_without_approval_stops_before_buffer(self):
        with patch.dict(os.environ, {"THREADS_MODE": "live", "BUFFER_API_KEY": "k"}):
            code, out = self.run_main("--spec", str(self.write_spec("")), "--offline", "--live")
        self.assertNotEqual(code, 0)
        self.assertIn("ownerApproved", out)
        tp.buffer_graphql.assert_not_called()

    def test_live_without_threads_mode_stops_before_buffer(self):
        with patch.dict(os.environ, {"THREADS_MODE": "preview", "BUFFER_API_KEY": "k"}):
            code, out = self.run_main("--spec", str(self.write_spec("ok")), "--offline", "--live")
        self.assertNotEqual(code, 0)
        self.assertIn("THREADS_MODE", out)
        self.assertNotIn("k\n", out)
        tp.buffer_graphql.assert_not_called()

    def test_key_in_ledger_is_skipped(self):
        ledger = {"posts": {"a": {"id": "old", "dueAt": "2026-11-10T10:00:00Z"}}}
        rows = fq.make_plan({"date": "2026-11-10", "posts": [post("a", "年金", "employee", text1=MAIN), post("b", "相続", opener="money")]},
                            offline=True, last_opener="", ledger=ledger, measurer=lambda u: (1200, 675))
        self.assertEqual(rows[0]["booked"], "old")
        self.assertEqual(rows[1]["slot"], hm(19, 45))  # 予約済みの 19:00 をよける
        with patch.object(tp, "create_post", side_effect=AssertionError("二重に予約してはいけない")):
            fq.book(rows[:1], {"ownerApproved": "x"}, "k", "c", ledger, hm(12))


if __name__ == "__main__":
    unittest.main()
