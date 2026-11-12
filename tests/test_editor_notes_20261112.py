"""「（編集部注）」などの札の付いた AI の補足を、中身ごと消す（2026-11-12 AdSense 監査・事実だけの決まり）"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import article_style  # noqa: E402
import editor_notes  # noqa: E402


class StripTest(unittest.TestCase):
    def test_bare_marker_drops_the_sentence(self):
        text = "利用には契約が要ります。契約とは管理を任せることです（編集部注）。\n"
        self.assertEqual("利用には契約が要ります。\n", editor_notes.strip_text(text))

    def test_note_in_parentheses_is_removed_and_the_rest_kept(self):
        text = "「証券金融会社（編集部注：日本証券金融など）」から株を借ります。"
        self.assertEqual("「証券金融会社」から株を借ります。", editor_notes.strip_text(text))

    def test_nested_parentheses(self):
        text = "料金の記載はありません。（編集部注：Gemini API（Vertex AI 経由）の料金が適用されます。）"
        self.assertEqual("料金の記載はありません。", editor_notes.strip_text(text))

    def test_paragraph_led_by_a_label_is_removed(self):
        text = "## 料金\n\n月額10ドルです。\n\n（編集部注）動画では1日とされていますが、実際は3日です。土日を含むためです。\n"
        self.assertEqual("## 料金\n\n月額10ドルです。\n", editor_notes.strip_text(text))

    def test_labeled_comparison_section_is_removed(self):
        text = ("## 何が発表されたのか\n\n新機能です。\n\n## 競合サービスとの比較\n\n"
                "| 項目 | 本製品 | 他社 (編集部注) |\n| --- | --- | --- |\n| 速さ | 速い | 遅い |\n\n"
                "取材班の見立てでは、本製品が優位です。\n\n## まとめ\n\n以上です。\n")
        self.assertEqual("## 何が発表されたのか\n\n新機能です。\n\n## まとめ\n\n以上です。\n", editor_notes.strip_text(text))

    def test_labeled_table_column_is_dropped(self):
        text = "| 項目 | 本製品 | 他社（編集部注） |\n| --- | --- | --- |\n| 料金 | 月10ドル | 月20ドル |\n"
        self.assertEqual("| 項目 | 本製品 |\n| --- | --- |\n| 料金 | 月10ドル |\n", editor_notes.strip_text(text))

    def test_text_without_labels_is_unchanged(self):
        text = "## 料金\n\n月額10ドルです（公式の料金ページ、11/12確認）。\n"
        self.assertIs(text, editor_notes.strip_text(text))

    def test_structured_fields_drop_only_the_labeled_sentence(self):
        record = {"body": "本文です。", "workMoney": {"points": ["編集部の見立てでは、まず50%で考えます。70%は後から支給されます。"]}}
        editor_notes.strip_record(record)
        self.assertEqual(["70%は後から支給されます。"], record["workMoney"]["points"])

    def test_autofix_strips_labels_for_every_writer(self):
        record = {"slug": "x", "title": "t", "body": "本文です。背景はこうです（編集部注）。\n", "easy": ""}
        article_style.autofix(record)
        self.assertNotIn("編集部注", record["body"])


class RealDataTest(unittest.TestCase):
    def test_no_live_article_has_editor_labels(self):
        left = []
        for path in sorted((ROOT / "content" / "articles").glob("*.json")):
            data = json.loads(path.read_text("utf-8"))
            text = json.dumps({k: data.get(k) for k in editor_notes.FIELDS + editor_notes.OTHER_FIELDS}, ensure_ascii=False)
            if editor_notes.LABEL_RE.search(text):
                left.append(path.stem)
        self.assertEqual([], left)


if __name__ == "__main__":
    unittest.main()
