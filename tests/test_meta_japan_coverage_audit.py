import unittest
from scripts.meta_japan_coverage_audit import audit, normalize, parse

class TestMetaJapanCoverageAudit(unittest.TestCase):
    def test_dedup_and_cover_exact_url(self):
        u='https://about.fb.com/ja/news/2026/10/muse-japan/'
        page=f'<a href="{u}">Meta Muse 日本で提供開始</a><a href="{u}"><img></a><a href="https://about.fb.com/ja/news/2026/10/other/">決算</a>'
        r=audit(page,{u})
        self.assertEqual(r['totalLinks'],2)
        self.assertEqual(len(r['relevant']),1)
        self.assertTrue(r['relevant'][0]['covered'])
        self.assertEqual(normalize(u+'?a=b'),u)

    def test_invalid_page_is_not_no_news(self):
        with self.assertRaises(ValueError): parse('<html>error page</html>')

if __name__ == '__main__': unittest.main()
