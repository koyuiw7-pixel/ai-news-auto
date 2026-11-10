"""数字の抜けた数える言葉（2026-11-10「セミナーには名が参加しました」。記事は「84名が参加」）を SNS の門番で止める検査。
外部通信なし・何も投稿しない。

  1. 助詞・句読点のすぐ後ろに数字なしの「名・件・万件・万円・億円・兆円・％」が来る文は壊れた日本語（ルール9）
  2. 「人が」「円が」「この件は」「名を変える」「数万円」などのふつうの文は止めない
  3. どの SNS の門番（check_post）でも、読者向けの書き方（check_threads_reader）でも止まる
  4. LLM が書いた3行（compose_hook3）が壊れていたら、記事の文から組み立て直す
  5. まだ出していない予定・下書きに、数字の抜けた文が残っていない

  python3 -m unittest tests.test_sns_bare_counter_20261110
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sns_rules as r  # noqa: E402
import threads_post as tp  # noqa: E402

BAD_SAMPLE = "AWSジャパンが開催したランサムウェア対策に関するセミナーには名が参加しました。"
BAD = [
    BAD_SAMPLE,
    "会場には名以上が集まりました。",
    "参加者は名でした。",
    "同社は件の申請を受け付けました。",
    "相談は件にのぼります。",
    "相談は万件を超えました。",
    "被害は約万円にのぼります。",
    "支給額は最大万円です。",
    "投資額は億円です。",
    "利用者の％が回答しました。",
]
GOOD = [
    "セミナーには84名が参加しました。",
    "3つの軸で、84名が参加しました。",
    "約30万件の相談がありました。",
    "1,200件を超えました。",
    "最大104万円が支給されます。",
    "割合は5.5％です。",
    "数万円の負担です。",
    "何％上がるかは未定です。",
    "人が集まりました。",
    "円が下落しました。",
    "この件は調査中です。",
    "本件については記事にまとめました。",
    "件数が増えています。",
    "条件が変わります。",
    "事件が起きました。",
    "要件を満たす人が対象です。",
    "その名が知られています。",
    "会社は名を変えました。",
    "候補に同氏の名が挙がりました。",
    "名ばかりの制度です。",
    "氏名が公表されました。",
]


def bare(text: str) -> list[str]:
    return [v for v in r.grammar_problems(text) if "数字の抜けた" in v]


class BareCounterTest(unittest.TestCase):
    def test_bad_sentences_are_rejected(self):
        for text in BAD:
            self.assertTrue(bare(text), text)

    def test_normal_sentences_pass(self):
        for text in GOOD:
            self.assertEqual(r.grammar_problems(text), [], text)

    def test_every_platform_gate_rejects_it(self):
        art = {"slug": "acme-tool", "title": "Acme がセミナーを開催", "genreSlug": "ai", "_virtual": True}
        text = f"クラウドの安全対策を担当する方へ。\n\n{BAD_SAMPLE}\n\n確認項目のチェックリストは記事にあります。"
        for platform in ("threads", "x", "bluesky", "facebook"):
            found = r.check_post(platform, text, [], art)
            self.assertTrue(any("数字の抜けた" in v for v in found), platform)

    def test_reader_format_rejects_it_when_composing(self):
        art = {"slug": "acme-tool", "title": "Acme がセミナーを開催", "lede": "セミナーには84名が参加しました。", "_virtual": True}
        main = f"クラウドの安全対策を担当する方へ。\n\n{BAD_SAMPLE}\n防御と復旧の3つの軸が解説されました。\n\n確認項目のチェックリストは記事にあります。"
        reply = ("続き（確認項目の一覧）→ https://ai-tech-express.jp/articles/acme-tool"
                 "?utm_source=threads&utm_medium=social&utm_campaign=acme-tool&utm_content=reader_reply")
        found = r.check_threads_reader("threads", main, reply, art)
        self.assertTrue(any("数字の抜けた" in v for v in found), found)

    def test_hook3_falls_back_to_article_sentences(self):
        art = {
            "slug": "acme-seminar", "title": "Acme がセミナーを開催",
            "lede": "Acmeはセキュリティセミナーを開き、84名が参加しました。対策の3つの軸が示されました。",
            "highlights": ["検知機能の有効化やバックアップの保護を今日から確認できます。"],
        }
        broken = {"line1": "Acmeのセミナーには名が参加し、対策が変わります。", "line2": "クラウドを使う会社の担当者に関係します。",
                  "line3": "確認項目は記事にまとめました。"}
        import llm

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}), patch.object(llm, "generate_json", return_value=(broken, {})):
            text = tp.compose_hook3(art, use_llm=True)
        self.assertNotIn("には名が", text)
        self.assertIn("84名が参加しました。", text)  # 記事の文から組み立て直す
        self.assertEqual(r.grammar_problems(text), [])

    def test_no_pending_post_has_a_bare_counter(self):
        """まだ出していない予定（awaiting_video）と読者向けの下書きに、数字の抜けた文が残っていない"""
        texts: list[tuple[str, str]] = []
        posted = json.loads((ROOT / "state" / "threads_posted.json").read_text("utf-8"))
        for slug, rec in (posted.get("posted") or {}).items():
            if not isinstance(rec, dict) or rec.get("status") != "awaiting_video":
                continue
            for inp in ((rec.get("pending") or {}).get("inputs") or {}).values():
                texts.append((slug, str((inp or {}).get("text") or "")))
                for part in ((((inp or {}).get("metadata") or {}).get("threads") or {}).get("thread")) or []:
                    texts.append((slug, r.strip_links(str(part.get("text") or ""))))
        reader_path = ROOT / "state" / "threads_reader.json"
        if reader_path.exists():
            for slug, rec in (json.loads(reader_path.read_text("utf-8")).get("posts") or {}).items():
                if isinstance(rec, dict) and rec.get("status") == "draft":
                    texts.append((slug, str(rec.get("main") or "")))
        for slug, text in texts:
            self.assertEqual(bare(text), [], f"{slug}: {text[:60]}")


if __name__ == "__main__":
    unittest.main()
