"""2026-11-10（SEO 作業の束 A6）: 使い方ガイドが作れなかった理由を記録し、季節の最中の失敗は issue で知らせる。
題名が日付を約束するのに公式ページにその日付が無ければ作らない。外部への通信なし。"""

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evergreen  # noqa: E402
import owner_rules_audit  # noqa: E402

TEXT = "ワンストップ特例の申請書は寄附をした翌年の1月10日（必着）までに返送してください。" * 60
IN_SEASON = {"from": "11-15", "peak": "01-05", "until": "01-10"}


def topic(**over):
    base = {"slug": "furusato-onestop", "kind": "procedure", "tool": "furusato", "keyword": "ワンストップ特例 期限",
            "title": "ワンストップ特例の期限は1月10日　申請書の書き方", "sources": ["https://www.city.example.lg.jp/a.html"], "season": IN_SEASON}
    base.update(over)
    return base


class DatePromiseGateTest(unittest.TestCase):
    def test_rejects_title_date_missing_from_sources(self):
        sources = [{"url": "u", "text": "確定申告の期限は翌年3月15日までです。"}]
        self.assertIn("1月10日", evergreen.date_promise_problem(topic(), sources))

    def test_accepts_when_a_source_has_the_date(self):
        sources = [{"url": "u", "text": "確定申告の期限は翌年3月15日"}, {"url": "v", "text": "翌年１月１０日 必着"}]
        self.assertEqual(evergreen.date_promise_problem(topic(), sources), "")

    def test_promise_without_explicit_date_needs_some_date(self):
        t = topic(title="電気・ガス料金の補助はいつまで　値引きの額", keyword="電気代 補助 いつまで")
        self.assertTrue(evergreen.date_promise_problem(t, [{"url": "u", "text": "値引きを行います。"}]))
        self.assertEqual(evergreen.date_promise_problem(t, [{"url": "u", "text": "2027年2月分まで値引き"}]), "")

    def test_no_promise_no_gate(self):
        t = topic(title="基礎控除はいくら　所得ごとの金額の表", keyword="基礎控除 いくら")
        self.assertEqual(evergreen.date_promise_problem(t, [{"url": "u", "text": "金額"}]), "")

    def test_build_skips_before_generation(self):
        with mock.patch.object(evergreen.feeds, "fetch_article_text", return_value={"title": "案内", "text": "確定申告は3月15日まで。" * 300}), \
                mock.patch.object(evergreen, "generate") as gen:
            self.assertIsNone(evergreen.build(topic()))
        gen.assert_not_called()
        self.assertIn("1月10日", evergreen.last_failure["reason"])

    def test_not_found_pages_are_not_sources(self):
        page = {"title": "お探しのページが見つかりませんでした。", "text": "x" * 2000}
        skipped = []
        with mock.patch.object(evergreen.feeds, "fetch_article_text", return_value=page):
            self.assertEqual(evergreen.fetch_sources(["https://www.example.go.jp/x"], skipped), [])
        self.assertEqual(skipped[0]["error"], "エラー画面")


