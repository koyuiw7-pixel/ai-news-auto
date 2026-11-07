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
        # 見出し画像の AI のイメージは、確かめて coverImage に入るまでは表紙にそのまま出さない
        self.assertEqual(noir_cover.cover_path(noir(imageCredit={"kind": "ai"})), "blur")
        self.assertEqual(noir_cover.cover_path(noir()), "blur")
        self.assertEqual(noir_cover.cover_path(noir(thumbnail="")), "black")

    def test_needs_cover(self):
        self.assertTrue(noir_cover.needs_cover(noir()))
        self.assertTrue(noir_cover.needs_cover(noir(thumbnail="", imageCredit=None)))
        self.assertTrue(noir_cover.needs_cover(noir(imageCredit={"kind": "stock"})))
        self.assertTrue(noir_cover.needs_cover(noir(imageCredit={"kind": "ai"})))
        self.assertFalse(noir_cover.needs_cover(noir(heroOk=True, imageCredit={"kind": "official"})))
        self.assertFalse(noir_cover.needs_cover(noir(coverImage="/img/c.jpg", coverCredit={"kind": "ai"})))
        self.assertFalse(noir_cover.needs_cover({**noir(), "layout": None}))
        self.assertFalse(noir_cover.needs_cover(noir(noPhoto=True)))
        no_judge = noir()
        no_judge.pop("heroOk")
        self.assertFalse(noir_cover.needs_cover(no_judge))
        self.assertFalse(noir_cover.needs_cover(noir(coverTries=3)))


SCENES = ("Receipts and coins on a shop counter", ["hands counting coins at a register", "a tax office counter", "receipts and coins"])


def patches(face=(False,) * 3, relevant=(True,) * 3, generated=True, launch=False):
    return [
        mock.patch.object(images, "real_object_article", return_value=False),
        mock.patch.object(images, "announcement_article", return_value=launch),
        mock.patch.object(noir_cover, "cover_scenes", return_value=SCENES),
        mock.patch.object(images, "generate_ai", return_value=(object(), "flux-2-klein-4b") if generated else None),
        mock.patch.object(images, "shows_face", side_effect=list(face)),
        mock.patch.object(noir_cover, "relevant", side_effect=list(relevant)),
        mock.patch.object(images, "store", return_value=("https://ai-tech-express.jp/img/x-cover-1.jpg", (1200, 630))),
    ]


class MakeCoverTest(unittest.TestCase):
    def run_make(self, **kw):
        ps = patches(**kw)
        mocks = [p.start() for p in ps]
        try:
            return noir_cover.make_cover(noir()), mocks
        finally:
            for p in ps:
                p.stop()

    def test_first_scene_ok(self):
        made, mocks = self.run_make()
        self.assertEqual(mocks[3].call_count, 1)
        self.assertEqual(mocks[6].call_args.args[0], "x-cover")
        self.assertEqual(made["coverCredit"]["kind"], "ai")
        self.assertEqual(made["coverCredit"]["provider"], "Cloudflare Workers AI")
        self.assertTrue(made["coverCredit"]["relevant"])
        self.assertEqual(made["coverCredit"]["prompt"], SCENES[1][0])

    def test_irrelevant_image_redrawn_with_next_scene(self):
        # 見出しとのつながりが見えなければ、別の切り口の場面で作り直す
        made, mocks = self.run_make(relevant=(False, True))
        self.assertEqual(mocks[3].call_count, 2)
        self.assertEqual(mocks[3].call_args_list[1].args[0]["scene"], SCENES[1][1])
        self.assertEqual(made["coverCredit"]["prompt"], SCENES[1][1])

    def test_gives_up_after_two_redraws(self):
        # 3枚とも見出しとつながらなければ作らない（話題と関係の無い場面を出すより、ぼかした見出し画像）
        made, mocks = self.run_make(relevant=(False, False, False))
        self.assertIsNone(made)
        self.assertEqual(mocks[3].call_count, noir_cover.MAX_DRAWS)
        self.assertEqual(mocks[6].call_count, 0)

    def test_face_redrawn(self):
        made, mocks = self.run_make(face=(True, True, False))
        self.assertEqual(mocks[3].call_count, 3)
        self.assertEqual(made["coverCredit"]["prompt"], SCENES[1][2])

    def test_never_generic_venue_scene(self):
        # 2026-11-07 オーナー「何もイメージできない」: 製品の無い会場の場面（NO_PRODUCT_SCENE）には逃げない
        made, mocks = self.run_make(relevant=(False, False, False))
        self.assertIsNone(made)
        for call in mocks[3].call_args_list:
            # 製品を描かない決まり（productLaunch / serviceLaunch）は足さない（2026-11-07 オーナー: 発表の製品は描いてよい）
            self.assertEqual(set(call.args[0]), {"scene"})
        self.assertNotIn("NO_PRODUCT_SCENE", Path(noir_cover.__file__).read_text("utf-8"))
        self.assertFalse(hasattr(images, "NO_PRODUCT_SCENE"))

    def test_launch_marked_for_label(self):
        # 新製品・サービスの発表は coverCredit.launch（サイトの札は「公式画像がないためイメージ（AI生成）」）
        made, _ = self.run_make(launch=True)
        self.assertTrue(made["coverCredit"]["launch"])
        made, _ = self.run_make()
        self.assertNotIn("launch", made["coverCredit"])

    def test_none_when_generation_fails(self):
        made, _ = self.run_make(generated=False)
        self.assertIsNone(made)


