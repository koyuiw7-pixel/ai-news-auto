"""ノワールの表紙はいつも写真（scripts/noir_cover.py・台帳 W36。2026-11-07 オーナー「黒地にしたいわけではない」）。

- 公式の、大きな文字の無い写真（heroOk: true）が第一。無ければ表紙用の AI のイメージ（coverImage / coverCredit）を作る
- 見出し画像（thumbnail / imageCredit）は変えない（SNS カード・一覧の写真は今までどおり）
- 作れなければ、ぼかした公式の画像。何も無いときだけ黒い表紙
"""

from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import images  # noqa: E402
import noir_cover  # noqa: E402


def noir(**extra) -> dict:
    base = {"slug": "x", "title": "題名", "layout": "noir", "thumbnail": "https://ai-tech-express.jp/img/x-1.jpg",
            "imageCredit": {"kind": "official", "imageKind": "banner"}, "heroOk": False}
    base.update(extra)
    return base


class CoverPathTest(unittest.TestCase):
    def test_order(self):
        self.assertEqual(noir_cover.cover_path(noir(heroOk=True, imageCredit={"kind": "official"})), "official")
        self.assertEqual(noir_cover.cover_path(noir(coverImage="/img/x-cover.jpg", coverCredit={"kind": "ai"})), "ai")
        self.assertEqual(noir_cover.cover_path(noir(imageCredit={"kind": "ai"})), "ai-thumbnail")
        self.assertEqual(noir_cover.cover_path(noir()), "blur")
        self.assertEqual(noir_cover.cover_path(noir(thumbnail="")), "black")

    def test_needs_cover(self):
        self.assertTrue(noir_cover.needs_cover(noir()))
        self.assertTrue(noir_cover.needs_cover(noir(thumbnail="", imageCredit=None)))
        self.assertTrue(noir_cover.needs_cover(noir(imageCredit={"kind": "stock"})))
        # 公式の写真を出せる・もう表紙がある・見出し画像が AI のイメージ（そのまま使う）なら作らない
        self.assertFalse(noir_cover.needs_cover(noir(heroOk=True, imageCredit={"kind": "official"})))
        self.assertFalse(noir_cover.needs_cover(noir(coverImage="/img/c.jpg", coverCredit={"kind": "ai"})))
        self.assertFalse(noir_cover.needs_cover(noir(imageCredit={"kind": "ai"})))
        # 今までの見た目の記事・地震の記事・公式の写真の判定がまだの記事・何度も失敗した記事は作らない
        self.assertFalse(noir_cover.needs_cover({**noir(), "layout": None}))
        self.assertFalse(noir_cover.needs_cover(noir(noPhoto=True)))
        no_judge = noir()
        no_judge.pop("heroOk")
        self.assertFalse(noir_cover.needs_cover(no_judge))
        self.assertFalse(noir_cover.needs_cover(noir(coverTries=3)))


