"""公開確認の回帰テスト。ネット接続・SNS投稿は行わない。"""

import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import threads_post


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


if __name__ == "__main__":
    unittest.main()
