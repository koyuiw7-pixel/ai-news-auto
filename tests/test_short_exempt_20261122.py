"""検索に表示されていた短い記事を検索に戻し、毎週の検索の書き直しを 11/30 まで止める（2026-11-22・台帳 A72・A68）。

- content/noindex_short_exempt.json の17本は short の noindex にしない（Python とサイトで同じ判定）
- ほかの短い記事と、ほかの noindex の理由はそのまま
- この一覧は順位の一覧（search_positions.json）に足さないので、毎週の書き直しの対象を増やさない
- search_refresh.py --weekly は日本時間 11/30 より前は何もしない
ネットワークは使わない。
"""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import search_protected  # noqa: E402
import search_refresh  # noqa: E402

JST = timezone(timedelta(hours=9))
EXEMPT = json.loads((ROOT / "content" / "noindex_short_exempt.json").read_text("utf-8"))["slugs"]


def rec(slug: str, **kw) -> dict:
    return {"slug": slug, "title": "電気料金の改定", "genreSlug": "lifestyle", "body": "あ" * 500, **kw}


class ShortExemptTest(unittest.TestCase):
    def test_list_is_the_approved_17_live_articles(self):
        self.assertEqual(17, len(EXEMPT))
        self.assertEqual(17, len(set(EXEMPT)))
        for slug in EXEMPT:
            self.assertTrue((ROOT / "content" / "articles" / f"{slug}.json").exists(), slug)

    def test_exempt_is_indexed_other_short_stays_noindex(self):
        self.assertIsNone(indexnow.noindex_reason(rec(EXEMPT[0])))
        self.assertEqual("short", indexnow.noindex_reason(rec("other-short-article")))

    def test_other_noindex_reasons_still_win(self):
        slug = EXEMPT[0]
        self.assertEqual("manual", indexnow.noindex_reason(rec(slug, indexable=False)))
        self.assertEqual("no-body", indexnow.noindex_reason(rec(slug, body="短い")))
        self.assertEqual("duplicate", indexnow.noindex_reason(rec(slug, duplicateOf="another")))
        with mock.patch.object(indexnow, "ZERO_VISIT", frozenset({slug})):
            self.assertEqual("zero-visit", indexnow.noindex_reason(rec(slug)))

    def test_site_uses_the_same_list(self):
        if not shutil.which("node") or not (ROOT / "node_modules" / "typescript").exists():
            self.skipTest("node / typescript が無い")
        script = """
const fs=require('fs'),path=require('path'),ts=require('typescript'),Module=require('module');
const f=path.join(process.cwd(),'lib/indexing.ts');
const js=ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
const m=new Module(f,module);m.filename=f;m.paths=Module._nodeModulePaths(path.dirname(f));m._compile(js,f);
const base={sourceType:'web',channelSlug:'official',genreSlug:'ai',title:'x',tags:[],bodyLength:500,bodyChars:500};
console.log(JSON.stringify([m.exports.noindexReason({...base,slug:process.argv[1]}),m.exports.noindexReason({...base,slug:'other-short-article'})]));
"""
        out = subprocess.run(["node", "-e", script, EXEMPT[0]], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual([None, "short"], json.loads(out.stdout))

    def test_exempt_does_not_add_refresh_targets(self):
        """一覧にはこの変更で順位の行を足していない（元から行があるのは house-foods の1本だけ）"""
        pages = search_protected.positions_pages()
        self.assertEqual({"house-foods-price-revision-2027"}, set(EXEMPT) & set(pages))


class WeeklyHoldTest(unittest.TestCase):
    def test_hold_boundary_is_jst(self):
        self.assertTrue(search_refresh.weekly_held(datetime(2026, 11, 23, 4, 50, tzinfo=JST)))
        self.assertTrue(search_refresh.weekly_held(datetime(2026, 11, 29, 23, 59, tzinfo=JST)))
        self.assertFalse(search_refresh.weekly_held(datetime(2026, 11, 30, 0, 0, tzinfo=JST)))

    def _run_on(self, when: datetime, argv: list[str]):
        class Fixed(datetime):
            @classmethod
            def now(cls, tz=None):
                return when.astimezone(tz) if tz else when

        out = io.StringIO()
        with mock.patch.object(search_refresh, "datetime", Fixed), mock.patch.object(sys, "argv", ["search_refresh.py", *argv]), \
                mock.patch.object(search_refresh.search_protected, "load_positions", side_effect=AssertionError("読まない")) as load, \
                contextlib.redirect_stdout(out):
            code = search_refresh.main()
        return code, out.getvalue(), load

    def test_monday_1123_weekly_does_nothing(self):
        code, out, load = self._run_on(datetime(2026, 11, 23, 4, 50, tzinfo=JST), ["--apply", "--weekly", "--max", "5"])
        self.assertEqual(0, code)
        self.assertIn("止めています", out)
        load.assert_not_called()

    def test_monday_1130_is_eligible_again(self):
        with self.assertRaises(AssertionError):
            self._run_on(datetime(2026, 11, 30, 4, 50, tzinfo=JST), ["--weekly"])


if __name__ == "__main__":
    unittest.main()