class EnsureCoverTest(unittest.TestCase):
    def test_success_keeps_thumbnail(self):
        article = noir()
        made = {"coverImage": "https://ai-tech-express.jp/img/x-cover-ab.jpg", "coverCredit": {"kind": "ai", "model": "flux-1-schnell"}}
        with mock.patch.object(noir_cover, "reuse_thumbnail", return_value=None), mock.patch.object(noir_cover, "make_cover", return_value=made):
            self.assertEqual(noir_cover.ensure_cover(article), "ai")
        self.assertEqual(article["thumbnail"], "https://ai-tech-express.jp/img/x-1.jpg")
        self.assertEqual(article["imageCredit"], {"kind": "official", "imageKind": "banner"})

    def test_failure_falls_back_to_blur_and_counts(self):
        article = noir()
        with mock.patch.object(noir_cover, "reuse_thumbnail", return_value=None), mock.patch.object(noir_cover, "make_cover", side_effect=RuntimeError("boom")):
            self.assertEqual(noir_cover.ensure_cover(article), "blur")
        self.assertEqual(article["coverTries"], 1)
        self.assertNotIn("coverImage", article)

    def test_reuse_ai_thumbnail_only_when_relevant(self):
        article = noir(imageCredit={"kind": "ai", "model": "m"})
        with mock.patch.object(images, "http_get", return_value=(b"", "", "")), mock.patch.object(images, "open_image", return_value=object()), \
                mock.patch.object(images, "shows_face", return_value=False), \
                mock.patch.object(noir_cover, "relevant", return_value=True):
            self.assertEqual(noir_cover.reuse_thumbnail(article)["coverImage"], article["thumbnail"])
        with mock.patch.object(images, "http_get", return_value=(b"", "", "")), mock.patch.object(images, "open_image", return_value=object()), \
                mock.patch.object(images, "shows_face", return_value=False), \
                mock.patch.object(noir_cover, "relevant", return_value=False):
            self.assertIsNone(noir_cover.reuse_thumbnail(article))

    def test_relevance_prompt_uses_headline(self):
        with mock.patch.object(images, "cf_vision", side_effect=["Yes", "No"]) as vision:
            self.assertTrue(noir_cover.relevant(object(), {"title": "防水工事業の倒産"}, "waterproofing bankruptcies"))
        self.assertIn("防水工事業の倒産", vision.call_args_list[0].args[1])
        # 小さい写真（一覧・SNS の大きさ）で判定する（2026-11-07 オーナー・Muse）
        self.assertEqual(vision.call_args_list[0].kwargs["size"], images.CHECK_SIZE)
        # つながりは見えても、作り物のブランド・大げさな被害は誤解を招くので使わない
        with mock.patch.object(images, "cf_vision", side_effect=["Yes", "Yes"]):
            self.assertFalse(noir_cover.relevant(object(), {"title": "t"}, ""))
        with mock.patch.object(images, "cf_vision", return_value=None):
            self.assertFalse(noir_cover.relevant(object(), {"title": "t"}, ""))


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
