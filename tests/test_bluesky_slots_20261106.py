"""2026-11-06 オーナー承認（台帳 S40・2026-11-07 から）: Bluesky だけの上限（1日3本）・枠（7:30・13:00・21:00）・2行の文面。
外部通信なし（投稿しない）で、選び方・数え方・文面・門番を確かめる。"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bluesky_post as bp  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules  # noqa: E402

JST = timezone(timedelta(hours=9))
DAY = datetime(2026, 11, 7, tzinfo=JST)
LINK = "https://ai-tech-express.jp/articles/"


def at(h, m=0):
    return DAY + timedelta(hours=h, minutes=m)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def article(slug, title, made, **extra):
    base = {
        "slug": slug, "title": title, "body": "## 日本で使える？\n" + "あ" * 2000, "genreSlug": "ai", "tags": ["AI"],
        "generatedAt": iso(made), "description": "説明です。",
        "lede": f"{title}が、日本の利用者向けに今日から無料で使えるようになりました。料金は変わりません。",
        "workMoney": {"points": ["スマホで調べものをする人は、追加の料金なしで新しい機能を試せます。"]},
        "_virtual": True,  # テスト用の記事（content/articles に無い）
        # 記事に合う画像（2026-11-09 台帳 S49: 画像の無い記事は SNS に出さない）
        "thumbnail": f"https://ai-tech-express.jp/img/{slug}-0a1b2c3d.jpg", "imageCredit": {"kind": "stock"},
    }
    base.update(extra)
    return base


def arts():
    return [article("acme-a", "Acme AIの新機能A", at(9)), article("acme-b", "Bコープの翻訳AI", at(11))]


class SlotsTest(unittest.TestCase):
    def test_plan_numbers_are_separate_from_threads(self):
        self.assertEqual(sns_plan.bluesky_slots_jst(), [(7, 30), (13, 0), (21, 0)])
        self.assertEqual(sns_plan.bluesky_daily_cap(), 3)
        self.assertEqual(bp.PER_DAY, 3)
        # Threads の上限・枠はそのまま（台帳 S27・S39）
        self.assertEqual(sns_plan.daily_cap(), 5)
        self.assertEqual(sns_plan.slots_jst(), [(7, 15), (12, 15), (18, 45), (20, 30)])
        with patch.dict("os.environ", {"BLUESKY_PER_DAY": "9"}):
            self.assertEqual(sns_plan.bluesky_daily_cap(), 3)  # 変数で増やせない
        with patch.dict("os.environ", {"BLUESKY_PER_DAY": "1"}):
            self.assertEqual(sns_plan.bluesky_daily_cap(), 1)

    def test_windows(self):
        w = sns_plan.bluesky_slot_window
        for h, m in [(0, 15), (6, 59), (7, 0), (7, 29), (23, 0), (23, 30)]:
            self.assertIsNone(w(at(h, m)), (h, m))
        self.assertEqual(w(at(7, 30))[0], 0)
        self.assertEqual(w(at(12, 59))[0], 0)
        self.assertEqual(w(at(13, 0))[0], 1)
        self.assertEqual(w(at(20, 59))[0], 1)
        self.assertEqual(w(at(21, 0))[0], 2)
        self.assertEqual(w(at(22, 59))[0], 2)


class ChooseTest(unittest.TestCase):
    def test_threads_posts_do_not_count_against_bluesky(self):
        # Threads に今日5本（上限いっぱい）出ていても、Bluesky は別に数える
        state = {"posted": {f"t{i}": {"id": f"x{i}", "status": "scheduled", "dueAt": iso(at(8 + i))} for i in range(5)}}
        self.assertEqual(sns_plan.count_today(state["posted"], DAY.date()), 5)
        self.assertEqual(bp.posted_today(state, at(13, 5), {}), 0)
        picked = bp.choose(state, {}, at(13, 5), articles=arts())
        self.assertEqual([(k, kind) for k, _, kind in picked], [("acme-b", "brief")])

    def test_bluesky_posts_do_not_count_against_threads(self):
        posted = {"t": {"id": "x", "status": "scheduled", "dueAt": iso(at(8))}}
        extra = {f"b{i}": {"uri": "at://me/p", "at": iso(at(8 + i)), "kind": "brief"} for i in range(3)}
        self.assertEqual(sns_plan.count_today(posted, DAY.date()), 1)  # Bluesky だけの記録（bluesky_extra）は数えない
        self.assertEqual(bp.posted_today({"posted": posted}, at(22), extra), 3)

    def test_one_post_per_slot_late_within_window(self):
        extra = {"x": {"uri": "at://me/p", "at": iso(at(13, 2)), "title": "前の投稿", "kind": "brief"}}
        self.assertEqual(bp.choose({"posted": {}}, extra, at(14), articles=arts()), [])  # 13時の枠はもう出した
        picked = bp.choose({"posted": {}}, extra, at(21, 40), articles=arts())  # 夜の枠に遅れても23時までは出す
        self.assertEqual(len(picked), 1)
        # 13時の枠を取りこぼしたら、21時の前までは遅れて出してよい
        self.assertEqual(len(bp.choose({"posted": {}}, {}, at(18, 30), articles=arts())), 1)

    def test_never_more_than_three_and_never_outside_7_to_23(self):
        extra = {f"x{i}": {"uri": "at://me/p", "at": iso(at(h)), "title": f"t{i}"} for i, h in enumerate((0, 3, 9))}
        self.assertEqual(bp.choose({"posted": {}}, extra, at(21, 10), articles=arts()), [])
        for h, m in [(6, 50), (7, 10), (23, 5)]:
            self.assertEqual(bp.choose({"posted": {}}, {}, at(h, m), articles=arts()), [], (h, m))

    def test_morning_slot_is_the_digest(self):
        state = {"posted": {"digest-20261107": {"style": "digest", "dueAt": iso(at(7, 15)), "items": ["acme-a"]}}}
        picked = bp.choose(state, {}, at(7, 35), articles=arts())
        self.assertEqual([(k, kind) for k, _, kind in picked], [("digest-20261107", "mirror")])
        # まとめが無ければ夜のあいだのいちばんの記事
        picked = bp.choose({"posted": {}}, {}, at(7, 35), articles=[article("night", "夜の発表AI", at(1))])
        self.assertEqual([k for k, _, _ in picked], ["night"])

    def test_midday_prefers_breaking_then_newest(self):
        items = [article("new", "新しいAIの記事", at(12, 30)), article("brk", "速報のAIの記事", at(9), breaking=True)]
        self.assertEqual([k for k, _, _ in bp.choose({"posted": {}}, {}, at(13, 1), articles=items)], ["brk"])

    def test_evening_prefers_articles_since_midday_slot(self):
        items = [article("morning", "朝のAIの記事", at(9)), article("evening", "夕方のAIの記事", at(17))]
        self.assertEqual([k for k, _, _ in bp.choose({"posted": {}}, {}, at(21, 1), articles=items)], ["evening"])

    def test_skips_already_posted_failed_excluded_and_too_fresh(self):
        items = [
            article("done", "出したAIの記事", at(10)),
            article("failed", "失敗したAIの記事", at(10, 5)),
            article("fresh", "公開直後のAIの記事", at(12, 55)),
            article("ent", "企業向けAWSの新機能", at(11), tags=["AWS"]),
            article("ok", "使えるAIの記事", at(9)),
        ]
        state = {"posted": {"done": {"id": "1", "channels": {"bluesky": "at://me/1"}}}}
        extra = {"failed": {"failed": "x"}}
        self.assertEqual([k for k, _, _ in bp.choose(state, extra, at(13, 5), articles=items)], ["ok"])

    def test_disaster_alert_keeps_its_exemption(self):
        quake = {"breaking": True, "disaster": True, "dueAt": iso(at(10)), "id": "q"}
        extra = {f"x{i}": {"uri": "at://me/p", "at": iso(at(h)), "title": f"t{i}"} for i, h in enumerate((7, 8, 9))}
        state = {"posted": {"quake": quake}}
        picked = bp.choose(state, extra, at(10, 2), articles=[])
        self.assertEqual([(k, kind) for k, _, kind in picked], [("quake", "mirror")])  # 上限いっぱいでもすぐ出す
        quake["blueskyAt"] = iso(at(10, 3))
        self.assertEqual(bp.posted_today(state, at(11), {}), 0)  # 本数に数えない


class BriefTextTest(unittest.TestCase):
    def sample(self, **extra):
        return article("acme-tool", "Acme AIの新機能", at(9), **extra)

    def test_two_lines_one_hashtag_no_question(self):
        p = bp.plan_brief(self.sample())
        lines = p["text"].splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("Acme AIの新機能が"))
        self.assertTrue(lines[1].startswith("スマホで調べものをする人は"))
        self.assertEqual(lines[2], "#AI")
        self.assertFalse(p["text"].rstrip().endswith(("？", "?")))
        self.assertIn("utm_source=bluesky&utm_medium=social&utm_campaign=brief&utm_content=card_body", p["link"])
        record = bp.build_record(p["text"], p["link"], p["title"], p["desc"], None)
        self.assertLessEqual(len(record["text"]), bp.MAX_GRAPHEMES)
        self.assertEqual(record["embed"]["$type"], "app.bsky.embed.external")  # リンクカード
        media = [{"type": "image", "url": p["images"][0], "card": True}]
        self.assertEqual(sns_rules.check_post("bluesky", record["text"], media, p["gate"], kind="brief", links=[p["link"]]), [])

    def test_hashtag_is_a_facet(self):
        p = bp.plan_brief(self.sample())
        record = bp.build_record(p["text"], p["link"], p["title"], p["desc"], None)
        tags = [f for f in record["facets"] if f["features"][0]["$type"].endswith("#tag")]
        self.assertEqual(len(tags), 1)
        raw = record["text"].encode()
        self.assertEqual(raw[tags[0]["index"]["byteStart"]:tags[0]["index"]["byteEnd"]].decode(), "#AI")
        self.assertEqual(tags[0]["features"][0]["tag"], "AI")

    def test_second_line_skips_questions_and_low_impact(self):
        a = self.sample(workMoney={"points": ["直接の影響は小さいです。", "あなたは使ってみたいですか？"]},
                        verdict={"take": "無料で使えます。日本語の画面で、スマホからもすぐ試せます。"})
        lines = bp.brief_lines(a)
        self.assertEqual(lines[1], "日本語の画面で、スマホからもすぐ試せます。")
        # ほかに無ければ、影響が小さいことを伝える文を使う（事実だけ）
        b = self.sample(workMoney={"points": ["直接の影響は小さく、一般の人が今すぐ手続きをする必要はありません。"]})
        self.assertEqual(bp.brief_lines(b)[1], "直接の影響は小さく、一般の人が今すぐ手続きをする必要はありません。")
        self.assertIsNone(bp.brief_lines(self.sample(workMoney={}, highlights=[])))

    def test_hashtag_by_topic(self):
        self.assertEqual(bp.brief_hashtag(self.sample()), "#AI")
        gadget = article("pen", "ドコモの純正タッチペン", at(9), genreSlug="tech-gadget", tags=["ドコモ"])
        self.assertEqual(bp.brief_hashtag(gadget), "#ガジェット")
        leak = article("leak", "通販サイトで個人情報が流出", at(9), genreSlug="business", tags=["情報漏えい"])
        self.assertEqual(bp.brief_hashtag(leak), "")  # 災害・事故・安全の話題は付けない（台帳 S35）

    def test_fits_in_300_with_long_slug(self):
        a = article("a" * 80, "Acme AIの新機能", at(9))
        p = bp.plan_brief(a)
        record = bp.build_record(p["text"], p["link"], p["title"], p["desc"], None)
        self.assertLessEqual(len(record["text"]), bp.MAX_GRAPHEMES)
        self.assertEqual(record["text"].splitlines()[:3], p["text"].splitlines())  # 切り詰めない


class GateTest(unittest.TestCase):
    URL = f"{LINK}acme-tool?utm_source=bluesky&utm_medium=social&utm_campaign=brief&utm_content=card_body"
    ART = article("acme-tool", "Acme AIの新機能", at(9))
    MEDIA = [{"type": "image", "url": "https://ai-tech-express.jp/card/acme-tool", "card": True}]

    def check(self, text, platform="bluesky"):
        return sns_rules.check_post(platform, f"{text}\nai-tech-express.jp/articles/acme-tool", self.MEDIA, self.ART, kind="brief",
                                    links=[self.URL])

    def test_rejects_question_and_wrong_shapes(self):
        ok = "Acme AIの新機能が、今日から無料で使えるようになりました。\nスマホで調べものをする人は、追加の料金なしで試せます。\n#AI"
        self.assertEqual(self.check(ok), [])
        q = "Acme AIの新機能が、今日から無料で使えるようになりました。\nあなたはどう使いますか？\n#AI"
        self.assertTrue(any("[ルール19]" in v for v in self.check(q)))
        self.assertTrue(any("ハッシュタグ" in v for v in self.check(ok.replace("\n#AI", ""))))
        self.assertTrue(any("ハッシュタグ" in v for v in self.check(ok + " #ChatGPT")))
        self.assertTrue(any("2行" in v for v in self.check("Acme AIの新機能が、今日から無料で使えるようになりました。\n#AI")))
        self.assertTrue(any("ざっくり" in v for v in self.check(ok.replace("スマホで", "ざっくり言えばスマホで"))))

    def test_audit_reads_brief_posts_by_campaign(self):
        post = {"platform": "bluesky", "text": "Acme AIの新機能が、今日から無料で使えるようになりました。\n"
                                              "スマホで調べものをする人は、追加の料金なしで試せます。\n#AI\nai-tech-express.jp/articles/acme-tool",
                "links": [self.URL], "media": self.MEDIA, "at": "2026-11-07T04:00:00Z"}
        with patch.object(sns_rules, "ARTICLES_DIR", Path("/nonexistent")):
            got = sns_rules.audit_post(post)
        self.assertFalse(any("問いかけ" in v for v in got), got)


sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -m unittest tests.X でも同じフォルダの補助を読めるように
import legacy_sns_plan  # noqa: E402  2026-11-08 より前の枠の数で動かす（台帳 S47。今の数は tests/test_sns_volume_20261108.py）


def setUpModule():
    legacy_sns_plan.start()


def tearDownModule():
    legacy_sns_plan.stop()


if __name__ == "__main__":
    unittest.main()
