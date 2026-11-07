"""2026-11-05 オーナー判断・指摘（台帳 S4・S34・S35）。ネット接続・投稿なし。

  S4  事実の文を「要約すると、」で始めない（以前は必須）。決まった前置きを毎回付けない。門番は止めずに直す（autofix）
  S34 書き出しはジャンルの決まった呼びかけにしない（地震の訓練に「新しいガジェットが好きな人、」）。災害・事故・安全の話題は事実だけ
  S35 #AI は AI の話だけ・【速報】は発表から2時間以内の本当の速報だけ・決まった「詳しくはこちら👇（かんたん版あり）」をやめる・
      数字は万・億（77百万件 → 7,700万件）・記事が書き直されたら動画待ちの文面を作り直す
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import labels  # noqa: E402
import sns_pending_refresh  # noqa: E402
import sns_rules  # noqa: E402
import sns_video_followup as svf  # noqa: E402
import threads_hooks  # noqa: E402
import threads_post as tp  # noqa: E402

FRESH = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
LINK = "https://ai-tech-express.jp/articles/{slug}?utm_source={src}&utm_medium=social&utm_campaign=classic&utm_content=video_{pos}"

# 2026-11-05 朝の実例に近い記事（地震の訓練・ジャンルの付け間違いつき）
EEW = {
    "slug": "eew-drill-test", "_virtual": True, "genreSlug": "tech-gadget", "genre": "テクノロジー・ガジェット",
    "title": "11月5日10時ごろ、全国で緊急地震速報の訓練　テレビやスマホには流れず",
    "tags": ["緊急地震速報", "防災", "気象庁", "地震", "防災訓練"], "sourceName": "気象庁", "breaking": True,
    "sourcePublishedAt": FRESH, "threadsStyle": 3,
    "lede": "11月5日（木）10時ごろ、全国で緊急地震速報の訓練が行われます。テレビ・ラジオや携帯電話の緊急速報メールには流れません。",
    "description": "気象庁が11月5日（木）10時ごろに緊急地震速報の全国訓練を実施します。テレビ・ラジオや緊急速報メールには流れません。",
    "highlights": ["気象庁が11月5日（木）10時ごろ、緊急地震速報の全国的な訓練を実施する"],
    "threadsPost": "職場や学校で防災を担当している人、押さえておきたい話です。\n\n要約すると、気象庁が11月5日（木）10時ごろに緊急地震速報の全国訓練を行います。\n"
                   "テレビ・ラジオや緊急速報メールには流れません。\n\n速報が鳴ったとき、まず何をするか決めていますか？",
}
# 読者が記事の中身で決まらない、ふつうの話題（以前はジャンルから「仕事のニュースを追っている人、」になった）
PLAIN = {
    "slug": "plain-test", "_virtual": True, "genreSlug": "business", "title": "Acme社、本社を大阪に移転　2027年春から",
    "threadsStyle": 3, "sourceName": "Acme",
    "lede": "Acme社は本社を2027年春に東京から大阪へ移すと発表しました。新しい本社には約500人が勤めます。",
    "description": "Acme社が本社を大阪に移転します。",
    "highlights": ["本社の移転は2027年春の予定です。", "新しい本社には約500人が勤めます。"],
    "threadsPost": "要約すると、Acme社が本社を2027年春に大阪へ移します。\n新しい本社には約500人が勤めます。",
}
NEW = {
    "slug": "rakuten-accounts", "_virtual": True, "genreSlug": "investment", "title": "楽天証券の口座数が1,500万を突破、国内最多",
    "threadsStyle": 3, "tags": ["楽天証券", "NISA"],
    "threadsPost": "証券口座を持っている人、これは要チェックです。\n\n要約すると、楽天証券の口座が1,500万を超えました。\n国内の証券会社1社では、いちばん多い数です。\n\n"
                   "証券口座、どこを使っていますか？NISAは始めましたか？",
    "highlights": ["楽天証券の総合口座数が1,500万口座を突破しました。"], "description": "楽天証券の口座数が1,500万を突破しました。",
}


def no_history():
    return patch.multiple(tp, weak_hook_keys=MagicMock(return_value=[]), recent_openers=MagicMock(return_value=[]))


class SummaryLeadTest(unittest.TestCase):
    """S4: 「要約すると」を書かない（生成・プロンプト・門番）"""

    def test_generation_never_writes_summary_lead(self):
        for art in (NEW, PLAIN, EEW):
            article = copy.deepcopy(art)
            with no_history():
                text = tp.compose(article, [])
            self.assertNotIn("要約すると", text, art["slug"])
            self.assertNotIn("要約すると", tp.compose_x(article, text))
            self.assertNotIn("要約すると", tp.with_link(text, article))

    def test_prompts_do_not_ask_for_summary_lead(self):
        rules = threads_hooks.POST_RULES
        self.assertNotIn("「要約すると、」で始め", rules)
        self.assertIn("決まった前置きは付けず", rules)
        self.assertNotRegex(rules.split("書き方の例")[1].split("- 数字")[0], r"要約すると")
        import persona
        self.assertIn("SNS の投稿では「要約すると、」を使わない", persona.PLAIN_STYLE)

    def test_gate_flags_and_autofix_strips(self):
        text = "Acmeを使っている人、これは要チェックです。\n\n要約すると、Acmeが新しいAIを公開しました。\n月額は1,000円です。\n\nふだん使う道具、何を重視して選びますか？"
        art = {"slug": "acme", "title": "Acmeが新しいAIを公開", "_virtual": True}
        body = text + "\n\n" + LINK.format(slug="acme", src="threads", pos="body")
        self.assertTrue(any("ルール13" in v for v in sns_rules.check_post("threads", body, [], art, pending_video=True)))
        fixed, changes = sns_rules.autofix(body, art, "threads")
        self.assertNotIn("要約すると", fixed)
        self.assertIn("Acmeが新しいAIを公開しました。", fixed)  # 文は残す
        self.assertTrue(changes)
        self.assertFalse(any("ルール13" in v for v in sns_rules.check_post("threads", fixed, [], art, pending_video=True)))

    def test_buffer_path_is_fixed_in_place_before_posting(self):
        """送る直前の門番（enforce_buffer）が、送る入力そのものを直す（止めない）"""
        art = {"slug": "acme", "title": "Acmeが新しいAIを公開", "_virtual": True}
        text = ("Acmeを使っている人、これは要チェックです。\n\n要約すると、Acmeが新しいAIを公開しました。\n月額は1,000円です。\n\n"
                "ふだん使う道具、何を重視して選びますか？\n\n" + LINK.format(slug="acme", src="threads", pos="body"))
        inp = {"text": text, "metadata": {"threads": {"thread": [{"text": text, "assets": []}]}}}
        sns_rules.enforce_buffer("threads", inp, art, source="test", pending_video=True, history=False)
        self.assertNotIn("要約すると", inp["text"])
        self.assertNotIn("要約すると", inp["metadata"]["threads"]["thread"][0]["text"])

    def test_repeated_lead_in_is_logged_not_blocked(self):
        text = "Acmeを使っている人へ。\n\nポイントは、Acmeが新しいAIを公開したことです。\n月額は1,000円です。\n\n道具、何を重視しますか？"
        self.assertEqual(sns_rules.lead_in_of(text), "ポイントは")
        self.assertTrue(sns_rules.lead_in_warnings(text, ["ポイントは", "", "ポイントは"]))
        self.assertEqual(sns_rules.lead_in_warnings(text, ["ポイントは", "", ""]), [])
        # 主語・日付は前置きではない
        self.assertEqual(sns_rules.lead_in_of("書き出し。\n\n気象庁が、訓練を行います。\n\n問い？"), "")

    def test_quality_strips_old_lead_from_generated_post(self):
        import quality
        rec = {"threadsStyle": 3, "title": "t", "threadsPost": "書き出しです。\n\n要約すると、Acmeが公開しました。\n月額は1,000円です。\n\n何を重視しますか？"}
        self.assertTrue(quality.summary_opener_problems(rec))
        self.assertTrue(quality.fix_summary_opener(rec))
        self.assertNotIn("要約すると", rec["threadsPost"])


class OpenerTest(unittest.TestCase):
    """S34: ジャンルから作った呼びかけをやめる。災害・事故・安全の話題は事実だけ"""

    def test_no_genre_template_callout(self):
        self.assertEqual(threads_hooks.audience_of({"title": "Acme社、本社を大阪に移転", "genreSlug": "tech-gadget"}), ("", ""))
        self.assertEqual(threads_hooks.callout({"title": "Acme社、本社を大阪に移転", "genreSlug": "business"}), ("", ""))
        article = copy.deepcopy(PLAIN)
        with no_history():
            text = tp.compose(article, [])
        first = text.splitlines()[0]
        self.assertFalse(sns_rules.template_callout(first), first)
        self.assertTrue(sns_rules.fact_opener_ok(first), first)
        self.assertEqual(article["_opener"], "fact")

    def test_gate_rejects_genre_template_but_keeps_content_callouts(self):
        art = {"slug": "acme", "title": "Acmeが新しいイヤホンを発表", "_virtual": True}
        rest = "\n\nAcmeが新しいイヤホンを発表しました。\n価格は1万円です。\n\nイヤホン、何を重視して選びますか？\n\n" + LINK.format(slug="acme", src="threads", pos="body")
        bad = sns_rules.check_post("threads", "新しいガジェットが好きな人、これは見てほしいです。" + rest, [], art, pending_video=True)
        self.assertTrue(any("ルール14" in v for v in bad))
        ok = sns_rules.check_post("threads", "自転車好きの人に、知っておいてほしい話です。" + rest, [], art, pending_video=True)
        self.assertFalse(any("ルール14" in v for v in ok), ok)  # 記事の中身から書いた呼びかけ（Honda RN0）は止めない

    def test_disaster_topic_is_facts_only(self):
        article = copy.deepcopy(EEW)
        self.assertTrue(sns_rules.safety_topic(article))
        with no_history():
            text = tp.compose(article, [], breaking=True)
        first = text.splitlines()[0]
        self.assertFalse(sns_rules.is_callout_line(first), first)
        self.assertNotIn("ガジェット", text)
        self.assertFalse(text.rstrip().endswith(("？", "?")), text)
        self.assertIsNone(sns_rules.EMOJI_RE.search(tp.with_link(text, article)))
        self.assertEqual(tp.x_hashtags(article), "")
        x = tp.compose_x(article, text)
        self.assertNotIn("#", x)
        reply = LINK.format(slug="eew-drill-test", src="x", pos="reply")
        self.assertEqual(sns_rules.check_post("x", x, [], article, reply_text=reply, pending_video=True), [])
        self.assertEqual(sns_rules.check_post("threads", tp.with_link(text, article), [], article, pending_video=True), [])

    def test_autofix_removes_callout_question_and_emoji_from_old_disaster_text(self):
        old = ("【速報】熊本市で住まいの被害を調べている人に、知っておいてほしい話です。\n\n要約すると、全指定避難所は11月1日に閉鎖されました。\n"
               "住家被害認定調査は1万1,405件です。\n\n災害のあとの手続き、窓口に何度も足を運ぶのと、まとめて済ませるのとどちらが楽ですか？\n\n"
               "詳しくはこちら👇（かんたん版あり）\n" + LINK.format(slug="kumamoto-quake-27th-meeting", src="threads", pos="body"))
        art = {"slug": "kumamoto-quake-27th-meeting", "title": "熊本地震のり災証明書の申請状況　市の最新会議資料", "breaking": True, "_virtual": True}
        fixed, _ = sns_rules.autofix(old, art, "threads")
        self.assertNotIn("知っておいてほしい", fixed)
        self.assertNotIn("？", fixed)
        self.assertNotIn("👇", fixed)
        self.assertNotIn("要約すると", fixed)
        self.assertNotIn("【速報】", fixed)  # 会議の資料は速報ではない（S35）
        self.assertIn("全指定避難所は11月1日に閉鎖されました。", fixed)
        self.assertIn("utm_content=video_body", fixed)  # リンクと utm はそのまま
        self.assertEqual(sns_rules.check_post("threads", fixed, [], art, pending_video=True), [])

    def test_disaster_drill_goes_to_public_genre(self):
        fix = labels.genre_fix({"title": EEW["title"], "tags": EEW["tags"], "genreSlug": "ai"})
        self.assertEqual(fix[0], "public")
        self.assertEqual(labels.genre_fix({"title": EEW["title"], "tags": EEW["tags"], "genreSlug": "tech-gadget"})[0], "public")
        self.assertIsNone(labels.genre_fix({"title": "Sonyが新しいイヤホンを発表", "tags": ["Sony"], "genreSlug": "tech-gadget"}))
        live = json.loads((ROOT / "content" / "articles" / "eew-drill-2026-11-05.json").read_text("utf-8"))
        self.assertEqual(live["genreSlug"], "public")


class TemplateBitsTest(unittest.TestCase):
    """S35: #AI・【速報】・決まった案内の行・数字の単位"""

    def test_ai_hashtag_only_for_ai_topics(self):
        self.assertEqual(tp.x_hashtags({"title": "アララのメール配信で約7,700万件流出の恐れ", "tags": ["情報流出"]}), "")
        self.assertEqual(tp.x_hashtags({"title": "ゆうちょ銀行が松井証券と提携", "tags": ["証券"]}), "")
        self.assertIn("#AI", tp.x_hashtags({"title": "OpenAIがChatGPTの新機能を公開", "tags": []}))
        fixed, _ = sns_rules.autofix("ゆうちょ銀行が提携します。\n\n証券口座、いくつ持っていますか？\n\n#AI", {"slug": "y", "title": "ゆうちょ銀行が松井証券と提携"}, "x")
        self.assertNotIn("#AI", fixed)

    def test_breaking_label_only_for_fresh_primary_news(self):
        stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        self.assertTrue(sns_rules.sns_breaking_ok({"breaking": True, "sourcePublishedAt": FRESH, "title": "Acmeが新製品"}))
        self.assertFalse(sns_rules.sns_breaking_ok({"breaking": True, "sourcePublishedAt": stale, "title": "Acmeが新製品"}))
        self.assertFalse(sns_rules.sns_breaking_ok({"breaking": True, "title": "Acmeが新製品"}))  # 発表の時刻が分からない
        self.assertFalse(sns_rules.sns_breaking_ok({"breaking": True, "sourcePublishedAt": FRESH, "slug": "kumamoto-quake-27th-meeting"}))
        self.assertFalse(sns_rules.sns_breaking_ok({"breaking": True, "sourcePublishedAt": FRESH, "slug": "arara-message-data-leak-second-report"}))
        # サイトの札（画像・帯）は今のまま
        self.assertTrue(sns_rules.is_fast_news({"breaking": True}))

    def test_link_line_is_plain(self):
        text = tp.with_link("書き出しです。\n\n事実です。\n\n問いですか？", {"slug": "s", "easy": "かんたん版"})
        self.assertNotIn("詳しくはこちら", text)
        self.assertNotIn("👇", text)
        self.assertTrue(text.splitlines()[-1].startswith("https://"))

    def test_number_units_normalized_on_sns_text(self):
        fixed, changes = sns_rules.autofix("アララから約77百万件のメールアドレスが持ち出されました。", {"slug": "a", "title": "t"}, "x")
        self.assertIn("約7,700万件", fixed)
        self.assertTrue(changes)


