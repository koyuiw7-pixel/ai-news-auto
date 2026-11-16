"""Muse の追記（もう出ている記事への書き足し）が記事に届く（2026-11-16）。

それまで: 運び役（scripts/muse_articles_push.py）はフォルダの直下の「YYYYMMDD-….md」しか見ず、addenda/ の追記は1本も届いていなかった。
  - 対象の記事は、先頭に書かれた slug で「ちょうど1本」に決まるときだけ（記事の名前や説明からは推測しない）
  - 出典との事実確認に通ったものだけ足す。形は手で入れたドコモの追記（debaded0）と同じ（updates に kind: followup の1行）
  - 同じ追記を二重に足さない
外への通信・LLM は使わない（出典の読み込みと事実確認は差し替える）。
"""
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import muse_addenda as ma  # noqa: E402
import muse_format  # noqa: E402

PLAIN = """対象スラッグ: apbc-final

## 決勝の相手は韓国に決まりました

決勝の対戦相手は、韓国です。予選リーグの最終日に韓国代表がチャイニーズ・タイペイ代表を6対4で下し、予選2位で決勝に進みました。日本は予選を3戦全勝で終えています。
出典：NPB公式 試合日程・結果 https://npb.jp/apbc/2026/

### 相手が決まった経緯

韓国・チャイニーズ・タイペイ・オーストラリアの3チームが1勝2敗で並び、大会規定による順位決定で韓国が予選2位に入りました。
出典：NPB公式 試合速報 https://npb.jp/scores/2026/1114/kor-tpe-80/ ／ 侍ジャパン公式「放送・配信予定」 https://www.japan-baseball.jp/jp/games/apbc2026/broadcast.html
"""

FRONT = """---
title: リコール追加分（既存記事 daihatsu-recall へ追加）
genre: 暮らし
sources:
  - url: https://www.daihatsu.co.jp/info/recall-search/99376.htm
    name: ダイハツ工業「ロッキーのリコールについて」
    facts: 対象25,040台
notes: 既存記事 daihatsu-recall への追加分のみ。新規記事ではない。
---

## 追加分：車台番号の範囲は、3車種でここまでです

対象の型式と車台番号の範囲、製作期間、台数は次のとおりです。3車種とも、届出に入っているのは1.2Lエンジン車の型式だけです。ハイブリッド車などの型式は、この届出には含まれていません。

## 追加分：修理は無料です

直し方は3車種とも同じで、発電機のプーリを対策品に交換します。
"""

