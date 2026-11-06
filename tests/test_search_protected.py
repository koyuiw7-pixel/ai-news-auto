"""検索から人が来ている記事は掃除で取り下げない（2026-11-06 オーナー決定・台帳 A46）。

11/3 の掃除で Google 検索のクリックがあった記事まで 410 にして、検索の流入の約4分の1を失った。
content/search_protected.json の記事は、scripts/retire_articles.py のどの区分でも、apply() でも取り下げない。"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import retire_articles  # noqa: E402
import search_protected  # noqa: E402


class SearchProtectedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "search_protected.json"
        self.path.write_text(json.dumps({"articles": {"earning": {"clicks": 7, "impressions": 118}}}), "utf-8")
        self._protected = search_protected.protected_slugs
        self._posts = retire_articles.sns_posts
        search_protected.protected_slugs = lambda path=self.path: self._protected(self.path)
        retire_articles.sns_posts = lambda everywhere=False: {}

    def tearDown(self):
        search_protected.protected_slugs = self._protected
        retire_articles.sns_posts = self._posts
        self.tmp.cleanup()

    def test_split_refuses_protected_slugs(self):
        self.assertEqual((["other"], ["earning"]), search_protected.split(["other", "earning"], self.path))

    def test_every_plan_keeps_protected_articles(self):
        now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        old = (now - timedelta(days=30)).isoformat()
        notice = "財務省、製造たばこの小売定価の認可情報を随時公開"
        arts = [
            {"slug": "earning", "title": notice, "publishedAt": old, "channelSlug": "two-minute-papers", "body": "短い"},
            {"slug": "other", "title": notice, "publishedAt": old, "channelSlug": "two-minute-papers", "body": "短い"},
        ]
        for picked, kept in (retire_articles.plan_notice(arts, now), retire_articles.plan(arts, now), retire_articles.plan_noindex(arts, now)):
            self.assertNotIn("earning", picked)
            self.assertIn("other", picked)
            self.assertIn("earning", {k["slug"] for k in kept})
            self.assertIn("A46", next(k["why"] for k in kept if k["slug"] == "earning"))
        self.assertEqual({"other"}, set(retire_articles.plan_creator(arts)))

    def test_apply_refuses_protected_even_if_planned(self):
        """計画に入ってしまっても、apply() が最後に拒む（記事の JSON を消さない・retired.json に足さない）"""
        root = Path(self.tmp.name)
        arts = root / "articles"
        arts.mkdir()
        for slug in ("earning", "other"):
            (arts / f"{slug}.json").write_text(json.dumps({"slug": slug, "title": slug, "body": ""}), "utf-8")
        saved = (retire_articles.ARTICLES, retire_articles.RETIRED, retire_articles.ROOT)
        retire_articles.ARTICLES, retire_articles.RETIRED, retire_articles.ROOT = arts, root / "retired.json", root
        try:
            retire_articles.apply({"earning": {"reason": "thin", "title": "e"}, "other": {"reason": "thin", "title": "o"}},
                                  datetime(2026, 11, 20, tzinfo=timezone.utc))
        finally:
            retire_articles.ARTICLES, retire_articles.RETIRED, retire_articles.ROOT = saved
        self.assertTrue((arts / "earning.json").exists())
        self.assertFalse((arts / "other.json").exists())
        store = json.loads((root / "retired.json").read_text("utf-8"))
        self.assertEqual({"other"}, set(store["articles"]))


class ProtectedListTest(unittest.TestCase):
    """本物の一覧: 守る記事は公開中で、取り下げの一覧（content/retired.json）に入っていない"""

    def test_protected_articles_are_live_and_not_retired(self):
        data = search_protected.load()
        self.assertTrue(data.get("articles"), "content/search_protected.json が空")
        self.assertIn("Search Console", data.get("window", "") + data.get("_note", ""))
        retired = set(json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"])
        for slug, row in data["articles"].items():
            self.assertTrue((ROOT / "content" / "articles" / f"{slug}.json").exists(), f"{slug} の記事が無い")
            self.assertNotIn(slug, retired, f"{slug} が取り下げの一覧に残っている")
            self.assertGreaterEqual(int(row.get("clicks", 0)) + int(row.get("impressions", 0)), 1)

    def test_restored_articles_are_not_new_sns_candidates(self):
        """書き直して戻した記事は、作った日時（generatedAt）を昔のままにして SNS の新着の候補に入れない"""
        for slug in search_protected.protected_slugs():
            a = json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))
            if not a.get("restoredAt"):
                continue
            made = datetime.fromisoformat(a["generatedAt"].replace("Z", "+00:00"))
            restored = datetime.fromisoformat(a["restoredAt"].replace("Z", "+00:00"))
            self.assertGreater(restored - made, timedelta(days=3), f"{slug} の generatedAt が新しい")

    def test_restored_articles_are_excluded_from_every_sns_path(self):
        """書き直して戻した記事は、Threads の2週間の補充枠などでも選ばない（すべての SNS の経路が使う sns_plan.excluded）"""
        import sns_plan  # noqa: PLC0415

        self.assertTrue(sns_plan.excluded({"slug": "x", "title": "厚労省の調査", "restoredAt": "2026-11-06T00:00:00+00:00"}))
        for slug in search_protected.protected_slugs():
            a = json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))
            if a.get("restoredAt"):
                self.assertTrue(sns_plan.excluded(a), slug)

if __name__ == "__main__":
    unittest.main()
