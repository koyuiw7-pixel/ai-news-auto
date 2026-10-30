"""手動改稿の保護と通常ガイドの更新を、外部APIなしで検証する。"""

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("evergreen_editorial_test", ROOT / "scripts" / "evergreen.py")
eg = importlib.util.module_from_spec(spec)
# 実際のLLM・取得モジュールを読み込まず、このスクリプトの制御だけを検証する。
with patch.dict(sys.modules, {name: MagicMock() for name in ("feeds", "llm", "quality")}):
    spec.loader.exec_module(eg)

NOW = datetime(2026, 10, 30, 17, 0, tzinfo=timezone(timedelta(hours=9)))


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


def guide(slug="manual", *, days_old=1, editorial=True):
    checked = (NOW - timedelta(days=days_old)).isoformat(timespec="seconds")
    data = {
        "slug": slug,
        "title": "確認済みの手動原稿",
        "intro": "この本文を保持する",
        "editorialNote": "編集者が一次資料を確認しました。",
        "checkedAt": checked,
        "updatedAt": checked,
        "createdAt": checked,
        "sources": [{"url": "https://example.test/source", "checkedAt": checked}],
        "match": "ChatGPT",
    }
    if editorial:
        data["refreshMode"] = "editorial"
    else:
        data["promptVersion"] = eg.PROMPT_VERSION
    return data


class EditorialRefreshTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        for target, value in (("datetime", Clock), ("OUT_DIR", self.directory / "howto"),
                              ("FAILED", self.directory / "failed.json")):
            replacement = patch.object(eg, target, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        for target in ("fetch_sources", "generate"):
            replacement = patch.object(eg, target, side_effect=AssertionError("external work is forbidden"))
            replacement.start()
            self.addCleanup(replacement.stop)
        replacement = patch.object(eg, "related_news", return_value=[])
        self.news = replacement.start()
        self.addCleanup(replacement.stop)
        replacement = patch.object(eg.quality, "fact_check", side_effect=AssertionError("LLM is forbidden"))
        replacement.start()
        self.addCleanup(replacement.stop)

    def read(self, slug):
        return json.loads((eg.OUT_DIR / f"{slug}.json").read_text())

    def run_main(self, guides, plan, *args):
        with patch.object(eg, "existing", return_value=guides), patch.object(eg, "load_plan", return_value=plan), \
                patch.object(sys, "argv", ["evergreen.py", "--max", "0", *args]):
            self.assertEqual(eg.main(), 0)

    def test_editorial_does_not_refresh_for_missing_or_old_prompt_version(self):
        for version in (None, eg.PROMPT_VERSION - 1):
            data = guide()
            if version is not None:
                data["promptVersion"] = version
            self.assertEqual(eg.refresh_reason(data, 14), "")
        self.assertFalse(eg.OUT_DIR.exists())

    def test_due_editorial_is_queued_once_without_changing_content_or_check_dates(self):
        data = guide(days_old=14)
        before = copy.deepcopy(data)
        reason = eg.refresh_reason(data, 14)
        self.assertEqual(reason, "14日経過")
        eg.refresh(data, {}, reason)
        self.assertEqual(self.read("manual"), {
            **before, "needsReview": NOW.isoformat(timespec="seconds"), "needsReviewReason": reason,
        })
        self.assertEqual(eg.refresh_reason(data, 14), "")
        with patch.object(eg, "write") as write:
            eg.refresh(data, {}, reason)
        write.assert_not_called()

    def test_new_pricing_news_queues_fresh_editorial(self):
        self.news.return_value = [{"title": "ChatGPTの無料プランを変更"}]
        data = guide()
        before = data["checkedAt"]
        reason = eg.refresh_reason(data, 14)
        self.assertEqual(reason, "関連ニュース「ChatGPTの無料プランを変更」")
        eg.refresh(data, {}, reason)
        self.assertEqual(data["needsReviewReason"], reason)
        self.assertEqual(data["checkedAt"], before)
        self.news.assert_called_once_with("ChatGPT", since=before)

    def test_missing_check_date_requests_editorial_review(self):
        data = guide()
        del data["checkedAt"]
        reason = eg.refresh_reason(data, 14)
        self.assertEqual(reason, "確認日なし")
        eg.refresh(data, {}, reason)
        self.assertNotIn("checkedAt", data)
        self.assertEqual(data["needsReviewReason"], reason)

    def test_editorials_do_not_use_automatic_refresh_slots_including_after_limit(self):
        first = guide("first-manual", days_old=20)
        automatic = guide("automatic", days_old=20, editorial=False)
        last = guide("last-manual", days_old=20)
        skipped = guide("second-automatic", days_old=20, editorial=False)
        guides = {g["slug"]: g for g in (first, automatic, last, skipped)}
        plan = [{"slug": g["slug"], "keyword": "keyword"} for g in (automatic, skipped)]
        sources = [{"url": "https://example.test/source", "text": "unchanged", "title": "source"}]
        automatic["sourceHash"] = eg.source_hash(sources)
        with patch.object(eg, "fetch_sources", return_value=sources) as fetch:
            self.run_main(guides, plan, "--refresh", "--refresh-max", "1")
        fetch.assert_called_once()
        self.assertIn("needsReview", first)
        self.assertIn("needsReview", last)
        self.assertEqual(automatic["checkedAt"], NOW.isoformat(timespec="seconds"))
        self.assertFalse((eg.OUT_DIR / "second-automatic.json").exists())
        self.assertEqual(self.read("first-manual")["checkedAt"], first["createdAt"])
        # 再実行でも保留中の手動記事は再起票せず、次の通常記事へ進む。
        skipped["sourceHash"] = eg.source_hash(sources)
        with patch.object(eg, "fetch_sources", return_value=sources) as fetch, \
                patch.object(eg, "write", wraps=eg.write) as write:
            self.run_main(guides, plan, "--refresh", "--refresh-max", "1")
        fetch.assert_called_once()
        self.assertEqual([call.args[0]["slug"] for call in write.call_args_list], ["second-automatic"])

    def test_force_and_direct_build_cannot_overwrite_editorial_or_mark_it_failed(self):
        data = guide()
        before = copy.deepcopy(data)
        topic = {"slug": "manual", "keyword": "keyword"}
        eg.write(data)
        self.assertIsNone(eg.build(topic, data))
        with patch.object(eg, "build", side_effect=AssertionError("must skip protected guide")):
            self.run_main({"manual": data}, [topic], "--only", "manual", "--force")
        self.assertEqual(self.read("manual"), before)
        self.assertFalse(eg.FAILED.exists())

    def test_ordinary_missing_prompt_still_refreshes_and_rebuilds(self):
        data = guide(editorial=False)
        del data["promptVersion"]
        reason = eg.refresh_reason(data, 14)
        self.assertEqual(reason, "原稿の作り方を更新")
        sources = [{"url": "https://example.test/source", "text": "official facts", "title": "source"}]
        topic = {"slug": data["slug"], "keyword": "keyword"}
        with patch.object(eg, "fetch_sources", return_value=sources), patch.object(eg, "build", return_value=data) as build:
            eg.refresh(data, topic, reason)
        build.assert_called_once_with({**topic, "sources": [sources[0]["url"]]}, previous=data)

    def test_editor_can_complete_review_without_disabling_protection(self):
        data = guide(days_old=20)
        eg.refresh(data, {}, eg.refresh_reason(data, 14))
        # 編集者による再確認後の状態。自動処理ではこの操作を行わない。
        data["checkedAt"] = NOW.isoformat(timespec="seconds")
        data.pop("needsReview")
        data.pop("needsReviewReason")
        self.assertEqual(eg.refresh_reason(data, 14), "")
        self.assertEqual(data["refreshMode"], "editorial")
        self.assertNotIn("promptVersion", data)


if __name__ == "__main__":
    unittest.main()
