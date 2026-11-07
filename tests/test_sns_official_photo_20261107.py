"""2026-11-07 オーナー承認（台帳 S45）: SNS の投稿の画像に、会社の公式発表の写真を出典つきで使う。ネット接続・投稿なし。

  - 記事の写真が公式発表の写真（文字が主役でない）ならそれ。でなければ本文の公式の写真（photo / kit）。無ければ今までのカード
  - 調査会社・情報会社のサイトの画像（台帳 A37）は使わない
  - AI のイメージに戻るときは「画像はイメージ（AI生成）」のまま。公式の写真に AI の注記は付けない
  - 出典（画像：会社名（公式発表より））がカードに載る
サイト側（lib/sns-photo.ts）は tests/test_sns_official_photo.cjs が同じ例で確かめる。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sns_rules  # noqa: E402
import threads_post as tp  # noqa: E402

IMG = "https://ai-tech-express.jp/img/"
OFFICIAL = {
    "slug": "samsung-buds-x", "thumbnail": f"{IMG}samsung-buds-x-1a2b3c4d.jpg", "sourceType": "web", "channelSlug": "samsung",
    "sourceUrl": "https://news.samsung.com/global/x",
    "imageCredit": {"kind": "official", "org": "Samsung", "sourceUrl": "https://news.samsung.com/global/x", "width": 1200, "height": 675},
}
AI_WITH_BODY = {
    "slug": "nvidia-muse-x", "thumbnail": f"{IMG}nvidia-muse-x-aaaa1111.jpg", "sourceType": "web", "channelSlug": "nvidia",
    "sourceUrl": "https://blogs.nvidia.com/blog/x/",
    "imageCredit": {"kind": "ai", "model": "flux-2-klein-4b", "provider": "Cloudflare Workers AI"},
    "bodyImages": [
        {"src": f"{IMG}nvidia-muse-x-fig1-bbbb2222.jpg", "width": 1200, "height": 628, "kind": "dense", "credit": "NVIDIA", "sourceUrl": "https://blogs.nvidia.com/blog/x/"},
        {"src": f"{IMG}nvidia-muse-x-fig2-cccc3333.jpg", "width": 700, "height": 393, "kind": "photo", "credit": "NVIDIA", "sourceUrl": "https://blogs.nvidia.com/blog/x/"},
    ],
}
AI_ONLY = {
    "slug": "yokohama-tire-recall-x", "thumbnail": f"{IMG}yokohama-tire-recall-x-dddd4444.jpg", "sourceType": "web", "channelSlug": "mlit",
    "imageCredit": {"kind": "ai", "model": "flux-2-klein-4b", "provider": "Cloudflare Workers AI"},
    "bodyImages": [{"src": f"{IMG}yokohama-tire-recall-x-fig1-eeee5555.jpg", "kind": "dense", "credit": "国土交通省"}],
}
RESEARCH = {
    "slug": "tsr-bankruptcy-x", "thumbnail": f"{IMG}tsr-bankruptcy-x-ffff6666.jpg", "sourceType": "web", "channelSlug": "tsr",
    "sourceUrl": "https://www.tsr-net.co.jp/data/detail/1234_1527.html",
    "imageCredit": {"kind": "official", "org": "東京商工リサーチ", "sourceUrl": "https://www.tsr-net.co.jp/data/detail/1234_1527.html"},
    "bodyImages": [{"src": f"{IMG}tsr-bankruptcy-x-fig1-9999aaaa.jpg", "kind": "photo", "credit": "東京商工リサーチ",
                    "sourceUrl": "https://www.tsr-net.co.jp/data/detail/1234_1527.html"}],
}


class OfficialPhotoTest(unittest.TestCase):
    def test_official_photo_is_chosen_with_credit(self):
        photo = sns_rules.sns_photo(OFFICIAL)
        self.assertEqual(photo["from"], "thumbnail")
        self.assertEqual(photo["src"], OFFICIAL["thumbnail"])
        self.assertEqual(sns_rules.card_note(OFFICIAL), "画像：Samsung（公式発表より）")
        self.assertNotIn("AI", sns_rules.card_note(OFFICIAL))

    def test_official_body_photo_replaces_ai_image(self):
        photo = sns_rules.sns_photo(AI_WITH_BODY)
        self.assertEqual(photo["from"], "body")
        self.assertTrue(photo["src"].endswith("fig2-cccc3333.jpg"))  # 図（dense）は飛ばして写真
        note = sns_rules.card_note(AI_WITH_BODY)
        self.assertEqual(note, "画像：NVIDIA（公式発表より）")
        self.assertNotIn("AI生成", note)

    def test_research_firm_image_is_not_chosen(self):
        self.assertIsNone(sns_rules.sns_photo(RESEARCH))
        other = {**OFFICIAL, "channelSlug": "samsung", "imageCredit": {**OFFICIAL["imageCredit"], "sourceUrl": "https://www.tdb.co.jp/report/x/"}}
        self.assertIsNone(sns_rules.sns_photo(other))
        body = {**AI_WITH_BODY, "bodyImages": [{**AI_WITH_BODY["bodyImages"][1], "sourceUrl": "https://www.tsr-net.co.jp/x"}]}
        self.assertIsNone(sns_rules.sns_photo(body))

    def test_text_heavy_official_images_are_not_chosen(self):
        for kind in ("banner", "dense", "logo", "generic"):
            a = {**OFFICIAL, "imageCredit": {**OFFICIAL["imageCredit"], "imageKind": kind}}
            self.assertIsNone(sns_rules.sns_photo(a), kind)
        self.assertIsNone(sns_rules.sns_photo({**OFFICIAL, "heroOk": False}))
        # 告知のバナーでも、本文に公式の写真があればそちら
        a = {**OFFICIAL, "imageCredit": {**OFFICIAL["imageCredit"], "imageKind": "banner"}, "bodyImages": AI_WITH_BODY["bodyImages"]}
        self.assertEqual(sns_rules.sns_photo(a)["from"], "body")

    def test_ai_fallback_keeps_ai_label(self):
        self.assertIsNone(sns_rules.sns_photo(AI_ONLY))
        self.assertEqual(sns_rules.card_note(AI_ONLY), "画像はイメージ（AI生成）")
        self.assertIn("AI生成", tp.card_photo_note(AI_ONLY))

    def test_video_frame_credit_says_video(self):
        a = {**OFFICIAL, "imageCredit": {**OFFICIAL["imageCredit"], "imageKind": "youtube"}}
        self.assertEqual(sns_rules.card_note(a), "画像：Samsung（公式動画より）")

    def test_gate_reads_the_swapped_credit_for_the_card(self):
        # 製品の発表で記事の写真が AI でも、カードには本文の公式の写真が載る → 「製品を AI で描いた」で止めない
        card = [{"type": "image", "url": tp.card_url(AI_WITH_BODY), "width": 1200, "height": 675}]
        orig = sns_rules.product_launch
        sns_rules.product_launch = lambda a: True
        try:
            self.assertEqual(sns_rules.check_media("threads", card, AI_WITH_BODY, "article"), [])
            ai_card = [{"type": "image", "url": tp.card_url(AI_ONLY), "width": 1200, "height": 675}]
            self.assertIn("[ルール2] 発表された製品を AI で描いた画像に「公式画像がないためイメージ（AI生成）」の札がない", sns_rules.check_media("threads", ai_card, AI_ONLY, "article"))
            # 2026-11-07 オーナー（台帳 I2）: 札（launch）があれば、公式の画像が無い発表の AI のイメージを使ってよい
            labeled = {**AI_ONLY, "imageCredit": {**AI_ONLY["imageCredit"], "launch": True}}
            self.assertEqual(sns_rules.check_media("threads", [{"type": "image", "url": tp.card_url(labeled), "width": 1200, "height": 675}], labeled, "article"), [])
            self.assertEqual(sns_rules.card_note(labeled), "公式画像がないためイメージ（AI生成）")
        finally:
            sns_rules.product_launch = orig

    def test_ledger_row(self):
        ledger = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next(line for line in ledger.splitlines() if line.startswith("| S45 "))
        for words in ("2026-11-07", "オーナー承認・SNSの投稿の質を上げる", "lib/sns-photo.ts", "scripts/sns_rules.py", "A37", "AI生成"):
            self.assertIn(words, row)


if __name__ == "__main__":
    unittest.main()
