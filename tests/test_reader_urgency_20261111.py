"""2026-11-11 読者目線レビュー 6位: 意味の無い「速報」と「すぐにできること」が信頼をこわす。

- 赤い「速報」（サイトの札・SNS の【速報】）は、読者に関わる話題だけ。面会・会談・式典・人事などは付けない
- 読者がすることの無い発表には「今日やること」「すぐにできること（手順つき）」を書かない・出さない
- 「面会の詳しい内容を〇〇課に電話で問い合わせる」のような、記事の中身を問い合わせるだけの行動は書かない・出さない
判定の正本は scripts/persona.py。サイトの lib/cover-path.ts（lib/reader-urgency.ts から読む）と文字列が同じであることを確かめる。
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import persona  # noqa: E402
import sns_rules  # noqa: E402
import web_articles  # noqa: E402

MOF = "財務省の片山大臣、ベトナム財政大臣と面会　今後の二国間協力を協議"
MOF_ACTIONS = ["面会の詳しい内容や次回協議の予定を、財務省国際局地域協力課に電話で問い合わせる", "財務省の二国間財務大臣会談等のページで、ほかの面会の記録を見る"]


def ts_source(name: str) -> str:
    src = (ROOT / "lib" / "cover-path.ts").read_text("utf-8")
    m = re.search(rf'export const {name} =\s*"((?:[^"\\]|\\.)*)";', src)
    assert m, name
    return m.group(1).replace("\\\\", "\\")


class SameRulesTest(unittest.TestCase):
    def test_site_and_scripts_use_the_same_patterns(self):
        self.assertEqual(ts_source("NO_READER_ACTION_SOURCE"), persona.NO_READER_ACTION_RE.pattern)
        self.assertEqual(ts_source("READER_URGENT_SOURCE"), persona.READER_URGENT_RE.pattern)
        self.assertEqual(ts_source("MEANINGLESS_ACTION_SOURCE"), persona.MEANINGLESS_ACTION_RE.pattern)
        # サイトの赤い「速報」（isFastNews）と、記事の欄（lib/depth.ts）・今までの見た目の「今日やること」が同じ判定を使う
        self.assertIn("return urgentForReader(article);", (ROOT / "lib" / "cover-path.ts").read_text("utf-8"))
        self.assertIn("readerActions(a.title", (ROOT / "lib" / "depth.ts").read_text("utf-8"))
        self.assertIn("readerActions(article.title", (ROOT / "app" / "articles" / "[slug]" / "page.tsx").read_text("utf-8"))


class BreakingLabelTest(unittest.TestCase):
    def test_meeting_is_not_breaking(self):
        mof = {"title": MOF, "genreSlug": "public", "speedMinutes": 30}
        self.assertFalse(persona.urgent_for_reader(mof))
        self.assertFalse(sns_rules.is_fast_news(mof))

    def test_life_money_announcements_and_ai_stay_breaking(self):
        self.assertTrue(sns_rules.is_fast_news({"title": "ドコモで顧客情報が流出、最大30万件", "genreSlug": "lifestyle", "breaking": True}))
        self.assertTrue(sns_rules.is_fast_news({"title": "児童手当の申請期限を延長", "genreSlug": "public", "speedMinutes": 20}))
        self.assertTrue(sns_rules.is_fast_news({"title": "OpenAI が新しいモデルを公開", "genreSlug": "ai", "breaking": True}))
        # 暮らしとお金に直接関わらない発表は、速さだけでは速報にしない
        self.assertFalse(sns_rules.is_fast_news({"title": "国際海事機関、事務局長の再任を決定", "genreSlug": "business", "speedMinutes": 10}))


class TodayActionsTest(unittest.TestCase):
    def test_generator_drops_actions_for_meetings_and_meaningless_inquiries(self):
        self.assertEqual([], web_articles.clean_actions(MOF_ACTIONS, MOF))
        kept = web_articles.clean_actions(["申請書を市区町村の窓口に出す", "検討会の今後の予定を担当課に電話で問い合わせる", "公式ページで対象を確かめる"], "児童手当の申請")
        self.assertEqual(["申請書を市区町村の窓口に出す", "公式ページで対象を確かめる"], kept)
        self.assertIn("面会・会談・式典・人事・表彰", web_articles.FAQ_TODAY_FIELD)

    def test_fill_does_not_add_actions_to_meetings(self):
        record = {"genreSlug": "public", "title": MOF}
        self.assertEqual([], web_articles.fill_faq_actions(record))  # モデルを呼ばずに何もしない
        self.assertNotIn("todayActions", record)

    def test_depth_fields_prompt_and_filter(self):
        import depth_fields  # noqa: PLC0415

        self.assertIn("today_steps を空配列 [] にする", (ROOT / "scripts" / "depth_fields.py").read_text("utf-8"))
        self.assertIn("persona.reader_actions(", (ROOT / "scripts" / "depth_fields.py").read_text("utf-8"))
        self.assertEqual([], persona.reader_actions(MOF, [{"action": a} for a in MOF_ACTIONS]))

    def test_existing_articles_have_no_meaningless_actions(self):
        bad = []
        for path in (ROOT / "content" / "articles").glob("*.json"):
            try:
                a = json.loads(path.read_text("utf-8"))
            except ValueError:
                continue
            texts = [str(x) for x in a.get("todayActions") or []] + [str(s.get("action", "")) for s in a.get("todaySteps") or [] if isinstance(s, dict)]
            bad += [f"{a.get('slug')}: {t}" for t in texts if persona.meaningless_action(t)]
        self.assertEqual([], bad)


if __name__ == "__main__":
    unittest.main()
