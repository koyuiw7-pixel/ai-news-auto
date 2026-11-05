"""2026-11-05 オーナー指摘（台帳 S37・S38）。ネット接続・投稿なし。

  S37 同じことを2回書かない: 11:00 のアララの投稿で、書き出しと事実の1文目が同じ「約7,700万件が流出した恐れ」だった
      （LLM の書き直しが書き出しを見ていなかった）。作る所で外して次の新しい事実で埋め、門番（ルール16）も全部の SNS で止める・直す。
  S38 前の晩に Buffer に予約した熊本地震の投稿が、決まりを変えたあとも古い「詳しくはこちら👇（かんたん版あり）」のまま出た。
      門番（ルール17）が残りを止め、autofix がリンクだけの行にする。出る前に予約を読み直して直す（sns_video_followup.presend_recheck）
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sns_rules  # noqa: E402
import sns_video_followup as svf  # noqa: E402
import threads_post as tp  # noqa: E402

VIDEO = [{"type": "video", "url": "https://ai-tech-express.jp/video/x.mp4", "width": 1920, "height": 1080}]

ARARA = {
    "slug": "arara-message-data-leak-second-report", "_virtual": True, "genreSlug": "business",
    "title": "アララのメール配信で約7,700万件流出の恐れ　「利用内容確認のご依頼」の不審メールに注意",
    "tags": ["情報流出", "サイバー攻撃", "メール配信", "個人情報", "ビジネス"], "threadsStyle": 3,
    "lede": "メール配信サービス「アララメッセージ」で、メールアドレス約7,700万件が持ち出された恐れがあります（11月2日の第2報）。"
            "カード会社を装った不審なメールも最大約713万通送られ、送信元は「news@arara.com」、件名は「利用内容確認のご依頼」などです。",
    "description": "アララのメール配信サービス「アララメッセージ」で、メールアドレス約7,700万件が持ち出された恐れがあります。",
    "highlights": ["アララメッセージへの不正アクセスが広がり、持ち出されたメールアドレスは約7,700万件（精査中）",
                   "被害は共用環境の1システムから、契約企業の環境のサーバー97台に拡大。対象は最大約380社と推計",
                   "サービスは10月31日から止まっていて再開は未定。件数の精査の結果は第3報で示される予定"],
    "threadsPost": "メール配信サービスの担当の皆さん、確認してほしい話です。\n\n要約すると、アララの「アララメッセージ」から約77百万件のメールアドレスが持ち出されました。\n"
                   "10月31日にサービスは全面停止し、再開時期は未定です。\n\nメールの配信を外部サービスに頼る場面、どこまで任せられると思いますか？",
}
OPENER = "メール配信サービス「アララメッセージ」で、メールアドレス約7,700万件が持ち出された恐れがあります。"
RESTATED = "アララのメール配信サービスで不正アクセスがあり、約7,700万件のメールアドレスが流出した恐れがあります。"
NEXT_FACT = "被害は契約企業のサーバー97台に広がり、対象は最大約380社と推計されています。"
# 2026-11-05 11:00 に Threads に出た文面そのもの（Buffer 6aebcf0401b5398f879db1bb）
LIVE_ARARA = (f"{OPENER}\n\n{RESTATED}\n{NEXT_FACT}\n60秒の動画で解説しています。\n\n"
              "https://ai-tech-express.jp/articles/arara-message-data-leak-second-report?utm_source=threads&utm_medium=social&utm_campaign=sns_video_short&utm_content=video_body")

KUMAMOTO = {
    "slug": "kumamoto-quake-risai-online-application", "_virtual": True, "genreSlug": "public",
    "title": "熊本地震のり災証明書、14市町でオンライン申請　大津町は11月30日まで", "tags": ["熊本地震", "り災証明書", "マイナポータル"],
}
KUMAMOTO_URL = ("https://ai-tech-express.jp/articles/kumamoto-quake-risai-online-application"
                "?utm_source=threads&utm_medium=social&utm_campaign=sns_video_short&utm_content=video_body")
# 前の晩（2026-11-04T21:30Z）に Buffer に入った、古い決まりの文面の形
OLD_KUMAMOTO = ("熊本地震のり災証明書は、熊本市など14市町でオンライン申請できます。\n\n"
                "マイナポータルか、自治体ごとの専用ページから申請できます。\n大津町は11月30日で受付を終えます。\n"
                f"60秒の動画で解説しています。\n\n詳しくはこちら👇（かんたん版あり）\n{KUMAMOTO_URL}")


def utm(platform: str) -> str:
    src = {"x": "x"}.get(platform, platform)
    return (f"https://ai-tech-express.jp/articles/{ARARA['slug']}?utm_source={src}&utm_medium=social"
            f"&utm_campaign=sns_video_short&utm_content=video_body")


class DuplicateLineTest(unittest.TestCase):
    def test_exact_live_example_is_a_duplicate(self):
        self.assertTrue(sns_rules.near_duplicate(OPENER, RESTATED))
        self.assertEqual(sns_rules.duplicate_lines(LIVE_ARARA), [(OPENER, RESTATED)])

    def test_gate_blocks_duplicate_on_every_channel(self):
        for platform in ("threads", "facebook", "bluesky", "x", "instagram"):
            body = f"{OPENER}\n\n{RESTATED}\n{NEXT_FACT}"
            if platform == "instagram":
                text, links, reply = f"{body}\n\n{sns_rules.INSTAGRAM_LINK_LINE}", [utm(platform)], ""
            elif platform == "x":
                text, links, reply = body, [], utm(platform)
            else:
                text, links, reply = f"{body}\n\n{utm(platform)}", [], ""
            problems = sns_rules.check_post(platform, text, VIDEO, ARARA, reply_text=reply, links=links)
            self.assertTrue(any(p.startswith("[ルール16]") for p in problems), (platform, problems))

    def test_autofix_drops_the_restated_line_and_then_passes(self):
        fixed, changes = sns_rules.autofix(LIVE_ARARA, ARARA, "threads")
        self.assertNotIn(RESTATED, fixed)
        self.assertIn(OPENER, fixed)
        self.assertIn(NEXT_FACT, fixed)
        self.assertTrue(any("ルール16" in c for c in changes))
        self.assertEqual(sns_rules.check_post("threads", fixed, VIDEO, ARARA), [])

    def test_buffer_input_is_fixed_before_sending(self):
        inp = {"text": LIVE_ARARA, "metadata": {"threads": {"thread": [{"text": LIVE_ARARA, "assets": [{"video": {"url": VIDEO[0]["url"]}}]}]}}}
        sns_rules.autofix_buffer_input("threads", inp, ARARA)
        self.assertNotIn(RESTATED, inp["text"])
        self.assertNotIn(RESTATED, inp["metadata"]["threads"]["thread"][0]["text"])

    def test_different_facts_are_not_duplicates(self):
        pairs = [
            ("楽天モバイルが新しいプランを月額980円で始めます。", "料金は月額980円で、12月1日から申し込めます。"),
            ("気象庁が11月5日10時ごろに緊急地震速報の訓練を行います。", "テレビ・ラジオや緊急速報メールには流れません。"),
            (OPENER, NEXT_FACT),
            ("Acme社は本社を2027年春に大阪へ移します。", "新しい本社には約500人が勤めます。"),
        ]
        for a, b in pairs:
            self.assertFalse(sns_rules.near_duplicate(a, b), (a, b))

    def test_composer_replaces_a_restating_llm_summary_with_the_next_fact(self):
        restating = f"{RESTATED}\n{NEXT_FACT}"
        with patch.object(tp, "llm_summary", return_value=restating), patch.object(tp, "llm_fact_opener", return_value=OPENER):
            text = tp.compose(dict(ARARA), [], use_llm=True)
        self.assertTrue(text.startswith(OPENER))
        self.assertNotIn(RESTATED, text)
        self.assertEqual(sns_rules.duplicate_lines(text), [])
        self.assertGreaterEqual(len(sns_rules.blocks_of(text)[1].splitlines()), 2, text)  # 次の新しい事実で2文に戻す

    def test_composer_without_llm_has_no_duplicate(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": ""}):
            text = tp.compose(dict(ARARA), [])
        self.assertEqual(sns_rules.duplicate_lines(text), [])

    def test_hook3_with_restated_lines_is_not_used(self):
        art = dict(ARARA, lede=f"{OPENER}", workMoney={"points": [RESTATED]})
        self.assertEqual(tp.compose_hook3(art), "")


class OldFooterTest(unittest.TestCase):
    def test_gate_blocks_the_old_footer(self):
        problems = sns_rules.check_post("threads", OLD_KUMAMOTO, VIDEO, KUMAMOTO)
        self.assertTrue(any(p.startswith("[ルール17]") for p in problems), problems)
        for leftover in ("本文です。\n\n（かんたん版あり）", "本文です👇"):
            self.assertTrue(any(p.startswith("[ルール17]") for p in sns_rules.check_post("facebook", leftover, VIDEO, KUMAMOTO)))

    def test_autofix_keeps_only_the_link(self):
        fixed, changes = sns_rules.autofix(OLD_KUMAMOTO, KUMAMOTO, "threads")
        self.assertNotIn("👇", fixed)
        self.assertNotIn("かんたん版", fixed)
        self.assertNotIn("詳しくはこちら", fixed)
        self.assertTrue(fixed.rstrip().endswith(KUMAMOTO_URL))
        self.assertTrue(changes)
        self.assertFalse([p for p in sns_rules.check_post("threads", fixed, VIDEO, KUMAMOTO) if p.startswith(("[ルール17]", "[ルール14]"))])

    def test_url_on_the_same_line_is_kept(self):
        fixed, _ = sns_rules.autofix(f"本文です。\n\n詳しくはこちら👇（かんたん版あり） {KUMAMOTO_URL}", KUMAMOTO, "facebook")
        self.assertEqual(fixed.splitlines()[-1], KUMAMOTO_URL)

    def test_morning_digest_arrow_is_left_alone(self):
        digest = {"link": "https://ai-tech-express.jp/digest/2026-11-05", "items": ["a", "b"]}
        text = "ほかの新着もサイトにまとめています👇\nhttps://ai-tech-express.jp/digest/2026-11-05"
        self.assertEqual(sns_rules.autofix(text, digest, "threads")[0], text)


NOW = datetime(2026, 11, 5, 1, 0, tzinfo=timezone.utc)  # 10:00 日本時間


def node(pid: str, service: str, text: str, due: datetime, slug: str = "kumamoto-quake-risai-online-application") -> dict:
    video = [{"mimeType": "video/mp4", "source": "https://ai-tech-express.jp/video/k.mp4"}]
    if service == "facebook":
        return {"id": pid, "service": service, "status": "scheduled", "dueAt": due.isoformat(), "text": text, "assets": video, "metadata": {}}
    return {"id": pid, "service": service, "status": "scheduled", "dueAt": due.isoformat(), "text": text, "assets": [],
            "metadata": {"thread": [{"text": text, "assets": video}]}}


class PresendRecheckTest(unittest.TestCase):
    def setUp(self):
        self.edits, self.pauses, self.issues = [], [], []
        self.due = NOW + timedelta(hours=2, minutes=15)
        self.posted = {"posted": {"kumamoto-quake-risai-online-application": {"status": "scheduled", "id": "6aeba4f5dce07267a1944fc2",
                                                                              "dueAt": self.due.isoformat(), "channels": {}}}}

    def editor(self, key, inp, article=None, service="threads"):
        self.edits.append((service, inp))
        return {"status": "scheduled", "dueAt": self.due.isoformat()}

    def run_check(self, nodes, apply=True, force=False, state=None, rebuild=None):
        state = state if state is not None else {"videos": {}}
        reader = lambda key, pid, raise_unavailable=False: {"status": "scheduled", "dueAt": self.due.isoformat(), "metadata": {"topic": "ニュース"}}  # noqa: E731
        with patch.object(svf, "node_problems", side_effect=self.fake_problems):
            return svf.presend_recheck(apply=apply, now=NOW, api_key="k", force=force, state=state, posted=self.posted, nodes=nodes,
                                       editor=self.editor, reader=reader, pauser=lambda k, n: self.pauses.append(n) or {"status": "draft"},
                                       rebuild=rebuild or (lambda *a: (_ for _ in ()).throw(RuntimeError("no rebuild"))),
                                       issue=lambda slug, why: self.issues.append(why)), state

    def fake_problems(self, n):
        thread = (n.get("metadata") or {}).get("thread") or []
        text = (thread[0].get("text") if thread else "") or n.get("text") or ""
        return ("kumamoto-quake-risai-online-application", True,
                sns_rules.check_post({"twitter": "x"}.get(n["service"], n["service"]), text, [], KUMAMOTO, pending_video=True))

    def test_old_footer_post_is_edited_in_place_and_keeps_time_and_video(self):
        rows, state = self.run_check([node("6aeba4f5dce07267a1944fc2", "threads", OLD_KUMAMOTO, self.due)])
        self.assertEqual(len(self.edits), 1, rows)
        service, inp = self.edits[0]
        self.assertEqual(service, "threads")
        self.assertNotIn("dueAt", inp)
        self.assertNotIn("mode", inp)
        thread = inp["metadata"]["threads"]["thread"]
        self.assertNotIn("👇", thread[0]["text"])
        self.assertNotIn("かんたん版", thread[0]["text"])
        self.assertEqual(thread[0]["assets"], [{"video": {"url": "https://ai-tech-express.jp/video/k.mp4"}}])
        self.assertEqual(inp["metadata"]["threads"]["topic"], "ニュース")
        self.assertEqual(rows[0]["action"], "autofix")
        self.assertIn("6aeba4f5dce07267a1944fc2", state["presend"])
        self.assertFalse(self.pauses)

    def test_plan_only_lists_and_does_not_edit(self):
        rows, _ = self.run_check([node("p1", "facebook", OLD_KUMAMOTO, self.due)], apply=False, force=True)
        self.assertEqual(rows[0]["action"], "plan")
        self.assertTrue(any(p.startswith("[ルール17]") for p in rows[0]["problems"]))
        self.assertFalse(self.edits)

    def test_no_buffer_read_when_nothing_is_due_or_already_checked(self):
        calls = []
        far = {"posted": {"x": {"status": "scheduled", "id": "far", "dueAt": (NOW + timedelta(hours=10)).isoformat()}}}
        self.assertEqual(svf.presend_targets({}, far, NOW), [])
        state = {"presend": {"6aeba4f5dce07267a1944fc2": {"rules": svf.rules_version(), "at": NOW.isoformat()}}}
        self.assertEqual(svf.presend_targets(state, self.posted, NOW), [])
        with patch.object(svf, "scheduled_nodes", side_effect=lambda *a, **k: calls.append(a) or []):
            out = svf.presend_recheck(apply=True, now=NOW, api_key="k", state=state, posted=self.posted)
        self.assertEqual(out, [])
        self.assertEqual(calls, [])  # Buffer を読まない
        self.assertEqual(svf.presend_targets({}, self.posted, NOW), ["6aeba4f5dce07267a1944fc2"])

    def test_unfixable_post_goes_back_to_draft_not_deleted(self):
        bad = "ガジェット好きの皆さん、これは要チェックです。\n\n" + OLD_KUMAMOTO
        with patch.object(sns_rules, "autofix", side_effect=lambda t, a=None, p="": (t, [])):
            rows, _ = self.run_check([node("u1", "twitter", bad, self.due)])
        self.assertEqual(rows[0]["action"], "paused")
        self.assertEqual(len(self.pauses), 1)
        self.assertFalse(self.edits)
        self.assertTrue(self.issues)

    def test_posts_about_to_go_out_are_not_touched(self):
        soon = NOW + timedelta(minutes=5)
        rows, _ = self.run_check([node("s1", "threads", OLD_KUMAMOTO, soon)])
        self.assertEqual(rows[0]["action"], "too_late")
        self.assertFalse(self.edits)


class WiringTest(unittest.TestCase):
    def test_hourly_run_calls_presend_and_workflow_offers_plan(self):
        src = (ROOT / "scripts" / "sns_video_followup.py").read_text("utf-8")
        self.assertIn("presend_recheck(apply=True, now=now, state=state, posted=posted)", src)
        wf = (ROOT / ".github" / "workflows" / "sns_video.yml").read_text("utf-8")
        self.assertIn("presend-plan", wf)
        self.assertIn("--presend", wf)


if __name__ == "__main__":
    unittest.main()
