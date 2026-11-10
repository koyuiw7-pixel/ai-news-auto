"""scripts/llmo_access_check.py（AI検索の巡回の毎日の確認・LLMO-A2）。外部への通信なし。"""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import llmo_access_check as check  # noqa: E402
import pipeline_health as ph  # noqa: E402

LIVE_ROBOTS = """User-Agent: *
Allow: /
Disallow: /api/
Disallow: /review

User-Agent: OAI-SearchBot
User-Agent: ChatGPT-User
User-Agent: PerplexityBot
Allow: /
Disallow: /api/
Disallow: /review

Sitemap: https://ai-tech-express.jp/sitemap.xml
"""
BAD_ROBOTS = "User-Agent: *\nContent-signal: search=yes, ai-train=no\nAllow: /\n\nUser-Agent: OAI-SearchBot\nDisallow: /\n"


class RobotsCheckTest(unittest.TestCase):
    def test_search_agents_are_read_from_robots_ts(self):
        agents = check.search_agents()
        for name in ("OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Claude-SearchBot", "Bingbot", "DuckAssistBot"):
            self.assertIn(name, agents)
        self.assertNotIn("GPTBot", agents)  # 学習用はオーナー判断（B1）なので見張りの対象外

    def test_live_style_robots_passes(self):
        self.assertEqual(check.check_robots(LIVE_ROBOTS, check.search_agents()), [])

    def test_content_signal_and_disallow_fail_with_clear_message(self):
        failures = check.check_robots(BAD_ROBOTS, ["OAI-SearchBot", "PerplexityBot"])
        self.assertEqual(len(failures), 2)
        self.assertIn("Content-signal", failures[0])
        self.assertIn("OAI-SearchBot", failures[1])
        self.assertIn("Disallow: /", failures[1])

    def test_star_group_disallow_applies_to_unnamed_agent(self):
        failures = check.check_robots("User-agent: *\nDisallow: /\n", ["DuckAssistBot"])
        self.assertEqual(len(failures), 1)
        self.assertIn("DuckAssistBot", failures[0])

    def test_cli_with_local_robots_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "robots.txt"
            path.write_text(BAD_ROBOTS, "utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "llmo_access_check.py"), "--robots-file", str(path)],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL robots.txt に Content-signal の行があります", result.stdout)
        self.assertIn("OAI-SearchBot（AI検索の巡回）に Disallow: / があります", result.stdout)
        self.assertIn("AI Crawl Control", result.stdout)


