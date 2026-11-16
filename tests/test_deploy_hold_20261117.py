"""2026-11-17: 保留（[no-deploy]）した記事は、期限までに必ずデプロイに載せる（scripts/deploy_hold.py・state/deploy_held.json）。

きっかけ: 07:13 JST の Muse の記事（lawson-morisugi-challenge-nov17）が [no-deploy] で保留され、本番で 404 のまま15分以上残った。
  - Muse の保留を出す回が「55分のまとめ」しか無かった
  - 0/1 の印 state/deploy_pending は、push の3方向マージで同じころの別のデプロイの「0」に負けて消えた
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import deploy_hold  # noqa: E402
import git_safe_push  # noqa: E402

FLOWS = ROOT / ".github" / "workflows"


def epoch(hms: str) -> int:
    return int(datetime.fromisoformat(f"2026-11-16T{hms}+00:00").timestamp())


class HoldFileTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state" / "deploy_held.json"
        patcher = patch.object(deploy_hold, "PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv) -> str:
        with patch("sys.stdout.write") as write:
            self.assertEqual(deploy_hold.main(list(argv)), 0)
        return "".join(call.args[0] for call in write.call_args_list).strip()

    def test_incident_timeline_is_deployed_by_the_next_auto_run(self):
        last = epoch("22:07:27")  # 前回のデプロイ（記事づくりの回が呼んだ。Lawson より前の版）
        self.run_cli("add", "--by", "muse", "--due", str(last + 900), "--slugs", "lawson-morisugi-challenge-nov17",
                     "--now", str(epoch("22:13:51")))
        self.assertEqual(self.run_cli("due", "--now", str(epoch("22:20:00"))), "0")  # 15分の決まりの中は待つ
        self.assertEqual(self.run_cli("due", "--now", str(epoch("22:23:41"))), "1")  # 22:23 の記事づくりの回が出す
        self.run_cli("clear")
        self.assertEqual(self.run_cli("due", "--now", str(epoch("23:59:00"))), "0")
        self.assertEqual(json.loads(self.path.read_text("utf-8")), {"held": {}})

    def test_earlier_due_is_kept_and_unknown_keys_still_held(self):
        data = deploy_hold.add({"held": {}}, ["a"], "muse", 1000, 10)
        data = deploy_hold.add(data, ["a", "b"], "auto_run", 5000, 20)
        self.assertEqual(data["held"]["a"], {"by": "muse", "at": 10, "due": 1000})
        self.assertEqual(data["held"]["b"]["due"], 5000)
        self.assertEqual(deploy_hold.due_keys(data, 999), [])
        self.assertEqual(deploy_hold.due_keys(data, 1000), ["a"])
        data["held"]["broken"] = {"due": "x"}
        self.assertIn("broken", deploy_hold.due_keys(data, 0))  # 読めない期限は出す側に倒す
        self.run_cli("add", "--by", "muse", "--due", "100", "--now", "50")  # 記事が分からなくても控える
        self.assertEqual(list(deploy_hold.load()["held"]), ["muse@50"])

    def test_broken_or_missing_file_reads_as_empty(self):
        self.assertEqual(deploy_hold.load(), {"held": {}})
        self.path.parent.mkdir(parents=True)
        self.path.write_text("not json")
        self.assertEqual(self.run_cli("due", "--now", "1"), "0")


class MergeKeepsHeldArticleTest(unittest.TestCase):
    """push の3方向マージ（scripts/git_safe_push.py）で、保留の控えが消えないこと"""

    def test_old_flag_was_lost_like_the_incident(self):
        # Muse の回が読んだときの印は 1、書いたのも 1（＝変えていない扱い）。そのあいだに別の回がデプロイを呼んで 0 にした
        merged, _ = git_safe_push.merge_file("state/deploy_pending", b"1\n", b"1\n", b"0\n")
        self.assertEqual(merged, b"0\n")  # 印が消える（だから記事ごとの控えにした）

    def test_held_article_survives_a_concurrent_clear(self):
        base = json.dumps({"held": {}}).encode()
        theirs = json.dumps({"held": {}}).encode()  # 別の回がデプロイを呼んで空にした
        ours = json.dumps({"held": {"lawson": {"by": "muse", "at": 2, "due": 3}}}).encode()  # Muse が保留した
        merged, _ = git_safe_push.merge_file("state/deploy_held.json", base, ours, theirs)
        self.assertIn("lawson", json.loads(merged)["held"])

    def test_clear_does_not_drop_an_entry_added_after_the_clearing_run_started(self):
        base = json.dumps({"held": {"old": {"due": 1}}}).encode()
        ours = json.dumps({"held": {}}).encode()  # この回がデプロイを呼ぶ（old はこの回の push のあとのデプロイに載る）
        theirs = json.dumps({"held": {"old": {"due": 1}, "lawson": {"due": 3}}}).encode()  # あいだに Muse が保留した
        merged, _ = git_safe_push.merge_file("state/deploy_held.json", base, ours, theirs)
        self.assertEqual(json.loads(merged)["held"], {"lawson": {"due": 3}})
        merged, _ = git_safe_push.merge_file("state/deploy_held.json", None, ours, theirs)  # まだファイルが無かったとき
        self.assertIn("lawson", json.loads(merged)["held"])


class WorkflowsUseTheHoldTest(unittest.TestCase):
    """保留する所はすべて控えを足し、デプロイを決める所はすべて控えを空にする（同じ決まりを全部の道に）"""

    def flows(self):
        for path in sorted(FLOWS.glob("*.yml")):
            text = path.read_text("utf-8")
            if "state/deploy_pending" in text:
                yield path.name, text

    def test_every_hold_adds_and_every_deploy_clears(self):
        names = []
        for name, text in self.flows():
            names.append(name)
            holds = text.count("echo 1 > state/deploy_pending")
            deploys = text.count("echo 0 > state/deploy_pending")
            self.assertEqual(text.count("scripts/deploy_hold.py add "), holds, name)
            self.assertEqual(text.count("scripts/deploy_hold.py clear"), deploys, name)
            self.assertIn("state/deploy_held.json", text, name)
        self.assertEqual(names, ["angle_now.yml", "auto_run.yml", "deep_dive.yml", "muse_inbox.yml"])

    def test_muse_hold_due_is_15_minutes_after_last_deploy(self):
        flow = (FLOWS / "muse_inbox.yml").read_text("utf-8")
        self.assertIn("deploy_hold.py add --by muse --due $((LAST + MUSE_DEPLOY_GAP)) --staged", flow)
        self.assertIn('HELD=$(python3 scripts/deploy_hold.py due --now "$NOW" || echo 1)', flow)

    def test_auto_run_deploys_when_a_hold_is_due(self):
        flow = (FLOWS / "auto_run.yml").read_text("utf-8")
        step = flow[flow.index("- name: Commit & push"):flow.index("- name: Deploy to Cloudflare")]
        self.assertIn('HELD=$(python3 scripts/deploy_hold.py due --now "$NOW" || echo 1)', step)
        self.assertIn('if [ "$HELD" = "1" ]; then DUE=1; fi', step)
        self.assertIn('elif { [ "$PENDING" = "1" ] || [ "$HELD" = "1" ]; } && [ "$DUE" = "1" ]; then', step)
        self.assertIn("deploy_hold.py add --by auto_run --due $((LAST + 3300)) --staged", step)

    def test_auto_run_decision_lines_run_as_written(self):
        """記事が増えない回でも、期限の来た控えがあればデプロイする（bash でそのまま動かす）"""
        flow = (FLOWS / "auto_run.yml").read_text("utf-8")
        due_line = re.search(r'if \[ "\$HELD" = "1" \]; then DUE=1; fi', flow).group(0)
        flush = re.search(r'elif \{ \[ "\$PENDING" = "1" \] \|\| \[ "\$HELD" = "1" \]; \} && \[ "\$DUE" = "1" \]; then', flow).group(0)

        def decide(pending: str, held: str, due: str) -> str:
            script = (f'PENDING={pending}; HELD={held}; DUE={due}; {due_line}\n'
                      f'if false; then :\n{flush} echo deploy\nelse echo skip\nfi')
            return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout.strip()

        self.assertEqual(decide("0", "1", "0"), "deploy")  # Lawson の件: 印は消えていたが控えの期限が来た
        self.assertEqual(decide("1", "0", "1"), "deploy")  # これまでの55分のまとめ
        self.assertEqual(decide("1", "0", "0"), "skip")
        self.assertEqual(decide("0", "0", "1"), "skip")


if __name__ == "__main__":
    unittest.main()
