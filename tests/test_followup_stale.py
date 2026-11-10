"""SEO A19「古い記事の『今日・明日』と、過ぎた予定の見出し」。外部への通信なし。"""

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import article_style  # noqa: E402
import stale_words as sw  # noqa: E402

D = date(2026, 11, 2)  # 月曜


class Absolutize(unittest.TestCase):
    def fix(self, text: str) -> str:
        return sw.absolutize_text(text, D)

    def test_honjitsu_becomes_date(self):
        self.assertEqual("11月2日から受付を始めました。", self.fix("本日から受付を始めました。"))
        self.assertEqual("11月2日より提供を開始します。", self.fix("本日より提供を開始します。"))

    def test_record_uses_source_date(self):
        rec = {"sourcePublishedAt": "2026-11-02T10:00:00+09:00", "body": "本日から申し込めます。", "updatedAt": "x"}
        changed, _ = sw.absolutize(rec)
        self.assertEqual(["body"], changed)
        self.assertEqual("11月2日から申し込めます。", rec["body"])
        self.assertEqual("x", rec["updatedAt"], "言い回しの直しで更新日時を動かさない")

    def test_utc_source_time_is_read_in_jst(self):
        rec = {"sourcePublishedAt": "2026-11-01T16:00:00+00:00", "body": "本日から"}
        sw.absolutize(rec)
        self.assertEqual("11月2日から", rec["body"])

    def test_no_source_date_no_change(self):
        rec = {"generatedAt": "2026-11-02T00:00:00+00:00", "body": "本日から"}
        self.assertEqual(([], []), sw.absolutize(rec))
        self.assertEqual("本日から", rec["body"])

    def test_weeks_months_years_get_brackets(self):
        self.assertEqual("来週（11月9日の週）に始まります。", self.fix("来週に始まります。"))
        self.assertEqual("先週（10月26日の週）の発表", self.fix("先週の発表"))
        self.assertEqual("今月（11月）中に", self.fix("今月中に"))
        self.assertEqual("来月（12月）から", self.fix("来月から"))
        self.assertEqual("今年度（2026年度）は120校", self.fix("今年度は120校"))
        self.assertEqual("2026年11月に提供", self.fix("今年11月に提供"))
        self.assertEqual("今年（2026年）で40周年", self.fix("今年で40周年"))
        self.assertEqual("来月（2027年1月）から", sw.absolutize_text("来月から", date(2026, 12, 5)))
        self.assertEqual("今年度（2025年度）", sw.absolutize_text("今年度", date(2026, 2, 1)))

    def test_leaves_quotes_tables_headings_comparisons(self):
        for text in ("「先週の売上をまとめて」と頼む", "| 前年度上半期 | 今年度上半期 |", "## 今日やること", "前年度比7.7％増", "本日（11月2日）より", "本日10月29日から"):
            self.assertEqual(text, self.fix(text))

    def test_generic_today_is_listed_not_rewritten(self):
        amb: list[str] = []
        for text in ("今日から使える7つの提案", "製品として今日から直接試すことはできません", "今日の最先端モデルが明日には後れを取る"):
            self.assertEqual(text, sw.absolutize_text(text, D, amb))
        self.assertGreaterEqual(len(amb), 3)

    def test_idempotent(self):
        once = self.fix("本日から。来週に。今年度は。")
        self.assertEqual(once, self.fix(once))

    def test_autofix_runs_it_at_generation(self):
        rec = {"sourcePublishedAt": "2026-11-02", "body": "本日より提供を開始しました。", "lede": "", "highlights": []}
        article_style.autofix(rec)
        self.assertIn("11月2日より", rec["body"])


class Passed(unittest.TestCase):
    def rec(self, title, gen="2026-11-01T00:00:00+00:00"):
        return {"slug": "x", "title": title, "generatedAt": gen, "sourceUrl": "https://www.mhlw.go.jp/a", "sourceName": "厚生労働省"}

    def test_detects_passed_future_dates(self):
        today = date(2026, 11, 10)
        recs = [self.rec("危険ドラッグの成分3物質を指定薬物に追加　11月6日施行へ"),
                self.rec("新製品を12月3日発売"),  # まだ先
                self.rec("10月20日に発表した内容のまとめ")]  # 公開より前の日付
        found = sw.passed_candidates(today, recs)
        self.assertEqual([("x", date(2026, 11, 6))], [(r["slug"], d) for r, d, _ in found])

    def test_note_only_when_page_still_has_date_and_no_postponement(self):
        when = date(2026, 11, 6)
        at = datetime(2026, 11, 10, 3, tzinfo=timezone.utc)
        rec = self.rec("11月6日施行へ")
        ok, _ = sw.apply_passed(rec, when, "施行日は令和８年１１月６日です。", at)
        self.assertTrue(ok)
        note = rec["updates"][-1]
        self.assertEqual("followup", note["kind"])
        self.assertEqual("予定の11月6日を過ぎました。11月10日時点の公式ページでは、日付の変更や延期の案内はありません", note["title"])
        self.assertEqual("https://www.mhlw.go.jp/a", note["sourceUrl"])
        self.assertEqual(note["at"], rec["updatedAt"])
        self.assertEqual([], sw.passed_candidates(date(2026, 11, 10), [rec]), "同じ予定に2回付けない")
        for text, why in (("施行日を延期します。11月6日", "延期"), ("お知らせ", "日付"), ("", "読めない")):
            r = self.rec("11月6日施行へ")
            ok, reason = sw.apply_passed(r, when, text, at)
            self.assertFalse(ok)
            self.assertIn(why, reason)
            self.assertNotIn("updates", r)


if __name__ == "__main__":
    unittest.main()
