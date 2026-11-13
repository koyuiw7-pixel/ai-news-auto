"""2026-11-13: 1件目の出典が読めなくても、ほかに読めた公式の出典があれば、それだけで記事にする（全ジャンル）。

きっかけ: 7日で6本が「1件目の出典を読めませんでした」で落ちた（PDF・JavaScript で描くページ。ほかの出典は読めていた）。
読めなかったページにしか無い事実は書かせない（指示に入れる）。事実確認・数字の門は読めた資料だけで見るので、うその基準は変わらない。
1本も読めなければ今までどおり見送る。ネット・LLM を使わない。
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import feeds  # noqa: E402
import llm  # noqa: E402
import main as m  # noqa: E402
import muse_articles as ma  # noqa: E402
import pacing  # noqa: E402
import web_articles as w  # noqa: E402

PDF = "https://www.mhlw.go.jp/content/12500000/001750551.pdf"
HTML = "https://www.nenkin.go.jp/service/kokunen/hokenryo/hokenryo.html"
DATA = {"title": "国民年金保険料は2027年度に月額が変わる　前納の割引額も確認", "genre": "お金", "notes": "",
        "body": "## 月額\n令和9年度の国民年金保険料の月額を確かめます。",
        "sources": [{"url": PDF, "name": "厚生労働省", "facts": "f"}, {"url": HTML, "name": "日本年金機構", "facts": "f"}]}
NAME = "20261113-お金-国民年金保険料2027年度.md"


def fake_fetch(bad: set[str]):
    def fetch(url):
        if url in bad:
            raise RuntimeError("本文を取得できません（直接 PDF の文字を取り出せない）")
        return {"text": "国民年金保険料の公式の案内。" * 60, "title": "公式", "image": "", "published": ""}
    return fetch


def run_process(bad: set[str]):
    """process を、入稿1本・ネットなし・記事づくり（build_article）を差し替えて動かす。（build_article の呼び出し, 結果の行）"""
    calls: list[dict] = []
    results = {"items": {}}

    def fake_build(path, data, fetched, unread=None):
        calls.append({"fetched": [s["url"] for s in fetched], "unread": list(unread or [])})
        return "reject", "試験のため見送り"

    with tempfile.TemporaryDirectory() as tmp:
        inbox = Path(tmp)
        (inbox / NAME).write_text("x", "utf-8")
        with mock.patch.object(ma, "INBOX", inbox), \
                mock.patch.object(ma, "check_file", return_value=(dict(DATA), [])), \
                mock.patch.object(ma, "duplicate_of", return_value=None), \
                mock.patch.object(ma, "load_results", return_value=results), \
                mock.patch.object(ma, "save_results"), \
                mock.patch.object(m, "load_state", return_value={}), mock.patch.object(m, "save_state"), \
                mock.patch.object(pacing, "live_today", return_value=0), \
                mock.patch.object(feeds, "fetch_article_text", side_effect=fake_fetch(bad)), \
                mock.patch.object(ma, "build_article", side_effect=fake_build):
            ma.process(argparse.Namespace(max=3, budget=600, daily_cap=0))
    return calls, results["items"][NAME]


class UnreadFirstSourceTest(unittest.TestCase):
    def test_goes_on_with_the_readable_source_in_every_genre(self):
        calls, row = run_process({PDF})
        self.assertEqual(calls, [{"fetched": [HTML], "unread": [PDF]}])
        self.assertNotIn("1件目の出典", row["reason"])
        # 見送ったときの理由には、読めなかった出典を添える（Muse が読めるページに替えられるように）
        self.assertIn("読めなかった出典", row["reason"])
        self.assertIn(PDF, row["reason"])

    def test_all_sources_unreadable_is_still_rejected_before_any_llm(self):
        calls, row = run_process({PDF, HTML})
        self.assertEqual(calls, [])
        self.assertEqual(row["status"], "rejected")
        self.assertIn("出典（公式ページ）を1本も読めませんでした", row["reason"])

    def test_nothing_changes_when_every_source_is_readable(self):
        calls, _ = run_process(set())
        self.assertEqual(calls, [{"fetched": [PDF, HTML], "unread": []}])


def prompt_for(unread):
    seen: list[str] = []

    def fake_generate(system, prompt, schema, **kwargs):
        seen.append(prompt)
        return {"is_relevant": False, "skip_reason": "x"}, "stub-model"

    fetched = [{"url": HTML, "name": "日本年金機構", "page": {"text": "t"}, "published": None, "text": "t"}]
    with mock.patch.object(w, "compose_with_facts", return_value=("public", "system", "＜指示＞", {}, "news", {}, {})), \
            mock.patch.object(m, "pick_voice", return_value=("v1", "声")), \
            mock.patch.object(ma, "source_text_of", return_value="t"), \
            mock.patch.object(ma.source_date, "check", return_value=[]), \
            mock.patch.object(ma.source_date, "past_change", return_value=[]), \
            mock.patch.object(llm, "generate_json", side_effect=fake_generate):
        ma.build_article(Path(NAME), DATA, fetched, **({"unread": unread} if unread is not None else {}))
    return seen[0]


class UnreadNoteTest(unittest.TestCase):
    def test_prompt_names_the_unread_pages_and_forbids_facts_only_they_support(self):
        prompt = prompt_for([PDF])
        self.assertIn("# 読めなかった出典", prompt)
        self.assertIn(f"- {PDF}", prompt)
        self.assertIn("読めなかったページを根拠にしない", prompt)
        self.assertIn("確かめられないものは書かない（削る）", prompt)
        self.assertIn("題名・lede・highlights・threads_post も同じ", prompt)
        self.assertIn("中心の事実が確かめられないなら is_relevant を false", prompt)
        self.assertIn("読めなかったページを並べない", prompt)

    def test_no_note_when_everything_was_read(self):
        for unread in (None, []):
            self.assertNotIn("# 読めなかった出典", prompt_for(unread))

    def test_note_survives_urls_with_braces(self):
        self.assertIn("https://example.go.jp/a{b}.pdf", prompt_for(["https://example.go.jp/a{b}.pdf"]))


class PdfReadingTest(unittest.TestCase):
    def test_pdf_sources_are_text_extracted(self):
        """PDF は feeds が pdf_text（pdftotext → pypdf）で文字を取り出す。Muse の回にも pdftotext を入れる"""
        source = (ROOT / "scripts" / "feeds.py").read_text("utf-8")
        self.assertIn("pdf_text.extract(", source)
        workflow = (ROOT / ".github" / "workflows" / "muse_inbox.yml").read_text("utf-8")
        self.assertIn("poppler-utils", workflow)
        self.assertLess(workflow.index("Install poppler"), workflow.index("name: Muse articles"))


if __name__ == "__main__":
    unittest.main()
