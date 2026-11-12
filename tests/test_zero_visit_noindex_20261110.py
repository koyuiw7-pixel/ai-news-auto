"""14日間訪問0の記事の noindex（2026-11-10 オーナー承認・台帳 A61）。

- 一覧 content/noindex_zero_visit.json の記事は、公開したまま検索に出さない（サイトマップ・ニュース用サイトマップ・IndexNow からも外れる）
- 取り下げ（retire_articles.plan_noindex）の対象にしない
- 一覧に入れるのは作ってから14日たった記事だけ。Search Console の表示・検索からの訪問がある記事は入れない
- 記事ページは広告（AdSense）と提携の囲みを出さない（app/articles/[slug]/page.tsx）
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

DATA = json.loads((ROOT / "content" / "noindex_zero_visit.json").read_text("utf-8"))


def _when(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class ZeroVisitListTest(unittest.TestCase):
    def test_list_shape(self):
        slugs = DATA["slugs"]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(slugs, sorted(slugs))
        self.assertEqual(indexnow.ZERO_VISIT, frozenset(slugs))

    def test_only_pages_older_than_14_days_when_listed(self):
        # 一覧の数え始め（window.to）の時点で、作ってから14日たっていない記事は入れない
        cutoff = _when(DATA["window"]["to"]) - timedelta(days=DATA.get("minAgeDays", 14))
        young = []
        for slug in DATA["slugs"]:
            path = ROOT / "content" / "articles" / f"{slug}.json"
            if not path.exists():
                continue  # 取り下げ済み（一覧に残っていても害はない）
            record = json.loads(path.read_text("utf-8"))
            made = _when(record.get("generatedAt") or record.get("publishedAt"))
            if made > cutoff:
                young.append((slug, made.isoformat()))
        self.assertEqual(young, [])

    def test_no_search_signals(self):
        # 検索の守り（Search Console の表示・検索からの訪問）がある記事は入れない
        text = (ROOT / "content" / "search_positions.json").read_text("utf-8") + \
            (ROOT / "content" / "search_protected.json").read_text("utf-8")
        hit = [s for s in DATA["slugs"] if f'"{s}"' in text or f"/articles/{s}\"" in text or f"/articles/{s}?" in text]
        self.assertEqual(hit, [])

    def test_no_roundups(self):
        roundups = []
        for slug in DATA["slugs"]:
            path = ROOT / "content" / "articles" / f"{slug}.json"
            if path.exists() and json.loads(path.read_text("utf-8")).get("type") == "roundup":
                roundups.append(slug)
        self.assertEqual(roundups, [])


class ZeroVisitRuleTest(unittest.TestCase):
    def setUp(self):
        self.slug = DATA["slugs"][0]
        self.good = {"slug": self.slug, "title": "ChatGPTの料金が月20ドルから変わる", "genreSlug": "ai", "body": "a" * 3000}

    def test_noindex_reason(self):
        self.assertEqual(indexnow.noindex_reason(self.good), "zero-visit")
        self.assertFalse(indexnow.is_indexable(self.good))
        self.assertIsNone(indexnow.noindex_reason({**self.good, "slug": "not-in-list"}))
        # 手で検索に出すと決めた記事（indexable: true）はそちらが先
        self.assertIsNone(indexnow.noindex_reason({**self.good, "indexable": True}))

    def test_not_retired(self):
        import retire_articles  # noqa: PLC0415
        from datetime import timezone  # noqa: PLC0415
        record = json.loads((ROOT / "content" / "articles" / f"{self.slug}.json").read_text("utf-8"))
        original = retire_articles.recent_sns
        retire_articles.recent_sns = lambda *a, **k: set()
        try:
            picked, _kept = retire_articles.plan_noindex([record], datetime.now(timezone.utc))
        finally:
            retire_articles.recent_sns = original
        self.assertNotIn(self.slug, picked)

    def test_article_page_hides_pr_boxes(self):
        page = (ROOT / "app" / "articles" / "[slug]" / "page.tsx").read_text("utf-8")
        self.assertIn("const noPr = isZeroVisit(article.slug);", page)
        # 2026-11-12: AdSense の審査の期間（lib/ad-review.ts の adReview）も同じ枠を消す
        for needle in ("noPr || adReview ? undefined : compareOffersFor(article)", "compareOffers || noPr || adReview ? undefined : actionAdWithBenefits(actionAdForArticle(article)",
                       "noPr || adReview ? undefined : shopLinkForArticle(article)", "!noPr && !adReview && bodyTail", "!noPr && !adReview && !actionAd"):
            self.assertIn(needle, page)
        # 得のカード（ad-benefits）は広告・商品枠が undefined ならそのまま undefined を返す＝noPr では得のカードも出ない
        self.assertIn("const offerPlan = noPr\n    ? { offer: undefined, rail: undefined, inline: undefined }", page)
        bene = (ROOT / "lib" / "ad-benefits.ts").read_text("utf-8")
        self.assertIn("return ad ? { ...ad, items: withArticleBenefits(ad.items, slug) } : ad;", bene)
        self.assertIn("return offer ? { ...offer, items: itemsWithArticleBenefits(offer.items, slug) } : offer;", bene)
        # AdSense の枠は検索に出す記事だけ（showAds = isIndexable）。zero-visit は isIndexable が false
        self.assertIn("const showAds = isIndexable(", page)


if __name__ == "__main__":
    unittest.main()
