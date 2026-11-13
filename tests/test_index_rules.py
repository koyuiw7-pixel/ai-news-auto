"""検索に出す記事の判定が、IndexNow（scripts/indexnow.py）とサイト（lib/indexing.ts: サイトマップ・ニュース用サイトマップ・robots）で同じか。

1. lib/index-rules.json が scripts/indexnow.py・persona.py の今の基準から書き出したものと一致する
2. 実際の記事と例で、両方の noindex の理由が一致する（node と typescript が無い環境では 2 を飛ばす）
ネットワークは使わない。
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402

NODE_SCRIPT = r"""
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');
const filename = path.join(process.cwd(), 'lib/indexing.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, esModuleInterop: true}}).outputText;
const m = new Module(filename, module);
m.filename = filename;
m.paths = Module._nodeModulePaths(process.cwd());
m._compile(compiled, filename);
const items = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(items.map((a) => m.exports.noindexReason(a))));
"""

SAMPLES = [
    {"genreSlug": "business", "title": "財務省が国債金利を公表"},
    {"genreSlug": "public", "title": "道路の工事", "seoTitle": "補助金の申請方法"},
    {"genreSlug": "public", "title": "道路の工事"},
    {"genreSlug": "lifestyle", "title": "電気料金の値上げ"},
    {"genreSlug": "lifestyle", "title": "新作ラテ"},
    {"genreSlug": "tech-gadget", "title": "新しいスマホ"},
    {"genreSlug": "science", "title": "新しい顕微鏡", "tags": ["AI"]},
    {"genreSlug": "science", "title": "AIX という名前の装置"},
    {"genreSlug": "sports", "title": "ＮＢＡのウォリアーズが勝利"},
    {"genreSlug": "sports", "title": "大谷翔平のドジャース"},
    {"genreSlug": "sports", "title": "W杯で海外の選手が活躍"},
    {"genreSlug": "sports", "title": "全日本社会人選手権が閉幕"},
    {"genreSlug": "entertainment", "title": "新作ゲーム"},
    # エンタメはビジネス・テックの目線だけ（scripts/genre_focus.py。2026-11-03）
    {"genreSlug": "entertainment", "title": "カプコン、中間決算は増収増益　販売本数は前年比1.3倍"},
    {"genreSlug": "entertainment", "title": "Ｎｅｔｆｌｉｘ、広告つきプランの月額を890円に"},
    {"genreSlug": "entertainment", "title": "映画の予告編を公開　キャストも発表"},
    {"genreSlug": "entertainment", "title": "人気アニメのコラボグッズを発売、価格は1500円"},
    {"genreSlug": "investment", "title": "金融庁、NISAの手続きを簡素化"},
    {"genreSlug": "real-estate", "title": "公示地価が上昇"},
    # 広げた暮らしの話題（台帳 A56）と、広げても入れない事件・事故・芸能
    {"genreSlug": "lifestyle", "title": "常磐自動車道 夜間通行止めのお知らせ"},
    {"genreSlug": "public", "title": "大雪に関する早期天候情報"},
    {"genreSlug": "tech-gadget", "title": "通信障害の発生について"},
    {"genreSlug": "lifestyle", "title": "ローソン 15品発売"},
    {"genreSlug": "lifestyle", "title": "新フレーバー登場", "channelSlug": "lawson"},
    {"genreSlug": "lifestyle", "title": "新フレーバー登場", "channelSlug": "nipponham"},
    {"genreSlug": "lifestyle", "title": "人身事故による運転見合わせ"},
    {"genreSlug": "lifestyle", "title": "障害対応ツールの提供"},
    {"genreSlug": "public", "title": "子育て世帯への給付の申請受付"},
    # 話題のレーンの記事（2026-11-13）は分野で外さない。うわさ・事件・訃報の題名は外す
    {"genreSlug": "sports", "title": "ＮＢＡのウォリアーズが勝利", "trendKeyword": "ウォリアーズ"},
    {"genreSlug": "entertainment", "title": "映画の予告編を公開　キャストも発表", "trendKeyword": "予告編"},
    {"genreSlug": "entertainment", "title": "人気俳優の熱愛が発覚", "trendKeyword": "熱愛"},
]


def _summary(article: dict, body_length: int, japan_value: bool) -> dict:
    keys = ("slug", "type", "title", "seoTitle", "tags", "genreSlug", "channelSlug", "sourceType", "indexable", "verdict", "breaking", "newsType",
            "trendKeyword")
    out = {k: article.get(k) for k in keys if article.get(k) is not None}
    out.setdefault("tags", [])
    out.setdefault("title", "")
    out.setdefault("genreSlug", "ai")
    out.setdefault("channelSlug", "")
    out.update(bodyLength=body_length, hasJapanValue=japan_value)
    return out


class IndexRulesTest(unittest.TestCase):
    def test_rules_json_is_up_to_date(self):
        self.assertFalse(
            indexnow.rules_drift(),
            "lib/index-rules.json が古い。python3 scripts/indexnow.py --export-rules で書き出す",
        )

    def test_python_and_site_agree(self):
        node = shutil.which("node")
        if not node or subprocess.run([node, "-e", "require.resolve('typescript')"], cwd=ROOT,
                                      capture_output=True).returncode != 0:
            self.skipTest("node / typescript が無い")
        articles, expected, summaries = [], [], []
        for path in sorted((ROOT / "content" / "articles").glob("*.json")):
            try:
                articles.append(json.loads(path.read_text("utf-8")))
            except (OSError, ValueError):
                continue
        jp = "## 日本で使える？\n" + "a" * 2000
        for sample in SAMPLES:
            articles.append({**sample, "body": jp})
        for article in articles:
            if not isinstance(article, dict):
                continue
            article = {k: v for k, v in article.items() if k != "duplicateOf"}  # 重複は別の仕組み（索引側）で付く
            body = article.get("body", "")
            expected.append(indexnow.noindex_reason(article))
            summaries.append(_summary(article, len(body), bool(article.get("scheduledRelease")) or bool(indexnow.JAPAN_VALUE.search(body))))
        out = subprocess.run([node, "-e", NODE_SCRIPT], cwd=ROOT, input=json.dumps(summaries), capture_output=True,
                             text=True, check=True)
        got = json.loads(out.stdout)
        diffs = [(s.get("slug") or s["title"], e, g) for s, e, g in zip(summaries, expected, got) if e != g]
        self.assertEqual(diffs, [], "IndexNow とサイトで noindex の理由が違う")


    def test_news_reason_agrees(self):
        """ニュース用サイトマップに載せない理由も両方で同じ（SEO A5: 発表の時刻が分からない比較の記事は publishedAt で代用しない）"""
        node = shutil.which("node")
        if not node or subprocess.run([node, "-e", "require.resolve('typescript')"], cwd=ROOT,
                                      capture_output=True).returncode != 0:
            self.skipTest("node / typescript が無い")
        from datetime import datetime, timezone

        now = "2026-11-02T12:00:00+00:00"
        base = {"sourceType": "web", "genreSlug": "business", "title": "財務省が国債金利を公表", "slug": "x",
                "body": "## 日本で使える？\n" + "a" * 2000, "generatedAt": "2026-11-02T06:00:00+00:00"}
        cases = [
            {"publishedAt": "2026-11-02T05:00:00+00:00"},
            {"publishedAt": "2026-10-27T16:00:00+00:00"},  # ニュース: publishedAt で代用 → stale-source
            {"publishedAt": "2026-10-27T16:00:00+00:00", "kind": "comparison"},  # 比較: 代用しない → 載せる
            {"publishedAt": "2026-10-27T16:00:00+00:00", "kind": "comparison", "sourcePublishedAt": "2026-10-27T16:00:00+00:00"},
            {"publishedAt": "2026-11-02T05:00:00+00:00", "sourcePublishedAt": "2026-10-29T00:00:00+00:00"},
            {"publishedAt": "2026-11-02T05:00:00+00:00", "generatedAt": "2026-10-30T00:00:00+00:00"},
            {"publishedAt": "2026-11-02T05:00:00+00:00", "late": True},
        ]
        articles = [{**base, **c} for c in cases]
        expected = [indexnow.news_reason(a, now=datetime.fromisoformat(now)) for a in articles]
        self.assertEqual(expected, [None, "stale-source", None, "stale-source", "stale-source", "old", "late"])
        summaries = []
        for a in articles:
            row = _summary(a, len(a["body"]), True)
            row.update({k: a[k] for k in ("publishedAt", "generatedAt", "sourcePublishedAt", "kind", "late") if k in a})
            summaries.append(row)
        script = NODE_SCRIPT.replace("m.exports.noindexReason(a)", f"m.exports.newsSitemapReason(a, Date.parse('{now}'))")
        out = subprocess.run([node, "-e", script], cwd=ROOT, input=json.dumps(summaries), capture_output=True,
                             text=True, check=True)
        self.assertEqual(json.loads(out.stdout), expected, "IndexNow とサイトでニュース用サイトマップの理由が違う")


if __name__ == "__main__":
    unittest.main()


class DuplicateSourceKeyTest(unittest.TestCase):
    """SEO A10: 同じ出典URLの予備の重複判定で ?period=（毎月の資料）と #entry-…（リリースノートの1項目）を残す。
    地震・津波は気象庁の同じ地図のページが出典なので URL では比べない。Python（indexnow・story）と JS（article-index）で同じ"""

    PDF = "https://www.stat.go.jp/data/kakei/sokuhou/tsuki/pdf/fies_mr.pdf"
    JMA = "https://www.jma.go.jp/bosai/map.html#contents=earthquake_map"
    NOTES = "https://platform.claude.com/docs/en/release-notes/overview.md"

    def recs(self):
        return [
            {"slug": "kakei-08", "title": "8月の家計調査", "sourceUrl": f"{self.PDF}?period=2026-08", "body": "x" * 900, "generatedAt": "1"},
            {"slug": "kakei-09", "title": "9月の家計調査", "sourceUrl": f"{self.PDF}?period=2026-09", "body": "x" * 800, "generatedAt": "2"},
            {"slug": "quake-1", "title": "静岡県で震度3", "sourceUrl": self.JMA, "body": "x" * 900, "generatedAt": "1"},
            {"slug": "quake-2", "title": "千葉県で震度4", "sourceUrl": self.JMA, "body": "x" * 800, "generatedAt": "2"},
            {"slug": "notes-a", "title": "Claude の新しい API", "sourceUrl": f"{self.NOTES}#entry-2026-11-03", "body": "x" * 900, "generatedAt": "1"},
            {"slug": "notes-b", "title": "Claude の別の更新", "sourceUrl": f"{self.NOTES}#entry-2026-11-05", "body": "x" * 800, "generatedAt": "2"},
            {"slug": "utm-a", "title": "A社が新しい料金プランを発表", "sourceUrl": "https://example.com/news/a?utm_source=x", "body": "x" * 900, "generatedAt": "1"},
            {"slug": "utm-b", "title": "A社、新しい料金プランを発表へ", "sourceUrl": "https://example.com/news/a/", "body": "x" * 800, "generatedAt": "2"},
            # 2026-11-13: 同じ出典でも題名の切り口が違う記事（CEO の退任と決算の日程）は重複にしない
            {"slug": "angle-a", "title": "B社のCEOが即日退任　後任は暫定", "sourceUrl": "https://example.com/news/b", "body": "x" * 900, "generatedAt": "1"},
            {"slug": "angle-b", "title": "B社の決算は11月18日朝　投資信託の4.8%に響く日", "sourceUrl": "https://example.com/news/b", "body": "x" * 800, "generatedAt": "2"},
        ]

    def test_python_keeps_period_and_entry(self):
        self.assertEqual({"utm-b"}, indexnow.duplicate_slugs(self.recs()))
        import story  # noqa: PLC0415

        self.assertFalse(story.url_keys(f"{self.PDF}?period=2026-08") & story.url_keys(f"{self.PDF}?period=2026-09"))
        self.assertFalse(story.url_keys(f"{self.NOTES}#entry-2026-11-03") & story.url_keys(f"{self.NOTES}#entry-2026-11-05"))
        self.assertTrue(story.url_keys("https://example.com/news/a?utm_source=x") & story.url_keys("https://example.com/news/a/"))

    def test_js_mirror_agrees(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node が無い")
        script = ("import('./lib/article-index.mjs').then((m) => { const items = JSON.parse(require('node:fs').readFileSync(0, 'utf8'))"
                  ".map((a) => ({ ...a, bodyLength: a.body.length })); m.markDuplicates(items);"
                  " process.stdout.write(JSON.stringify(items.filter((a) => a.duplicate).map((a) => a.slug))); })")
        out = subprocess.run([node, "-e", script], cwd=ROOT, input=json.dumps(self.recs()), capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, out.stderr[-500:])
        self.assertEqual(["utm-b"], json.loads(out.stdout))

    def test_restored_three_are_not_duplicates(self):
        arts = [json.loads(p.read_text("utf-8")) for p in (ROOT / "content" / "articles").glob("*.json")]
        dup = indexnow.duplicate_slugs(arts)
        for slug in ("household-survey-2026-09-spending", "quake-20261029000759", "claude-text-watermark-api"):
            if any(a.get("slug") == slug for a in arts):
                self.assertNotIn(slug, dup, slug)
