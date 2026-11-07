"""2026-11-07 オーナー指摘: 記事の写真が無い（thumbnail ""）のに表紙用の AI のイメージ（coverImage）がある記事で、
X の画像・リンクカードが暗い／青い文字だけの画像になった（不二家の値上げの記事）。ネット接続・投稿なし。

  - カード（/card）とカバー（/cover）の写真は ①使える記事の写真 ②coverImage（「画像はイメージ（AI生成）」の札） ③文字だけ
  - 門番・下見の注記（sns_rules.card_note）も、実際に載る写真の出典で見る
  - X の画像（thread_image のカバー）にも版を付け、7日のキャッシュに古い画像を残さない
サイト側（lib/sns-photo.ts の shareImageArticle）は tests/test_share_image_cover_20261107.cjs が同じ例で確かめる。
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
FUJIYA = {
    "slug": "fujiya-beverage-price-increase-2027",
    "title": "不二家、飲料を値上げ",
    "thumbnail": "",
    "imageCredit": {"kind": "card", "category": "price"},
    "coverImage": f"{IMG}fujiya-beverage-price-increase-2027-cover-d977c5e1.jpg",
    "coverCredit": {"kind": "ai", "model": "flux-2-klein-4b", "relevant": True},
}


class ShareImageCoverTest(unittest.TestCase):
    def test_empty_thumbnail_uses_cover_with_ai_label(self):
        a = sns_rules.share_image_article(FUJIYA)
        self.assertEqual(a["thumbnail"], FUJIYA["coverImage"])
        self.assertEqual(sns_rules.card_note(FUJIYA), "画像はイメージ（AI生成）")
        launch = {**FUJIYA, "coverCredit": {**FUJIYA["coverCredit"], "launch": True}}
        self.assertEqual(sns_rules.card_note(launch), "公式画像がないためイメージ（AI生成）")

    def test_usable_thumbnail_kept(self):
        official = {**FUJIYA, "thumbnail": f"{IMG}x-bbbb2222.jpg", "imageCredit": {"kind": "official", "org": "不二家"}, "heroOk": True}
        self.assertIs(sns_rules.share_image_article(official), official)
        self.assertEqual(sns_rules.card_note(official), "画像：不二家（公式発表より）")
        self.assertEqual(sns_rules.share_image_article(official, force=True)["thumbnail"], FUJIYA["coverImage"])

    def test_no_cover_or_no_photo_unchanged(self):
        none = {**FUJIYA, "coverImage": "", "coverCredit": None}
        self.assertIs(sns_rules.share_image_article(none), none)
        self.assertEqual(sns_rules.card_note(none), "")
        quake = {**FUJIYA, "noPhoto": True}
        self.assertIs(sns_rules.share_image_article(quake), quake)

    def test_urls_change_with_cover_and_version(self):
        self.assertIn(f"?v={tp.CARD_VERSION}-", tp.card_url(FUJIYA))
        self.assertNotEqual(tp.card_url(FUJIYA), tp.card_url({**FUJIYA, "coverImage": f"{IMG}other.jpg"}))
        cover = tp.thread_image(FUJIYA)
        self.assertIn(f"/cover/{FUJIYA['slug']}?v={tp.CARD_VERSION}-", cover)
        self.assertTrue(tp.is_cover_url(cover, FUJIYA))
        self.assertNotEqual(cover, tp.thread_image({**FUJIYA, "coverImage": f"{IMG}other.jpg"}))


if __name__ == "__main__":
    unittest.main()
