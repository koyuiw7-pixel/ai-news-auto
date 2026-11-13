"""SEO A16「更新日を正直にする」。外部への通信なし。

1. 記事の updatedAt を書くのは scripts/updated_at.py だけ（ほかは状態ファイル・ガイド・製品などの記録で、理由つきの例外）
2. 事実・訂正・続報・資料の読み直しでは更新日時を進めて更新履歴を1行。言い回し・題名・章立てでは動かさない
3. 深掘りの欄を公開直後（30分以内）に足したときは、公開の準備の一部として更新履歴に出さない
4. サイトマップにビルドの時刻・changefreq・priority を書かない。一覧は載っている記事の日時
"""

import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import search_refresh  # noqa: E402
import updated_at  # noqa: E402

# 記事ではない記録の updatedAt（その記録自体を書きかえた時刻）。記事の更新日時ではないので例外
NOT_ARTICLE_WRITERS = {
    "buying_guides.py",  # 比較ガイドの記録（生成し直したとき）
    "deep_dive.py",  # state/deep_dive.json（試した記録）
    "muse_images.py",  # 画像の状態ファイル
    "muse_articles.py",  # Muse の取り込み結果
    "muse_ingest.py",  # Muse の受け取り待ちの列
    "muse_queue.py",  # Muse の依頼の列
    "pricing_watch.py",  # 公式の料金の表（料金が変わった日だけ。checkedAt と分けている）
    "products.py",  # 製品の名簿
}
WRITE = re.compile(r"""\[["']updatedAt["']\]\s*=(?!=)""")


class UpdatedAtGate(unittest.TestCase):
    def test_only_helper_writes_article_updated_at(self):
        offenders = []
        for path in sorted((ROOT / "scripts").glob("*.py")):
            if path.name == "updated_at.py" or path.name in NOT_ARTICLE_WRITERS:
                continue
            for n, line in enumerate(path.read_text("utf-8").splitlines(), 1):
                if WRITE.search(line):
                    offenders.append(f"{path.name}:{n}")
        self.assertEqual([], offenders, "記事の更新日時は scripts/updated_at.py の touch_updated で書く")

    def test_writers_use_helper(self):
        for name in ("followup.py", "quake.py", "search_refresh.py", "depth_fields.py", "dify_answer_update.py"):
            self.assertIn("updated_at.touch_", (ROOT / "scripts" / name).read_text("utf-8"), name)


class TouchUpdated(unittest.TestCase):
    def test_fact_kinds_stamp_and_note(self):
        rec = {"slug": "x"}
        at = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)
        self.assertTrue(updated_at.touch_updated(rec, "followup", at=at, title="続報: 施行されました", source_url="https://www.mhlw.go.jp/x", source_name="厚生労働省"))
        self.assertEqual("2026-11-10T03:00:00+00:00", rec["updatedAt"])
        self.assertEqual({"at": rec["updatedAt"], "kind": "followup", "title": "続報: 施行されました",
                          "sourceUrl": "https://www.mhlw.go.jp/x", "sourceName": "厚生労働省"}, rec["updates"][-1])
        for kind in ("facts", "correction", "refresh"):
            self.assertTrue(updated_at.touch_updated({}, kind, at=at))

    def test_style_kinds_never_stamp(self):
        for kind in ("style", "title", "sections"):
            rec = {"updatedAt": "2026-11-01T00:00:00+00:00"}
            self.assertFalse(updated_at.touch_updated(rec, kind))
            self.assertEqual({"updatedAt": "2026-11-01T00:00:00+00:00"}, rec)

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            updated_at.touch_updated({}, "polish")

    def test_guide_without_note(self):
        rec = {"updatedAt": "old"}
        updated_at.touch_updated(rec, "correction", at="2026-11-10T12:00:00+09:00", note=False)
        self.assertEqual({"updatedAt": "2026-11-10T12:00:00+09:00"}, rec)

    def test_updates_capped(self):
        rec = {"updates": [{"at": str(i)} for i in range(25)]}
        updated_at.touch_updated(rec, "facts", at="z")
        self.assertEqual(updated_at.MAX_UPDATES, len(rec["updates"]))
        self.assertEqual("z", rec["updates"][-1]["at"])

    def test_search_refresh_stamp_leaves_note(self):
        now = datetime(2026, 11, 16, 1, 0, tzinfo=timezone.utc)
        new = search_refresh.stamp({"slug": "x"}, {"query": "q", "position": 8, "impressions": 20}, now)
        self.assertEqual("2026-11-16T01:00:00+00:00", new["updatedAt"])
        self.assertEqual("refresh", new["updates"][-1]["kind"])


