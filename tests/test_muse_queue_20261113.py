"""2026-11-13: Muse の入稿は「急ぎ → 日付の新しい順」で審査する。1本の原稿が1回の時間を使い切らない。残りがあれば次の回をすぐ呼ぶ。

きっかけ: 13本がいっぺんに入稿され、ファイル名の順（日付の古い順）だったので、前の日の原稿の出し直し10本のうしろに
今日の話題の原稿（消費税の法案・X の機能の変更・NVIDIA の決算日）が並んだ。1回は25分を超え、次の回は予約（12分・42分）待ちだった。
ネット・LLM を使わない（審査の中身は差し替える。ワークフローは文字で確かめ、判定の行は bash でそのまま動かす）。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import main as m  # noqa: E402
import muse_articles as ma  # noqa: E402
import muse_format as mf  # noqa: E402
import pacing  # noqa: E402
from test_muse_score_repair_20261113 import OBJECTION, run_build, verdict  # noqa: E402

FLOW = (ROOT / ".github" / "workflows" / "muse_inbox.yml").read_text("utf-8")


def draft(genre: str = "お金", head: str = "", notes: str = "メモ") -> str:
    return (f"---\ntitle: 会社員の平均給与は487万円で過去最高　国税庁の調査\ngenre: {genre}\n{head}sources:\n"
            f"  - url: https://www.nta.go.jp/a.pdf\n    name: 国税庁\n    facts: 487万円\nnotes: |\n  {notes}\n---\n## 見出し\n本文です。\n")


class UrgentMarkerTest(unittest.TestCase):
    def test_marker_line_in_the_header(self):
        data = mf.parse(draft(head="急ぎ: はい\n"))
        self.assertTrue(mf.is_urgent(data))
        self.assertNotIn("急ぎ", data["notes"])  # メモには混ぜない
        self.assertEqual(data["genre"], "お金")
        self.assertEqual(len(data["sources"]), 1)

    def test_other_spellings_and_notes(self):
        for head in ("急ぎ：はい\n", "至急: はい\n", "urgent: yes\n", "急ぎ: 「はい」\n"):
            self.assertTrue(mf.is_urgent(mf.parse(draft(head=head))), head)
        self.assertTrue(mf.is_urgent(mf.parse(draft(notes="話題なので。\n  急ぎ: はい"))))

    def test_no_marker_or_a_no_is_not_urgent(self):
        self.assertFalse(mf.is_urgent(mf.parse(draft())))
        self.assertFalse(mf.is_urgent(mf.parse(draft(head="急ぎ: いいえ\n"))))
        self.assertFalse(mf.is_urgent(mf.parse(draft(notes="急ぎではないが早めに出したい"))))
        self.assertEqual(mf.problems(mf.parse(draft(head="急ぎ: はい\n")), "20261113-お金-平均給与.md"), [])

    def test_writer_sees_the_marker_in_the_format_help(self):
        self.assertIn("急ぎ: はい", mf.FORMAT_MD)
        self.assertIn("審査の順番", mf.FORMAT_MD)
        self.assertIn("速報解説", mf.URGENT_GENRES)


class OrderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name: str, **kwargs) -> Path:
        path = self.inbox / name
        path.write_text(draft(**kwargs), "utf-8")
        return path

    def names(self, queue) -> list[str]:
        return [path.name for path, _ in queue]

    def test_urgent_then_newest_date_then_name(self):
        """今日の入稿の形: 前の日の出し直し → うしろ。速報解説・急ぎの印 → 先頭"""
        self.put("20261112-手続き-高額療養費.md", genre="手続き")
        self.put("20261112-お金-住宅ローン控除.md")
        self.put("20261113-AI・テック-Xの機能変更.md", genre="AI・テック")
        self.put("20261113-速報解説-消費税の法案.md", genre="速報解説")
        self.put("20261112-ビジネス-NVIDIA決算日.md", genre="ビジネス", head="急ぎ: はい\n")
        queue = ma.order_inbox(sorted(self.inbox.glob("*.md")), {"items": {}}, times={})
        self.assertEqual(self.names(queue), [
            "20261113-速報解説-消費税の法案.md", "20261112-ビジネス-NVIDIA決算日.md",
            "20261113-AI・テック-Xの機能変更.md", "20261112-お金-住宅ローン控除.md", "20261112-手続き-高額療養費.md"])
        why = dict((path.name, reason) for path, reason in queue)
        self.assertEqual(why["20261113-速報解説-消費税の法案.md"], "急ぎ（速報解説）")
        self.assertEqual(why["20261112-ビジネス-NVIDIA決算日.md"], "急ぎ（急ぎの印）")
        self.assertEqual(why["20261112-お金-住宅ローン控除.md"], "日付 20261112")

    def test_same_date_newest_commit_first(self):
        a, b = self.put("20261113-お金-a.md"), self.put("20261113-お金-b.md")
        self.assertEqual(self.names(ma.order_inbox([a, b], {}, times={"20261113-お金-a.md": 100, "20261113-お金-b.md": 200})),
                         ["20261113-お金-b.md", "20261113-お金-a.md"])
        self.assertEqual(self.names(ma.order_inbox([b, a], {}, times={})), ["20261113-お金-a.md", "20261113-お金-b.md"])

    def test_genre_from_the_file_name_when_the_header_is_unreadable(self):
        broken = self.inbox / "20261112-速報解説-壊れた原稿.md"
        broken.write_text("先頭の項目が無い原稿", "utf-8")
        ok = self.put("20261113-お金-a.md")
        self.assertEqual(self.names(ma.order_inbox([ok, broken], {}, times={})), [broken.name, ok.name])

    def test_deferred_drafts_go_behind_their_group(self):
        a, b, c = self.put("20261113-速報解説-a.md", genre="速報解説"), self.put("20261113-速報解説-b.md", genre="速報解説"), self.put("20261113-お金-c.md")
        queue = ma.order_inbox([a, b, c], {"items": {a.name: {"status": "waiting", "deferred": 1}}}, times={})
        self.assertEqual(self.names(queue), [b.name, a.name, c.name])
        self.assertIn("持ち越し1回", queue[1][1])

    def test_one_log_line_with_order_and_reason(self):
        a, b = self.put("20261113-速報解説-a.md", genre="速報解説"), self.put("20261112-お金-b.md")
        line = ma.order_line(ma.order_inbox([b, a], {}, times={}))
        self.assertNotIn("\n", line)
        self.assertIn("1. 20261113-速報解説-a.md［急ぎ（速報解説）］", line)
        self.assertIn("2. 20261112-お金-b.md［日付 20261112］", line)

    def test_commit_times_survive_a_missing_git(self):
        with mock.patch.object(ma.subprocess, "run", side_effect=OSError("no git")):
            self.assertEqual(ma.inbox_commit_times(), {})
        out = mock.Mock(returncode=0, stdout="@200\n\ncontent/muse_inbox/20261113-お金-a.md\n@100\n\ncontent/muse_inbox/20261113-お金-a.md\ncontent/muse_inbox/20261112-お金-b.md\n")
        with mock.patch.object(ma.subprocess, "run", return_value=out):
            self.assertEqual(ma.inbox_commit_times(), {"20261113-お金-a.md": 200, "20261112-お金-b.md": 100})


class DraftShareTest(unittest.TestCase):
    """1本の原稿は、1回の時間の4割まで。超えたら手直し・作り直しをやめて次の回へ（見送りにしない）"""

    def test_share_is_40_percent(self):
        self.assertEqual(ma.DRAFT_BUDGET_SHARE, 0.4)

    def build(self, evaluations, fixes, clock: list[float], deadline):
        ticks = iter(clock)
        last = [clock[-1]]

        def now():
            last[0] = next(ticks, last[0])
            return last[0]

        real = ma.build_article
        with mock.patch.object(ma.time, "time", side_effect=now), \
                mock.patch.object(ma, "build_article", side_effect=lambda *a, **k: real(*a, **k, deadline=deadline)):
            return run_build(evaluations, fixes)

    def test_no_second_attempt_after_the_share_is_used(self):
        """1回目が不合格（70点）で時間切れ → 作り直さず次の回へ"""
        (status, out), prompts, fixes = self.build([verdict(70, [OBJECTION])], [], clock=[10_000.0], deadline=600.0)
        self.assertEqual(status, "defer")
        self.assertIn("次の回にもう一度試します", out)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(fixes, [])

    def test_repair_rounds_stop_when_time_is_up(self):
        (status, out), prompts, fixes = self.build([verdict(88, [OBJECTION])], [], clock=[10_000.0], deadline=600.0)
        self.assertEqual(status, "defer")
        self.assertEqual(fixes, [])       # 手直しの LLM を呼ばない
        self.assertEqual(len(prompts), 1)  # 作り直しもしない

    def test_within_the_share_nothing_changes(self):
        (status, record), _, fixes = self.build([verdict(88, [OBJECTION])], [({"slug": "kaigo", "title": "t", "body": "b"}, verdict(92))],
                                                clock=[100.0], deadline=600.0)
        self.assertEqual(status, "ok")
        self.assertEqual(record["qualityScore"], 92)
        self.assertEqual(len(fixes), 1)

    def test_without_a_deadline_it_is_rejected_as_before(self):
        (status, out), prompts, _ = run_build([verdict(88, [OBJECTION]), verdict(88, [OBJECTION])], [(None, "直せず"), (None, "直せず")])
        self.assertEqual(status, "reject")
        self.assertEqual(len(prompts), 2)

    def test_pass_score_is_not_lowered_by_the_time_limit(self):
        """時間切れでも、合格点に届かない原稿は公開しない"""
        (status, _), _, _ = self.build([verdict(89, [OBJECTION])], [], clock=[10_000.0], deadline=600.0)
        self.assertNotEqual(status, "ok")


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = Path(self.tmp.name) / "inbox"
        self.inbox.mkdir()
        self.results: dict = {"items": {}}
        self.calls: list[tuple[str, bool]] = []
        self.logs: list[str] = []
        self.outcome: dict[str, tuple] = {}

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name: str, **kwargs) -> None:
        (self.inbox / name).write_text(draft(**kwargs), "utf-8")

    def run_process(self, max_n: int = 6, budget: int = 1500) -> None:
        def fake_build(path, data, fetched, unread=None, deadline=None):
            self.calls.append((path.name, deadline is not None))
            return self.outcome.get(path.name) or ("ok", {"slug": "s-" + str(len(self.calls)), "title": data["title"]})

        patches = [
            mock.patch.object(ma, "INBOX", self.inbox), mock.patch.object(ma, "load_results", return_value=self.results),
            mock.patch.object(ma, "save_results"), mock.patch.object(ma, "inbox_commit_times", return_value={}),
            mock.patch.object(ma, "duplicate_of", return_value=None), mock.patch.object(ma, "register_today"),
            mock.patch.object(ma, "fetch_sources", return_value=[{"url": "https://www.nta.go.jp/a.pdf"}]),
            mock.patch.object(ma, "build_article", side_effect=fake_build),
            mock.patch.object(ma, "log", side_effect=self.logs.append),
            mock.patch.object(m, "load_state", return_value={}), mock.patch.object(m, "save_state"),
            mock.patch.object(m, "write_article", return_value=ROOT / "content" / "articles" / "x.json"),
            mock.patch.object(pacing, "live_today", return_value=0),
        ]
        for p in patches:
            p.start()
        try:
            ma.process(argparse.Namespace(max=max_n, budget=budget, daily_cap=0))
        finally:
            for p in reversed(patches):
                p.stop()

    def test_urgent_drafts_are_built_first_and_the_order_is_logged_once(self):
        self.put("20261112-手続き-高額療養費.md", genre="手続き")
        self.put("20261112-お金-住宅ローン控除.md")
        self.put("20261113-速報解説-消費税の法案.md", genre="速報解説")
        self.put("20261113-AI・テック-Xの機能変更.md", genre="AI・テック", head="急ぎ: はい\n")
        self.run_process(max_n=2)
        self.assertEqual([name for name, _ in self.calls], ["20261113-AI・テック-Xの機能変更.md", "20261113-速報解説-消費税の法案.md"])
        order = [line for line in self.logs if "審査の順番" in line]
        self.assertEqual(len(order), 1)
        self.assertLess(order[0].index("消費税の法案"), order[0].index("住宅ローン控除"))
        # 公開の上限で止まった残り（前の日の出し直し）は入稿に残る
        self.assertEqual(sorted(p.name for p in self.inbox.glob("*.md")), ["20261112-お金-住宅ローン控除.md", "20261112-手続き-高額療養費.md"])

    def test_time_share_applies_only_while_others_wait(self):
        self.put("20261113-お金-a.md")
        self.put("20261113-お金-b.md")
        self.run_process()
        self.assertEqual(self.calls, [("20261113-お金-a.md", True), ("20261113-お金-b.md", False)])

    def test_deferred_draft_stays_in_the_inbox_and_the_run_goes_on(self):
        self.put("20261113-お金-a.md")
        self.put("20261113-お金-b.md")
        self.outcome["20261113-お金-a.md"] = ("defer", ma.DEFER_REASON)
        self.run_process()
        self.assertEqual([name for name, _ in self.calls], ["20261113-お金-a.md", "20261113-お金-b.md"])
        self.assertTrue((self.inbox / "20261113-お金-a.md").exists())
        self.assertFalse((self.inbox / "20261113-お金-b.md").exists())
        row = self.results["items"]["20261113-お金-a.md"]
        self.assertEqual((row["status"], row["deferred"]), ("waiting", 1))
        self.assertIn("次の回にもう一度試します", row["reason"])
        self.assertEqual(self.results["items"]["20261113-お金-b.md"]["status"], "published")

    def test_after_two_deferrals_the_draft_gets_a_full_run(self):
        self.put("20261113-速報解説-a.md", genre="速報解説")
        self.put("20261113-お金-b.md")
        self.results["items"]["20261113-速報解説-a.md"] = {"status": "waiting", "deferred": ma.MAX_DEFERS}
        self.run_process()
        self.assertEqual(self.calls[0], ("20261113-速報解説-a.md", False))


class RedispatchTest(unittest.TestCase):
    """入稿が残ったら、予約（12分・42分）を待たずに次の回を呼ぶ。1本も片づかなかった回は呼ばない"""

    def test_workflow_can_dispatch_itself_and_queues_behind_the_current_run(self):
        self.assertIn("workflow_dispatch:", FLOW)
        self.assertIn("actions: write", FLOW)
        self.assertRegex(FLOW, r"concurrency:\n  group: muse-inbox\n  cancel-in-progress: false")
        step = FLOW[FLOW.index("- name: Run again for the rest"):FLOW.index("- name: Summary")]
        self.assertIn("if: ${{ steps.left.outputs.again == '1' }}", step)
        self.assertIn("gh workflow run muse_inbox.yml --ref main", step)
        self.assertIn("GH_TOKEN: ${{ github.token }}", step)
        self.assertNotIn("always()", step)  # push に失敗した回は呼ばない
        self.assertEqual(FLOW.count("gh workflow run muse_inbox.yml"), 1)

    def test_count_runs_after_the_articles_and_before_the_push(self):
        self.assertLess(FLOW.index("- name: Muse articles"), FLOW.index("- name: Count remaining"))
        self.assertLess(FLOW.index("- name: Count remaining"), FLOW.index("- name: Commit & push"))
        self.assertLess(FLOW.index("- name: Commit & push"), FLOW.index("- name: Run again for the rest"))

    def test_decision_line_runs_as_written(self):
        step = FLOW[FLOW.index("- name: Count remaining"):FLOW.index("# 公開した Muse の記事の写真")]
        line = re.search(r'if \[ "\$AFTER" -gt 0 \] && \[ "\$DONE" -gt 0 \]; then .*; fi', step).group(0)

        def decide(before: int, after: int) -> str:
            script = f'GITHUB_OUTPUT=/dev/stdout; BEFORE={before}; AFTER={after}; DONE=$((BEFORE - AFTER)); {line}'
            return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout.strip()

        self.assertEqual(decide(13, 7), "again=1")   # 6本片づいて7本残った → すぐ次の回
        self.assertEqual(decide(7, 0), "again=0")    # 残りなし
        self.assertEqual(decide(7, 7), "again=0")    # 1本も片づかなかった（本数がいっぱい・LLM が使えない）→ 回り続けない
        self.assertEqual(decide(3, 4), "again=0")

    def test_muse_step_still_has_its_budget(self):
        self.assertIn("--budget 1500", FLOW)
        self.assertIn("timeout-minutes: 32", FLOW)


if __name__ == "__main__":
    unittest.main()
