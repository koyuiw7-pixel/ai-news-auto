"""2026-11-06 オーナー承認（台帳 S43・2026-11-07 から）: Facebook だけの上限（1日3本）・枠（7:30・12:30・20:00）・文面・動画の直接投稿。
外部通信なし（投稿しない・Buffer を呼ばない）で、選び方・数え方・文面・門番・Threads の経路から Facebook が外れることを確かめる。"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import facebook_post as fp  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules  # noqa: E402
import threads_post as tp  # noqa: E402

JST = timezone(timedelta(hours=9))
DAY = datetime(2026, 11, 7, tzinfo=JST)


def at(h, m=0):
    return DAY + timedelta(hours=h, minutes=m)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def article(slug, title, made, **extra):
    base = {
        "slug": slug, "title": title, "body": "## 日本で使える？\n" + "あ" * 2100, "genreSlug": "tech-gadget", "tags": [],
        "generatedAt": iso(made), "description": "説明です。",
        "lede": f"{title.split('、')[0]}は、新しいモデルを11月20日に税込3万9800円で発売します。予約は全国の店舗で受け付けます。",
        "workMoney": {"points": ["スマホを買い替える人は、今の端末の下取り額と比べて選べます。"]},
        "_virtual": True,  # テスト用の記事（content/articles に無い）
    }
    base.update(extra)
    return base


def phone(slug="pixel", made=None, **extra):
    return article(slug, "Pixel 11、新色を11月20日に発売", made or at(9), **extra)


def life(slug="denki", made=None, **extra):
    return article(slug, "東京電力、12月の電気料金を値上げ", made or at(9), genreSlug="public",
                   lede="東京電力の12月の電気料金は、標準的な家庭で月8,912円になります。11月より210円高くなります。",
                   workMoney={"points": ["毎月の電気代が上がるので、家計の固定費を見直す人は、料金プランを比べられます。"]}, **extra)


def quake(slug="quake-1", made=None):
    return article(slug, "【地震】千葉県北東部で最大震度5弱、M5.4（気象庁）", made or at(9), genreSlug="public", tags=["地震"],
                   disaster=True, breaking=True,
                   threadsPost="【地震】千葉県北東部で最大震度5弱、M5.4（気象庁）\n震源は千葉県北東部、深さ約50km、M5.4\n最新情報は気象庁の発表を確認してください。")


def rec(kind, when, i="p"):
    return {"id": i, "at": iso(when), "kind": kind, "title": f"前の投稿 {when:%H%M}"}


class PlanTest(unittest.TestCase):
    def test_plan_numbers_are_separate_from_threads_and_x(self):
        self.assertEqual(sns_plan.fb_slots_jst(), [(7, 30), (12, 30), (20, 0)])
        self.assertEqual(sns_plan.fb_daily_cap(), 3)
        self.assertEqual(sns_plan.daily_cap(), 5)  # Threads はそのまま
        self.assertEqual(sns_plan.slots_jst(), [(7, 15), (12, 15), (18, 45), (20, 30)])
        self.assertEqual(sns_plan.x_slots_jst(), [(7, 30), (12, 30), (21, 0)])
        with patch.dict("os.environ", {"FACEBOOK_PER_DAY": "9"}):
            self.assertEqual(sns_plan.fb_daily_cap(), 3)
        self.assertFalse(sns_plan.fb_on(datetime(2026, 11, 6, 23, 59, tzinfo=JST)))
        self.assertTrue(sns_plan.fb_on(at(0)))

    def test_windows(self):
        w = sns_plan.fb_slot_window
        for h, m in [(6, 59), (7, 29), (23, 0)]:
            self.assertIsNone(w(at(h, m)), (h, m))
        self.assertEqual(w(at(7, 30))[0], 0)
        self.assertEqual(w(at(12, 30))[0], 1)
        self.assertEqual(w(at(19, 59))[0], 1)
        self.assertEqual(w(at(20, 0))[0], 2)
        self.assertEqual(w(at(22, 59))[0], 2)


class ChooseTest(unittest.TestCase):
    def test_threads_and_x_posts_do_not_count_against_facebook(self):
        posted = {f"t{i}": {"id": f"x{i}", "status": "scheduled", "dueAt": iso(at(8 + i))} for i in range(5)}
        picked = fp.choose({}, posted, at(12, 35), articles=[phone()])
        self.assertEqual([(a["slug"], k) for a, k in picked], [("pixel", "slot")])
        fs = {f"f{i}": rec("slot", at(8 + i)) for i in range(3)}
        self.assertEqual(sns_plan.count_today(posted, DAY.date()), 5)  # Facebook だけの記録は Threads に数えない
        self.assertEqual(fp.posted_today(fs, at(22)), 3)

    def test_one_per_slot_cap_three_and_window(self):
        self.assertEqual(fp.choose({"o": rec("slot", at(12, 31))}, {}, at(15), articles=[phone()]), [])
        self.assertEqual(len(fp.choose({}, {}, at(18), articles=[phone()])), 1)  # 12:30 の枠に遅れても20時の前まで
        full = {f"f{i}": rec("slot", at(h)) for i, h in enumerate((7, 8, 9))}
        self.assertEqual(fp.choose(full, {}, at(20, 10), articles=[phone(made=at(15))]), [])
        for h, m in [(6, 50), (7, 10), (23, 5)]:
            self.assertEqual(fp.choose({}, {}, at(h, m), articles=[phone(made=at(5))]), [], (h, m))

    def test_midday_slot_prefers_lifestyle(self):
        items = [phone(made=at(10)), life(made=at(9))]
        self.assertEqual([a["slug"] for a, _ in fp.choose({}, {}, at(12, 35), articles=items)], ["denki"])
        self.assertTrue(sns_plan.fb_lifestyle(life()))
        self.assertFalse(sns_plan.fb_lifestyle(quake()))

    def test_breaking_and_alerts_anytime_not_counted(self):
        full = {f"f{i}": rec("slot", at(h)) for i, h in enumerate((7, 8, 9))}
        picked = fp.choose(full, {}, at(23, 40), articles=[quake(made=at(23, 30)), phone("brk", made=at(23, 20), breaking=True)],
                           breaking_only=True)
        self.assertEqual([(a["slug"], k) for a, k in picked], [("quake-1", "alert"), ("brk", "breaking")])
        full.update({"quake-1": rec("alert", at(23, 40)), "brk": rec("breaking", at(23, 40))})
        self.assertEqual(fp.posted_today(full, at(23, 45)), 3)


class TextTest(unittest.TestCase):
    def test_fact_with_number_then_household_effect_link_last(self):
        a = life()
        inp = fp.build_input(a, "chan")
        lines = [x for x in inp["text"].splitlines() if x.strip()]
        self.assertRegex(lines[0], r"\d")
        self.assertIn("家計", lines[1])
        self.assertTrue(lines[-1].startswith("https://ai-tech-express.jp/articles/denki?"))
        self.assertIn("utm_campaign=fbpost", lines[-1])
        self.assertIn("utm_content=card_body", lines[-1])
        self.assertEqual(inp["metadata"]["facebook"]["linkAttachment"]["thumbnail"]["url"], tp.card_url(a))
        self.assertNotIn("？", inp["text"])
        self.assertEqual(fp.problems(a), [])

    def test_approved_video_is_uploaded_directly(self):
        video = {"url": "https://ai-tech-express.jp/videos/denki-short.mp4", "variant": "short"}
        inp = fp.build_input(life(), "chan", video)
        self.assertEqual(inp["assets"], [{"video": {"url": video["url"]}}])
        self.assertNotIn("linkAttachment", inp["metadata"]["facebook"])  # 動画とリンクカードは同時に付けない
        self.assertIn("utm_content=video_body", inp["text"].splitlines()[-1])
        self.assertEqual(fp.problems(life(), video), [])
        with patch.object(fp.bp, "video_of", return_value=video):
            self.assertEqual(fp.video_for(life()), video)
            self.assertEqual(fp.video_for(quake()), {})  # 急ぎの知らせは動画を付けない

    def test_question_only_for_lifestyle_never_for_safety(self):
        link = fp.article_link(life(), False)
        ok_q = f"{fp.fb_text(life())}\nあなたの家では、電気代の見直しをしていますか？\n\n{link}"
        self.assertFalse([v for v in sns_rules.check_fbpost("facebook", ok_q, sns_rules.strip_links(ok_q), life()) if "問いかけ" in v])
        q = f"{fp.fb_text(phone())}\n新しいスマホ、どう選びますか？\n\n{fp.article_link(phone(), False)}"
        self.assertTrue([v for v in sns_rules.check_fbpost("facebook", q, sns_rules.strip_links(q), phone()) if "問いかけ" in v])

    def test_gate_rejects_wrong_shapes(self):
        a = life()
        link = fp.article_link(a, False)
        bad_first = f"電気代が上がります。\n毎月の電気代が上がるので、家計を見直せます。\n\n{link}"
        self.assertTrue(any("数字" in v for v in sns_rules.check_fbpost("facebook", bad_first, sns_rules.strip_links(bad_first), a)))
        no_tail = f"{link}\n{fp.fb_text(a)}"
        self.assertTrue(any("最後の行" in v for v in sns_rules.check_fbpost("facebook", no_tail, sns_rules.strip_links(no_tail), a)))
        self.assertEqual(sns_rules.campaign_kind("facebook", [link]), "fbpost")


class DecoupleTest(unittest.TestCase):
    def test_threads_queue_drops_facebook_from_11_07(self):
        chans = {"twitter": {"id": "tw"}, "facebook": {"id": "fb"}}
        link = "https://ai-tech-express.jp/articles/pixel"
        before = tp.publish_extra_channels("", chans, "本文です。", link, phone(), datetime(2026, 11, 6, 20, 30, tzinfo=JST), build_only=True)
        after = tp.publish_extra_channels("", chans, "本文です。", link, phone(), at(7, 15), build_only=True)
        self.assertIn("facebook", before)
        self.assertEqual(after, {})

    def test_other_paths_cannot_create_facebook_posts(self):
        calls = []
        with patch.object(sns_plan, "fb_on", return_value=True), patch.object(tp, "buffer_graphql", side_effect=lambda *a, **k: calls.append(a)):
            with self.assertRaises(tp.XOwnSlotsOnly):
                tp.create_post("k", {"channelId": "fb", "text": "x"}, service="facebook", article=phone(), source="threads_post.publish_extra_channels")
        self.assertEqual(calls, [])

    def test_publish_queued_and_workflows(self):
        self.assertIn('if service == "facebook" and sns_plan.fb_on(slot):', (ROOT / "scripts" / "sns_video_followup.py").read_text("utf-8"))
        wf = (ROOT / ".github" / "workflows" / "facebook_post.yml").read_text("utf-8")
        for cron in ('"33 22 * * *"', '"33 3 * * *"', '"3 11 * * *"', '"*/10 * * * *"'):
            self.assertIn(cron, wf)
        self.assertIn("group: facebook-post", wf)
        self.assertIn("facebook_post.py --breaking-only", (ROOT / ".github" / "workflows" / "breaking_post.yml").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
