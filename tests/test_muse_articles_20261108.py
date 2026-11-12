"""Muse の記事の入稿（2026-11-08 オーナー承認・台帳 A59）。ネット・LLM を使わない"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import muse_format  # noqa: E402

BODY = "\n\n".join(
    ["国税庁は2026年9月、民間給与実態統計調査の結果を公表しました。" * 3]
    + [f"## 見出し{i}\n\n" + ("1年を通じて勤めた人の平均給与は487万円で、前の年より1.9%増えました（国税庁の調査結果）。" * 12) for i in range(3)]
)


def submission(title: str = "会社員の平均給与は487万円で過去最高　国税庁の2025年分の調査", url: str = "https://www.nta.go.jp/a.pdf",
               body: str = BODY) -> str:
    return (f"---\ntitle: {title}\ngenre: お金\nsources:\n  - url: {url}\n    name: 国税庁\n    facts: 平均給与487万円（1ページ）\n"
            f"notes: |\n  年末に検索が増える。\n  年代別は未確認。\n---\n{body}\n")


class FormatTest(unittest.TestCase):
    def test_example_in_format_md_parses(self):
        example = re.search(r"```\n(---.*?)```", muse_format.FORMAT_MD, re.S).group(1)
        data = muse_format.parse(example)
        self.assertEqual(data["genre"], "お金")
        self.assertTrue(data["sources"][0]["url"].startswith("https://www.nta.go.jp/"))
        self.assertTrue(data["sources"][0]["facts"])
        self.assertIn("年代別", data["notes"])

    def test_good_submission_has_no_problems(self):
        data = muse_format.parse(submission())
        self.assertEqual(muse_format.problems(data, "20261108-お金-平均給与.md"), [])

    def test_vertical_bar_press_and_short_body_are_rejected(self):
        data = muse_format.parse(submission(title="平均給与は487万円｜国税庁の民間給与実態統計調査の結果", url="https://news.yahoo.co.jp/x",
                                            body="## a\n\n短い\n\n## b\n\n短い"))
        text = " ".join(muse_format.problems(data, "bad-name.md"))
        self.assertNotIn("「｜」", text)  # 2026-11-08: 「｜」は自動で直す
        self.assertNotIn("｜", data["title"])
        self.assertIn("出典にできません", text)
        self.assertNotIn("本文が短すぎます", text)  # 2026-11-08: 字数では落とさない
        self.assertIn("ファイル名", text)

    def test_missing_front_matter_is_a_format_error(self):
        with self.assertRaises(muse_format.FormatError):
            muse_format.parse("題名だけ\n本文")

    def test_mac_nfd_file_names_are_normalized(self):
        import unicodedata

        nfd = unicodedata.normalize("NFD", "20261108-お金-平均給与.md")
        self.assertEqual(muse_format.nfc(nfd), "20261108-お金-平均給与.md")
        self.assertEqual(muse_format.problems(muse_format.parse(submission()), nfd), [])


class PipelineTest(unittest.TestCase):
    def test_published_muse_article_counts_toward_daily_stage(self):
        import muse_articles
        import pacing

        with tempfile.TemporaryDirectory() as tmp:
            articles = Path(tmp)
            (articles / "muse-slug.json").write_text("{}", encoding="utf-8")
            state: dict = {"processed_web": {}}
            muse_articles.register_today(state, "muse-abc", {"slug": "muse-slug", "sourceUrl": "https://www.nta.go.jp/a.pdf",
                                                              "title": "会社員の平均給与は487万円"})
            self.assertEqual(pacing.live_today(state, articles_dir=articles), 1)
            self.assertEqual(state["processed_web"]["muse-abc"]["writer"], "muse")

    def test_genres_map_to_site_lanes_and_procedures_need_90(self):
        import genres
        import muse_articles

        slugs = {g.slug for g in genres.WEB_GENRES} | {"ai"}
        for genre in muse_format.GENRES:
            self.assertIn(muse_articles.LANE_BY_GENRE[genre], slugs)
        self.assertEqual(muse_articles.pass_score("手続き"), 90)
        self.assertGreaterEqual(muse_articles.pass_score("お金"), 80)

    def test_press_sources_are_rejected_before_any_llm(self):
        import muse_articles

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "20261108-お金-平均給与.md"
            path.write_text(submission(url="https://www3.nhk.or.jp/news/html/x.html"), encoding="utf-8")
            _, problems = muse_articles.check_file(path)
            self.assertTrue(any("出典" in p for p in problems))

    def test_muse_articles_are_excluded_from_bulk_rewrites(self):
        import rewrite_types

        self.assertFalse(rewrite_types.eligible({"sourceType": "web", "sourceUrl": "https://www.nta.go.jp/a.pdf", "slug": "x",
                                                 "refreshMode": "editorial", "writer": "muse"}, set()))
        self.assertIn('a.get("refreshMode") != "editorial"', (ROOT / "scripts" / "rewrite_titles.py").read_text("utf-8"))

    def test_inbox_runs_in_its_own_workflow_and_commits_results(self):
        # 2026-11-09: 記事づくりの回（auto_run.yml）から外し、muse_inbox.yml（別の concurrency）で動かす（100本/日のため）
        auto = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        flow = (ROOT / ".github" / "workflows" / "muse_inbox.yml").read_text("utf-8")
        self.assertNotIn("python scripts/muse_articles.py", auto)
        self.assertIn("content/muse_inbox/**", flow)
        self.assertIn("group: muse-inbox", flow)
        self.assertNotIn("group: auto-article-pipeline", flow)
        # 今日の本数は記事づくりの回と同じ段の上限で数える
        self.assertIn("python scripts/ramp.py", flow)
        # 2026-11-12: Muse は自動の記事の本数に食われない別の上限（scripts/ramp.py の MUSE_DAILY_CAP）
        self.assertIn('--daily-cap "${{ steps.ramp.outputs.muse_daily_cap || steps.ramp.outputs.web_daily_cap }}"', flow)
        self.assertIn("state/muse_articles.json", flow)
        self.assertIn("git add -A content", flow)  # 記事・content/state.json・消した入稿
        self.assertIn("scripts/git_safe_push.py", flow)
        self.assertLess(flow.index("scripts/muse_articles.py"), flow.index("scripts/images.py"))


class PushTest(unittest.TestCase):
    def setUp(self):
        import muse_articles_push as push

        self.push = push
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.folder = base / "saisoku-articles"
        self.clone = base / "repo"
        (self.clone / "state").mkdir(parents=True)
        (self.clone / "content" / "articles").mkdir(parents=True)
        self.folder.mkdir()
        self.patches = [mock.patch.object(push, "FOLDER", self.folder), mock.patch.object(push, "CLONE", self.clone)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_results_move_files_and_write_reason(self):
        sent = self.folder / "sent"
        sent.mkdir()
        (sent / "20261108-お金-a.md").write_text("x", encoding="utf-8")
        (sent / "20261108-お金-b.md").write_text("x", encoding="utf-8")
        items = {"20261108-お金-a.md": {"status": "published", "url": "https://ai-tech-express.jp/articles/a"},
                 "20261108-お金-b.md": {"status": "rejected", "reason": "重複: 同じ話題"}}
        self.push.settle_results(items)
        self.assertTrue((self.folder / "done" / "20261108-お金-a.md").exists())
        self.assertIn("重複", (self.folder / "rejected" / "20261108-お金-b.reason.txt").read_text("utf-8"))

    def test_bad_new_file_goes_to_rejected_with_reason(self):
        path = self.folder / "20261108-お金-c.md"
        path.write_text("front matter なし", encoding="utf-8")
        old = time.time() - 600
        os.utime(path, (old, old))
        self.assertEqual(self.push.pick_new(muse_format, {}), [])
        self.assertTrue((self.folder / "rejected" / "20261108-お金-c.reason.txt").exists())

    def test_files_still_being_written_wait(self):
        (self.folder / "20261108-お金-d.md").write_text(submission(), encoding="utf-8")
        self.assertEqual(self.push.pick_new(muse_format, {}), [])
        self.assertTrue((self.folder / "20261108-お金-d.md").exists())

    def test_ledger_lists_recent_articles_and_muse_results(self):
        now = datetime.now(timezone.utc).isoformat()
        (self.clone / "content" / "articles" / "a.json").write_text(json.dumps(
            {"slug": "a", "title": "公式の発表の記事", "generatedAt": now}, ensure_ascii=False), encoding="utf-8")
        (self.clone / "content" / "articles" / "m.json").write_text(json.dumps(
            {"slug": "m", "title": "Muse の記事", "generatedAt": now, "writer": "muse"}, ensure_ascii=False), encoding="utf-8")
        self.push.write_ledger({"20261108-お金-a.md": {"status": "rejected", "reason": "書式: 本文が短すぎます", "at": now, "title": "t"}},
                               ["20261108-お金-e.md"])
        text = (self.folder / "ledger.md").read_text("utf-8")
        self.assertIn("https://ai-tech-express.jp/articles/a", text)
        self.assertIn("Muse の記事（Muse）", text)
        self.assertIn("見送り", text)
        self.assertIn("審査中", text)


if __name__ == "__main__":
    unittest.main()