class Depth(unittest.TestCase):
    born = "2026-11-08T00:00:00+00:00"

    def test_depth_right_after_publish_is_not_an_update(self):
        rec = {"generatedAt": self.born}
        at = datetime(2026, 11, 8, 0, 10, tzinfo=timezone.utc)
        self.assertFalse(updated_at.touch_depth(rec, {"officialDesk": [1]}, at=at))
        self.assertNotIn("updatedAt", rec)

    def test_depth_later_is_a_fact_update(self):
        rec = {"generatedAt": self.born}
        at = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(updated_at.touch_depth(rec, {"officialDesk": [1], "todaySteps": [1, 2]}, at=at))
        self.assertEqual("facts", rec["updates"][-1]["kind"])
        self.assertIn("「公式の窓口」", rec["updates"][-1]["title"])
        self.assertIn("「今日やること」", rec["updates"][-1]["title"])

    def test_depth_without_fact_fields_is_not_an_update(self):
        self.assertFalse(updated_at.touch_depth({"generatedAt": self.born}, {}, at=datetime(2026, 11, 9, tzinfo=timezone.utc)))

    def test_backfill_uses_depth_time_and_is_idempotent(self):
        rec = {"generatedAt": self.born, "depthAt": "2026-11-08T05:00:00+00:00", "insight": ["x"],
               "updatedAt": "2026-11-04T01:17:57+00:00"}  # 一括で押された日時（更新履歴なし）
        self.assertTrue(updated_at.backfill_depth(rec))
        self.assertEqual("2026-11-08T05:00:00+00:00", rec["updatedAt"])
        self.assertEqual(1, len(rec["updates"]))
        self.assertFalse(updated_at.backfill_depth(rec))

    def test_backfill_keeps_newer_followup(self):
        rec = {"generatedAt": self.born, "depthAt": "2026-11-08T05:00:00+00:00", "insight": ["x"],
               "updatedAt": "2026-11-09T00:00:00+00:00", "updates": [{"at": "2026-11-09T00:00:00+00:00", "title": "続報"}]}
        self.assertTrue(updated_at.backfill_depth(rec))
        self.assertEqual("2026-11-09T00:00:00+00:00", rec["updatedAt"])
        self.assertEqual(["2026-11-08T05:00:00+00:00", "2026-11-09T00:00:00+00:00"], [u["at"] for u in rec["updates"]])


class Sitemap(unittest.TestCase):
    src = (ROOT / "lib" / "sitemap.ts").read_text("utf-8")

    def test_no_build_time_or_changefreq(self):
        self.assertNotIn("changeFrequency", self.src)
        self.assertNotIn("<changefreq>", self.src)
        self.assertNotIn("<priority>", self.src)
        self.assertNotIn("new Date()", self.src, "ビルドの時刻を lastmod にしない")

    def test_listing_pages_use_member_dates(self):
        for needle in ("newestOf(getArticlesByGenre", "newestOf(getArticlesByChannel", "newestOf(getArticlesByTag", "newestOf(eventArticles(event))"):
            self.assertIn(needle, self.src)

    def test_display_ignores_untrusted_updated_at(self):
        idx = (ROOT / "lib" / "article-index.mjs").read_text("utf-8")
        self.assertIn("updatedAt: trustedUpdatedAt(parsed)", idx)

    def test_only_touch_updated_writes_article_updated_at(self):
        """記事の updatedAt を書く自動の処理は scripts/updated_at.py だけ（2026-11-13: 履歴が無くても updatedAt を「最終更新」に出すようにしたので、
        言い回し・章立て・かんたん版の作り直しが直接書くと、中身の変わらない更新日時が Google に出る）。
        記事ではない記録（まとめの状態・ガイド・料金表・待ち行列）に書くスクリプトだけを名前で許す"""
        import re
        not_articles = {
            "updated_at.py", "buying_guides.py", "deep_dive.py", "evergreen.py", "morning_digest.py", "muse_images.py", "muse_ingest.py",
            "muse_queue.py", "muse_articles.py", "popular_articles.py", "pricing.py", "pricing_table.py", "products.py", "pricing_watch.py",
            "sns_plan_actual.py", "threads_learn.py",
        }
        writes = re.compile(r"""\[["']updatedAt["']\]\s*=|["']updatedAt["']\s*:""")
        offenders = sorted(p.name for p in (ROOT / "scripts").glob("*.py") if p.name not in not_articles and writes.search(p.read_text("utf-8")))
        self.assertEqual([], offenders, "記事の updatedAt は updated_at.touch_updated で書く")
        # 許した2つ（deep_dive・muse_articles）は状態ファイルの updatedAt だけで、記事の updatedAt は書かない
        for name in ("deep_dive.py", "muse_articles.py"):
            src = (ROOT / "scripts" / name).read_text("utf-8")
            self.assertEqual(1, len(writes.findall(src)), name)
            self.assertRegex(src, r'data\["updatedAt"\] = datetime\.now', name)


if __name__ == "__main__":
    unittest.main()
