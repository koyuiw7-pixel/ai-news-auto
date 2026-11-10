"""SEO A14（本文が先）: 検索された言葉を、まず本文に。題名（searchTitle）は扱わない。外部への通信なし。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import deep_dive  # noqa: E402
import search_refresh  # noqa: E402
import search_words  # noqa: E402


class SearchWordsTest(unittest.TestCase):
    def test_words_drop_question_tails(self):
        self.assertEqual(["chatgpt", "terra"], search_words.words_of("ChatGPT terraとは"))
        self.assertEqual(["児童手当", "支給日"], search_words.words_of("児童手当　支給日"))

    def test_report_lists_pages_missing_words_and_never_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            rec = {"slug": "a", "title": "児童手当の12月", "body": "12月は2か月分が振り込まれます。"}
            (d / "a.json").write_text(json.dumps(rec, ensure_ascii=False), "utf-8")
            before = (d / "a.json").read_text("utf-8")
            rows = search_words.report({"pages": {"a": {"query": "児童手当 支給日"}, "gone": {"query": "x"}}}, d)
            self.assertEqual([("a", "児童手当 支給日", ["支給日"])], rows)
            self.assertEqual(before, (d / "a.json").read_text("utf-8"))

    def test_prompts_ask_for_searched_words_in_the_first_paragraph(self):
        focus = search_refresh.focus_for({"query": "児童手当 支給日", "position": 7.0})
        self.assertIn("本文の最初の段落", focus)
        self.assertIn("題名は変えない", focus)
        self.assertIn("本文の最初の段落", deep_dive.DEEP_NOTE)
        self.assertNotIn("searchTitle", (ROOT / "scripts" / "search_words.py").read_text("utf-8").split('"""')[2])


if __name__ == "__main__":
    unittest.main()
