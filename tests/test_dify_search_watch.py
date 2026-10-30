"""変更検知の誤報・基準消失を防ぐ。外部接続なし。"""
import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dify_search_watch as watch


class DifySearchWatchTest(unittest.TestCase):
    date1 = "2026-10-30T04:00:00+00:00"
    date2 = "2026-10-30T10:00:00+00:00"

    def release(self, body="Before upgrade, back up the database and files.", **extra):
        return json.dumps({"tag_name": "1.18.0", "name": "Release 1.18.0", "body": body,
                           "draft": False, "prerelease": False,
                           "html_url": "https://github.com/langgenius/dify/releases/tag/1.18.0", **extra}).encode()

    def docs(self, tail="* RAM >= 4 GiB"):
        return ("# Deploy Dify with Docker Compose\n\n## Before Deployment\n" + tail).encode()

    def fetcher(self, release=None, docs=None):
        values = {"release": release or self.release(), "docker-compose": docs or self.docs()}
        return lambda source: values[source["id"]]

    def baseline(self):
        return watch.run_watch({}, self.date1, self.fetcher())[0]

    def test_first_run_is_baseline_not_a_change_or_question(self):
        state, report = watch.run_watch({}, self.date1, self.fetcher())
        self.assertEqual([r["status"] for r in report["sources"]], ["baseline", "baseline"])
        self.assertEqual(report["candidates"], [])
        self.assertEqual(len(state["sources"]), 2)

    def test_unchanged_ignores_download_counts_metadata_and_line_endings(self):
        state = self.baseline()
        body = "Before upgrade, back up the database and files.\r\n\r\n"
        _, report = watch.run_watch(state, self.date2, self.fetcher(self.release(body, assets=[{"download_count": 999}], updated_at=self.date2)))
        self.assertEqual([r["status"] for r in report["sources"]], ["unchanged", "unchanged"])
        self.assertEqual(report["candidates"], [])

    def test_changed_token_creates_review_evidence_and_keeps_queue(self):
        state = self.baseline()
        changed = self.release("Before upgrade, configure DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN; old runtimes are incompatible.")
        updated, report = watch.run_watch(state, self.date2, self.fetcher(changed))
        self.assertEqual(report["sources"][0]["status"], "changed")
        self.assertTrue(any("トークン" in item["question"] for item in report["candidates"]))
        item = report["candidates"][0]
        self.assertNotEqual(item["previousHash"], item["currentHash"])
        self.assertEqual(item["previousCheckedAt"], self.date1)
        self.assertEqual(item["status"], "needs_editorial_review")
        self.assertIn("DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN", item["evidenceAfter"])
        _, repeated = watch.run_watch(updated, self.date2, self.fetcher(changed))
        self.assertEqual(repeated["candidates"], [])
        self.assertEqual(repeated["reviewQueue"], report["candidates"])

    def test_failed_fetch_retains_previous_good_baseline(self):
        state = self.baseline()
        def failing(source):
            if source["id"] == "release":
                raise urllib.error.URLError("network unavailable")
            return self.docs()
        updated, report = watch.run_watch(state, self.date2, failing)
        self.assertEqual(updated["sources"]["release"], state["sources"]["release"])
        self.assertEqual(report["candidates"], [])
        self.assertTrue(report["errors"][0]["previousBaselineRetained"])

    def test_html_error_or_oversized_source_does_not_replace_baseline(self):
        state = self.baseline()
        for invalid in (b"<html>Service unavailable</html>", b"x" * (watch.MAX_BYTES + 1)):
            with self.subTest(size=len(invalid)):
                updated, report = watch.run_watch(state, self.date2, self.fetcher(docs=invalid))
                self.assertEqual(updated["sources"]["docker-compose"], state["sources"]["docker-compose"])
                self.assertEqual(len(report["errors"]), 1)

    def test_draft_prerelease_and_wrong_repo_are_rejected(self):
        for extra in ({"draft": True}, {"prerelease": True}, {"html_url": "https://example.com/1.18.0"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                watch.parse_source(watch.SOURCES[0], self.release(**extra))

    def test_source_set_change_rebaselines_instead_of_claiming_a_change(self):
        state = self.baseline()
        state["sourceFingerprint"] = "old-source-set"
        _, report = watch.run_watch(state, self.date2, self.fetcher())
        self.assertTrue(report["baselineReset"])
        self.assertEqual(report["candidates"], [])

    def test_redirect_to_other_host_or_plain_http_is_blocked(self):
        handler = watch.SameHostRedirect()
        request = urllib.request.Request(watch.SOURCES[0]["url"])
        for url in ("https://example.com/", "http://api.github.com/anything"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", {}, url)


if __name__ == "__main__":
    unittest.main()
