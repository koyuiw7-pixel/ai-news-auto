"""polish / surgical_fix が、指示文の章名（「# 今の原稿の数値」など）をこぼした本文を受け取らないことの検査。

2026-11-07 elevenagents-unity-sdk-npc-voice の本文が「# 今の原稿の数値」で始まったまま公開された。
外部 API は呼ばない（llm.generate_json と evaluate を差し替える）。
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import quality  # noqa: E402

BODY = (
    "## 概要\n\nElevenLabsがUnity向けのSDKを公開した。ゲームの登場人物が声で話せるようになり、開発者は少ない手間で会話を作れる。\n\n"
    "## 詳しく\n\n料金は月5ドルからで、無料枠もある。対応は2026年11月から始まる。"
)


def _record() -> dict:
    return {"title": "t", "body": BODY}


class PromptEchoDetect(unittest.TestCase):
    def test_clean_body_passes(self):
        self.assertEqual(quality.prompt_echo_problem(BODY, BODY), "")

    def test_prompt_headings_rejected(self):
        for head in ("# 今の原稿の数値", "# 直し方", "# 変えてはいけないもの", "# 原稿", "## 直し方", "### 原稿", "# 校閲の指摘"):
            with self.subTest(head=head):
                self.assertTrue(quality.prompt_echo_problem(f"{head}\n\n{BODY}", BODY))

    def test_any_new_h1_rejected(self):
        self.assertTrue(quality.prompt_echo_problem("# ElevenLabsの新SDK\n\n" + BODY, BODY))

    def test_existing_h1_in_original_allowed(self):
        body = "# 元からある題\n\n" + BODY
        self.assertEqual(quality.prompt_echo_problem(body, body), "")

    def test_delimiters_rejected(self):
        self.assertTrue(quality.prompt_echo_problem("<<<\n" + BODY + "\n>>>", BODY))

    def test_normal_h2_with_similar_words_ok(self):
        body = BODY + "\n\n## 直し方のコツ\n\n設定を見直す。"
        self.assertEqual(quality.prompt_echo_problem(body, ""), "")


class PolishFallsBack(unittest.TestCase):
    def _polish(self, echoed: str):
        with patch.object(quality.llm, "generate_json", return_value=({"body_markdown": echoed}, "fake")), \
             patch.object(quality, "evaluate", side_effect=AssertionError("evaluate は呼ばれないはず")):
            return quality.polish(_record(), "source", "ai", check_facts=False)

    def test_polish_rejects_leading_prompt_heading(self):
        polished, info = self._polish("# 今の原稿の数値\n\n" + BODY)
        self.assertIsNone(polished)  # 呼び出し側は元の原稿のまま使う
        self.assertIn("指示文", info)

    def test_polish_rejects_echoed_sections(self):
        echoed = "# 今の原稿の数値\n- 平均文長 70字\n\n# 原稿\n<<<\n" + BODY + "\n>>>"
        polished, _ = self._polish(echoed)
        self.assertIsNone(polished)

    def test_surgical_rejects_prompt_heading(self):
        data = {"title": "t", "lede": "", "highlights": [], "body_markdown": "# 直し方\n\n" + BODY,
                "easy_markdown": "", "work_money_points": []}
        with patch.object(quality.llm, "generate_json", return_value=(data, "fake")), \
             patch.object(quality, "evaluate", side_effect=AssertionError("evaluate は呼ばれないはず")):
            fixed, info = quality.surgical_fix(_record(), "source", "ai", ["指摘"])
        self.assertIsNone(fixed)
        self.assertIn("指示文", info)


if __name__ == "__main__":
    unittest.main()