class PageChecksTest(unittest.TestCase):
    def test_first_sentence_skips_headings_and_markdown(self):
        body = "## 見出し\n\n**りそな**の[決算](https://x)は 増益です。次の文。"
        self.assertEqual(check.first_sentence(body), "りそなの決算は増益です")

    def test_page_text_strips_tags(self):
        self.assertIn("りそなの決算は増益です", check.page_text('<p>りそなの<a href="/x">決算</a>は\n増益です。</p>'))

    def test_meta_robots(self):
        good = '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1"/>'
        self.assertIsNone(check.meta_robots_problem(good))
        self.assertIn("nosnippet", check.meta_robots_problem('<meta name="robots" content="index, nosnippet, max-snippet:-1"/>'))
        self.assertIn("max-snippet:-1", check.meta_robots_problem('<meta name="robots" content="index, follow"/>'))
        self.assertIn("ありません", check.meta_robots_problem("<html></html>"))

    def test_pick_article_skips_just_published_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            def write(slug, published, **extra):
                (folder / f"{slug}.json").write_text(json.dumps({"slug": slug, "publishedAt": published, "body": f"{slug}の本文です。", **extra}), "utf-8")
            write("old", "2026-11-10T01:00:00+00:00")
            write("settled", "2026-11-10T05:00:00+00:00")
            write("dup", "2026-11-10T05:30:00+00:00", duplicateOf="old")
            write("fresh", "2026-11-10T06:30:00+00:00")
            now = datetime(2026, 11, 10, 7, 0, tzinfo=timezone.utc)
            self.assertEqual(check.pick_article(now, folder), ("settled", "settledの本文です"))

    def test_pick_guide_skips_redirected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "a.json").write_text(json.dumps({"slug": "a", "intro": "Aの紹介。"}), "utf-8")
            (folder / "b.json").write_text(json.dumps({"slug": "b", "intro": "Bの紹介。"}), "utf-8")
            self.assertEqual(check.pick_guide(folder, moved={"a"}), ("b", "Bの紹介"))

    def test_budget_never_exceeds_25(self):
        budget = check.Budget()
        with patch.object(check.request, "urlopen", side_effect=OSError("offline")):
            for _ in range(25):
                budget.fetch("https://example.invalid/")
            with self.assertRaises(RuntimeError):
                budget.fetch("https://example.invalid/")

    def test_requests_carry_internal_header_and_cache_buster(self):
        seen = []
        def fake(req, timeout):
            seen.append(req)
            raise OSError("offline")
        with patch.object(check.request, "urlopen", side_effect=fake):
            check.Budget().fetch("https://ai-tech-express.jp/robots.txt", check.USER_AGENTS["OAI-SearchBot"])
        self.assertEqual(seen[0].get_header("X-saisoku-internal"), "1")
        self.assertRegex(seen[0].full_url, r"/robots\.txt\?v=\d+$")
        self.assertIn("OAI-SearchBot", seen[0].get_header("User-agent"))

    def test_live_check_uses_at_most_25_requests(self):
        class Fake(check.Budget):
            def fetch(self, url, user_agent="x"):
                self.used += 1
                assert self.used <= self.limit
                if url.endswith("/robots.txt"):
                    return 200, {}, LIVE_ROBOTS
                if url.endswith(".txt"):
                    return 200, {}, url.rsplit("/", 1)[-1][:-4]
                return 200, {"cf-mitigated": "challenge"} if "Googlebot" in user_agent else {}, "<p>no body</p>"
        budget = Fake()
        passes, failures = check.check_live("https://example.invalid", budget)
        self.assertLessEqual(budget.used, 25)
        self.assertTrue(any("cf-mitigated" in f for f in failures))
        self.assertTrue(any("本文の最初の一文" in f for f in failures))
        self.assertIn("AI Crawl Control", check.report(passes, failures))


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.health = Path(self.tmp.name) / "pipeline_health.json"
        self.health.write_text(json.dumps({"status": "ok", "consecutive_zero": 0}), "utf-8")
        patcher = patch.object(ph, "HEALTH_PATH", self.health)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_report_only_until_11_13_jst(self):
        self.assertFalse(check.should_record(datetime(2026, 11, 12, 14, 59, tzinfo=timezone.utc)))
        self.assertTrue(check.should_record(datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)))

    def test_failures_are_written_once_and_keep_other_keys(self):
        ph.record_llmo_access(["(b) OAI-SearchBot で /articles/x が HTTP 403"], datetime(2026, 11, 13, tzinfo=timezone.utc))
        data = json.loads(self.health.read_text("utf-8"))
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["llmo_access"]["status"], "failed")
        self.assertIn("AI Crawl Control", data["llmo_access"]["note"])
        mtime = self.health.stat().st_mtime_ns
        ph.record_llmo_access(["(b) OAI-SearchBot で /articles/x が HTTP 403"], datetime(2026, 11, 14, tzinfo=timezone.utc))
        self.assertEqual(self.health.stat().st_mtime_ns, mtime)  # 同じ結果なら書き直さない
        ph.record_llmo_access([], datetime(2026, 11, 15, tzinfo=timezone.utc))
        data = json.loads(self.health.read_text("utf-8"))
        self.assertEqual(data["llmo_access"], {"status": "ok", "recovered_at": "2026-11-15T00:00:00+00:00"})


if __name__ == "__main__":
    unittest.main()
