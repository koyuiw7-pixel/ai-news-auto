"""本文が短い記事を検索に出さない（2026-11-21 オーナー承認・AdSense の3回目の申請の前の準備・台帳 A72）。

- 空白を除いた本文が 800字未満（scripts/thicken_short.py の chars と同じ数え方）の記事は noindex（理由 short）
- 800字ちょうどからは検索に出す。まとめの記事（type: roundup）・手動の indexable は今までどおり先に決まる
- サイト（lib/indexing.ts の noindexReason・lib/article-index.mjs の bodyChars）も同じ判定
- 記事ページは short でも AdSense の枠・提携の囲みを出す（オーナーの決まり「広告の無いページを作らない」）
ネットワークは使わない。
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import thicken_short  # noqa: E402


def rec(chars: int, **kw) -> dict:
    base = {"slug": f"short-{chars}", "title": "電気料金が来月から値上げ", "genreSlug": "lifestyle", "body": ""}
    base.update(kw)
    if not base["body"]:
        # 「## 概要」の4字（空白を除く）を引いて、空白を除いた字数をちょうど chars にする
        base["body"] = "## 概要\n" + " \n".join(("あ" * (chars - 4))[i:i + 50] for i in range(0, chars - 4, 50))
    return base


class ShortBodyRuleTest(unittest.TestCase):
    def test_counts_like_thicken_short(self):
        for n in (799, 800, 1200):
            a = rec(n)
            self.assertEqual(n, len(re.sub(r"\s", "", a["body"])))
            self.assertEqual(n, thicken_short.chars(a["body"]))

    def test_799_is_short_800_is_indexed(self):
        self.assertEqual(800, indexnow.SHORT_BODY)
        self.assertEqual("short", indexnow.noindex_reason(rec(799)))
        self.assertIsNone(indexnow.noindex_reason(rec(800)))
        self.assertFalse(indexnow.is_indexable(rec(799)))
        self.assertIn("理由 short", indexnow.index_status_line(rec(799)))

    def test_whitespace_does_not_count(self):
        padded = rec(799)
        padded["body"] += "\n\n" + " " * 500
        self.assertGreaterEqual(len(padded["body"]), 800)
        self.assertEqual("short", indexnow.noindex_reason(padded))

    def test_other_rules_come_first(self):
        self.assertIsNone(indexnow.noindex_reason(rec(100, type="roundup")))
        self.assertIsNone(indexnow.noindex_reason(rec(300, type="roundup")))
        self.assertIsNone(indexnow.noindex_reason(rec(300, indexable=True)))
        self.assertEqual("manual", indexnow.noindex_reason(rec(300, indexable=False)))
        self.assertEqual("no-body", indexnow.noindex_reason({**rec(300), "body": "短い"}))

    def test_trend_articles_are_also_short(self):
        """話題のまとめの記事（trendKeyword）も、本文が短ければ検索に出さない（11/18〜11/21 の訪問がほぼ0だった）"""
        self.assertEqual("short", indexnow.noindex_reason(rec(600, trendKeyword="紅白")))
        self.assertIsNone(indexnow.noindex_reason(rec(900, trendKeyword="紅白")))

    def test_rules_exported_for_site(self):
        rules = json.loads((ROOT / "lib" / "index-rules.json").read_text("utf-8"))
        self.assertEqual(indexnow.SHORT_BODY, rules["shortBody"])
        self.assertIn("short", indexnow.NOINDEX_LABELS)

    def test_site_agrees(self):
        node = shutil.which("node")
        if not node or subprocess.run([node, "-e", "require.resolve('typescript')"], cwd=ROOT, capture_output=True).returncode != 0:
            self.skipTest("node / typescript が無い")
        # 索引の値（derivedOf の bodyChars）を使って、サイトの noindexReason と比べる
        script = r"""
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
import(path.join(process.cwd(), 'lib/article-index.mjs')).then((idx) => {
  const items = JSON.parse(fs.readFileSync(0, 'utf8'));
  const out = items.map((a) => {
    const d = idx.derivedOf(a);
    return [d.bodyChars, m.exports.noindexReason({ tags: [], channelSlug: '', ...a, ...d })];
  });
  process.stdout.write(JSON.stringify(out));
});
"""
        cases = [rec(799), rec(800), rec(799, type="roundup"), rec(600, trendKeyword="紅白"), rec(300, indexable=True)]
        padded = rec(799)
        padded["body"] += "\n\n" + " " * 500
        cases.append(padded)
        out = subprocess.run([node, "-e", script], cwd=ROOT, input=json.dumps(cases), capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, out.stderr[-800:])
        got = json.loads(out.stdout)
        self.assertEqual([thicken_short.chars(a["body"]) for a in cases], [g[0] for g in got])
        self.assertEqual([indexnow.noindex_reason(a) for a in cases], [g[1] for g in got])
        self.assertEqual(["short", None, None, "short", None, "short"], [g[1] for g in got])


class ShortNotRetiredTest(unittest.TestCase):
    def test_short_articles_are_not_retired(self):
        """検索に出さないだけで、記事は消さない（retire_articles.plan_noindex の取り下げの対象にしない）"""
        import retire_articles  # noqa: PLC0415
        from datetime import datetime, timezone  # noqa: PLC0415

        short = rec(500, generatedAt="2026-11-01T00:00:00+00:00", sourceUrl="https://example.test/short")
        self.assertEqual("short", indexnow.noindex_reason(short))
        original = retire_articles.recent_sns
        retire_articles.recent_sns = lambda *a, **k: set()
        try:
            picked, _kept = retire_articles.plan_noindex([short], datetime.now(timezone.utc))
        finally:
            retire_articles.recent_sns = original
        self.assertNotIn(short["slug"], picked)


class ShortPageKeepsAdsTest(unittest.TestCase):
    def test_article_page_keeps_ads_for_short(self):
        page = (ROOT / "app" / "articles" / "[slug]" / "page.tsx").read_text("utf-8")
        self.assertIn('const showAds = indexReason === null || indexReason === "short";', page)
        # 提携の囲み・PR を消すのは14日間訪問0の記事だけ（short では消さない）
        self.assertIn("const noPr = isZeroVisit(article.slug);", page)
        # robots の noindex は isIndexable で決める（short も noindex になる）
        self.assertIn("isIndexable({ ...article, duplicate: getArticleSummary(article.slug)?.duplicate }) ? {} : { robots: { index: false, follow: true } }", page)


if __name__ == "__main__":
    unittest.main()