class PendingTextTest(unittest.TestCase):
    """動画待ちの文面（state/threads_posted.json の pending.inputs）も今の決まりに直す・記事が変わったら作り直す"""

    def _rec(self, article):
        with no_history():
            text = tp.compose(copy.deepcopy(article), [])
        art = copy.deepcopy(article)
        channels = {"threads": {"id": "T"}, "twitter": {"id": "X"}, "facebook": {"id": "F"}}
        rec = tp.queue_for_video("", channels, tp.with_link(text, art), text, "https://ai-tech-express.jp/articles/" + art["slug"], art,
                                 datetime.now(timezone.utc) + timedelta(hours=2), fb_text=text)
        return rec

    def test_old_pending_texts_are_fixed_on_every_channel(self):
        old = "書き出しの人、これは要チェックです。\n\n要約すると、楽天証券の口座が1,500万を超えました。\n\n証券口座、どこを使っていますか？"
        rec = {"status": "awaiting_video", "pending": {"inputs": {
            "threads": {"text": old + "\n\n詳しくはこちら👇（かんたん版あり）\n" + LINK.format(slug="rakuten-accounts", src="threads", pos="body"),
                        "metadata": {"threads": {"thread": [{"text": old}]}}},
            "twitter": {"text": old + "\n\n#AI", "metadata": {"twitter": {"thread": [{"text": old + "\n\n#AI"},
                                                                              {"text": "詳しくはこちら👇\n" + LINK.format(slug="rakuten-accounts", src="x", pos="reply")}]}}},
            "facebook": {"text": old},
        }}}
        sns_pending_refresh.refresh_record("rakuten-accounts", rec, copy.deepcopy(NEW), rebuild=False)
        for service, text in sns_pending_refresh.texts_of(rec).items():
            self.assertNotIn("要約すると", text, service)
            self.assertNotIn("詳しくはこちら", text, service)
        self.assertNotIn("#AI", rec["pending"]["inputs"]["twitter"]["text"])
        self.assertNotIn("詳しくはこちら", rec["pending"]["inputs"]["twitter"]["metadata"]["twitter"]["thread"][1]["text"])

    def test_queue_records_article_hash_and_rebuilds_when_article_changes(self):
        article = copy.deepcopy(PLAIN)
        rec = self._rec(article)
        self.assertEqual(rec["pending"]["articleHash"], tp.article_hash(article))
        self.assertFalse(svf.refresh_if_article_changed(article["slug"], rec, article, use_llm=False))  # 変わっていなければ作り直さない
        changed = {**article, "lede": "Acme社は本社を2027年春に東京から大阪へ移すと発表しました。新しい本社には約7,700万円をかけます。",
                   "highlights": ["新しい本社には約7,700万円をかけます。"], "threadsPost": ""}
        slot = rec["pending"]["slot"]
        self.assertTrue(svf.refresh_if_article_changed(article["slug"], rec, changed, use_llm=False))
        self.assertEqual(rec["pending"]["slot"], slot)  # 枠はそのまま
        self.assertEqual(rec["pending"]["articleHash"], tp.article_hash(changed))
        self.assertIn("utm_content=video_body", rec["pending"]["inputs"]["threads"]["text"])

def setUpModule():
    __import__("sys").path.insert(0, __import__("os").path.dirname(__file__))
    import legacy_threads  # 以前の書き方の仕組みのテスト（台帳 S46 の新しい書き方・承認待ちの止めは外す）

    legacy_threads.start()


def tearDownModule():
    import legacy_threads

    legacy_threads.stop()


if __name__ == "__main__":
    unittest.main()
