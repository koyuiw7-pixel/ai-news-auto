"""公開確認の回帰テスト。ネット接続・SNS投稿は行わない。"""

import sys
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import threads_post
import threads_learn


class PublishCheckTest(unittest.TestCase):
    url = "https://ai-tech-express.jp/articles/example"

    def response(self, status):
        response = MagicMock()
        response.__enter__.return_value.status = status
        return response

    def http_error(self, status):
        error = urllib.error.HTTPError(self.url, status, "not ready", {}, None)
        self.addCleanup(error.close)
        return error

    def test_identified_head_accepts_only_published_page(self):
        with patch.object(threads_post.urllib.request, "urlopen", return_value=self.response(200)) as open_url:
            self.assertTrue(threads_post.wait_until_live(self.url, timeout=0))
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_method(), "HEAD")
        self.assertEqual(request.full_url, self.url)
        self.assertEqual(request.get_header("User-agent"), "SaisokuPublishCheck/1.0 (+https://ai-tech-express.jp)")
        self.assertEqual(open_url.call_args.kwargs["timeout"], 20)

    def test_http_errors_are_not_treated_as_published(self):
        for status in (403, 404, 429, 500, 503):
            with self.subTest(status=status):
                error = self.http_error(status)
                with patch.object(threads_post.urllib.request, "urlopen", side_effect=error):
                    self.assertFalse(threads_post.wait_until_live(self.url, timeout=0))

    def test_other_success_status_is_not_a_published_article(self):
        with patch.object(threads_post.urllib.request, "urlopen", return_value=self.response(204)):
            self.assertFalse(threads_post.wait_until_live(self.url, timeout=0))

    def test_connection_failure_is_not_treated_as_published(self):
        with patch.object(threads_post.urllib.request, "urlopen", side_effect=urllib.error.URLError("unavailable")):
            self.assertFalse(threads_post.wait_until_live(self.url, timeout=0))

    def test_deployment_can_become_ready_while_waiting(self):
        error = self.http_error(404)
        with patch.object(threads_post.urllib.request, "urlopen", side_effect=[error, self.response(200)]) as open_url, \
             patch.object(threads_post.time, "monotonic", side_effect=[0, 1]), \
             patch.object(threads_post.time, "sleep") as sleep:
            self.assertTrue(threads_post.wait_until_live(self.url, timeout=30))
            self.assertEqual(open_url.call_count, 2)
            sleep.assert_called_once_with(15)

    def test_wait_stops_at_deadline(self):
        error = self.http_error(403)
        with patch.object(threads_post.urllib.request, "urlopen", side_effect=error) as open_url, \
             patch.object(threads_post.time, "monotonic", side_effect=[0, 1, 30]), \
             patch.object(threads_post.time, "sleep") as sleep:
            self.assertFalse(threads_post.wait_until_live(self.url, timeout=30))
            self.assertEqual(open_url.call_count, 2)
            sleep.assert_called_once_with(15)


class LearningIsolationTest(unittest.TestCase):
    def test_verification_post_does_not_change_threads_or_x_format_results(self):
        common = {"postedAt": "2026-10-30T01:00:00+00:00", "style": "standalone", "format": "classic"}
        state = {"posted": {
            "ordinary": {**common, "metrics": {"views": 10}, "xMetrics": {"impressions": 20}},
            "verification": {**common, "format": "hook_thread", "metrics": {"views": 1000}, "xMetrics": {"impressions": 2000},
                             "verification": {"excludeFromLearning": True}},
            "digest": {**common, "style": "digest", "metrics": {"views": 1000}, "xMetrics": {"impressions": 2000}},
        }}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "learning.json"
            with patch.object(sys, "argv", ["threads_learn.py", "--offline"]), \
                 patch.object(threads_learn, "load_state", return_value=state), \
                 patch.object(threads_learn, "LEARNING_PATH", output), \
                 patch.object(threads_learn, "fetch_metrics", side_effect=AssertionError("network forbidden")):
                self.assertEqual(threads_learn.main(), 0)
            result = json.loads(output.read_text())
        self.assertEqual((result["posts"], result["xPosts"]), (1, 1))
        self.assertEqual(result["axes"]["postFormat"]["classic"]["avgViews"], 10)
        self.assertEqual(result["xAxes"]["postFormat"]["classic"]["avgViews"], 20)
        self.assertNotIn("hook_thread", result["axes"]["postFormat"])


if __name__ == "__main__":
    unittest.main()
