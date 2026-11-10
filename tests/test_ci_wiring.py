"""すべてのテストが GitHub Actions で動いているかの見張り（2026-11-04: どこにも入っていないテストが16本あった）。

  python3 -m unittest tests.test_ci_wiring
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
WORKFLOWS = ROOT / ".github" / "workflows"


class CiWiringTest(unittest.TestCase):
    def test_all_tests_workflow_runs_every_test_file(self):
        """all_tests.yml が tests/ の Python と Node のテストを全部動かす形のまま（一部だけに絞っていない）"""
        text = (WORKFLOWS / "all_tests.yml").read_text("utf-8")
        self.assertRegex(text, r"python -m pytest[^\n]*\btests/(?:\s|$)")
        self.assertIn("node --test tests/test_*.cjs", text)
        self.assertNotRegex(text, r"--ignore|--deselect|-k\s")  # 外したテストがあれば、ここで分かる
        self.assertRegex(text, r"(?m)^\s*push:")

    def test_every_test_file_follows_the_naming_rule(self):
        """テストを書いたファイルは test_*.py / test_*.cjs の名前にする（名前が違うと全部動かす形でも拾われない）"""
        stray = []
        for path in sorted(TESTS.rglob("*.py")):
            if path.name.startswith("test_") or "fixtures" in path.parts or path.name == "__init__.py":
                continue
            src = path.read_text("utf-8", errors="ignore")
            if re.search(r"^\s*def test_|unittest\.TestCase", src, re.M):
                stray.append(str(path.relative_to(ROOT)))
        for path in sorted(TESTS.glob("*.cjs")):
            if path.name.startswith("test_") or path.name.endswith(".browser.cjs"):
                continue  # *.browser.cjs はブラウザの中で動かす部品（テストではない）
            if re.search(r"node:test|\btest\(", path.read_text("utf-8", errors="ignore")):
                stray.append(str(path.relative_to(ROOT)))
        self.assertEqual(stray, [], "テストの名前が test_ で始まっていない（CI で動かない）")

    def test_indexnow_runs_after_the_page_is_live(self):
        """seo A2・LLMO-A3（2026-11-10）: IndexNow はデプロイの完了を待たない auto_run.yml では送らず、
        deploy_cloudflare.yml で公開の確認（Record live time）のあとに送る。失敗してもデプロイは赤にしない"""
        auto = (WORKFLOWS / "auto_run.yml").read_text("utf-8")
        self.assertNotRegex(auto, r"(?m)^\s*(?:run:\s*)?python3? scripts/indexnow\.py")
        self.assertNotRegex(auto, r"(?m)^\s*- name: Notify IndexNow")
        deploy = (WORKFLOWS / "deploy_cloudflare.yml").read_text("utf-8")
        live = deploy.index("- name: Record live time")
        step = deploy.index("- name: Notify IndexNow")
        self.assertLess(deploy.index("- name: Deploy\n"), live)
        self.assertLess(live, step)
        body = deploy[step:deploy.index("- name:", step + 1)]
        self.assertIn("continue-on-error: true", body)
        self.assertIn("scripts/indexnow.py --hours", body)
        self.assertIn("--merge-state", body)
        self.assertIn("git add state/indexnow_sent.json", body)


if __name__ == "__main__":
    unittest.main()
