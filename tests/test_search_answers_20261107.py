"""2026-11-07 オーナー指示: すでに検索で表示されている記事・イベントのページに、探されている問いの答えを冒頭の章で入れる
（事実は公式のページで確かめたものだけ・門は変えない）。docs/search_answers_20261107.md。外部への通信なし。"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import headline_normalize as hn  # noqa: E402
import indexnow  # noqa: E402

ANSWERS = {
    "honda-rn0-emtb-eicma-2026": "## Honda RN0の価格と日本での発売は？",
    "mhlw-izoku-nenkin-chosa-2026": "## 遺族年金受給者実態調査の対象・期限・回答方法・問い合わせ先",
    "sakana-ai-symposium-2026-sawara": "## Sakana Sawaraはいつ公開？使える？",
    "microsoft-work-iq-agent-context-m365": "## Work IQの料金は？",
    "llama-app-mac-local-ai-hugging-face": "## Llamaアプリの入れ方とローカルAPI",
    "deepmind-sierra-native-voice-ai-tau-bench": "## tau-Voice（τ-voice）とは",
    "nvidia-halos-safe-autonomous-vehicle-safety": "## NVIDIA Halos SAFEとは",
}


def article(slug):
    return json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))


class SearchAnswersTest(unittest.TestCase):
    def test_answer_section_is_early_with_official_source(self):
        for slug, heading in ANSWERS.items():
            a = article(slug)
            body = a["body"]
            self.assertIn(heading, body, slug)
            heads = [line for line in body.splitlines() if line.startswith("## ")]
            self.assertLessEqual(heads.index(heading), 1, f"{slug}: 答えの章は冒頭（最初か2つ目の見出し）")
            section = body[body.index(heading):].split("\n## ", 1)[0]
            self.assertIn("出典：", section, slug)
            self.assertIn("2026年11月7日に確認", section, slug)
            self.assertIsNone(indexnow.publish_block_reason(a), slug)
            self.assertEqual(hn.title_problems(a["title"]), [], slug)
            self.assertNotIn("とは？", a.get("seoTitle", "") if slug != "deepmind-sierra-native-voice-ai-tau-bench" else "")

    def test_unknowns_are_stated_not_guessed(self):
        self.assertIn("発売日、販売する国は書かれていません", article("honda-rn0-emtb-eicma-2026")["body"])
        self.assertIn("料金、パラメータ数、対応する言語", article("sakana-ai-symposium-2026-sawara")["body"])

    def test_types_rewrite_keeps_verified_answer(self):
        """種類の型での書き直し（scripts/rewrite_types.py）が、公式で確かめた答えの章を消さない（2026-11-08 に Sakana の章が消えた）"""
        import rewrite_types  # noqa: PLC0415

        old = "前文。\n\n## 概要\n\n古い概要。\n\n## Xはいつ使える？\n\n答え。\n\n出典：[公式](https://example.com/)（2026年11月7日に確認）\n\n## 料金は？\n\n未発表。"
        new = "新しい前文。\n\n## 何が変わる\n\n新しい本文。\n\n## まだ分からないこと\n\n- 料金"
        body = rewrite_types.keep_sections(old, new)
        heads = [line for line in body.splitlines() if line.startswith("## ")]
        self.assertEqual(heads[0], "## Xはいつ使える？")
        self.assertIn("（2026年11月7日に確認）", body)
        self.assertNotIn("古い概要", body)
        self.assertTrue(body.startswith("新しい前文。"))

    def test_event_answers(self):
        events = {e["slug"]: e for e in json.loads((ROOT / "content" / "events.json").read_text("utf-8"))["events"]}
        adobe = events["adobe-max-2026"]
        qs = [a["q"] for a in adobe["answers"]]
        self.assertTrue(any("Adobe MAX Japan 2026" in q for q in qs))
        japan = next(a for a in adobe["answers"] if "Japan" in a["q"])
        self.assertIn("日程は載っていません", japan["a"])
        self.assertTrue(all(a.get("sources") for a in adobe["answers"]))
        self.assertEqual(adobe["keynotes"][0]["startUtc"], "2026-11-10T14:00:00Z")  # 9時（米東部）＝日本時間23時
        self.assertIn("12月2日（水）午前4時", events["nvidia-gtc-dc-2026"]["answers"][0]["a"])
        page = (ROOT / "app" / "events" / "[slug]" / "page.tsx").read_text("utf-8")
        self.assertIn("event.answers", page)
        self.assertNotIn('event.slug === "adobe-max-2026" && (', page)

    def test_internal_links_use_query_wording(self):
        self.assertIn("[Work IQの料金", article("microsoft-copilot-work-iq-dev-tools")["body"])
        self.assertIn("(/events/nvidia-gtc-dc-2026)", article("nvidia-gtc-berlin-2026-keynote-highlights")["body"])

    def test_log_has_no_search_numbers(self):
        doc = (ROOT / "docs" / "search_answers_20261107.md").read_text("utf-8")
        self.assertNotRegex(doc, r"表示\s*\d|順位\s*\d|\d+@\d")


if __name__ == "__main__":
    unittest.main()
