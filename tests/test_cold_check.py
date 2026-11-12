"""デプロイ直後の1回目の表示の確かめ（scripts/cold_check.py・台帳 W29）の判定。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import cold_check  # noqa: E402

BASE = "https://ai-tech-express.jp"


def result(ttfb, status=200, cache="HIT", error=""):
    return {"path": "/x", "status": status, "ttfb": ttfb, "cache": cache, "ver": "v", "error": error}


class JudgeTest(unittest.TestCase):
    def test_page_built_on_first_request_fails_even_when_fast(self):
        # 遅さの根本: ビルドで作っておらず、アクセスが来てから描いている（2026-11-03 に 30〜90 秒待たされた）
        verdict, reason = cold_check.judge(result(0.6, cache="MISS"), None)
        self.assertEqual(verdict, "fail")
        self.assertIn("MISS", reason)

    def test_slow_twice_fails_and_slow_once_warns(self):
        self.assertEqual(cold_check.judge(result(2.5), result(2.4))[0], "fail")
        self.assertEqual(cold_check.judge(result(2.5), result(0.4))[0], "warn")
        self.assertEqual(cold_check.judge(result(1.9), None)[0], "ok")
        self.assertEqual(cold_check.LIMIT, 2.0)

    def test_errors_and_timeouts_fail(self):
        self.assertEqual(cold_check.judge(result(30.0, status=0, error="TimeoutError"), None)[0], "fail")
        self.assertEqual(cold_check.judge(result(0.2, status=503, cache=""), None)[0], "fail")

    def test_stale_and_plain_pages_pass(self):
        self.assertEqual(cold_check.judge(result(0.5, cache="STALE"), None)[0], "ok")
        self.assertEqual(cold_check.judge(result(0.5, cache=""), None)[0], "ok")


class SampleTest(unittest.TestCase):
    def test_worker_timing_is_summarized_in_seconds(self):
        # Worker の内訳（Server-Timing。Cloudflare の cfEdge・cfWorker とこちらの base・article・app。台帳 W43）
        header = "base-cold;dur=812, article;dur=140, app;dur=95, total;dur=907, cfEdge;dur=20, cfOrigin;dur=0, cfWorker;dur=950"
        self.assertEqual(cold_check.timing_of(header), "base-cold 0.81・article 0.14・app 0.10・cfEdge 0.02・cfWorker 0.95")
        self.assertEqual(cold_check.timing_of(""), "")

    def test_sitemap_paths_and_always_checked_pages(self):
        xml = f"<urlset><url><loc>{BASE}</loc></url><url><loc>{BASE}/articles/a</loc></url><url><loc>https://other.example/x</loc></url></urlset>"
        self.assertEqual(cold_check.sitemap_paths(xml, BASE), ["/", "/articles/a"])
        paths = [f"/articles/{i}" for i in range(100)] + ["/products/chatgpt-voice"]
        chosen = cold_check.choose(paths, 20, seed="s")
        # 2026-11-04 の点検で遅かったページは毎回測る
        for always in ("/articles/openai-gpt-6-astra-comprehensive-guide-matome", "/products/chatgpt-voice"):
            self.assertIn(always, chosen)
        self.assertEqual(len(chosen), len(set(chosen)))
        self.assertEqual(len(chosen), len(cold_check.ALWAYS) + 20)

    def test_requests_are_marked_internal_and_bypass_the_edge_cache(self):
        self.assertEqual(cold_check.HEADERS["X-Saisoku-Internal"], "1")
        self.assertEqual(cold_check.with_params("/a", "9"), "/a?_internal=1&_cold=9")
        self.assertEqual(cold_check.with_params("/a?b=1"), "/a?b=1&_internal=1")


class PlainTest(unittest.TestCase):
    """何も付けない URL の確かめ（seo A1。報告だけ）"""

    def second(self, ver="new", body="<a href=\"/articles/newest\">", status=200, error=""):
        return {"status": status, "ver": ver, "edge": "hit", "body": body, "error": error}

    def test_top_slug_is_the_first_article_link(self):
        self.assertEqual(cold_check.top_slug('<a href="/articles/a-1">x</a><a href="/articles/b">'), "a-1")
        self.assertEqual(cold_check.top_slug(f"<loc>{BASE}/articles/c_2</loc>"), "c_2")
        self.assertEqual(cold_check.top_slug("<p>none</p>"), "")

    def test_old_version_or_missing_article_is_reported(self):
        self.assertTrue(cold_check.judge_plain("/", "new", "newest", self.second())[0])
        ok, message = cold_check.judge_plain("/", "new", "newest", self.second(ver="old"))
        self.assertFalse(ok)
        self.assertIn("古い版", message)
        ok, message = cold_check.judge_plain("/sitemap.xml", "new", "newest", self.second(body="<urlset/>"))
        self.assertFalse(ok)
        self.assertIn("newest", message)
        self.assertFalse(cold_check.judge_plain("/", "new", "newest", self.second(status=0, error="TimeoutError"))[0])

    def test_plain_fetch_has_no_query_string(self):
        seen = []

        class Res:
            status = 200
            headers = {"x-saisoku-ver": "new"}

            def read(self):
                return b'<a href="/articles/newest">'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake(request, timeout):
            seen.append(request.full_url)
            return Res()

        original = cold_check.urllib.request.urlopen
        cold_check.urllib.request.urlopen = fake
        try:
            self.assertEqual(cold_check.plain(None), 0)
        finally:
            cold_check.urllib.request.urlopen = original
        base = cold_check.site_url()
        self.assertTrue(seen[0].startswith(base + "/?_internal=1&_cold="))
        self.assertEqual(seen[1:], [base + "/", base + "/", base + "/sitemap.xml", base + "/sitemap.xml"])

    def test_report_never_fails_the_deploy(self):
        original = cold_check.fetch_body
        cold_check.fetch_body = lambda *a, **k: {"status": 0, "ver": "", "edge": "", "body": "", "error": "URLError"}
        try:
            self.assertEqual(cold_check.plain(None), 0)
        finally:
            cold_check.fetch_body = original


class WorkflowTest(unittest.TestCase):
    def test_plain_check_runs_after_deploy_and_is_report_only(self):
        wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy_cloudflare.yml").read_text("utf-8")
        self.assertIn("scripts/cold_check.py plain", wf)
        self.assertLess(wf.index("npx opennextjs-cloudflare deploy"), wf.index("scripts/cold_check.py plain"))
        step = wf[wf.rindex("- name:", 0, wf.index("scripts/cold_check.py plain")):]
        self.assertIn("continue-on-error: true", step)

    def test_deploy_runs_the_check_after_publishing(self):
        wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy_cloudflare.yml").read_text("utf-8")
        self.assertIn("scripts/cold_check.py version", wf)
        self.assertIn("scripts/cold_check.py check --previous", wf)
        self.assertLess(wf.index("npx opennextjs-cloudflare deploy"), wf.index("scripts/cold_check.py check"))


if __name__ == "__main__":
    unittest.main()