ARTICLE = {
    "slug": "apbc-final", "title": "侍ジャパン決勝は11月15日19時", "description": "決勝の放送と配信の予定です。", "highlights": ["決勝は19時開始"],
    "writer": "muse", "sourceUrl": "https://www.japan-baseball.jp/jp/games/apbc2026/", "sourceName": "侍ジャパン公式",
    "generatedAt": "2026-11-14T09:36:48+00:00", "easy": "",
    "body": "11月15日19時から東京ドームで行われる決勝は、テレビでも配信でも見られます。\n\n## 決勝は19時開始\n\n- 決勝：19時開始。\n\n## 確かめる窓口\n\n侍ジャパン公式サイト。",
}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.articles = base / "content" / "articles"
        self.inbox = base / "content" / "muse_inbox" / "addenda"
        self.articles.mkdir(parents=True)
        self.inbox.mkdir(parents=True)
        self.results = base / "state" / "muse_articles.json"
        for slug in ("apbc-final", "daihatsu-recall", "vivant-extra-ticket-sales", "vivant-movie-extra-tickets"):
            (self.articles / f"{slug}.json").write_text(json.dumps({**ARTICLE, "slug": slug}, ensure_ascii=False), encoding="utf-8")
        self.patches = [mock.patch.object(ma, "ARTICLES_DIR", self.articles), mock.patch.object(ma, "INBOX", self.inbox),
                        mock.patch.object(ma.muse_articles, "RESULTS", self.results)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def article(self, slug="apbc-final") -> dict:
        return json.loads((self.articles / f"{slug}.json").read_text("utf-8"))


class TargetTest(Base):
    def test_slug_line_decides_the_article(self):
        add = ma.parse(PLAIN, "add-apbc-20261115.md")
        self.assertEqual(add["slug"], "apbc-final")
        self.assertEqual(add["heading"], "決勝の相手は韓国に決まりました")

    def test_front_matter_slug_in_title_and_notes(self):
        add = ma.parse(FRONT, "recall-daihatsu-20261113.md")
        # sources の URL の中の「recall-search」は対象にしない。title・notes に書いた、本当にある記事だけ
        self.assertEqual(add["slug"], "daihatsu-recall")
        self.assertEqual(add["heading"], "車台番号の範囲は、3車種でここまでです")
        self.assertIn("### 修理は無料です", add["body"])
        self.assertNotRegex(add["body"], r"(?m)^## ")
        self.assertEqual(add["sources"][0]["url"], "https://www.daihatsu.co.jp/info/recall-search/99376.htm")

    def test_description_only_is_not_guessed(self):
        # 実際にあった形: 「対象: VIVANT追加販売の記事」。VIVANT の追加販売の記事は2本あり、名前からは決められない
        text = PLAIN.replace("対象スラッグ: apbc-final", "対象: VIVANT追加販売の記事")
        with self.assertRaises(ma.AddendumError) as ctx:
            ma.parse(text, "add-vivant-20261115.md")
        self.assertIn("対象スラッグ", str(ctx.exception))

    def test_both_articles_instruction_is_not_guessed(self):
        # 実際にあった形: ドコモの追記（手で入れた分）。「速報記事・続報記事の両方に」は対象を決められない＝二重に足さない
        text = "# 追記用：ドコモ障害 第七報\n\n対象記事：速報記事・続報記事の両方に、このブロックをそのまま末尾へ足す。\n\n---\n\n" + PLAIN.split("\n", 2)[2]
        with self.assertRaises(ma.AddendumError):
            ma.parse(text, "add-docomo-7th-20261116.md")

    def test_two_slugs_or_unknown_slug_are_refused(self):
        with self.assertRaises(ma.AddendumError) as two:
            ma.parse(PLAIN.replace("apbc-final", "vivant-extra-ticket-sales, vivant-movie-extra-tickets"), "a.md")
        self.assertIn("2本", str(two.exception))
        with self.assertRaises(ma.AddendumError) as none:
            ma.parse(PLAIN.replace("apbc-final", "no-such-article"), "a.md")
        self.assertIn("見つかりません", str(none.exception))

    def test_slug_in_the_body_is_not_a_target(self):
        text = PLAIN.replace("対象スラッグ: apbc-final\n", "").replace("決勝の対戦相手は", "記事 apbc-final の続きです。決勝の対戦相手は")
        with self.assertRaises(ma.AddendumError):
            ma.parse(text, "a.md")

    def test_article_url_is_accepted(self):
        add = ma.parse(PLAIN.replace("対象スラッグ: apbc-final", "対象: https://ai-tech-express.jp/articles/apbc-final"), "a.md")
        self.assertEqual(add["slug"], "apbc-final")


class ParseTest(Base):
    def test_sources_are_collected_and_taken_out_of_the_body(self):
        add = ma.parse(PLAIN, "a.md")
        self.assertEqual([s["url"] for s in add["sources"]], [
            "https://npb.jp/apbc/2026/", "https://npb.jp/scores/2026/1114/kor-tpe-80/",
            "https://www.japan-baseball.jp/jp/games/apbc2026/broadcast.html"])
        self.assertEqual(add["sources"][0]["name"], "NPB公式 試合日程・結果")
        self.assertEqual(add["sources"][2]["name"], "侍ジャパン公式「放送・配信予定」")
        self.assertNotIn("出典", add["body"])
        self.assertNotIn("対象スラッグ", add["body"])
        self.assertIn("### 相手が決まった経緯", add["body"])

    def test_source_list_and_editor_lines(self):
        text = PLAIN + "\n出典：\n- 映画公式サイト NEWS https://vivant.toho-movie.jp/news.html\n- ローソン公式 https://www.lawson.co.jp/campaign/x/\n\n次に読む記事として、追加販売の記事を挙げます。\n"
        add = ma.parse(text, "a.md")
        self.assertIn("https://www.lawson.co.jp/campaign/x/", [s["url"] for s in add["sources"]])
        self.assertNotIn("次に読む記事として", add["body"])
        self.assertNotIn("lawson", add["body"])

    def test_no_source_or_too_short_is_refused(self):
        with self.assertRaises(ma.AddendumError) as ctx:
            ma.parse("対象スラッグ: apbc-final\n\n## 見出し\n\n短い。\n", "a.md")
        self.assertIn("出典がありません", str(ctx.exception))
        self.assertIn("長さ", str(ctx.exception))

    def test_no_vertical_bar_reaches_the_article(self):
        add = ma.parse(PLAIN.replace("韓国に決まりました", "韓国｜決まりました"), "a.md")
        self.assertNotIn("｜", add["heading"])


class ApplyTest(Base):
    def test_same_shape_as_the_hand_applied_followup(self):
        add = ma.parse(PLAIN, "add-apbc-20261115.md")
        now = datetime(2026, 11, 14, 15, 30, tzinfo=timezone.utc)  # 日本時間 11月15日 0:30
        before = self.article()
        record = ma.apply(before, add, now)
        entry = record["updates"][-1]
        # 手で入れたドコモの追記（debaded0）と同じ欄
        self.assertEqual(set(entry), {"at", "kind", "title", "sourceUrl", "sourceName"})
        self.assertEqual(entry["kind"], "followup")
        self.assertEqual(entry["sourceUrl"], "https://npb.jp/apbc/2026/")
        self.assertTrue(entry["title"].endswith("を追記しました"))
        self.assertEqual(record["updatedAt"], entry["at"])
        self.assertEqual(record["generatedAt"], before["generatedAt"])
        self.assertEqual(record["title"], before["title"])
        self.assertEqual(record["museAddenda"], ["add-apbc-20261115.md"])
        self.assertIn("https://npb.jp/apbc/2026/", [s["url"] for s in record["museSources"]])
        self.assertEqual(record["museSources"][0]["url"], before["sourceUrl"])
        self.assertNotIn("updates", before)  # もとの dict は変えない
        body = record["body"]
        # 最初の章（地の文）のあと・もとの章の前に、サイトが「続報」として表示する見出しの形で足す
        self.assertRegex(body, r"(?m)^## 続報（11月15日）：決勝の相手は韓国に決まりました$")
        self.assertLess(body.index("テレビでも配信でも見られます"), body.index("## 続報（"))
        self.assertLess(body.index("## 続報（"), body.index("## 決勝は19時開始"))
        self.assertIn("出典: [NPB公式 試合日程・結果](https://npb.jp/apbc/2026/)", body)
        self.assertTrue(body.rstrip().endswith("侍ジャパン公式サイト。"))  # もとの本文は変えない

    def test_heading_first_article_keeps_its_first_section_on_top(self):
        body = "## 自分の車が対象かを確かめる\n\n表。\n\n## 届出は11月12日\n\n本文。"
        out = ma.insert_section(body, "## 続報（11月16日）：追記\n\n足した文。")
        self.assertLess(out.index("表。"), out.index("## 続報（"))
        self.assertLess(out.index("## 続報（"), out.index("## 届出は11月12日"))
        self.assertTrue(ma.insert_section("## 1つだけ\n\n本文。", "## 続報（11月16日）：追記").rstrip().endswith("追記"))

    def test_non_muse_article_gets_no_muse_sources(self):
        article = {k: v for k, v in ARTICLE.items() if k != "writer"}
        record = ma.apply(article, ma.parse(PLAIN, "a.md"))
        self.assertNotIn("museSources", record)
        self.assertEqual(record["updates"][-1]["kind"], "followup")

    def test_updated_at_is_written_only_by_touch_updated(self):
        src = (ROOT / "scripts" / "muse_addenda.py").read_text("utf-8")
        self.assertIn("updated_at.touch_updated(record, \"followup\"", src)
        self.assertNotIn('["updatedAt"] =', src)


class ReviewTest(Base):
    """出典の読み込みと事実確認は差し替える（外へ出ない）"""

    def put(self, name="add-apbc-20261115.md", text=PLAIN) -> Path:
        path = self.inbox / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_process(self, fact=None, fetched=None, added=None):
        fact = fact if fact is not None else {"grounded": True, "score": 92, "problems": [], "fatal": False, "model": "x"}

        def fetch(sources, skip_unreadable_first=False, unread=None):
            return fetched if fetched is not None else [{**s, "title": "", "text": "本文" * 200, "full_text": "", "page": {}} for s in sources]

        import quality

        fact_mock = mock.Mock(side_effect=fact) if isinstance(fact, Exception) else mock.Mock(return_value=fact)
        with mock.patch.object(ma.muse_articles, "fetch_sources", fetch), mock.patch.object(quality, "fact_check", fact_mock), \
                mock.patch.object(quality, "added_problems", return_value=added or []), \
                mock.patch.object(ma.source_date, "check", return_value=[]), mock.patch.dict(os.environ, {"GITHUB_OUTPUT": ""}):
            ma.process(mock.Mock(max=4, budget=300))
        return fact_mock

    def row(self, name="add-apbc-20261115.md") -> dict:
        return json.loads(self.results.read_text("utf-8"))["items"]["addenda/" + name]

    def test_pass_applies_once_and_records(self):
        path = self.put()
        fact = self.run_process()
        self.assertFalse(path.exists())
        self.assertEqual(self.row()["status"], "published")
        self.assertEqual(self.row()["url"], "https://ai-tech-express.jp/articles/apbc-final")
        self.assertIn("## 続報（", self.article()["body"])
        # 事実確認には追記の文だけを渡し、もとの記事は確認済みの事実として渡す
        pseudo, _source = fact.call_args.args[:2]
        self.assertIn("決勝の対戦相手は、韓国です", pseudo["body"])
        self.assertNotIn("確かめる窓口", pseudo["body"])
        self.assertIn("侍ジャパン決勝は11月15日19時", fact.call_args.kwargs["context"])

    def test_applied_count_reaches_the_workflow(self):
        self.put()
        out = Path(self.tmp.name) / "gh_output"
        out.write_text("", encoding="utf-8")
        real = os.environ.get

        with mock.patch.object(ma.os.environ, "get", lambda k, d=None: str(out) if k == "GITHUB_OUTPUT" else real(k, d)):
            self.run_process()
        self.assertEqual(out.read_text("utf-8").strip().splitlines()[-1], "applied=1")

    def test_same_file_again_is_not_applied_twice(self):
        self.put()
        self.run_process()
        once = self.article()
        # 同じファイルを置き直した・名前を変えて置き直した（運び役が「-HHMM」を付けた）どちらでも増えない
        self.put()
        self.put("add-apbc-20261115-2140.md")
        fact = self.run_process()
        fact.assert_not_called()
        self.assertEqual(self.article(), once)
        self.assertEqual(self.article()["body"].count("## 続報（"), 1)
        self.assertEqual(len(self.article()["updates"]), 1)
        self.assertEqual(self.row("add-apbc-20261115-2140.md")["status"], "published")
        self.assertIn("もう記事に入っています", self.row("add-apbc-20261115-2140.md")["reason"])

    def test_hand_applied_text_is_not_applied_again(self):
        article = self.article()
        article["body"] += "\n\n## 続報（11月15日）：手で入れた\n\n" + ma.parse(PLAIN, "x.md")["body"]
        (self.articles / "apbc-final.json").write_text(json.dumps(article, ensure_ascii=False), encoding="utf-8")
        self.put()
        self.run_process().assert_not_called()
        self.assertEqual(self.article()["body"], article["body"])

    def test_fact_check_failure_is_not_applied(self):
        before = self.article()
        for fact in ({"grounded": False, "score": 95, "problems": ["出典に無い数字"], "fatal": True, "model": "x"},
                     {"grounded": True, "score": 79, "problems": [], "fatal": False, "model": "x"}):
            path = self.put()
            self.run_process(fact=fact)
            self.assertFalse(path.exists())
            self.assertEqual(self.row()["status"], "rejected")
            self.assertIn("事実確認で不合格", self.row()["reason"])
            self.assertEqual(self.article(), before)

    def test_pass_score_is_the_muse_score(self):
        self.assertEqual(ma.muse_articles.MUSE_PASS_SCORE, 80)
        self.assertIn("muse_articles.MUSE_PASS_SCORE", (ROOT / "scripts" / "muse_addenda.py").read_text("utf-8"))

    def test_unreadable_sources_or_new_style_problems_are_not_applied(self):
        before = self.article()
        self.put()
        self.run_process(fetched=[])
        self.assertIn("1本も読めませんでした", self.row()["reason"])
        self.put()
        self.run_process(added=["投資の助言に読める文"])
        self.assertIn("投資の助言", self.row()["reason"])
        self.assertEqual(self.article(), before)

    def test_llm_down_keeps_the_file_then_gives_up(self):
        path = self.put()
        for attempt in range(1, ma.MAX_TRIES):
            self.run_process(fact=RuntimeError("quota"))
            self.assertTrue(path.exists())
            self.assertEqual(self.row()["status"], "waiting")
            self.assertEqual(self.row()["tries"], attempt)
        self.run_process(fact=RuntimeError("quota"))
        self.assertFalse(path.exists())
        self.assertEqual(self.row()["status"], "rejected")
        self.assertNotIn("updates", self.article())

    def test_undecidable_target_is_logged_not_guessed(self):
        before = {p.name: p.read_text("utf-8") for p in self.articles.glob("*.json")}
        path = self.put("add-vivant-20261115.md", PLAIN.replace("対象スラッグ: apbc-final", "対象: VIVANT追加販売の記事"))
        self.run_process().assert_not_called()
        self.assertFalse(path.exists())
        self.assertEqual(self.row("add-vivant-20261115.md")["status"], "rejected")
        self.assertIn("対象の記事を1本に決められません", self.row("add-vivant-20261115.md")["reason"])
        self.assertEqual({p.name: p.read_text("utf-8") for p in self.articles.glob("*.json")}, before)

    def test_past_plan_written_as_future_is_refused(self):
        text = PLAIN.replace("決勝の対戦相手は、韓国です。", "追加販売は2026年11月15日24時から、一部の劇場で始まります。")
        self.put(text=text)
        with mock.patch.object(ma, "datetime") as fake:
            fake.now.return_value = datetime(2026, 11, 16, 12, 0, tzinfo=ma.JST)
            self.run_process().assert_not_called()
        self.assertIn("日付", self.row()["reason"])

    def test_press_only_sources_are_refused(self):
        text = PLAIN.replace("https://npb.jp/apbc/2026/", "https://news.yahoo.co.jp/articles/abc").replace(
            "https://npb.jp/scores/2026/1114/kor-tpe-80/", "https://news.yahoo.co.jp/articles/def").replace(
            "https://www.japan-baseball.jp/jp/games/apbc2026/broadcast.html", "https://news.yahoo.co.jp/articles/ghi")
        import public_interest

        if not public_interest.is_press_url("https://news.yahoo.co.jp/articles/abc"):
            self.skipTest("報道の URL の一覧に無い")
        self.put(text=text)
        self.run_process().assert_not_called()
        self.assertEqual(self.row()["status"], "rejected")


class PushTest(unittest.TestCase):
    """Mac の運び役: addenda/ の追記も受け箱に入れる"""

    def setUp(self):
        import muse_articles_push as push

        self.push = push
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.folder = base / "saisoku-articles"
        self.clone = base / "repo"
        (self.clone / "state").mkdir(parents=True)
        (self.clone / "content" / "articles").mkdir(parents=True)
        (self.folder / "addenda").mkdir(parents=True)
        self.patches = [mock.patch.object(push, "FOLDER", self.folder), mock.patch.object(push, "CLONE", self.clone)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def put(self, name: str, age: float) -> Path:
        path = self.folder / "addenda" / name
        path.write_text(PLAIN, encoding="utf-8")
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path

    def test_addenda_were_never_picked_as_articles(self):
        # 原因の記録: 記事の入稿は直下の「YYYYMMDD-….md」だけ。addenda/ の中は見ない
        self.put("add-apbc-20261115.md", 600)
        self.assertEqual(self.push.pick_new(muse_format, {}), [])

    def test_fresh_addenda_are_picked_and_old_ones_returned(self):
        self.put("add-new-20261116.md", 600)
        self.put("add-writing-20261116.md", 5)
        old = self.put("add-old-20261113.md", 3 * 24 * 3600)
        (self.folder / "addenda" / "sent").mkdir()
        (self.folder / "addenda" / "sent" / "add-sent.md").write_text("x", encoding="utf-8")
        picked = self.push.pick_addenda({})
        self.assertEqual([(p.name, n) for p, n in picked], [("add-new-20261116.md", "add-new-20261116.md")])
        self.assertFalse(old.exists())
        self.assertIn("24時間", (self.folder / "addenda" / "rejected" / "add-old-20261113.reason.txt").read_text("utf-8"))
        self.assertTrue((self.folder / "addenda" / "add-writing-20261116.md").exists())

    def test_same_name_again_gets_a_new_name(self):
        self.put("add-a-20261116.md", 600)
        picked = self.push.pick_addenda({"addenda/add-a-20261116.md": {"status": "rejected"}})
        self.assertRegex(picked[0][1], r"^add-a-20261116-\d{4}\.md$")

    def test_results_move_addenda(self):
        sent = self.folder / "addenda" / "sent"
        sent.mkdir()
        (sent / "add-a.md").write_text("x", encoding="utf-8")
        (sent / "add-b.md").write_text("x", encoding="utf-8")
        (sent / "add-c.md").write_text("x", encoding="utf-8")
        items = {"addenda/add-a.md": {"status": "published", "url": "https://ai-tech-express.jp/articles/a"},
                 "addenda/add-b.md": {"status": "rejected", "reason": "対象の記事を1本に決められません"},
                 "addenda/add-c.md": {"status": "waiting"},
                 "add-a.md": {"status": "rejected", "reason": "記事の入稿の結果と取り違えない"}}
        notes = self.push.settle_results(items, self.folder / "addenda", "addenda/")
        self.assertEqual(len(notes), 2)
        self.assertTrue((self.folder / "addenda" / "done" / "add-a.md").exists())
        self.assertIn("対象の記事", (self.folder / "addenda" / "rejected" / "add-b.reason.txt").read_text("utf-8"))
        self.assertTrue((sent / "add-c.md").exists())

    def test_run_puts_addenda_in_the_inbox_without_push(self):
        self.put("add-new-20261116.md", 600)
        with mock.patch.object(self.push, "ensure_clone"), mock.patch.object(self.push, "images", return_value=[]):
            self.assertEqual(self.push.run(no_push=True), 0)
        self.assertTrue((self.clone / "content" / "muse_inbox" / "addenda" / "add-new-20261116.md").exists())
        self.assertTrue((self.folder / "addenda" / "add-new-20261116.md").exists())  # push していない回は動かさない


class WiringTest(unittest.TestCase):
    def test_workflow_runs_addenda_and_deploys(self):
        flow = (ROOT / ".github" / "workflows" / "muse_inbox.yml").read_text("utf-8")
        self.assertIn("python scripts/muse_addenda.py", flow)
        self.assertIn("content/muse_inbox/addenda/*.md", flow)
        self.assertLess(flow.index("scripts/muse_addenda.py --max"), flow.index("python scripts/muse_articles.py"))
        # 追記だけの回もデプロイする（新しい記事が無くても、読者に見える中身が変わる）
        self.assertIn('ADDED="${{ steps.addenda.outputs.applied || \'0\' }}"', flow)
        self.assertIn('[ "$COUNT" != "0" ] || [ "$ADDED" != "0" ]', flow)
        # 記事の受け箱の数え方（content/muse_inbox/*.md）に追記が混ざらない置き場
        self.assertEqual(ma.INBOX, ROOT / "content" / "muse_inbox" / "addenda")
        self.assertEqual(ma.muse_articles.INBOX, ROOT / "content" / "muse_inbox")

    def test_format_tells_the_writer_how(self):
        self.assertIn("対象スラッグ: ", muse_format.FORMAT_MD)
        self.assertIn("addenda/", muse_format.FORMAT_MD)
        self.assertNotIn("｜", muse_format.FORMAT_MD.split("## もう出ている記事への追記", 1)[1].split("## 結果の見方", 1)[0])
        # 書式の見本は、そのまま読める形
        example = muse_format.FORMAT_MD.split("## もう出ている記事への追記", 1)[1].split("```")[1]
        self.assertEqual(ma.target_candidates(example.split("##", 1)[0]), ["apbc-2026-final-tbs-prime-video"])


if __name__ == "__main__":
    unittest.main()
