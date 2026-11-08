"""Threads の自動投稿の新しい書き方（2026-11-07 夜 オーナー承認・台帳 S46）の検査。外部通信なし・何も投稿しない。

  1. 1行目で誰の話か・数字はちょうど1つ・決め手は記事に（最後の文で記事にしかないもの）・「｜」なし
  2. リンクは返信だけで「続き（◯◯）→ URL」（URL だけにしない）。utm_campaign=<slug>&utm_content=reader_reply
  3. どの経路でも Threads の記事の投稿は新しい書き方で確かめる（古い書き方は門番で止まる）
  4. state/threads_hold.json の held が true の間は Threads の自動投稿を出さない（急ぎの安全の知らせだけ出す）

  python3 -m pytest tests/test_threads_reader_20261108.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sns_rules  # noqa: E402
import threads_gate as g  # noqa: E402
import threads_reader as tr  # noqa: E402

ARTICLE = {
    "slug": "smbc-mail-leak-test",
    "title": "三井住友銀行のメール配信の委託先からアドレス22万7,216件が流出",
    "description": "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。",
    "body": "対象は7月1日〜10月31日に同行が送ったメールの宛先です。問い合わせ窓口と対象の見分け方を案内しています。",
    "_virtual": True,
}
MAIN = (
    "三井住友銀行からメールを受け取っていた法人・個人事業主の人へ。\n\n"
    "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。\n"
    "対象は7月1日〜10月31日に同行が送ったメールの宛先です。\n\n"
    "自分が対象かどうかの見分け方と問い合わせ先は記事にまとめています。"
)
REPLY = tr.reply_text(ARTICLE["slug"], "対象の見分け方")


def check(main: str = MAIN, reply: str = REPLY, **kw) -> list[str]:
    return sns_rules.check_threads_reader("threads", main, reply, ARTICLE, **kw)


class ReaderRuleTest(unittest.TestCase):
    def test_good_post_passes(self):
        self.assertEqual(check(), [])

    def test_reply_shape_and_utm(self):
        self.assertTrue(REPLY.startswith("続き（対象の見分け方）→ https://ai-tech-express.jp/articles/smbc-mail-leak-test?"))
        self.assertIn("utm_source=threads&utm_medium=social&utm_campaign=smbc-mail-leak-test&utm_content=reader_reply", REPLY)
        bare = REPLY.split("→ ", 1)[1]
        self.assertTrue(any("URL だけにしない" in p for p in check(reply=bare)))
        wrong = REPLY.replace("utm_campaign=smbc-mail-leak-test", "utm_campaign=classic")
        self.assertTrue(any("UTM" in p for p in check(reply=wrong)))

    def test_first_line_must_say_who(self):
        main = MAIN.replace("三井住友銀行からメールを受け取っていた法人・個人事業主の人へ。", "三井住友銀行で情報漏えいがありました。")
        self.assertTrue(any("誰の話か" in p for p in check(main)))

    def test_exactly_one_number(self):
        two = MAIN.replace("漏れました。", "漏れました。被害は800万円分です。")
        self.assertTrue(any("ちょうど1つ" in p for p in check(two)))
        none = MAIN.replace("22万7,216件", "多くの宛先")
        self.assertTrue(any("ちょうど1つ" in p for p in check(none)))
        self.assertEqual(sns_rules.reader_numbers("2026年分は最大104万円、10月28日時点、時効は5年"), ["104万", "5"])

    def test_number_must_be_in_article(self):
        bad = MAIN.replace("22万7,216件", "30万件")
        self.assertTrue(any("記事に無い数字" in p for p in check(bad)))

    def test_keep_deadline_and_steps_in_article(self):
        dl = MAIN.replace("対象は7月1日〜10月31日に同行が送ったメールの宛先です。", "申請は12月15日までに必要です。")
        self.assertTrue(any("期限" in p for p in check(dl)))
        steps = MAIN.replace("対象は7月1日〜10月31日に同行が送ったメールの宛先です。", "1. 公式サイトを開く\n2. 番号を入れる")
        self.assertTrue(any("手順" in p for p in check(steps)))

    def test_ending_names_article_only_thing_and_varies(self):
        end = MAIN.replace("自分が対象かどうかの見分け方と問い合わせ先は記事にまとめています。", "気をつけてください。")
        self.assertTrue(any("記事にしかないもの" in p for p in check(end)))
        same = check(recent_endings=["自分が対象かどうかの見分け方と問い合わせ先は記事にまとめています。"])
        self.assertTrue(any("直近の投稿と同じ" in p for p in same))

    def test_no_vertical_bar_no_body_link_no_hype(self):
        self.assertTrue(any("｜" in p for p in check(MAIN.replace("法人・個人事業主", "法人｜個人事業主"))))
        self.assertTrue(any("本文にリンク" in p for p in check(MAIN + "\nhttps://ai-tech-express.jp/articles/smbc-mail-leak-test")))
        self.assertTrue(any("煽" in p for p in check(MAIN.replace("漏れました。", "漏れました！"))))

    def test_opener_form_rotates(self):
        self.assertEqual(tr.form_of("三井住友銀行からメールを受け取っていた人へ。"), "he")
        self.assertEqual(tr.form_of("年末調整の準備を進めている人、控除が変わります。"), "ten")
        self.assertEqual(tr.form_of("遺族年金を受け取る人は、請求が必要です。"), "wa")
        self.assertEqual(tr.form_of("ドコモを使っている人に関わる話です。"), "ni")
        self.assertTrue(any("前の投稿と同じ形" in p for p in check(recent_forms=["he"])))
        self.assertEqual(tr.next_form({"posts": {"a": {"form": "he", "at": "2026-11-08T00:00:00"}}}), "ten")
        self.assertEqual(tr.next_form({"posts": {"a": {"form": "ni", "at": "2026-11-08T00:00:00"}}}), "he")


class AllPathsTest(unittest.TestCase):
    def test_threads_article_posts_are_checked_as_reader(self):
        self.assertEqual(sns_rules.reader_kind("threads", "article", ARTICLE), "reader")
        self.assertEqual(sns_rules.reader_kind("threads", "digest", ARTICLE), "digest")
        self.assertEqual(sns_rules.reader_kind("threads", "article", {**ARTICLE, "disaster": True}), "article")
        self.assertEqual(sns_rules.reader_kind("bluesky", "article", ARTICLE), "article")

    def test_old_style_input_is_blocked_by_shared_gate(self):
        old = {"channelId": "c", "text": "要約すると、流出しました。\n\nどう思いますか？",
               "metadata": {"threads": {"thread": [{"text": "流出がありました。どう思いますか？\n\nhttps://ai-tech-express.jp/articles/smbc-mail-leak-test"
                                                            "?utm_source=threads&utm_medium=social&utm_campaign=classic&utm_content=video_body",
                                                    "assets": [{"image": {"url": "https://ai-tech-express.jp/img/x.jpg"}}]}]}}}
        with patch.object(sns_rules, "report"), patch.object(sns_rules, "check_media", return_value=[]):
            with self.assertRaises(sns_rules.SnsRuleViolation):
                sns_rules.enforce_buffer("threads", old, ARTICLE, source="test", history=False)

    def test_apply_input_makes_two_part_thread_from_saved_draft(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(tr, "STATE_PATH", Path(tmp) / "r.json"):
            tr.remember(ARTICLE, {"main": MAIN, "reply": REPLY, "label": "対象の見分け方", "form": "he", "ending": tr.ending_of(MAIN)})
            inp = {"channelId": "c", "text": "古い文面", "metadata": {"threads": {"topic": "t", "thread": [
                {"text": "古い文面", "assets": [{"image": {"url": "https://ai-tech-express.jp/img/x.jpg"}}]}]}}}
            tr.apply_input(inp, ARTICLE, generate=lambda _p: self.fail("保存した下書きを使う"))
            thread = inp["metadata"]["threads"]["thread"]
            self.assertEqual([t["text"] for t in thread], [MAIN, REPLY])
            self.assertEqual(thread[0]["assets"][0]["image"]["url"], "https://ai-tech-express.jp/img/x.jpg")
            self.assertEqual(inp["metadata"]["threads"]["topic"], "t")
            self.assertTrue(tr.is_reader_input(inp))
            with patch.object(sns_rules, "report"), patch.object(sns_rules, "check_media", return_value=[]):
                sns_rules.enforce_buffer("threads", inp, ARTICLE, source="test", history=False)  # 通る

    def test_queue_for_video_uses_reader_text(self):
        # 11/8: 予定に入れる経路（queue_for_video）が古い文面のまま門番に通し、ルール22 で全部止まっていた
        import threads_post as tp

        with tempfile.TemporaryDirectory() as tmp, patch.object(tr, "STATE_PATH", Path(tmp) / "r.json"):
            tr.remember(ARTICLE, {"main": MAIN, "reply": REPLY, "label": "対象の見分け方", "form": "he", "ending": tr.ending_of(MAIN)})
            old = {"channelId": "c", "text": "流出がありました。どう思いますか？", "metadata": {"threads": {"topic": "t", "thread": [
                {"text": "流出がありました。どう思いますか？", "assets": [{"image": {"url": "https://ai-tech-express.jp/img/x.jpg"}}]}]}}}
            with patch.object(tp, "publish_via_buffer", return_value={"input": old}), patch.object(tp, "publish_extra_channels", return_value={}), \
                    patch.object(sns_rules, "report"), patch.object(sns_rules, "check_media", return_value=[]):
                result = tp.queue_for_video("", {"threads": {"id": "c"}}, "古い文面", "古い文面", "https://ai-tech-express.jp/articles/x", ARTICLE, None)
            thread = result["pending"]["inputs"]["threads"]["metadata"]["threads"]["thread"]
            self.assertEqual([t["text"] for t in thread], [MAIN, REPLY])
            with patch.object(sns_rules, "report"), patch.object(sns_rules, "check_media", return_value=[]):
                sns_rules.enforce_buffer("threads", result["pending"]["inputs"]["threads"], ARTICLE, source="test", history=False)  # 通る

    def test_compose_retries_then_gives_up_without_posting(self):
        bad = {"who_line": "ニュースです。", "facts": ["流出がありました。"], "closing": "以上です。", "label": "続き"}
        with self.assertRaises(tr.ReaderNotReady):
            tr.compose(ARTICLE, state={}, generate=lambda _p: bad, tries=2)
        self.assertTrue(issubclass(tr.ReaderNotReady, g.ThreadsHeld))  # 呼ぶ側は「次の回にもう一度」として扱う

    def test_compose_assembles_parts(self):
        good = {"who_line": "三井住友銀行からメールを受け取っていた法人・個人事業主の人へ。",
                "facts": ["メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。", "対象は7月1日〜10月31日に同行が送ったメールの宛先です。"],
                "closing": "自分が対象かどうかの見分け方と問い合わせ先は記事にまとめています。", "label": "対象の見分け方"}
        pair = tr.compose(ARTICLE, state={}, generate=lambda _p: good)
        self.assertEqual(pair["main"], MAIN)
        self.assertEqual(pair["reply"], REPLY)
        self.assertEqual(pair["form"], "he")


class HoldTest(unittest.TestCase):
    def test_held_blocks_everything_but_urgent(self):
        hold = {"held": True}
        self.assertTrue(g.style_hold(ARTICLE, "article", hold))
        self.assertTrue(g.style_hold(ARTICLE, "digest", hold))
        self.assertTrue(g.style_hold({**ARTICLE, "breaking": True}, "article", hold))
        with patch.object(sns_rules, "is_urgent", return_value=True):
            self.assertEqual(g.style_hold(ARTICLE, "article", hold), "")

    def test_release_is_one_flag_digest_separate(self):
        self.assertEqual(g.style_hold(ARTICLE, "article", {"held": False}), "")
        self.assertTrue(g.style_hold(None, "digest", {"held": False}))
        self.assertEqual(g.style_hold(None, "digest", {"held": False, "digest": True}), "")

    def test_missing_file_holds(self):
        self.assertTrue(g.style_hold(ARTICLE, "article", {}))

    def test_repo_state_has_hold_switch(self):
        # 11/8 09:45 オーナーが最初の3本を承認して held=false。切り替えはこのファイルの held だけ
        data = json.loads((ROOT / "state" / "threads_hold.json").read_text("utf-8"))
        self.assertIn("held", data)


if __name__ == "__main__":
    unittest.main()
