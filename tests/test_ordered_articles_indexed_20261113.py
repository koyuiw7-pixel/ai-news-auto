"""注文した記事（Muse）・話題のレーンの記事が、気づかないまま noindex で出ない（2026-11-13 オーナー「とにかく数字」）。

きっかけ: その日いちばんの話題の記事（紅白歌合戦の出場歌手一覧）が noindex で出て、Google に登録されなかった。
見張り: 直近3日に載せた Muse の記事（writer == "muse"）と話題のレーンの記事（trendKeyword・searchTrend・trendLane）は、
検索に出さない理由（indexnow.noindex_reason）が None か "duplicate" だけ。手で検索から外すときは記事に noindexNote（理由の文）を書く。
ネットワーク・LLM は使わない。
"""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402

DAYS = 3
BODY = "## 概要\n" + "本文" * 600


def ordered(article: dict) -> bool:
    """注文した記事（Muse）か、話題のレーンの記事か"""
    return article.get("writer") == "muse" or bool(article.get("trendKeyword") or article.get("searchTrend") or article.get("trendLane"))


def when(article: dict) -> datetime | None:
    return indexnow._parse(article.get("generatedAt") or article.get("publishedAt"))


def silent_noindex(articles: list[dict], days: int = DAYS) -> list[str]:
    """直近 days 日の注文した記事・話題の記事のうち、重複以外の理由で検索に出ないもの（「slug: 理由」）。
    基準の時刻は、記事の中でいちばん新しい載せた時刻（同じ記事の束なら、いつ動かしても結果が同じ）"""
    times = [t for t in (when(a) for a in articles) if t]
    if not times:
        return []
    since = max(times) - timedelta(days=days)
    dups = indexnow.duplicate_slugs(articles)
    out = []
    for a in articles:
        t = when(a)
        if not ordered(a) or t is None or t < since:
            continue
        reason = indexnow.noindex_reason(a, dups)
        if reason in (None, "duplicate"):
            continue
        if reason == "manual" and str(a.get("noindexNote") or "").strip():
            continue  # 手で外した（理由が書いてある）
        out.append(f"{a.get('slug')}: {reason}")
    return out


class OrderedArticlesAreIndexedTest(unittest.TestCase):
    def test_recent_muse_and_trend_articles_are_indexable(self):
        articles = []
        for path in sorted((ROOT / "content" / "articles").glob("*.json")):
            try:
                data = json.loads(path.read_text("utf-8"))
            except ValueError:
                continue
            if isinstance(data, dict):
                data.setdefault("slug", path.stem)
                articles.append(data)
        bad = silent_noindex(articles)
        self.assertEqual([], bad, "Muse・話題の記事が noindex で出ています（scripts/indexnow.py の noindex_reason）: " + " / ".join(bad[:10]))

    def rec(self, slug, title, **kw):
        base = {"slug": slug, "title": title, "body": BODY, "genreSlug": "entertainment", "generatedAt": "2026-11-13T03:00:00+00:00",
                "sourceUrl": f"https://example.test/{slug}"}
        base.update(kw)
        return base

    def test_titles_without_axis_words_are_indexed(self):
        """題名に軸の語（お金・暮らし）が無くても、公開した記事は検索に出す"""
        kohaku = self.rec("kohaku", "紅白歌合戦2026 出場歌手一覧（全41組）初出場7組と出場回数", writer="muse")
        nengajo = self.rec("nengajo", "2027年用年賀状はいつから？引受開始は12月20日", writer="muse", genreSlug="lifestyle")
        trend = self.rec("trend", "ウォリアーズが開幕戦に勝利", trendKeyword="ウォリアーズ", genreSlug="sports")
        for a in (kohaku, nengajo, trend):
            self.assertIsNone(indexnow.noindex_reason(a), a["slug"])
            self.assertEqual("検索: 出す（index）", indexnow.index_status_line(a))
        self.assertEqual([], silent_noindex([kohaku, nengajo, trend]))

    def test_guard_catches_silent_noindex(self):
        empty = self.rec("empty", "本文の無い Muse の記事", writer="muse", body="短い")
        by_hand = self.rec("by-hand", "手で外した話題の記事", trendKeyword="話題", indexable=False)
        noted = self.rec("noted", "理由を書いて外した記事", trendKeyword="話題2", indexable=False, noindexNote="報道だけが出典のため")
        dup = self.rec("dup", "重複の記事", writer="muse", duplicateOf="kept")
        old = self.rec("old", "古い記事", writer="muse", body="短い", generatedAt="2026-11-01T00:00:00+00:00")
        auto = self.rec("auto", "自動の記事", body="短い")
        self.assertEqual(["empty: no-body", "by-hand: manual"], silent_noindex([empty, by_hand, noted, dup, old, auto]))
        self.assertIn("理由 no-body", indexnow.index_status_line(empty))
        self.assertIn("noindex", indexnow.index_status_line(by_hand))

    def test_publish_logs_say_whether_the_article_is_indexed(self):
        muse = (ROOT / "scripts" / "muse_articles.py").read_text("utf-8")
        web = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn('log(f"   [muse] {index_status(record)}")', muse)
        self.assertEqual(2, web.count('log(f"   [trend] {indexnow.index_status_line(record)}")'))
        # 検索に出さない切り替えを使ったときは、理由を記事に残す
        self.assertIn('record["noindexNote"] = "TREND_PRESS_NOINDEX=1', web)

    def test_no_title_vocabulary_reason_remains(self):
        """題名の語で検索から外す理由（no-life-link）は、Python にもサイトにも残っていない"""
        py = (ROOT / "scripts" / "indexnow.py").read_text("utf-8")
        ts = (ROOT / "lib" / "indexing.ts").read_text("utf-8")
        self.assertNotIn('"no-life-link"', py)
        self.assertNotIn('"no-life-link"', ts)


if __name__ == "__main__":
    unittest.main()
