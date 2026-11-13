"""2026-11-13: Muse の記事を公開した回は、55分のまとめを待たずにすぐデプロイする（前回のデプロイから15分たっているとき）。

きっかけ: Muse の記事は Threads に出す記事なのに、原稿から公開まで中央値21分・最大66分かかっていた（点検 audit_20261113）。
デプロイの回数（費用）を守る決まり: 前回のデプロイから15分たっていなければ保留（＝まとめのほかに増えるのは15分に1回まで）。
自動の記事のまとめ（auto_run.yml の55分）は変えない。ワークフローの中身を文字で確かめ、判定の行は bash でそのまま動かす。
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLOW = (ROOT / ".github" / "workflows" / "muse_inbox.yml").read_text("utf-8")
COMMIT = FLOW[FLOW.index("- name: Commit & push"):FLOW.index("- name: Deploy to Cloudflare")]


class MuseDeployTest(unittest.TestCase):
    def test_gap_is_15_minutes_and_not_the_55_minute_batch(self):
        self.assertIn('MUSE_DEPLOY_GAP: "900"', COMMIT)
        self.assertIn('if [ $((NOW - LAST)) -ge "$MUSE_DEPLOY_GAP" ]; then', COMMIT)
        self.assertNotIn("3300", COMMIT)

    def test_only_a_publish_can_deploy(self):
        """審査結果だけの回（+0本）はデプロイしない。公開した回だけ"""
        publish = COMMIT[COMMIT.index('if [ "$COUNT" != "0" ]; then'):COMMIT.index("git commit -m")]
        yes, no = publish.split("            else\n", 1)[0], publish.split("            else\n", 1)[1]
        self.assertIn('echo "$NOW" > state/last_deploy', yes)
        self.assertIn("echo 0 > state/deploy_pending", yes)
        self.assertIn('echo "deploy=1" >> "$GITHUB_OUTPUT"', yes)
        self.assertNotIn("[no-deploy]", yes)
        self.assertIn("echo 1 > state/deploy_pending", no)
        self.assertIn('MSG="${MSG} [no-deploy]"', no)
        self.assertIn('MSG="chore(muse): Muse の入稿の審査結果を記録 [no-deploy]"', no)
        self.assertEqual(COMMIT.count('echo "deploy=1"'), 1)

    def test_deploy_step_dispatches_the_site_deploy(self):
        step = FLOW[FLOW.index("- name: Deploy to Cloudflare"):FLOW.index("- name: Summary")]
        self.assertIn("if: ${{ steps.commit.outputs.deploy == '1' }}", step)
        self.assertIn("gh workflow run deploy_cloudflare.yml --ref main", step)
        self.assertIn("actions: write", FLOW)

    def test_decision_line_runs_as_written(self):
        """判定の行を bash でそのまま動かす: 15分以上なら出す・未満なら保留"""
        line = re.search(r'if \[ \$\(\(NOW - LAST\)\) -ge "\$MUSE_DEPLOY_GAP" \]; then', COMMIT).group(0)
        gap = re.search(r'MUSE_DEPLOY_GAP: "(\d+)"', COMMIT).group(1)

        def decide(since_last: int) -> str:
            script = f'MUSE_DEPLOY_GAP={gap}; NOW=100000; LAST=$((NOW - {since_last})); {line} echo deploy; else echo hold; fi'
            return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout.strip()

        self.assertEqual(decide(899), "hold")
        self.assertEqual(decide(900), "deploy")
        self.assertEqual(decide(3299), "deploy")   # これまでは55分まで保留だった
        self.assertEqual(decide(60), "hold")
        # 記録が無いとき（LAST=0）は出す
        script = f'MUSE_DEPLOY_GAP={gap}; NOW=1794544378; LAST=0; {line} echo deploy; else echo hold; fi'
        self.assertEqual(subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout.strip(), "deploy")

    def test_automatic_batch_is_unchanged(self):
        auto = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("[ $((NOW - LAST)) -ge 3300 ]", auto)
        self.assertNotIn("MUSE_DEPLOY_GAP", auto)


if __name__ == "__main__":
    unittest.main()
