"""2026-11-07 オーナー決定（台帳 A49）: 日本語の企業向け・開発者向けの発表（AWS・Google Cloud の日本語ブログのトヨタ・KDDI の事例など）は
国内のニュースとして扱い、企業向けの上限（A41）と海外の AI の上限（A47）に数えない。外国語の企業向けの発表は今までどおり上限あり。外部への通信なし。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import news_mix as nm  # noqa: E402
import web_articles as wa  # noqa: E402

FULL = {"enterprise_dev": 99}


class JapaneseEnterpriseTest(unittest.TestCase):
    def test_japanese_feed_case_study_is_domestic(self):
        for item in (
            {"title": "トヨタはいかにして BasisPilot を構築したか – AWS 上の AI アシスト型 SAP 運用プラットフォーム", "source_slug": "aws-japan-blog"},
            {"title": "KDDI のコンシューマー向け RAG アプリ「Buffmee」: 高速化と信頼性向上を実現した舞台裏", "source_slug": "google-cloud-blog-ja"},
        ):
            self.assertTrue(nm.is_japanese_item(item))
            self.assertNotEqual(nm.classify(item), "enterprise_dev", item["title"])
            self.assertFalse(nm.over_cap(item, FULL), item["title"])
            self.assertFalse(wa.is_foreign_ai(item), item["title"])

    def test_foreign_enterprise_keeps_caps(self):
        item = {"title": "Getting started with Web Answer on Amazon Bedrock AgentCore", "source_slug": "aws-ml-blog"}
        self.assertFalse(nm.is_japanese_item(item))
        self.assertEqual(nm.classify(item), "enterprise_dev")
        self.assertTrue(nm.over_cap(item, FULL))
        self.assertTrue(wa.is_foreign_ai(item))

    def test_item_lang_wins_and_title_alone_does_not_decide(self):
        self.assertTrue(nm.is_japanese_item({"title": "x", "source_slug": "aws-ml-blog", "lang": "ja"}))
        # 記事の題名はいつも日本語なので、題名だけで国内にしない（海外の発表の記事を数え直すとき）
        self.assertEqual(nm.classify({"title": "Docker、AIコーディングエージェント向けサンドボックス", "source_slug": "docker-blog"}), "enterprise_dev")

    def test_ledger_row(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next((line for line in rules.splitlines() if line.startswith("| A49 |")), "")
        self.assertIn("2026-11-07", row)
        self.assertIn("日本語", row)


if __name__ == "__main__":
    unittest.main()
