"""Muse の表紙の写真（2026-11-08 オーナー承認・台帳 I8）"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import muse_images as mi  # noqa: E402
import muse_images_push as mp  # noqa: E402

TODAY = mi.jst_day()
NOW = datetime.now(timezone.utc).isoformat()


def art(slug: str, **kw) -> dict:
    base = {"slug": slug, "title": "会社員の平均給与は487万円", "generatedAt": NOW, "layout": "noir", "thumbnail": "",
            "imageCredit": {"kind": "card"}, "highlights": ["**487万円**で過去最高", "男女の差", "業種の差"],
            "workMoney": {"points": ["自分の年収と比べる目安"]}}
    base.update(kw)
    return base


def photo(w=1200, h=675, color=(120, 160, 200)):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(image)
    for i in range(0, w, 60):
        draw.rectangle([i, h // 3, i + 30, h], fill=(40 + i % 200, 90, 60))
    return image


class PhotoStateTest(unittest.TestCase):
    def test_states(self):
        self.assertEqual(mi.photo_state(art("a")), "none")
        official = art("a", thumbnail="https://x/a.jpg", imageCredit={"kind": "official"}, heroOk=True)
        self.assertEqual(mi.photo_state(official), "official")
        wai = art("a", coverImage="https://ai-tech-express.jp/img/a-cover.jpg", coverCredit={"kind": "ai", "model": "flux"})
        self.assertEqual(mi.photo_state(wai), "ai")
        muse = art("a", coverImage="https://ai-tech-express.jp/img/a-muse.jpg", coverCredit={"kind": "ai", "model": "muse"})
        self.assertEqual(mi.photo_state(muse), "muse")


class RequestsTest(unittest.TestCase):
    def test_priority_order_and_cap(self):
        articles = {
            "tech": art("tech", title="SageMakerでGPUを分割", channelSlug="aws-ml-blog"),
            "money": art("money", title="電気料金を12月から値上げ"),
            "sns": art("sns", title="新しいおにぎりの発売"),
            "old": art("old", generatedAt="2026-01-01T00:00:00+00:00"),
            "has-official": art("has-official", thumbnail="https://x/a.jpg", imageCredit={"kind": "official"}, heroOk=True),
            "quake": art("quake", noPhoto=True),
        }
        state = {"items": {}}
        added = mi.update_requests(state, articles, {"sns"}, cap=2, today=TODAY)
        self.assertEqual(added, ["sns", "money"])  # SNS → お金 の順。上限2枚
        self.assertTrue(state["items"]["sns"]["urgent"])
        self.assertEqual(state["items"]["money"]["url"], "https://ai-tech-express.jp/articles/money")
        self.assertEqual(state["items"]["money"]["points"][0], "487万円で過去最高")
        self.assertIn("年収", state["items"]["money"]["angle"])
        # 上限に達したら次の回も足さない
        self.assertEqual(mi.update_requests(state, articles, {"sns"}, cap=2, today=TODAY), [])

    def test_workers_ai_cover_only_replaced_for_high_priority(self):
        cover = {"coverImage": "https://ai-tech-express.jp/img/x-cover.jpg", "coverCredit": {"kind": "ai", "model": "flux"}}
        articles = {"low": art("low", title="新しいおにぎりの発売", **cover), "high": art("high", title="給付金の申請は12月まで", **cover)}
        state = {"items": {}}
        self.assertEqual(mi.update_requests(state, articles, set(), cap=20, today=TODAY), ["high"])

    def test_request_withdrawn_when_official_photo_arrives(self):
        articles = {"a": art("a", title="電気料金の値上げ")}
        state = {"items": {}}
        mi.update_requests(state, articles, set(), cap=20, today=TODAY)
        articles["a"].update(thumbnail="https://x/a.jpg", imageCredit={"kind": "official"}, heroOk=True)
        mi.update_requests(state, articles, set(), cap=20, today=TODAY)
        self.assertEqual(state["items"]["a"]["status"], "skipped")
        self.assertIn("公式の写真", state["items"]["a"]["reason"])

    def test_requests_md_marks_urgent_and_lists_points(self):
        state = {"dailyCap": 20, "items": {}}
        mi.update_requests(state, {"sns": art("sns", title="新しいおにぎり"), "m": art("m", title="電気料金の値上げ")}, {"sns"}, 20, TODAY)
        text = mp.requests_md(state)
        self.assertIn("### 急 sns", text)
        self.assertLess(text.index("### 急 sns"), text.index("### m"))
        self.assertIn("1200×675", text)
        self.assertIn("done-", text)
        self.assertIn("ロゴは描かない", text)


class ImageCheckTest(unittest.TestCase):
    def test_good_photo_passes(self):
        self.assertEqual(mi.image_problems(photo()), [])

    def test_dark_flat_small_wrong_ratio_fail(self):
        self.assertTrue(any("真っ暗" in p for p in mi.image_problems(photo(color=(3, 3, 3)).point(lambda v: v // 12))))
        from PIL import Image

        self.assertTrue(any("一色" in p for p in mi.image_problems(Image.new("RGB", (1200, 675), (128, 128, 128)))))
        self.assertTrue(any("小さすぎ" in p for p in mi.image_problems(photo(600, 338))))
        self.assertTrue(any("縦横" in p for p in mi.image_problems(photo(1000, 1000))))

    def test_fit_size(self):
        self.assertEqual(mi.fit_size(photo(1600, 900)).size, (1200, 675))


class ApplyTest(unittest.TestCase):
    def run_apply(self, article: dict, row: dict | None, image=None):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / f"{article['slug']}.jpg"
            buf = io.BytesIO()
            (image or photo()).save(buf, "JPEG", quality=90)
            path.write_bytes(buf.getvalue())
            with patch("images.store", return_value=("https://ai-tech-express.jp/img/x-muse-abc.jpg", (1200, 630))) as store:
                result = mi.apply_one(path, article, row)
            return result, store

    def test_apply_sets_cover_with_ai_label_credit(self):
        article = art("a")
        (status, detail), store = self.run_apply(article, {"priority": 2})
        self.assertEqual(status, "applied")
        self.assertEqual(article["coverImage"], "https://ai-tech-express.jp/img/x-muse-abc.jpg")
        self.assertEqual(article["coverCredit"]["kind"], "ai")  # 「画像はイメージ（AI生成）」の札・/cover・/card が拾う
        self.assertEqual(article["coverCredit"]["model"], "muse")
        self.assertTrue(store.call_args[0][0].endswith("-muse"))

    def test_low_priority_keeps_workers_ai_cover(self):
        article = art("a", coverImage="https://ai-tech-express.jp/img/a-cover.jpg", coverCredit={"kind": "ai", "model": "flux"})
        (status, _), store = self.run_apply(article, {"priority": 3})
        self.assertEqual(status, "skipped")
        self.assertEqual(article["coverCredit"]["model"], "flux")
        store.assert_not_called()

    def test_high_priority_replaces_workers_ai_cover(self):
        article = art("a", coverImage="https://ai-tech-express.jp/img/a-cover.jpg", coverCredit={"kind": "ai", "model": "flux"})
        (status, _), _ = self.run_apply(article, {"priority": 1})
        self.assertEqual(status, "applied")
        self.assertEqual(article["coverCredit"]["model"], "muse")

    def test_official_photo_wins(self):
        article = art("a", thumbnail="https://x/a.jpg", imageCredit={"kind": "official"}, heroOk=True)
        (status, _), store = self.run_apply(article, {"priority": 1})
        self.assertEqual(status, "skipped")
        store.assert_not_called()

    def test_muse_redraw_replaces_own_image(self):
        article = art("a", coverImage="https://ai-tech-express.jp/img/a-muse-old.jpg", coverCredit={"kind": "ai", "model": "muse"})
        (status, _), _ = self.run_apply(article, {"priority": 3})
        self.assertEqual(status, "applied")
        self.assertEqual(article["coverImage"], "https://ai-tech-express.jp/img/x-muse-abc.jpg")

    def test_dark_image_rejected(self):
        from PIL import Image

        (status, detail), store = self.run_apply(art("a"), {"priority": 1}, Image.new("RGB", (1200, 675), (5, 5, 5)))
        self.assertEqual(status, "skipped")
        store.assert_not_called()


class MacSideTest(unittest.TestCase):
    def test_muse_skip_notes_parsed(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "done-20261108.md").write_text("- nta-average-salary-2025-record.jpg\n- docomo-breach: 実在の会社の画面になるので描けません\n", "utf-8")
            notes = mp.muse_skips(Path(d), {"nta-average-salary-2025-record", "docomo-breach"})
        self.assertEqual(list(notes), ["docomo-breach"])
        self.assertIn("描けません", notes["docomo-breach"])

    def test_ledger_section_lists_applied(self):
        state = {"dailyCap": 20, "items": {"a": {"day": TODAY, "status": "applied", "image": "https://ai-tech-express.jp/img/a-muse.jpg", "at": NOW}}}
        text = "\n".join(mp.ledger_section(state))
        self.assertIn("Muse さんの画像", text)
        self.assertIn("記事に付けました", text)

    def test_noir_recheck_keeps_muse_cover(self):
        import noir_cover

        article = art("a", coverImage="https://ai-tech-express.jp/img/a-muse.jpg", coverCredit={"kind": "ai", "model": "muse"})
        self.assertFalse(noir_cover.recheck(article))
        self.assertIn("coverImage", article)

    def test_workflow_runs_step_and_commits_state(self):
        text = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("python scripts/muse_images.py", text)
        self.assertIn("vars.MUSE_IMAGE_DAILY || '20'", text)
        self.assertIn("git add state/muse_images.json", text)
        self.assertIn('"content/muse_images"', (ROOT / "scripts" / "muse_articles_push.py").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