class FailureReasonTest(unittest.TestCase):
    def run_main(self, plan, argv, fetch):
        tmp = Path(tempfile.mkdtemp())
        failed = tmp / "state" / "evergreen_failed.json"
        failed.parent.mkdir()
        failed.write_text(json.dumps({"old-slug": "2026-11-01T00:00:00+09:00"}), "utf-8")
        with mock.patch.object(evergreen, "FAILED", failed), mock.patch.object(evergreen, "OUT_DIR", tmp / "howto"), \
                mock.patch.object(evergreen, "load_plan", return_value=plan), \
                mock.patch.object(evergreen.feeds, "fetch_article_text", side_effect=fetch), \
                mock.patch.object(owner_rules_audit, "write_issue", return_value=True) as issue, \
                mock.patch.object(sys, "argv", ["evergreen.py", *argv]):
            self.assertEqual(evergreen.main(), 0)
        return json.loads(failed.read_text("utf-8")), issue

    def test_failed_build_writes_reason_with_http_status(self):
        def fetch(url):
            raise RuntimeError("HTTP Error 403: Forbidden")
        state, _ = self.run_main([topic()], ["--only", "furusato-onestop"], fetch)
        entry = state["furusato-onestop"]
        self.assertEqual(entry["reason"], "公式ページが足りない")
        self.assertEqual(entry["sourceChars"], 0)
        self.assertEqual(entry["skippedSources"][0]["status"], 403)
        self.assertTrue(entry["at"])
        self.assertEqual(state["old-slug"], "2026-11-01T00:00:00+09:00")  # 古い形の記録も残す

    def test_failed_generation_records_fact_score_and_numbers(self):
        def fake_generate(t, sources, attempts=2):
            evergreen.last_failure.update({"reason": "合格しなかった", "factScore": 70, "unverifiedNumbers": ["5万円"]})
            return None
        with mock.patch.object(evergreen, "generate", side_effect=fake_generate):
            state, _ = self.run_main([topic()], ["--only", "furusato-onestop"], lambda url: {"title": "案内", "text": TEXT})
        self.assertEqual(state["furusato-onestop"]["factScore"], 70)
        self.assertEqual(state["furusato-onestop"]["unverifiedNumbers"], ["5万円"])

    def test_in_season_failure_triggers_issue(self):
        def fetch(url):
            raise RuntimeError("HTTP Error 403: Forbidden")
        with mock.patch.object(evergreen, "season_urgency", return_value=3.0):
            _, issue = self.run_main([topic()], ["--only", "furusato-onestop", "--issue"], fetch)
        issue.assert_called_once()
        found, body = issue.call_args.args
        self.assertIn("furusato-onestop", body)
        self.assertIn("403", body)
        self.assertEqual(issue.call_args.kwargs["label"], evergreen.ISSUE_LABEL)
        self.assertTrue(found)

    def test_no_issue_without_flag(self):
        with mock.patch.object(evergreen, "season_urgency", return_value=3.0):
            _, issue = self.run_main([topic()], ["--only", "furusato-onestop"], lambda url: (_ for _ in ()).throw(RuntimeError("HTTP Error 403")))
        issue.assert_not_called()

    def test_out_of_season_failures_are_not_listed(self):
        failed = {"furusato-onestop": {"at": "2026-11-10T00:00:00+09:00", "reason": "x"}, "kakutei-who": "2026-11-08T12:54:31+09:00"}
        plan = {"furusato-onestop": topic(), "kakutei-who": topic(slug="kakutei-who", season={"from": "01-05", "peak": "02-25", "until": "03-15"})}
        rows = evergreen.in_season_failures(failed, plan, date(2026, 11, 20))
        self.assertEqual(len(rows), 1)
        self.assertIn("furusato-onestop", rows[0])

    def test_old_and_new_failure_formats_share_retry_window(self):
        self.assertEqual(evergreen.failed_at("2026-11-08T12:54:31+09:00"), "2026-11-08T12:54:31+09:00")
        self.assertEqual(evergreen.failed_at({"at": "2026-11-09T00:00:00+09:00"}), "2026-11-09T00:00:00+09:00")
        self.assertEqual(evergreen.failed_at(None), "")


class PlanSourcesTest(unittest.TestCase):
    def test_furusato_onestop_has_municipal_sources_and_no_year_in_title(self):
        plan = {t["slug"]: t for t in json.loads((ROOT / "content" / "evergreen_plan.json").read_text("utf-8"))["topics"]}
        t = plan["furusato-onestop"]
        self.assertTrue(any(".lg.jp/" in u for u in t["sources"]))
        self.assertNotRegex(t["title"], r"20\d\d|令和")
        self.assertNotIn("｜", t["title"])
        self.assertTrue(any("enecho.meti.go.jp" in u for u in plan["denki-gas-shien"]["sources"]))


if __name__ == "__main__":
    unittest.main()
