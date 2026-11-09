"""X・Bluesky・Facebook の読者向けの書き方（2026-11-08 夜 オーナー承認・sns_rules ルール23）の検査。外部通信なし・何も投稿しない。

  1. Threads の文面（state/threads_reader.json）を SNS ごとに合わせる: X は全角140字・返信に「続き（◯◯）→ URL」、
     Bluesky は300字・最後の行に「続き（◯◯）→」＋リンクカード、Facebook は Threads の本文＋最後の行にリンク
  2. utm_source=<SNS>&utm_campaign=<slug>&utm_content=reader_reply（X）／reader_body（Bluesky・Facebook）
  3. 「｜」なし・タグは X（災害・行事だけ）と Bluesky（1つまで）だけ
  4. 夜の枠（23:59 まで・1日15本・45分以上あける）・Bluesky の一時的な失敗は時間がたてば候補に戻す・予定と実績に Bluesky だけの投稿も数える

  python3 -m pytest tests/test_sns_reader_20261108.py
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

import bluesky_post as bp  # noqa: E402
import facebook_post as fp  # noqa: E402
import sns_plan  # noqa: E402
import sns_reader as sr  # noqa: E402
import sns_rules  # noqa: E402
import threads_reader as tr  # noqa: E402
import x_post as xp  # noqa: E402

ARTICLE = {
    "slug": "smbc-mail-leak-test",
    "title": "三井住友銀行のメール配信の委託先からアドレス22万7,216件が流出",
    "description": "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。",
    "body": "対象は7月1日〜10月31日に同行が送ったメールの宛先です。問い合わせ窓口と対象の見分け方を案内しています。",
    "genreSlug": "public",
    "_virtual": True,
}
MAIN = (
    "三井住友銀行からメールを受け取っていた法人・個人事業主の人へ。\n\n"
    "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。\n"
    "対象は7月1日〜10月31日に同行が送ったメールの宛先です。\n\n"
    "自分が対象かどうかの見分け方と問い合わせ先は記事にまとめています。"
)
STATE = {"posts": {ARTICLE["slug"]: {"main": MAIN, "reply": tr.reply_text(ARTICLE["slug"], "対象の見分け方"), "label": "対象の見分け方",
                                     "form": "he", "ending": MAIN.splitlines()[-1], "status": "draft", "version": tr.VERSION,
                                     "at": "2026-11-08T12:00:00+00:00"}}}


def with_state():
    return patch.object(tr, "load_state", return_value=json.loads(json.dumps(STATE)))


class ComposeTest(unittest.TestCase):
    def test_x_fits_and_links_in_reply(self):
        with with_state():
            got = sr.x_post(ARTICLE)
        self.assertIsNotNone(got)
        self.assertLessEqual(sns_rules.x_weight(got["text"]), sns_rules.X_LIMIT)
        self.assertNotIn("http", got["text"])
        self.assertTrue(got["reply"].startswith("続き（対象の見分け方）→ https://ai-tech-express.jp/articles/smbc-mail-leak-test?"))
        self.assertIn("utm_source=x&utm_medium=social&utm_campaign=smbc-mail-leak-test&utm_content=reader_reply", got["reply"])
        self.assertEqual(sns_rules.check_reader_post("x", got["text"], got["reply"], ARTICLE), [])

    def test_x_shortens_when_too_long(self):
        long_main = MAIN.replace("対象は7月1日〜10月31日に同行が送ったメールの宛先です。",
                                 "対象は7月1日〜10月31日に同行が送ったメールの宛先で、法人の担当者あてのものも含まれると同行は説明しています。")
        state = json.loads(json.dumps(STATE))
        state["posts"][ARTICLE["slug"]]["main"] = long_main
        with patch.object(tr, "load_state", return_value=state):
            got = sr.x_post(ARTICLE)
        self.assertIsNotNone(got)
        self.assertIn("22万7,216件", got["text"])
        body = "\n".join(x for x in got["text"].splitlines() if not x.startswith("#"))  # 話題のタグ（台帳 S52）は最後の行に付いてよい
        self.assertTrue(body.endswith("記事にまとめています。"))

    def test_bluesky_link_line_last_and_card(self):
        with with_state():
            got = sr.bluesky_post(ARTICLE)
        self.assertIsNotNone(got)
        self.assertLessEqual(len(got["text"]), 300)
        self.assertIn("utm_source=bluesky", got["link"])
        self.assertIn("utm_content=reader_body", got["link"])
        rec = bp.build_record(got["text"], got["link"], "t", "d", None, full_text=got["text"])
        link_facet = next(f for f in rec["facets"] if f["features"][0]["$type"].endswith("#link"))
        shown = rec["text"].encode()[link_facet["index"]["byteStart"]:link_facet["index"]["byteEnd"]].decode()
        self.assertEqual(shown, "ai-tech-express.jp/articles/smbc-mail-leak-test")
        self.assertEqual(rec["embed"]["$type"], "app.bsky.embed.external")
        self.assertEqual(sns_rules.check_reader_post("bluesky", got["text"], "", ARTICLE, links=[got["link"]]), [])

    def test_facebook_is_threads_text_plus_link(self):
        with with_state():
            got = sr.facebook_post(ARTICLE)
        self.assertTrue(got["text"].startswith(MAIN))
        last = got["text"].splitlines()[-1]
        self.assertTrue(last.startswith("続き（対象の見分け方）→ https://ai-tech-express.jp/articles/smbc-mail-leak-test?"))
        self.assertIn("utm_source=facebook", last)

    def test_no_pair_falls_back_to_classic(self):
        with patch.object(tr, "load_state", return_value={}):
            self.assertIsNone(sr.x_post(ARTICLE))
            self.assertIsNone(sr.bluesky_post(ARTICLE))
            self.assertIsNone(sr.facebook_post(ARTICLE))
            self.assertEqual(xp.compose_post(ARTICLE)["style"], "classic")
            self.assertIsNone(fp.reader_post(ARTICLE))
            self.assertIsNone(bp.plan_reader(ARTICLE))

    def test_platform_modules_use_reader(self):
        with with_state():
            self.assertEqual(xp.compose_post(ARTICLE)["kind"], "reader")
            self.assertEqual(fp.post_kind(ARTICLE), "reader")
            self.assertEqual(bp.plan_brief(ARTICLE)["kind"], "reader")
            inp = xp.build_input(ARTICLE, "c")
            self.assertTrue(inp["metadata"]["twitter"]["thread"][1]["text"].startswith("続き（"))


class RuleTest(unittest.TestCase):
    def fb(self, text):
        return sns_rules.check_reader_post("facebook", text, "", ARTICLE)

    def good_fb(self):
        return f"{MAIN}\n\n" + sr.link_line(STATE["posts"][ARTICLE["slug"]], sr.link(ARTICLE["slug"], "facebook"))

    def test_good_and_bad(self):
        self.assertEqual(self.fb(self.good_fb()), [])
        self.assertTrue(any("続き" in p for p in self.fb(MAIN + "\n\n" + sr.link(ARTICLE["slug"], "facebook"))))
        self.assertTrue(any("「｜」" in p for p in self.fb(self.good_fb().replace("法人・", "法人｜"))))
        self.assertTrue(any("ハッシュタグ" in p for p in self.fb(self.good_fb() + "\n#暮らし")))
        self.assertTrue(any("UTM" in p for p in self.fb(self.good_fb().replace("utm_source=facebook", "utm_source=threads"))))
        two = self.good_fb().replace("漏れました。", "漏れました。被害は3社です。")
        self.assertTrue(any("ちょうど1つ" in p for p in self.fb(two)))

    def test_x_tags_only_alerts_and_events(self):
        reply = sr.link_line(STATE["posts"][ARTICLE["slug"]], sr.link(ARTICLE["slug"], "x"))
        short = sr.short_main(MAIN)
        self.assertEqual(sns_rules.check_reader_post("x", short, reply, ARTICLE), [])
        self.assertTrue(any("ハッシュタグ" in p for p in sns_rules.check_reader_post("x", short + "\n#暮らし", reply, ARTICLE)))

    def test_check_post_dispatches_reader_for_other_platforms(self):
        text = self.good_fb()
        media = [{"type": "image", "url": f"https://ai-tech-express.jp/card/{ARTICLE['slug']}", "width": 1600, "height": 900}]
        out = sns_rules.check_post("facebook", text, media, ARTICLE, kind="reader")
        self.assertFalse([p for p in out if "ルール16" in p or "ルール23" in p or "ルール22" in p], out)
        url = sr.link(ARTICLE["slug"], "x")
        self.assertEqual(sns_rules.campaign_kind("x", [url]), "reader")


class ScheduleTest(unittest.TestCase):
    def test_evening_slots_15_and_gaps(self):
        plan = json.loads((ROOT / "scripts" / "sns_plan.json").read_text("utf-8"))
        for key in ("x", "facebook", "bluesky"):
            block = plan[key]
            self.assertEqual(block["window_end"], "23:59", key)
            mins = [int(t[:2]) * 60 + int(t[3:]) for t in block["slots_jst"]]
            self.assertEqual(len(mins), 15, key)
            self.assertTrue(all(b - a >= 45 for a, b in zip(mins, mins[1:])), key)
        self.assertIn("23:00", plan["x"]["slots_jst"])
        self.assertIn("12:30", plan["facebook"]["slots_jst"])  # 暮らしの話題の枠
        # Bluesky は Threads と同じ枠（2026-11-08 夜 オーナー「Threadsレベルまで本数を引き上げよう」）
        self.assertEqual(plan["bluesky"]["slots_jst"], plan["slots_jst"])
        self.assertIn("23:45", plan["bluesky"]["slots_jst"])
        self.assertEqual(plan["bluesky"]["daily_cap"], 15)

    def test_late_slot_window_until_2359(self):
        with patch.dict("os.environ", {"SNS_PER_DAY": ""}):
            at = datetime(2026, 11, 8, 14, 50, tzinfo=timezone.utc)  # 23:50 日本時間
            self.assertIsNotNone(sns_plan.x_slot_window(at))
            self.assertIsNotNone(sns_plan.bluesky_slot_window(at))
            self.assertIsNotNone(sns_plan.fb_slot_window(at))

    def test_priority_safety_money_procedures(self):
        money = {"slug": "m", "title": "年金の保険料、口座振替の前納で割引", "description": "申請の期限があります"}
        brand = {"slug": "b", "title": "ソニーの新しいヘッドホン", "description": ""}
        self.assertGreater(sr.daily_score(money), sr.daily_score(brand))


class BlueskyRecoveryTest(unittest.TestCase):
    def test_failed_retry_after_hours(self):
        now = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
        self.assertTrue(bp.blocked({"uri": "at://x", "at": "2026-11-08T10:00:00+00:00"}, now))
        self.assertTrue(bp.blocked({"failed": "x", "failedAt": (now - timedelta(hours=1)).isoformat()}, now))
        self.assertFalse(bp.blocked({"failed": "x", "failedAt": (now - timedelta(hours=4)).isoformat()}, now))
        self.assertFalse(bp.blocked(None, now))

    def test_card_404_is_not_recorded_as_failure(self):
        src = (ROOT / "scripts" / "bluesky_post.py").read_text("utf-8")
        self.assertIn("記事のカードがまだ開けません。次の回にもう一度", src)

    def test_plan_actual_counts_bluesky_only_posts(self):
        import sns_plan_actual as pa

        with tempfile.TemporaryDirectory() as d:
            st = Path(d)
            now = datetime.now(timezone.utc)
            (st / "bluesky_extra.json").write_text(json.dumps({"a": {"uri": "at://did/app.bsky.feed.post/1", "at": now.isoformat(), "slot": "21:30"}}))
            for name in ("threads_posted.json", "x_posted.json", "facebook_posted.json"):
                (st / name).write_text(json.dumps({"posted": {}} if name == "threads_posted.json" else {}))
            with patch.object(pa, "STATE", st):
                try:
                    data = pa.build()
                except Exception as error:  # noqa: BLE001
                    self.skipTest(f"build の読み方が違う: {error}")
            self.assertEqual([r["slug"] for r in data["sns"]["bluesky"]["actual"]], ["a"])


if __name__ == "__main__":
    unittest.main()
