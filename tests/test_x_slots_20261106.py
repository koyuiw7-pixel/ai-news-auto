"""2026-11-06 オーナー承認（台帳 S42・2026-11-07 から）: X だけの上限（1日3本）・枠（7:30・12:30・21:00）・話題・文面。
外部通信なし（投稿しない・Buffer を呼ばない）で、選び方・数え方・文面・門番・Threads の経路から X が外れることを確かめる。"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import morning_digest  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules  # noqa: E402
import threads_post as tp  # noqa: E402
import x_post as xp  # noqa: E402

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
        "lede": f"{title.split('、')[0]}は、新しいモデルを11月20日に全国の店舗で発売します。価格は税込3万9800円で、予約は今日から受け付けます。",
        "_virtual": True,  # テスト用の記事（content/articles に無い）
        # 記事に合う画像（2026-11-09 台帳 S49: 画像の無い記事は SNS に出さない）
        "thumbnail": f"https://ai-tech-express.jp/img/{slug}-0a1b2c3d.jpg", "imageCredit": {"kind": "stock"},
    }
    base.update(extra)
    return base


def phone(slug="pixel", made=None, **extra):
    return article(slug, "Pixel 11、新色を11月20日に発売　税込3万9800円", made or at(9), **extra)


def ent(slug="aws", made=None):
    return article(slug, "AWSの新しいデータベース機能", made or at(9), tags=["AWS"])


def earnings(slug="toyota-q2", made=None):
    return article(slug, "トヨタの4〜9月期、営業利益2兆1,911億円で9.2%増", made or at(9), tags=["トヨタ", "決算"],
                   lede="トヨタの4〜9月期の営業利益は2兆1,911億円でした。前年より9.2%増えています。")


def switch_earnings(slug="nintendo-q2", made=None):
    return article(slug, "任天堂の中間決算、営業利益は49.1%増", made or at(9), tags=["任天堂", "決算", "Nintendo Switch 2"],
                   lede="任天堂の4〜9月の営業利益は2,165億円でした。",
                   highlights=["Switch 2は本体649万台、ソフト2,449万本。前年より大きく伸びました"])


def quake(slug="quake-1", made=None):
    return article(slug, "【地震】千葉県北東部で最大震度5弱、M5.4（気象庁）", made or at(9), genreSlug="public", tags=["地震", "防災"],
                   disaster=True, breaking=True,
                   threadsPost="【地震】千葉県北東部で最大震度5弱、M5.4（気象庁）\n震源は千葉県北東部、深さ約50km、M5.4\n最新情報は気象庁の発表を確認してください。")


def outage(slug="au-down", made=None):
    return article(slug, "au、全国で通信障害　一部でつながりにくい状態", made or at(9),
                   lede="auの携帯電話が、全国の一部でつながりにくくなっています。KDDIが復旧を進めています。")


def rec(kind, when, slug_id="p"):
    return {"id": slug_id, "at": iso(when), "kind": kind, "title": f"前の投稿 {when:%H%M}"}


class PlanTest(unittest.TestCase):
    def test_plan_numbers_are_separate_from_threads(self):
        self.assertEqual(sns_plan.x_slots_jst(), [(7, 30), (12, 30), (21, 0)])
        self.assertEqual(sns_plan.x_daily_cap(), 3)
        # Threads の上限・枠はそのまま（台帳 S27・S39）
        self.assertEqual(sns_plan.daily_cap(), 5)
        self.assertEqual(sns_plan.slots_jst(), [(7, 15), (12, 15), (18, 45), (20, 30)])
        with patch.dict("os.environ", {"X_PER_DAY": "9"}):
            self.assertEqual(sns_plan.x_daily_cap(), 3)  # 変数で増やせない
        with patch.dict("os.environ", {"X_PER_DAY": "1"}):
            self.assertEqual(sns_plan.x_daily_cap(), 1)

    def test_starts_on_11_07(self):
        self.assertFalse(sns_plan.x_on(datetime(2026, 11, 6, 23, 59, tzinfo=JST)))
        self.assertTrue(sns_plan.x_on(datetime(2026, 11, 7, 0, 0, tzinfo=JST)))

    def test_windows(self):
        w = sns_plan.x_slot_window
        for h, m in [(0, 15), (6, 59), (7, 0), (7, 29), (23, 0), (23, 30)]:
            self.assertIsNone(w(at(h, m)), (h, m))
        self.assertEqual(w(at(7, 30))[0], 0)
        self.assertEqual(w(at(12, 29))[0], 0)
        self.assertEqual(w(at(12, 30))[0], 1)
        self.assertEqual(w(at(20, 59))[0], 1)
        self.assertEqual(w(at(21, 0))[0], 2)
        self.assertEqual(w(at(22, 59))[0], 2)


class ChooseTest(unittest.TestCase):
    def test_threads_posts_do_not_count_against_x(self):
        # Threads に今日5本（上限いっぱい）出ていても、X は別に数える
        posted = {f"t{i}": {"id": f"x{i}", "status": "scheduled", "dueAt": iso(at(8 + i))} for i in range(5)}
        self.assertEqual(sns_plan.count_today(posted, DAY.date()), 5)
        self.assertEqual(xp.posted_today({}, at(12, 35)), 0)
        picked = xp.choose({}, posted, at(12, 35), articles=[phone()])
        self.assertEqual([(a["slug"], kind) for a, kind in picked], [("pixel", "slot")])

    def test_x_posts_do_not_count_against_threads(self):
        posted = {"t": {"id": "x", "status": "scheduled", "dueAt": iso(at(8))}}
        xs = {f"x{i}": rec("slot", at(8 + i)) for i in range(3)}
        self.assertEqual(sns_plan.count_today(posted, DAY.date()), 1)  # X だけの記録（x_posted）は Threads に数えない
        self.assertEqual(xp.posted_today(xs, at(22)), 3)

    def test_one_post_per_slot_late_within_window(self):
        xs = {"old": rec("slot", at(12, 32))}
        self.assertEqual(xp.choose(xs, {}, at(14), articles=[phone()]), [])  # 12:30 の枠はもう出した
        self.assertEqual(len(xp.choose(xs, {}, at(21, 40), articles=[phone(made=at(15))])), 1)  # 夜の枠に遅れても23時までは出す
        # 12:30 の枠を取りこぼしたら、21時の前までは遅れて出してよい
        self.assertEqual(len(xp.choose({}, {}, at(18, 30), articles=[phone()])), 1)

    def test_never_more_than_three_and_never_outside_7_to_23(self):
        xs = {f"x{i}": rec("slot", at(h)) for i, h in enumerate((7, 8, 9))}
        self.assertEqual(xp.choose(xs, {}, at(21, 10), articles=[phone(made=at(15))]), [])
        for h, m in [(6, 50), (7, 10), (23, 5)]:
            self.assertEqual(xp.choose({}, {}, at(h, m), articles=[phone(made=at(5))]), [], (h, m))

    def test_breaking_and_alerts_go_anytime_and_are_not_counted(self):
        xs = {f"x{i}": rec("slot", at(h)) for i, h in enumerate((7, 8, 9))}  # 通常の枠は使い切った
        now = at(23, 40)  # 枠の外
        picked = xp.choose(xs, {}, now, articles=[quake(made=at(23, 30)), phone("brk", made=at(23, 20), breaking=True)], breaking_only=True)
        self.assertEqual([(a["slug"], k) for a, k in picked], [("quake-1", "alert"), ("brk", "breaking")])
        xs.update({"quake-1": rec("alert", now), "brk": rec("breaking", now)})
        self.assertEqual(xp.posted_today(xs, now), 3)  # 速報・災害の知らせは数えない

    def test_quiet_hours_only_alerts(self):
        now = datetime(2026, 11, 8, 2, 30, tzinfo=JST)
        picked = xp.choose({}, {}, now, articles=[quake(made=now - timedelta(minutes=5)), phone("brk", made=now - timedelta(minutes=5), breaking=True)],
                           breaking_only=True)
        self.assertEqual([a["slug"] for a, _ in picked], ["quake-1"])

    def test_normal_run_waits_before_catching_up_breaking(self):
        brk = phone("brk", made=at(10), breaking=True)
        self.assertEqual(xp.choose({}, {}, at(10, 10), articles=[brk]), [])  # 枠の外・速報のワークフローに任せる
        self.assertEqual([k for _, k in xp.choose({}, {}, at(10, 40), articles=[brk])], ["breaking"])

    def test_topic_order(self):
        items = [phone("pix", made=at(9)), outage(made=at(8)), article("kddi", "KDDI、新しい拠点を大阪に開設", at(10),
                                                                       lede="KDDIは大阪に新しい拠点を開きました。300人が働きます。")]
        self.assertEqual([a["slug"] for a in xp.candidates({}, {}, at(12, 35), at(0), items)], ["au-down", "pix", "kddi"])
        self.assertEqual(sns_plan.x_topic(quake())[0], "alert")
        self.assertEqual(sns_plan.x_topic(outage())[0], "outage")
        self.assertEqual(sns_plan.x_topic(phone())[0], "consumer")

    def test_earnings_only_never_goes_to_x(self):
        self.assertTrue(sns_plan.x_earnings_only(earnings()))
        self.assertEqual(xp.candidates({}, {}, at(12, 35), at(0), [earnings()]), [])
        self.assertEqual(xp.choose({}, {}, at(9, 30), articles=[earnings("brk-e", made=at(9, 20)) | {"breaking": True}], breaking_only=True), [])
        # 製品の話の決算（Switch 2 の販売台数）は、製品を1行目にして出してよい
        self.assertFalse(sns_plan.x_earnings_only(switch_earnings()))
        self.assertTrue(xp.x_text(switch_earnings()).startswith("Switch 2"))

    def test_keeps_foreign_enterprise_exclusion_and_skips_posted(self):
        self.assertEqual(xp.candidates({}, {}, at(12, 35), at(0), [ent()]), [])
        posted_before = {"pixel": {"id": "t", "channels": {"twitter": "old"}}}
        self.assertEqual(xp.candidates({}, posted_before, at(12, 35), at(0), [phone()]), [])
        self.assertEqual(xp.candidates({"pixel": {"failed": "rule"}}, {}, at(12, 35), at(0), [phone()]), [])


class TextTest(unittest.TestCase):
    def test_keyword_first_facts_no_question_within_140(self):
        text = xp.x_text(phone())
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("Pixel 11"), text)
        self.assertGreaterEqual(len(lines), 2)
        self.assertNotIn("？", text)
        self.assertNotIn("#", text)  # 災害・行事でなければタグなし
        self.assertLessEqual(sns_rules.x_weight(text), 280)
        self.assertEqual(xp.problems(phone(), text), [])

    def test_quoted_product_name_goes_first(self):
        a = article("buds", "サムスン初のオープンイヤー型「Galaxy Buds On」　耳に挟めるイヤホン", at(9),
                    lede="サムスンは耳をふさがないイヤホンを出しました。価格は229ドルです。")
        self.assertTrue(xp.x_text(a).startswith("【Galaxy Buds On】サムスン初のオープンイヤー型"), xp.x_text(a))

    def test_disaster_has_one_hashtag_and_starts_with_quake(self):
        text = xp.x_text(quake())
        self.assertTrue(text.startswith("【地震】"))
        self.assertEqual(sns_rules.HASHTAG_RE.findall(text), ["#地震"])
        inp = xp.build_input(quake(), "chan")
        # 送る直前の autofix（S35 の災害のタグ外し）でも X の #地震 は残る
        sns_rules.autofix_buffer_input("twitter", inp, quake())
        self.assertIn("#地震", inp["metadata"]["twitter"]["thread"][0]["text"])
        self.assertEqual(xp.problems(quake(), text), [])

    def test_link_in_reply_with_card_image(self):
        inp = xp.build_input(phone(), "chan")
        thread = inp["metadata"]["twitter"]["thread"]
        self.assertNotIn("http", thread[0]["text"])
        self.assertEqual(thread[0]["assets"][0]["image"]["url"], tp.card_url(phone()))
        self.assertIn("utm_source=x", thread[1]["text"])
        self.assertIn("utm_campaign=xpost", thread[1]["text"])
        self.assertIn("utm_content=card_reply", thread[1]["text"])


class GateTest(unittest.TestCase):
    def check(self, a, text):
        return xp.problems(a, text)

    def test_rejects_wrong_shapes(self):
        a = phone()
        good = xp.x_text(a)
        self.assertTrue(any("[ルール20] 1行目は検索される言葉" in v for v in self.check(a, "新しい話です。\n" + good.splitlines()[1])))
        self.assertTrue(any("ハッシュタグ" in v for v in self.check(a, good + "\n#Pixel")))
        self.assertTrue(any("決算の数字だけ" in v for v in self.check(earnings(), "トヨタの営業利益は2兆1,911億円でした。\n前年より9.2%増えています。")))
        self.assertTrue(any("1行目＋記事の事実" in v for v in self.check(a, good.splitlines()[0])))
        # X だけの文面はほかの SNS には使えない
        self.assertTrue(any("X だけ" in v for v in sns_rules.check_xpost("threads", good, good, a)))

    def test_audit_and_presend_recognise_xpost(self):
        link = xp.reply_link(phone())
        self.assertEqual(sns_rules.campaign_kind("twitter", [link]), "xpost")
        self.assertEqual(sns_rules.campaign_kind("threads", [link]), "article")


class DecoupleTest(unittest.TestCase):
    """2026-11-07 から、Threads の予定・速報・朝のまとめは X に出さない（Threads の動きはそのまま）"""

    def chans(self):
        return {"twitter": {"id": "tw"}, "facebook": {"id": "fb"}}

    def test_threads_queue_drops_x_from_11_07_only(self):
        a = phone()
        before = tp.publish_extra_channels("", self.chans(), "本文です。", "https://ai-tech-express.jp/articles/pixel", a,
                                           datetime(2026, 11, 6, 20, 30, tzinfo=JST), build_only=True)
        after = tp.publish_extra_channels("", self.chans(), "本文です。", "https://ai-tech-express.jp/articles/pixel", a,
                                          at(7, 15), build_only=True)
        self.assertIn("twitter", before)
        self.assertNotIn("twitter", after)  # Facebook も 11/07 から別（台帳 S43・tests/test_facebook_slots_20261106.py）

    def test_other_paths_cannot_create_x_posts(self):
        calls = []
        with patch.object(sns_plan, "x_on", return_value=True), patch.object(tp, "buffer_graphql", side_effect=lambda *a, **k: calls.append(a)):
            with self.assertRaises(tp.XOwnSlotsOnly):
                tp.create_post("k", {"channelId": "tw", "text": "x"}, service="twitter", article=phone(), source="sns_video_followup.publish_queued")
        self.assertEqual(calls, [])  # Buffer は呼ばない

    def test_digest_goes_to_threads_only_from_11_07(self):
        self.assertEqual(morning_digest.digest_services(datetime(2026, 11, 6, 7, 15, tzinfo=JST)), ["threads", "twitter"])
        self.assertEqual(morning_digest.digest_services(at(7, 15)), ["threads"])

    def test_publish_queued_skips_x_input_from_11_07(self):
        src = (ROOT / "scripts" / "sns_video_followup.py").read_text("utf-8")
        self.assertIn('if service == "twitter" and sns_plan.x_on(slot):', src)

    def test_workflows_fire_near_x_slots(self):
        wf = (ROOT / ".github" / "workflows" / "x_post.yml").read_text("utf-8")
        for cron in ('"33 22 * * *"', '"33 3 * * *"', '"3 12 * * *"', '"*/10 * * * *"'):
            self.assertIn(cron, wf)
        self.assertIn("group: x-post", wf)
        self.assertIn("x_post.py --breaking-only", (ROOT / ".github" / "workflows" / "breaking_post.yml").read_text("utf-8"))


sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -m unittest tests.X でも同じフォルダの補助を読めるように
import legacy_sns_plan  # noqa: E402  2026-11-08 より前の枠の数で動かす（台帳 S47。今の数は tests/test_sns_volume_20261108.py）


def setUpModule():
    legacy_sns_plan.start()


def tearDownModule():
    legacy_sns_plan.stop()


if __name__ == "__main__":
    unittest.main()
