"""2026-11-10 オーナー決定（台帳 S52）: X の記事のリンクを「本文（＋画像）」と「自分への返信」（S50）で半分ずつ出して比べる。
外部通信なし・何も投稿しない。

  1. 直近7日に少ない方の形を出す（同じなら slug で決める）。変数 X_LINK_MODE＝body／reply で片方だけにできる
  2. 本文の形: 最後の行に「続き（◯◯）→ URL」（utm_source=x・utm_content=reader_body）・返信なし・画像あり・280以内
  3. 返信の形: 今までどおり（utm_content=reader_reply）
  4. ハッシュタグは話題の名前のタグを含めて2つまで（広いタグ・3つは止める）
  5. 門番: リンクは本文か返信のどちらか1か所
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
    "thumbnail": "https://ai-tech-express.jp/img/smbc-mail-leak-test-0a1b2c3d.jpg", "imageCredit": {"kind": "stock"},
}
MAIN = (
    "三井住友銀行からメールを受け取っていた法人・個人事業主の人へ。\n\n"
    "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。\n\n"
    "見分け方と問い合わせ先は記事にまとめています。"
)
STATE = {"posts": {ARTICLE["slug"]: {"main": MAIN, "reply": tr.reply_text(ARTICLE["slug"], "対象の見分け方"), "label": "対象の見分け方",
                                     "form": "he", "ending": MAIN.splitlines()[-1], "status": "draft", "version": tr.VERSION,
                                     "at": "2026-11-08T12:00:00+00:00"}}}
NOW = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)


def with_state():
    return patch.object(tr, "load_state", return_value=json.loads(json.dumps(STATE)))


def no_fig():
    d = tempfile.TemporaryDirectory()
    return d, patch.object(xp, "FIG_DIR", Path(d.name))


class VariantTest(unittest.TestCase):
    def test_balances_by_recent_history(self):
        with patch.dict("os.environ", {"X_LINK_MODE": ""}):
            hist = {f"a{i}": {"at": (NOW - timedelta(hours=i)).isoformat(), "link": "reply"} for i in range(3)}
            hist["b"] = {"at": NOW.isoformat(), "link": "body"}
            self.assertEqual(sns_plan.x_link_variant("x", hist, NOW), "body")
            hist["c"] = {"at": NOW.isoformat(), "link": "body"}
            hist["d"] = {"at": NOW.isoformat(), "link": "body"}
            hist["e"] = {"at": NOW.isoformat(), "link": "body"}
            self.assertEqual(sns_plan.x_link_variant("x", hist, NOW), "reply")
            old = {f"o{i}": {"at": (NOW - timedelta(days=9)).isoformat(), "link": "body"} for i in range(5)}  # 7日より前は数えない
            self.assertIn(sns_plan.x_link_variant("same", old, NOW), ("body", "reply"))
            self.assertEqual(sns_plan.x_link_variant("same", old, NOW), sns_plan.x_link_variant("same", {}, NOW))
            # 記録の無い日でも、記事ごとに両方の形が出る（slug で決める）
            got = {sns_plan.x_link_variant(f"slug-{i}", {}, NOW) for i in range(20)}
            self.assertEqual(got, {"body", "reply"})

    def test_mode_variable(self):
        for mode in ("body", "reply"):
            with patch.dict("os.environ", {"X_LINK_MODE": mode}):
                self.assertEqual(sns_plan.x_link_variant("x", {"a": {"at": NOW.isoformat(), "link": mode}}, NOW), mode)


class ComposeTest(unittest.TestCase):
    def test_reader_body_variant(self):
        d, fig = no_fig()
        with d, fig, with_state():
            post = xp.compose_post(ARTICLE, link_at="body")
            inp = xp.build_input(ARTICLE, "c", post=post)
            probs = xp.problems(ARTICLE, post["text"], post)
        self.assertEqual((post["kind"], post["link"], post["reply"]), ("reader", "body", ""))
        lines = [x for x in post["text"].splitlines() if x.strip() and not x.startswith("#")]
        self.assertTrue(lines[-1].startswith("続き（対象の見分け方）→ https://ai-tech-express.jp/articles/smbc-mail-leak-test?"))
        self.assertIn("utm_source=x&utm_medium=social&utm_campaign=smbc-mail-leak-test&utm_content=reader_body", lines[-1])
        self.assertLessEqual(sns_rules.x_weight(post["text"]), sns_rules.X_LIMIT)
        self.assertNotIn("｜", post["text"])
        thread = inp["metadata"]["twitter"]["thread"]
        self.assertEqual(len(thread), 1)  # 返信なし
        self.assertTrue(thread[0]["assets"][0]["image"]["url"])  # 画像あり
        self.assertEqual(probs, [])

    def test_reader_reply_variant_unchanged(self):
        d, fig = no_fig()
        with d, fig, with_state():
            post = xp.compose_post(ARTICLE, link_at="reply")
            inp = xp.build_input(ARTICLE, "c", post=post)
            probs = xp.problems(ARTICLE, post["text"], post)
        self.assertEqual(post["link"], "reply")
        self.assertNotIn("http", post["text"])
        self.assertIn("utm_content=reader_reply", post["reply"])
        self.assertEqual(len(inp["metadata"]["twitter"]["thread"]), 2)
        self.assertEqual(probs, [])

    def test_classic_body_variant(self):
        with patch.object(tr, "load_state", return_value={}), patch.object(xp, "x_text", return_value="三井住友銀行のメールの宛先が流出しました。\n対象は22万7,216件です。"):
            post = xp.compose_post(ARTICLE, link_at="body")
        self.assertEqual((post["style"], post["link"], post["reply"]), ("classic", "body", ""))
        self.assertIn("utm_content=card_body", post["text"])
        self.assertTrue([x for x in post["text"].splitlines() if not x.startswith("#")][-1].startswith("続き → https://"))


class HashtagTest(unittest.TestCase):
    def test_topic_tag_up_to_two(self):
        docomo = dict(ARTICLE, slug="docomo-x", title="ドコモの料金プランが12月から変わります")
        self.assertIn("#ドコモ", sns_plan.x_hashtags(docomo))
        self.assertLessEqual(len(sns_plan.x_hashtags(docomo)), 2)
        quake = dict(ARTICLE, slug="q", title="ドコモの基地局が地震で停止", disaster=True)
        self.assertNotIn("#ドコモ", sns_plan.x_hashtags(quake))

    def test_gate_tags(self):
        docomo = dict(ARTICLE, slug="docomo-x", title="ドコモの料金プランが12月から変わります")
        text = "ドコモの料金が12月から変わります。\n月330円上がります。"

        def tag_problems(t):
            return [v for v in sns_rules.check_xpost("x", t, t, docomo) if "ハッシュタグ" in v]

        self.assertEqual(tag_problems(text + "\n#ドコモ"), [])
        self.assertTrue(tag_problems(text + "\n#暮らし"))
        self.assertTrue(tag_problems(text + "\n#ドコモ #a #b"))


if __name__ == "__main__":
    unittest.main()
