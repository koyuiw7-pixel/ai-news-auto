"""Muse に依頼した記事は、話題の分野で落とさない（2026-11-13 オーナー「落とすのは嘘だけ」）。ネット・LLM を使わない

きっかけ: NVIDIA の CEO 辞任（公式の発表が出典）の記事が「企業の人事で、暮らし・制度・お金に直接関わらない」という理由で落ちた。
話題を選ぶのは編集部。LLM が落としてよいのは、読めた資料で主な事実を確かめられないときだけ。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import llm  # noqa: E402
import main as m  # noqa: E402
import muse_articles as ma  # noqa: E402
import web_articles as w  # noqa: E402

BASE_PROMPT = "＜ふつうの記事の指示＞\n- is_relevant: 読者にとって実質的な情報価値のある発表・解説なら true。"
DATA = {
    "title": "NVIDIAのフアンCEOが辞任を発表　後任と今後の体制",
    "genre": "速報解説",
    "notes": "FTの報道は未確認",
    "body": "NVIDIAは13日、ジェンスン・フアンCEOの辞任を発表しました。FTが報じたところでは、背景に調査があるとされます。",
}
FETCHED = [{"url": "https://nvidianews.nvidia.com/news/ceo", "name": "NVIDIA", "page": {"text": "NVIDIA today announced"},
            "published": None, "text": "NVIDIA today announced that Jensen Huang will step down."}]


def run(draft: dict):
    """build_article を、LLM と記事の指示づくりだけ差し替えて動かす。返すのは（結果, LLM に渡した指示文）"""
    seen: list[str] = []

    def fake_generate(system, prompt, schema, **kwargs):
        seen.append(prompt)
        return draft, "stub-model"

    composed = ("business", "system", BASE_PROMPT, {}, "news", {}, {})
    with mock.patch.object(w, "compose_with_facts", return_value=composed), \
            mock.patch.object(m, "pick_voice", return_value=("v1", "声")), \
            mock.patch.object(ma, "source_text_of", return_value="NVIDIA today announced"), \
            mock.patch.object(ma.source_date, "check", return_value=[]), \
            mock.patch.object(ma.source_date, "past_change", return_value=[]), \
            mock.patch.object(llm, "generate_json", side_effect=fake_generate):
        result = ma.build_article(Path("20261113_nvidia.md"), DATA, FETCHED)
    return result, seen


class DeskTopicPromptTest(unittest.TestCase):
    def test_prompt_tells_the_llm_not_to_reject_by_topic(self):
        _, seen = run({"is_relevant": False, "skip_reason": "x"})
        self.assertEqual(len(seen), 1)
        prompt = seen[0]
        self.assertIn(ma.MUSE_DESK_NOTE, prompt)
        self.assertIn("話題は編集部が決めた", prompt)
        self.assertIn("話題の分野を理由に対象外にしないでください", prompt)
        self.assertIn("is_relevant は true にする", prompt)
        for field in ("企業の人事", "芸能", "スポーツ", "市場"):
            self.assertIn(field, prompt)

    def test_note_comes_after_the_regular_rules_and_the_draft(self):
        """後ろに置く（ふつうの記事の is_relevant の決まりより後 = この原稿ではこちらが優先）"""
        _, seen = run({"is_relevant": False, "skip_reason": "x"})
        prompt = seen[0]
        self.assertTrue(prompt.startswith(BASE_PROMPT))
        self.assertLess(prompt.index("# 記者の原稿（Muse）"), prompt.index("# 話題は編集部が決めた"))
        self.assertIn(DATA["body"], prompt)
        self.assertIn("上の is_relevant の決まりより優先する", prompt)

    def test_escape_hatch_is_only_for_unsupported_facts(self):
        note = ma.MUSE_DESK_NOTE
        self.assertIn("記事の中心になる事実を確かめられないときだけ", note)
        self.assertIn("資料がその出来事にまったく触れていない", note)
        self.assertIn("別の日・別の出来事", note)
        self.assertIn("古い一般の案内ページ", note)  # Microsoft 365 の障害の例（案内ページしか読めなかった）は今後も落とす
        self.assertIn("どの事実が、どの資料で確かめられなかったか", note)

    def test_reported_allegations_stay_attributed(self):
        note = ma.MUSE_DESK_NOTE
        self.assertIn("FTが報じた", note)
        self.assertIn("確定した事実のようには書かない", note)
        self.assertIn("公式のコメントや発表があるときは、必ず本文に入れる", note)
        self.assertIn("報道機関の記事の URL は出典に並べない", note)  # 出典に報道の URL を並べない決まりはそのまま

    def test_note_has_no_format_placeholders(self):
        """そのまま足す文なので、{ } が混ざると原稿の差し込みを壊す"""
        self.assertNotIn("{", ma.MUSE_DESK_NOTE)
        self.assertNotIn("}", ma.MUSE_DESK_NOTE)


class EscapeHatchStillRejectsTest(unittest.TestCase):
    def test_is_relevant_false_still_rejects_with_the_reason(self):
        reason = "出典の案内ページは数か月前の更新で、原稿が書く障害の発生を確かめられない"
        (status, why), _ = run({"is_relevant": False, "skip_reason": reason})
        self.assertEqual(status, "reject")
        self.assertIn(reason, why)

    def test_regular_lanes_do_not_get_the_desk_note(self):
        """ふつうの自動の記事の指示（web_articles・main）には入れない"""
        for name in ("web_articles.py", "main.py"):
            source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotIn("MUSE_DESK_NOTE", source)
            self.assertNotIn("話題は編集部が決めた", source)


if __name__ == "__main__":
    unittest.main()
