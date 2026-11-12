import pathlib
import sys
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import websub_ping  # noqa: E402


class WebSubTest(unittest.TestCase):
    def test_feeds_declare_hub(self):
        for f in ["app/feed.xml/route.ts", "app/feeds/news.xml/route.ts"]:
            s = (ROOT / f).read_text()
            self.assertIn('rel="hub"', s, f)
            self.assertIn(websub_ping.HUB, s, f)

    def test_request_is_publish_form(self):
        req = websub_ping.build_request("https://ai-tech-express.jp/feed.xml")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.full_url, websub_ping.HUB)
        body = urllib.parse.parse_qs(req.data.decode())
        self.assertEqual(body["hub.mode"], ["publish"])
        self.assertEqual(body["hub.url"], ["https://ai-tech-express.jp/feed.xml"])

    def test_ping_never_raises(self):
        orig = websub_ping.urllib.request.urlopen
        def boom(*a, **k):
            raise OSError("network down")
        websub_ping.urllib.request.urlopen = boom
        try:
            self.assertEqual(websub_ping.ping("https://ai-tech-express.jp/feed.xml"), 0)
        finally:
            websub_ping.urllib.request.urlopen = orig

    def test_deploy_workflow_pings_after_live(self):
        wf = (ROOT / ".github/workflows/deploy_cloudflare.yml").read_text()
        i = wf.find("scripts/websub_ping.py")
        self.assertGreater(i, 0)
        self.assertGreater(i, wf.find("Notify IndexNow"))


if __name__ == "__main__":
    unittest.main()
