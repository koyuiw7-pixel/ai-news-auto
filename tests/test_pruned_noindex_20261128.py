"""読まれていない記事を検索から外す一覧（2026-11-28 オーナー承認・根本の見直しの3）。

- 一覧 content/noindex_pruned.json の記事は、公開したまま検索に出さない（noindex_reason が pruned。取り下げない）
- 一覧に入れるのは作ってから14日たった記事だけ（新しく公開した記事はすぐに外さない）
- Search Console の表示・クリックがある記事、まとめ・比較の記事は入れない
ネットワークは使わない。
"""
import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import search_protected  # noqa: E402

DATA = json.loads((ROOT / "content" / "noindex_pruned.json").read_text("utf-8"))


def _when(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _record(slug: str):
    path = ROOT / "content" / "articles" / f"{slug}.json"
    return json.loads(path.read_text("utf-8")) if path.exists() else None


class PrunedListTest(unittest.TestCase):
    def test_shape(self):
        slugs = DATA["slugs"]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(slugs, sorted(slugs))
        self.assertEqual(indexnow.PRUNED, frozenset(slugs))

    def test_only_old_articles(self):
        cutoff = _when(DATA["decidedAt"]) - timedelta(days=DATA.get("minAgeDays", 14))
        young = []
        for slug in DATA["slugs"]:
            record = _record(slug)
            if record is None:
                continue
            made = _when(record.get("generatedAt") or record.get("publishedAt"))
            if made > cutoff:
                young.append(slug)
        self.assertEqual(young, [])

    def test_no_search_signals_no_roundups(self):
        protected = search_protected.protected_slugs(impressions90=search_protected.IMPRESSIONS90)
        self.assertEqual(sorted(set(DATA["slugs"]) & protected), [])
        bad = [s for s in DATA["slugs"] if (r := _record(s)) and (r.get("type") == "roundup" or r.get("kind"))]
        self.assertEqual(bad, [])

    def test_reason_and_not_retired(self):
        slug = next(s for s in DATA["slugs"] if _record(s))
        good = {"slug": slug, "title": "児童手当の支給額が変わる", "genreSlug": "public", "body": "あ" * 3000}
        self.assertEqual(indexnow.noindex_reason(good), "pruned")
        self.assertIsNone(indexnow.noindex_reason({**good, "slug": "not-in-pruned-list"}))
        self.assertIsNone(indexnow.noindex_reason({**good, "indexable": True}))
        self.assertIn("pruned", indexnow.NOINDEX_LABELS)


class SiteRuleTest(unittest.TestCase):
    def test_lib_indexing_reads_same_file(self):
        text = (ROOT / "lib" / "indexing.ts").read_text("utf-8")
        self.assertIn('import pruned from "../content/noindex_pruned.json"', text)
        self.assertIn('return "pruned"', text)

    def test_retire_skips_pruned(self):
        text = (ROOT / "scripts" / "retire_articles.py").read_text("utf-8")
        self.assertIn('"pruned"', text)


if __name__ == "__main__":
    unittest.main()
