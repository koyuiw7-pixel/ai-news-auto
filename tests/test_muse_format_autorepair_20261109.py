import unittest
from scripts import muse_format as mf


class AutoRepairTest(unittest.TestCase):
    """2026-11-09 オーナー「落とす理由は嘘だけ」: 書式の問題は落とさず自動で直す"""

    def base(self, **kw):
        d = {"title": "住友生命Vitalityの情報流出　対象かどうかの確かめ方", "genre": "速報解説", "body": "本文" * 50,
             "sources": [{"url": "https://www.sumitomolife.co.jp/news/a", "name": "公式", "facts": "x"}]}
        d.update(kw)
        return d

    def test_long_title_is_shortened_not_rejected(self):
        d = self.base(title="あ" * 30 + "　" + "い" * 40)
        self.assertEqual(mf.problems(d), [])
        self.assertLessEqual(len(d["title"]), mf.TITLE_HARD_MAX)

    def test_exclamation_removed(self):
        d = self.base(title="児童手当の第3子は月3万円！支給月と数え方を整理")
        self.assertEqual(mf.problems(d), [])
        self.assertNotIn("！", d["title"])

    def test_http_upgraded(self):
        d = self.base(sources=[{"url": "http://www.sumitomolife.co.jp/news/a", "name": "公式", "facts": "x"}])
        self.assertEqual(mf.problems(d), [])
        self.assertTrue(d["sources"][0]["url"].startswith("https://"))

    def test_company_help_pages_are_official(self):
        for url in ("https://help.netflix.com/ja/node/24926", "https://www.youtube.com/premium"):
            d = self.base(sources=[{"url": url, "name": "公式", "facts": "x"}])
            self.assertEqual(mf.problems(d), [], url)

    def test_press_source_dropped_when_official_exists(self):
        """主要な報道機関でない報道・まとめは、公式の出典があれば外して続ける"""
        d = self.base(sources=[{"url": "https://www.sankei.com/a", "name": "報道", "facts": "x"},
                               {"url": "https://www.sumitomolife.co.jp/news/a", "name": "公式", "facts": "x"}])
        self.assertEqual(mf.problems(d), [])
        self.assertEqual(len(d["sources"]), 1)
        self.assertIn("sumitomolife", d["sources"][0]["url"])

    def test_major_press_source_is_kept_after_the_official_one(self):
        """2026-11-13 オーナー承認: 主要な報道機関（日経など）は報道の出典として残し、公式の出典のあとに並べる"""
        d = self.base(sources=[{"url": "https://www.nikkei.com/a", "name": "報道", "facts": "x"},
                               {"url": "https://www.sumitomolife.co.jp/news/a", "name": "公式", "facts": "x"}])
        self.assertEqual(mf.problems(d), [])
        self.assertEqual([s.get("press", "") for s in d["sources"]], ["", "日本経済新聞"])
        self.assertIn("sumitomolife", d["sources"][0]["url"])

    def test_press_only_still_rejected(self):
        d = self.base(sources=[{"url": "https://x.com/foo/status/1", "name": "SNS", "facts": "x"}])
        self.assertTrue(mf.problems(d))


if __name__ == "__main__":
    unittest.main()
