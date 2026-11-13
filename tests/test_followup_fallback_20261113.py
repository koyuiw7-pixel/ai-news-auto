"""2026-11-13 オーナー「とにかく数字」「注目する話題がとれていない」: 続報の追記（既存の記事への書き足し）が門に落ちたとき、
話題ごと捨てずに新しい動きの記事として作り直す（点検 audit_20261113: 7日で47件。新しいモデルの発表が記事なしになっていた）。
追記を公開中の記事に書き込まないのは今までどおり。見出しがほぼ同じなら作り直さない（重複の門）。外部への通信なし。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import web_articles as w  # noqa: E402

SRC = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")


class FollowupFallbackTest(unittest.TestCase):
    def test_new_development_becomes_a_new_article(self):
        article = {"title": "Googleが「Gemini 4 Carbon」を発表　一部の防御担当者向けに先行公開", "videoTitle": "Introducing Gemini 4 Carbon"}
        ok, why = w.followup_fallback_ok("Gemini 4 Carbon is now available", article)
        self.assertTrue(ok, why)
        ok, _ = w.followup_fallback_ok("Gemini 4 Carbon、日本でも一般提供を開始　料金は月2,900円", article)
        self.assertTrue(ok)

    def test_same_headline_is_not_recreated(self):
        article = {"title": "ドコモ、dポイントの還元率を12月から変更", "videoTitle": "dポイントクラブの特典の変更について"}
        ok, why = w.followup_fallback_ok("ドコモ、dポイントの還元率を12月から変更へ", article)
        self.assertFalse(ok)
        self.assertIn("見出しが類似", why)
        ok, _ = w.followup_fallback_ok("dポイントクラブの特典の変更について", article)  # もとの発表と同じ題名
        self.assertFalse(ok)
        self.assertTrue(w.same_headline({"title": "ドコモ、dポイントの還元率を12月から変更へ"}, article))
        self.assertFalse(w.same_headline({"title": "dポイント、家族の合算は2027年3月に終了"}, article))

    def test_prompt_note_names_the_existing_article(self):
        note = w.FOLLOWUP_NEW_NOTE.format(title="Googleが「Gemini 4 Carbon」を発表", facts="一般提供の開始と料金")
        self.assertIn("Googleが「Gemini 4 Carbon」を発表", note)
        self.assertIn("一般提供の開始と料金", note)
        self.assertIn("資料に無いことは書かない", note)

    def test_pipeline_wiring(self):
        follow = SRC[SRC.index("    def try_followup("):SRC.index("    skip_counts: dict[str, int] = {}")]
        # 追記の事実確認・文体の門のどちらに落ちても、作り直しを試す。新しい事実が無い続報（no_new）は今までどおり見送り
        self.assertEqual(follow.count("if fallback_new("), 2)
        self.assertEqual(follow.count('return "new"'), 2)
        self.assertIn('mark(state, item, skipped=True, reason=f"followup: 新しい事実なし', follow)
        # 門に落ちた追記は記事に書き込まない（書き込みは合格のあとだけ）
        self.assertLess(follow.index('return "new"'), follow.index("path.write_text("))
        # 呼び出し側（公式の候補。話題のレーンで当たった公式の候補も同じ process_web を通る）は new を新しい記事として作る
        self.assertEqual(SRC.count('if outcome not in ("different", "new"):'), 1)
        self.assertIn("prompt += FOLLOWUP_NEW_NOTE.format(", SRC)
        # 作り直した記事は通常の門（gated）を通り、題名がもとの記事とほぼ同じなら出さない
        web = SRC[SRC.index("    def process_web("):SRC.index("    try:\n        # 大きなニュース")]
        self.assertLess(web.index("prompt += FOLLOWUP_NEW_NOTE.format("), web.index("status, record, model_name, info = gated("))
        self.assertIn("if same_headline(record, {\"title\": follow_new[\"title\"]}):", web)
        self.assertIn('record["followupOf"] = follow_new["slug"]', web)


if __name__ == "__main__":
    unittest.main()
