"""2026-11-07 オーナー決定（台帳 I2 を改める）: 公式の画像が無い新製品・サービスの発表は、AI が製品の種類を描いてよい。
札は「公式画像がないためイメージ（AI生成）」（imageCredit.launch）。ほかの AI のイメージは「画像はイメージ（AI生成）」のまま（台帳 I4）。
見張り（owner_rules_audit の I2）と SNS の門番（sns_rules）は、札の無い発表の AI 画像だけを止める。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import images  # noqa: E402
import owner_rules_audit as audit  # noqa: E402
import sns_rules  # noqa: E402

LAUNCH = {"title": "Googleが新型スマホ「Pixel 11」を発表", "genreSlug": "tech-gadget", "tags": []}


class LaunchLabelTest(unittest.TestCase):
    def test_audit_i2_needs_launch_label(self):
        self.assertTrue(images.product_launch(LAUNCH))
        unlabeled = {**LAUNCH, "imageCredit": {"kind": "ai"}}
        self.assertTrue(any(p.startswith("[I2]") for p in audit.image_record_problems(unlabeled)))
        labeled = {**LAUNCH, "imageCredit": {"kind": "ai", "launch": True}}
        self.assertEqual(audit.image_record_problems(labeled), [])
        # 前の決まりで「製品を描かない」と確かめた画像（noProduct）もそのまま通す
        self.assertEqual(audit.image_record_problems({**LAUNCH, "imageCredit": {"kind": "ai", "noProduct": True}}), [])

    def test_sns_card_note(self):
        with mock.patch.object(sns_rules, "sns_photo", return_value=None):
            self.assertEqual(sns_rules.card_note({"imageCredit": {"kind": "ai", "launch": True}}), "公式画像がないためイメージ（AI生成）")
            self.assertEqual(sns_rules.card_note({"imageCredit": {"kind": "ai"}}), "画像はイメージ（AI生成）")
            self.assertEqual(sns_rules.card_note({"imageCredit": {"kind": "card"}}), "")

    def test_site_labels_share_one_helper(self):
        # 記事ページ・カバー・SNS カード・朝のまとめの札は lib/image-credit.ts の aiCreditText（launch で札を変える）
        for rel in ("lib/card-designs.tsx", "app/cover/[slug]/route.tsx", "lib/digest.ts"):
            self.assertIn("aiCreditText(c)", (ROOT / rel).read_text("utf-8"), rel)
        helper = (ROOT / "lib" / "image-credit.ts").read_text("utf-8")
        self.assertIn('AI_LAUNCH_LABEL = "公式画像がないためイメージ（AI生成）"', helper)
        self.assertIn('AI_LABEL = "画像はイメージ（AI生成）"', helper)
        noir = (ROOT / "lib" / "noir.ts").read_text("utf-8")
        self.assertIn('NOIR_AI_LAUNCH_LABEL = "公式画像がないためイメージ（AI生成）"', noir)
        self.assertIn("credit.launch ? (", (ROOT / "components" / "ImageCredit.tsx").read_text("utf-8"))

    def test_ai_credit_marks_launch(self):
        # 見出し画像の AI のイメージにも launch を付ける（scripts/images.py の process）
        src = (ROOT / "scripts" / "images.py").read_text("utf-8")
        self.assertIn('credit["launch"] = True', src)
        self.assertNotIn("NO_PRODUCT_SCENE", src)


if __name__ == "__main__":
    unittest.main()
