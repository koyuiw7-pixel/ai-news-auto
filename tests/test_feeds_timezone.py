"""フィード・記事ページの時刻の読み方（SEO A5）。時間帯の書かれていない時刻（「JST」・日付だけを含む）は日本時間。
画面の「発表」は掲載より後にしない・元の発表の時刻が分からない web 記事には出さない（lib/announced.ts）。
ネットワークは使わない。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fast_lane  # noqa: E402
import feeds  # noqa: E402
import fix_future_dates  # noqa: E402




def iso_utc(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


class FeedTimezoneTest(unittest.TestCase):
    def test_jst_rfc822(self):
        # 金融庁のフィード（https://www.fsa.go.jp/fsaNewsListAll_rss2.xml）の書き方
        self.assertEqual(iso_utc(feeds._parse_date("Mon, 09 Nov 2026 17:00:00 JST")), "2026-11-09T08:00:00+00:00")

    def test_rfc822_without_zone_is_jst(self):
        self.assertEqual(iso_utc(feeds._parse_date("Mon, 09 Nov 2026 17:00:00")), "2026-11-09T08:00:00+00:00")

    def test_explicit_zones_unchanged(self):
        self.assertEqual(iso_utc(feeds._parse_date("Fri, 06 Nov 2026 09:40:00 +0000")), "2026-11-06T09:40:00+00:00")
        self.assertEqual(iso_utc(feeds._parse_date("Fri, 06 Nov 2026 09:40:00 GMT")), "2026-11-06T09:40:00+00:00")
        self.assertEqual(iso_utc(feeds._parse_date("Fri, 06 Nov 2026 18:40:00 +0900")), "2026-11-06T09:40:00+00:00")
        self.assertEqual(iso_utc(feeds._parse_date("Fri, 06 Nov 2026 04:40:00 EST")), "2026-11-06T09:40:00+00:00")
        # 「-0000」は RFC 5322 で UTC（発信元の時間帯は不明）
        self.assertEqual(iso_utc(feeds._parse_date("Fri, 06 Nov 2026 09:40:00 -0000")), "2026-11-06T09:40:00+00:00")
        self.assertEqual(iso_utc(feeds._parse_date("2026-11-06T20:30:00+09:00")), "2026-11-06T11:30:00+00:00")
        self.assertEqual(iso_utc(feeds._parse_date("2026-11-09T16:00:51+0900")), "2026-11-09T07:00:51+00:00")
        self.assertEqual(iso_utc(feeds._parse_date("2026-11-06T09:40:00Z")), "2026-11-06T09:40:00+00:00")

    def test_date_only(self):
        # 総務省統計局の dc:date は日付だけ。日本時間の0時
        self.assertEqual(iso_utc(feeds._parse_date("2026-11-10")), "2026-11-09T15:00:00+00:00")
        # 「Z」付きは UTC の0時のまま（Apple Newsroom）
        self.assertEqual(iso_utc(feeds._parse_date("2026-10-28Z")), "2026-10-28T00:00:00+00:00")

    def test_naive_iso_is_jst(self):
        self.assertEqual(iso_utc(feeds._parse_date("2026-11-09T17:00:00")), "2026-11-09T08:00:00+00:00")
        self.assertEqual(iso_utc(fast_lane.parse_time("2026-11-09T17:00:00")), "2026-11-09T08:00:00+00:00")
        self.assertEqual(iso_utc(fast_lane.parse_time("2026-11-09T17:00:00Z")), "2026-11-09T17:00:00+00:00")
        self.assertEqual(iso_utc(fast_lane.parse_time("2026-11-09T17:00:00+09:00")), "2026-11-09T08:00:00+00:00")
        self.assertIsNone(fast_lane.parse_time(""))
        self.assertIsNone(feeds._parse_date("not a date"))

    def test_page_published(self):
        self.assertEqual(iso_utc(feeds.page_published({"published": "2026-11-09T16:00:51+0900"})), "2026-11-09T07:00:51+00:00")
        self.assertIsNone(feeds.page_published({"published": ""}))
        self.assertIsNone(feeds.page_published(None))


class FixFutureDatesTest(unittest.TestCase):
    def test_confirmed_records_are_not_future(self):
        """一度だけの修正の対象は、直した後（今の値）で発表が掲載より後になっていない"""
        for slug in fix_future_dates.CONFIRMED:
            path = ROOT / "content" / "articles" / f"{slug}.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text("utf-8"))
            src = data.get("sourcePublishedAt")
            if src:
                self.assertLessEqual(fix_future_dates._parse(src), fix_future_dates._parse(data["generatedAt"]), slug)

    def test_fix_is_idempotent(self):
        for slug, wrong in fix_future_dates.CONFIRMED.items():
            ok, _ = fix_future_dates.fix(slug, wrong)
            self.assertFalse(ok, f"{slug} はまだ直っていない")


NODE_SCRIPT = r"""
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');
const filename = path.join(process.cwd(), 'lib/announced.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, esModuleInterop: true}}).outputText;
const m = new Module(filename, module);
m.filename = filename;
m.paths = Module._nodeModulePaths(process.cwd());
m._compile(compiled, filename);
const items = JSON.parse(fs.readFileSync(0, 'utf8'));
const day = (iso) => iso ? new Intl.DateTimeFormat('ja-JP', {year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Asia/Tokyo'}).format(new Date(iso)) : '';
process.stdout.write(JSON.stringify(items.map((a) => day(m.exports.announcedAt(a)))));
"""


class AnnouncedDisplayTest(unittest.TestCase):
    def test_announced_date(self):
        node = shutil.which("node")
        if not node or subprocess.run([node, "-e", "require.resolve('typescript')"], cwd=ROOT,
                                      capture_output=True).returncode != 0:
            self.skipTest("node / typescript が無い")
        cases = [
            # 発表が掲載より後（時間帯の書き違い）→ 掲載の日
            {"sourceType": "web", "sourcePublishedAt": "2026-11-09T17:00:00+00:00", "publishedAt": "2026-11-09T17:00:00+00:00",
             "generatedAt": "2026-11-09T08:23:18+00:00"},
            # ふつう → 発表の日
            {"sourceType": "web", "sourcePublishedAt": "2026-11-08T23:00:00+00:00", "generatedAt": "2026-11-09T08:23:18+00:00"},
            # web 記事で発表の時刻が分からない → 出さない（publishedAt は見つけた時刻の代用）
            {"sourceType": "web", "publishedAt": "2026-11-10T03:05:24+00:00", "generatedAt": "2026-11-10T03:21:42+00:00"},
            # 動画は publishedAt が動画の公開日時
            {"publishedAt": "2026-11-01T03:00:00+00:00", "generatedAt": "2026-11-02T03:00:00+00:00"},
        ]
        out = subprocess.run([node, "-e", NODE_SCRIPT], cwd=ROOT, input=json.dumps(cases), capture_output=True,
                             text=True, check=True)
        self.assertEqual(json.loads(out.stdout), ["2026/11/09", "2026/11/09", "", "2026/11/01"])

    def test_pages_use_announced(self):
        """記事の画面（ノワール・今までの見た目・出典と更新履歴）の「発表」は announcedAt を通す"""
        noir = (ROOT / "components/noir/NoirArticle.tsx").read_text("utf-8")
        page = (ROOT / "app/articles/[slug]/page.tsx").read_text("utf-8")
        record = (ROOT / "components/SourceRecord.tsx").read_text("utf-8")
        self.assertIn("announcedAt(article)", noir)
        self.assertNotIn("発表 {formatDate(article.publishedAt)}", noir)
        self.assertIn("announcedAt(article)", page)
        self.assertNotIn("<RelTime iso={article.publishedAt}", page)
        self.assertIn("announcedAt(article)", record)


if __name__ == "__main__":
    unittest.main()