class EnsureCoverTest(unittest.TestCase):
    def test_success_keeps_thumbnail(self):
        article = noir()
        made = {"coverImage": "https://ai-tech-express.jp/img/x-cover-ab.jpg", "coverCredit": {"kind": "ai", "model": "flux-1-schnell"}}
        with mock.patch.object(noir_cover, "make_cover", return_value=made):
            self.assertEqual(noir_cover.ensure_cover(article), "ai")
        self.assertEqual(article["thumbnail"], "https://ai-tech-express.jp/img/x-1.jpg")
        self.assertEqual(article["imageCredit"], {"kind": "official", "imageKind": "banner"})
        self.assertEqual(article["coverCredit"]["kind"], "ai")

    def test_failure_falls_back_and_counts(self):
        article = noir()
        with mock.patch.object(noir_cover, "make_cover", side_effect=RuntimeError("boom")):
            self.assertEqual(noir_cover.ensure_cover(article), "blur")
        self.assertEqual(article["coverTries"], 1)
        self.assertNotIn("coverImage", article)

    def test_make_cover_uses_free_workers_ai_and_checks(self):
        article = noir()
        plan = {"scene": "quiet office", "queries": ["office"], "product": ""}
        image = object()
        with mock.patch.object(images, "real_object_article", return_value=False), \
                mock.patch.object(images, "visual_plan", return_value=plan) as vplan, \
                mock.patch.object(images, "generate_ai", return_value=(image, "flux-2-klein-4b")) as gen, \
                mock.patch.object(images, "shows_face", side_effect=[True, False]), \
                mock.patch.object(images, "depicts_product", return_value=False), \
                mock.patch.object(images, "store", return_value=("https://ai-tech-express.jp/img/x-cover-1.jpg", (1200, 630))) as store:
            made = noir_cover.make_cover(article)
        self.assertEqual(gen.call_count, 2)  # 顔・文字が写ったら作り直す
        # 発表の記事でなくても、製品・画面を描かない場面で作る
        self.assertEqual(vplan.call_args.kwargs, {"product": False, "service": True})
        self.assertEqual(store.call_args.args[0], "x-cover")
        self.assertEqual(made["coverImage"], "https://ai-tech-express.jp/img/x-cover-1.jpg")
        self.assertEqual(made["coverCredit"]["kind"], "ai")
        self.assertEqual(made["coverCredit"]["provider"], "Cloudflare Workers AI")
        self.assertTrue(made["coverCredit"]["noProduct"])
        self.assertEqual(images.AI_MODELS, ["@cf/black-forest-labs/flux-2-klein-4b", "@cf/black-forest-labs/flux-1-schnell"])

    def test_make_cover_redraws_without_product(self):
        # 製品・機械・画面が写ったら、製品の無い場面で作り直す（発表の記事でなくても）
        with mock.patch.object(images, "real_object_article", return_value=False), \
                mock.patch.object(images, "visual_plan", return_value={"scene": "laptop dashboard", "product": "computer, phone or app screen"}), \
                mock.patch.object(images, "generate_ai", return_value=(object(), "m")) as gen, \
                mock.patch.object(images, "shows_face", return_value=False), \
                mock.patch.object(images, "depicts_product", side_effect=[True, False]), \
                mock.patch.object(images, "store", return_value=("/img/c.jpg", (1200, 630))):
            made = noir_cover.make_cover(noir())
        self.assertEqual(gen.call_args_list[1].args[0]["scene"], images.NO_PRODUCT_SCENE)
        self.assertEqual(made["coverCredit"]["prompt"], images.NO_PRODUCT_SCENE)

    def test_make_cover_none_when_generation_fails(self):
        with mock.patch.object(images, "real_object_article", return_value=False), \
                mock.patch.object(images, "visual_plan", return_value={"scene": "s"}), \
                mock.patch.object(images, "generate_ai", return_value=None):
            self.assertIsNone(noir_cover.make_cover(noir()))


class ImagesHookTest(unittest.TestCase):
    def test_images_run_makes_covers_for_recent_noir(self):
        # scripts/images.py の写真選びのあとに、新しいノワールの記事の表紙を作る（1回に NOIR_COVER_MAX 本まで）
        rows = [(Path(f"/tmp/{i}.json"), noir(slug=f"s{i}")) for i in range(4)] + [(Path("/tmp/old.json"), {"slug": "old", "thumbnail": "t"})]
        args = SimpleNamespace(budget=0, fast=True)
        tally: Counter = Counter()
        with mock.patch.object(noir_cover, "ensure_cover", return_value="ai") as ensure, mock.patch.object(images, "save"):
            images.noir_covers(rows, args, 0.0, tally)
        self.assertEqual(ensure.call_count, images.NOIR_COVER_MAX)
        self.assertEqual(tally["cover-ai"], images.NOIR_COVER_MAX)


if __name__ == "__main__":
    unittest.main()
