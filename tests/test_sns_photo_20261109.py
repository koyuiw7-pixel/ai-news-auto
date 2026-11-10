"""2026-11-09 オーナー指摘（台帳 S49）: SNS の投稿は、記事に合う本物の画像があるときだけ作る。

- 子ども手当の記事の Threads が、写真の無い青い文字だけのカードで出た
- 防じんマスクのリコールの記事が、年金の記事で保存した厚生労働省のサイト共通のロゴを使い回していた
枠の時刻に画像が無ければ、その枠は画像のある次の予定の投稿に譲る（枠を空けない・遅らせない）。
あわせて、投稿はどの枠でも動画を待たない（muse.wait_hours=0・台帳 S48 の更新）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import images  # noqa: E402
import muse_images  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules as r  # noqa: E402
import sns_video_followup as fu  # noqa: E402
import threads_post as tp  # noqa: E402

IMG = "https://ai-tech-express.jp/img/"
NOW = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)  # 12:00 JST
FLAGS = {"post": True, "ab_until": "2026-11-01", "after_ab": "short"}


def art(slug: str, **extra) -> dict:
    base = {"slug": slug, "title": "第3子の児童手当、月3万円に", "genreSlug": "public", "_virtual": True,
            "thumbnail": f"{IMG}{slug}-0a1b2c3d.jpg", "imageCredit": {"kind": "ai", "model": "flux"}}
    base.update(extra)
    return base


CARD_ONLY = art("child-allowance", thumbnail="", imageCredit={"kind": "card", "category": "policy"})
LOGO = art("respirator-recall", thumbnail=f"{IMG}nenkin-no-hi-2026-mhlw-01b9fc55.jpg",
           imageCredit={"kind": "official", "org": "厚生労働省", "imageKind": "logo"})


class PhotoProblemTest(unittest.TestCase):
    def test_text_card_logo_and_borrowed_are_not_real_photos(self):
        self.assertIn("文字だけ", r.photo_problem(CARD_ONLY))
        self.assertIn("ロゴ", r.photo_problem(LOGO))
        borrowed = art("respirator-recall", thumbnail=f"{IMG}nenkin-no-hi-2026-mhlw-01b9fc55.jpg", imageCredit={"kind": "official", "org": "厚労省"})
        self.assertIn("ほかの記事", r.photo_problem(borrowed))

    def test_empty_hall_filler_is_not_a_real_photo(self):
        hall = art("caa-recall", imageCredit={"kind": "ai", "prompt": "A softly lit, empty exhibition hall with blurred stage lights, no exhibits"})
        self.assertIn("誰もいない会場", r.photo_problem(hall))
        self.assertEqual(muse_images.photo_state(hall), "none")

    def test_own_photo_or_cover_is_fine(self):
        self.assertEqual(r.photo_problem(art("a")), "")
        # 記事の写真がカードでも、Muse の絵（coverImage）があれば、それがカードに敷かれる
        muse = {**CARD_ONLY, "coverImage": f"{IMG}child-allowance-muse-bb96b63d.jpg",
                "coverCredit": {"kind": "ai", "model": "muse"}}
        self.assertEqual(r.photo_problem(muse), "")
        self.assertEqual(r.share_photo(muse)[0], muse["coverImage"])
        # ロゴの記事にも Muse の絵が来れば、ロゴより先に Muse の絵を敷く
        logo_muse = {**LOGO, "coverImage": f"{IMG}respirator-recall-muse-11112222.jpg", "coverCredit": {"kind": "ai", "model": "muse"}}
        self.assertEqual(r.photo_problem(logo_muse), "")
        self.assertEqual(r.share_photo(logo_muse)[0], logo_muse["coverImage"])

    def test_quake_and_urgent_do_not_wait_for_a_photo(self):
        self.assertEqual(r.photo_problem({**CARD_ONLY, "noPhoto": True}), "")
        self.assertEqual(r.photo_problem({**CARD_ONLY, "title": "静岡で震度5強の地震"}), "")


class GateTest(unittest.TestCase):
    def media(self, slug):
        return [{"type": "image", "url": f"https://ai-tech-express.jp/card/{slug}?v=2-abc", "width": 1200, "height": 675}]

    def rule24(self, out):
        return [v for v in out if "ルール24" in v]

    def test_card_without_real_photo_is_blocked(self):
        self.assertTrue(self.rule24(r.check_photo(self.media("child-allowance"), CARD_ONLY, "article")))
        self.assertTrue(self.rule24(r.check_photo(self.media("respirator-recall"), LOGO, "reader")))
        self.assertEqual(r.check_photo(self.media("a"), art("a"), "article"), [])

    def test_pending_draft_digest_and_video_are_not_blocked_here(self):
        m = self.media("child-allowance")
        self.assertEqual(r.check_photo(m, CARD_ONLY, "article", pending_video=True), [])  # 出す時刻にもう一度確かめる
        self.assertEqual(r.check_photo(m, CARD_ONLY, "article", draft=True), [])
        self.assertEqual(r.check_photo(m, CARD_ONLY, "digest"), [])
        video = [{"type": "video", "url": "https://ai-tech-express.jp/video/x.mp4"}]
        self.assertEqual(r.check_photo(m + video, CARD_ONLY, "article"), [])

    def test_check_post_runs_the_photo_rule(self):
        self.assertTrue(any("ルール24" in v for v in r.check_post("threads", "本文", self.media("child-allowance"), CARD_ONLY)))


def queued(slug: str, slot: datetime) -> dict:
    card = f"https://ai-tech-express.jp/card/{slug}"
    inp = {"channelId": "t", "text": "本文", "metadata": {"threads": {"thread": [{"text": "本文", "assets": [{"image": {"url": card}}]}]}}}
    return {"id": "", "via": "buffer", "status": "awaiting_video", "dueAt": slot.isoformat(),
            "pending": {"slot": slot.isoformat(), "inputs": {"threads": inp}}}


class SwapSlotTest(unittest.TestCase):
    """枠の時刻に画像が無い投稿は出さず、その枠を画像のある次の投稿に譲る。譲った投稿は譲られた投稿の枠に回る"""

    def run_queue(self, articles: dict, posted: dict, now=NOW):
        sent = []
        with tempfile.TemporaryDirectory() as tmp:
            for slug, a in articles.items():
                Path(tmp, f"{slug}.json").write_text(json.dumps(a, ensure_ascii=False), "utf-8")
            with patch.object(fu, "ARTICLES", Path(tmp)), patch.object(fu, "probe_buffer", lambda: {}), \
                    patch.object(sns_plan, "video_post", lambda *a, **k: False), \
                    patch.object(sns_plan, "x_on", lambda *a: True), patch.object(sns_plan, "fb_on", lambda *a: True):
                state = {"videos": {}}
                out = fu.publish_queued(state, {"posted": posted}, now, FLAGS,
                                        creator=lambda s, i, a: sent.append((s, i, a["slug"] if a else "")) or f"id-{len(sent)}",
                                        issue=lambda *a: None, remote=lambda s: {})
        return state, sent, out

    def test_next_post_with_photo_takes_the_slot(self):
        first, later = NOW + timedelta(minutes=15), NOW + timedelta(hours=2)
        posted = {"child-allowance": queued("child-allowance", first), "famima": queued("famima", later)}
        state, sent, _ = self.run_queue({"child-allowance": CARD_ONLY, "famima": art("famima")}, posted)
        self.assertEqual([x[2] for x in sent], ["famima"])  # 画像のある投稿が前の枠で出る
        self.assertEqual(sent[0][1]["dueAt"], fu._iso(first))
        q = state["queued"]
        self.assertEqual(q["child-allowance"]["status"], "waiting")
        self.assertTrue(q["child-allowance"]["photoWait"])
        self.assertEqual(posted["child-allowance"]["pending"]["slot"], later.isoformat(timespec="seconds"))  # 後ろの枠に回る
        self.assertEqual(q["famima"]["status"], "created")

    def test_no_text_card_even_without_a_replacement(self):
        posted = {"child-allowance": queued("child-allowance", NOW + timedelta(minutes=10))}
        state, sent, _ = self.run_queue({"child-allowance": CARD_ONLY}, posted)
        self.assertEqual(sent, [])
        self.assertEqual(state["queued"]["child-allowance"]["status"], "waiting")

    def test_post_goes_out_once_the_photo_arrives(self):
        posted = {"child-allowance": queued("child-allowance", NOW - timedelta(minutes=20))}
        muse = {**CARD_ONLY, "coverImage": f"{IMG}child-allowance-muse-bb96b63d.jpg", "coverCredit": {"kind": "ai", "model": "muse"}}
        state, sent, _ = self.run_queue({"child-allowance": muse}, posted)
        self.assertEqual([x[2] for x in sent], ["child-allowance"])
        self.assertEqual(state["queued"]["child-allowance"]["status"], "created")


class NoVideoWaitTest(unittest.TestCase):
    def test_posts_never_wait_for_video(self):
        m = sns_plan.plan()["muse"]
        self.assertEqual((m["wait_hours"], m["max_wait_hours"]), (0, 0))
        self.assertEqual(sns_plan.video_wait_hours(), 0.0)
        with patch.dict("os.environ", {"MUSE_WAIT_HOURS": "4"}):
            self.assertEqual(sns_plan.video_wait_hours(), 0.0)  # 変数でも伸ばせない
        quiet = datetime(2026, 11, 9, 5, 0, tzinfo=timezone.utc)  # 14:00 JST（人の少ない時間帯でも待たない）
        self.assertEqual(fu.video_wait_h({"pending": {"slot": quiet.isoformat()}}), 0.0)
        data = {"items": [{"slug": "a", "status": "queued", "score": 9, "queuedAt": quiet.isoformat()}]}
        self.assertIsNone(sns_plan.muse_wait_until("a", quiet, data=data))


class BufferRefreshTest(unittest.TestCase):
    def test_stale_card_url_is_replaced_with_the_current_one(self):
        a = {**CARD_ONLY, "coverImage": f"{IMG}child-allowance-muse-bb96b63d.jpg", "coverCredit": {"kind": "ai", "model": "muse"}}
        node = {"id": "p1", "service": "threads", "text": "本文",
                "metadata": {"thread": [{"text": "本文", "assets": [{"mimeType": "image/png", "source": "https://ai-tech-express.jp/card/child-allowance?v=2-old"}]},
                                        {"text": "リンク", "assets": []}]}}
        inp = fu.share_assets_refresh(node, a)
        self.assertEqual(inp["metadata"]["threads"]["thread"][0]["assets"][0]["image"]["url"], tp.card_url(a))
        self.assertEqual(inp["metadata"]["threads"]["thread"][1]["text"], "リンク")  # 文面はそのまま
        node["metadata"]["thread"][0]["assets"][0]["source"] = tp.card_url(a)
        self.assertIsNone(fu.share_assets_refresh(node, a))  # 今の版なら何もしない

    def test_scheduled_post_without_photo_is_flagged(self):
        node = {"id": "p1", "service": "threads", "text": "本文 https://ai-tech-express.jp/articles/child-allowance",
                "assets": [{"mimeType": "image/png", "source": "https://ai-tech-express.jp/card/child-allowance"}]}
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "child-allowance.json").write_text(json.dumps(CARD_ONLY, ensure_ascii=False), "utf-8")
            with patch.object(fu, "ARTICLES", Path(tmp)):
                _slug, _video, problems = fu.node_problems(node)
        self.assertTrue(any(p.startswith(fu.PHOTO_RULE) for p in problems))


class ImagePickTest(unittest.TestCase):
    def test_no_card_first_and_no_logo_cover(self):
        self.assertFalse(images.card_first({"category": "policy"}, {"title": "第3子の児童手当、月3万円に"}))
        self.assertFalse(images.cover_worthy({"kind": "logo"}))
        self.assertFalse(images.cover_worthy({"kind": "generic"}))
        self.assertTrue(images.cover_worthy({"kind": "dense"}))

    def test_muse_is_asked_for_logo_and_planned_older_articles(self):
        self.assertEqual(muse_images.photo_state(LOGO), "none")
        old = {**CARD_ONLY, "generatedAt": "2026-11-08T05:28:34+00:00"}
        state: dict = {"items": {}}
        added = muse_images.update_requests(state, {"child-allowance": old}, {"child-allowance"}, cap=30, today="2026-11-09")
        self.assertEqual(added, ["child-allowance"])
        self.assertTrue(state["items"]["child-allowance"]["urgent"])
        # SNS の予定に無い前の日の記事は今までどおり頼まない
        self.assertEqual(muse_images.update_requests({"items": {}}, {"child-allowance": old}, set(), cap=30, today="2026-11-09"), [])

    def test_muse_picture_replaces_a_logo_thumbnail(self):
        from PIL import Image

        path = Path(tempfile.mkdtemp()) / "respirator-recall.jpg"
        pic = Image.linear_gradient("L").resize((1200, 675)).convert("RGB")  # 明るさに幅のある絵
        pic.save(path, quality=95)
        a = json.loads(json.dumps(LOGO))
        with patch.object(images, "store", lambda name, im, dry, keep_aspect=False: (f"{IMG}{name}-12345678.jpg", im.size)):
            status, url = muse_images.apply_one(path, a, {"priority": 1}, dry_run=True)
        self.assertEqual(status, "applied", url)
        self.assertEqual(a["thumbnail"], url)  # ロゴの写真を Muse の絵に替える
        self.assertEqual(a["imageCredit"]["model"], "muse")
        self.assertEqual(r.photo_problem(a), "")

    def test_slightly_dark_muse_picture_passes(self):
        from PIL import Image

        moody = Image.new("RGB", (1200, 675), (26, 26, 26))
        for x in range(0, 1200, 40):
            for y in range(675):
                moody.putpixel((x, y), (200, 40, 40))
        self.assertFalse(any("真っ暗" in p for p in muse_images.image_problems(moody)))


class PhotoPauseResumeTest(unittest.TestCase):
    """Buffer に予約中で画像の無い投稿: 下書きに戻して枠を後ろの画像のある投稿に譲り、画像が届いたら同じ投稿を予約に戻す"""

    def node(self, slug, due):
        return {"id": "p1", "service": "threads", "dueAt": due.isoformat(), "text": "本文",
                "metadata": {"thread": [{"text": "本文", "assets": [{"mimeType": "image/png", "source": f"https://ai-tech-express.jp/card/{slug}?v=2-old"}]}]}}

    def test_pause_gives_slot_and_resume_after_photo(self):
        due, later = NOW + timedelta(minutes=30), NOW + timedelta(hours=3)
        posted = {"posted": {"famima": queued("famima", later)}}
        state: dict = {}
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "child-allowance.json").write_text(json.dumps(CARD_ONLY, ensure_ascii=False), "utf-8")
            Path(tmp, "famima.json").write_text(json.dumps(art("famima"), ensure_ascii=False), "utf-8")
            with patch.object(fu, "ARTICLES", Path(tmp)), patch.object(fu, "POSTED", Path(tmp, "posted.json")):
                row = fu.photo_requeue("k", self.node("child-allowance", due), "child-allowance", state, posted, NOW,
                                       pauser=lambda k, n: {"status": "draft"})
                self.assertEqual(row["action"], "photo_paused")
                self.assertEqual(posted["posted"]["famima"]["pending"]["slot"], due.isoformat(timespec="seconds"))  # 枠を譲った
                self.assertEqual(state["photoPaused"]["p1"]["dueAt"], later.isoformat(timespec="seconds"))
                edits = []
                # 下書きに戻すと Buffer は画像を外している（pause_input）
                drafted = {**self.node("child-allowance", due), "status": "draft"}
                drafted["metadata"] = {"thread": [{"text": "本文", "assets": []}]}
                reader = lambda k, pid, raise_unavailable=False: drafted  # noqa: E731
                # まだ画像が無い → 戻さない
                out = fu.resume_photo_paused(state, NOW, api_key="k", editor=lambda *a: edits.append(a) or {}, reader=reader, issue=lambda *a: None)
                self.assertEqual((out[0]["action"], edits), ("photo_waiting", []))
                muse = {**CARD_ONLY, "coverImage": f"{IMG}child-allowance-muse-bb96b63d.jpg", "coverCredit": {"kind": "ai", "model": "muse"}}
                Path(tmp, "child-allowance.json").write_text(json.dumps(muse, ensure_ascii=False), "utf-8")
                out = fu.resume_photo_paused(state, NOW, api_key="k", editor=lambda *a: edits.append(a) or {}, reader=reader, issue=lambda *a: None)
        self.assertEqual(out[0]["action"], "resumed")
        inp = edits[0][1]
        self.assertEqual((inp["mode"], inp["saveToDraft"], inp["dueAt"]), ("customScheduled", False, fu._iso(later)))
        self.assertTrue(r.buffer_parts("threads", inp)[2])  # カードが付いている（ルール8）
        self.assertEqual(r.check_photo(r.buffer_parts("threads", inp)[2], muse, "article"), [])
        self.assertEqual(inp["metadata"]["threads"]["thread"][0]["assets"][0]["image"]["url"], tp.card_url(muse))
        self.assertEqual(state["photoPaused"], {})


if __name__ == "__main__":
    unittest.main()
