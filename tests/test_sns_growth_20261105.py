"""2026-11-05 とろいも案 v1 の SNS の伸ばし方（台帳 S27〜S31）。

S27 1日6枠（7:15・8:10・12:15・18:45・20:30・21:45）・自分の投稿は1日6本まで（速報も数える。ミサイル・災害は数えない）・レーンで選ぶ
S28 海外の企業向け・開発者向けの話題は SNS に出さない（サイトだけ。すべての経路＝門番 sns_rules のルール10）
S29 記事のリンクの utm_content=<投稿の種類>_<リンクの位置>（門番のルール11）。canonical はクエリなし
S30 Muse の動画の受け渡し（待ち4時間・速報0・来なければ今の自動動画）／Muse の型の文面（SNS_HOOK_FORMAT=1 のときだけ）
S31 Threads のリンクの位置の比べ（THREADS_LINK_AB=1 のときだけ）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: E402,F401  unittest でも自動投稿のスイッチを戻したときの決まり（auto_post=true）で動かす（tests/conftest.py・2026-11-10）

import growth_indicators as gi  # noqa: E402
import inflow_report  # noqa: E402
import muse_ingest  # noqa: E402
import muse_queue  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules as r  # noqa: E402
import sns_video_followup as fu  # noqa: E402
import threads_post as tp  # noqa: E402

JST = timezone(timedelta(hours=9))
LINK = "https://ai-tech-express.jp/articles/acme-tool"
ART = {"slug": "acme-tool", "title": "Acme が新しいAIツールを公開", "genreSlug": "ai", "_virtual": True}
AWS = {"slug": "aws-x", "title": "AWS、Bedrockの新モデルをインド国内で提供", "tags": ["AWS"], "sourceUrl": "https://aws.amazon.com/blogs/x",
       "verdict": {"audience": "開発者"}}
YUCHO = {"slug": "yucho", "title": "ゆうちょ銀行、松井証券の議決権約20%を取得へ", "lede": "ゆうちょ銀行が松井証券の議決権の19.99%を取得します。",
         "sourceUrl": "https://www.jp-bank.japanpost.jp/aboutus/press/2026/x.html", "sourceType": "web", "sourceName": "ゆうちょ銀行",
         "generatedAt": "2026-11-04T10:27:00+00:00"}
HONDA = {"slug": "honda", "title": "ホンダ、初のハイエンド電動MTB「RN0」を公開　車重約24kg", "sourceUrl": "https://global.honda/jp/news/x.html",
         "sourceType": "web", "generatedAt": "2026-11-04T10:00:00+00:00"}


def at(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=JST).astimezone(timezone.utc)


class SlotsAndCapTest(unittest.TestCase):
    def setUp(self):
        p = patch.multiple(tp, DIGEST_ON=False)
        p.start()
        self.addCleanup(p.stop)
        q = patch.object(sns_plan, "video_skipped", return_value=set())
        q.start()
        self.addCleanup(q.stop)

    def test_six_slots_from_the_plan(self):
        # 2026-11-06 テストの日（台帳 S39）から4枠・1日5本
        self.assertEqual(tp.SLOTS_JST, [(7, 15), (12, 15), (18, 45), (20, 30)])
        self.assertEqual(sns_plan.daily_cap(), 5)
        self.assertEqual(tp.DIGEST_SLOT_JST, (7, 15))

    def test_close_slots_are_both_usable(self):
        # 18:45 と 20:30（105分）はどちらも使える（間隔は45分）。2026-11-06〜 8:10・21:45 の枠は無い（S39）
        slots = tp.free_slots({"posted": {}}, at(5, 6, 0))
        self.assertEqual([s.astimezone(JST).strftime("%H:%M") for s in slots], ["07:15", "12:15"])
        slots = tp.free_slots({"posted": {}}, at(5, 15, 0))
        self.assertEqual([s.astimezone(JST).strftime("%H:%M") for s in slots], ["18:45", "20:30"])

    def test_daily_cap_counts_neither_breaking_nor_disaster(self):
        # 2026-11-06 オーナー決定（S41）: 速報は上限に数えない。通常の投稿だけで5本
        posted = {f"b{i}": {"id": f"t{i}", "breaking": True, "dueAt": at(5, 9, i).isoformat()} for i in range(3)}
        base = len(tp.free_slots({"posted": {}}, at(5, 15, 0)))
        self.assertEqual(len(tp.free_slots({"posted": posted}, at(5, 15, 0))), base)  # 速報3本でも枠は減らない
        posted["quake"] = {"id": "q", "disaster": True, "dueAt": at(5, 10, 0).isoformat()}
        self.assertEqual(len(tp.free_slots({"posted": posted}, at(5, 15, 0))), base)  # 災害も数えない
        posted.update({f"c{i}": {"id": f"c{i}", "dueAt": at(5, 11, i).isoformat()} for i in range(5)})
        self.assertEqual(tp.free_slots({"posted": posted}, at(5, 15, 0)), [])  # 通常5本で満杯

    def test_cap_exempt_by_title(self):
        self.assertTrue(sns_plan.cap_exempt({"title": "北朝鮮が弾道ミサイルを発射"}))
        self.assertFalse(sns_plan.cap_exempt({"title": "ゆうちょ銀行が松井証券に出資"}))

    def test_breaking_respects_cap(self):
        text = (ROOT / "scripts" / "breaking_post.py").read_text("utf-8")
        self.assertIn("sns_plan.daily_cap()", text)
        self.assertIn("sns_plan.excluded(article)", text)


class LaneAndExcludeTest(unittest.TestCase):
    def test_lanes(self):
        self.assertEqual(sns_plan.lane_of(YUCHO)[0], "money")
        self.assertEqual(sns_plan.lane_of(HONDA)[0], "brand")
        self.assertEqual(sns_plan.lane_of({"title": "無印良品のカード番号が流出した可能性"})[0], "safety")
        self.assertEqual(sns_plan.lane_of({"title": "Audio の新しい技術"})[0], "")  # 「au」の誤検知なし

    def test_api_and_business_words_pass_when_ordinary_people_care(self):
        """2026-11-08 オーナー決定（台帳 S28 を狭めた）: 外すのは開発者向けだけ。「API」「法人向け」は一般の人に関係する話題なら外さない"""
        self.assertEqual(sns_plan.excluded({"title": "OpenAI、ChatGPTのAPI料金を値下げ", "sourceUrl": "https://openai.com/x"}), "")
        self.assertEqual(sns_plan.excluded({"title": "法人向けChatGPTの料金を改定", "sourceUrl": "https://openai.com/x"}), "")
        self.assertTrue(sns_plan.excluded({"title": "新しいAPIを開発者向けに公開", "sourceUrl": "https://example.com/x"}))
        self.assertTrue(sns_plan.excluded({"title": "企業向けのデータ連携の仕組み", "sourceUrl": "https://example.com/x"}))

    def test_foreign_enterprise_is_excluded_everywhere(self):
        self.assertTrue(sns_plan.excluded(AWS))
        self.assertEqual(sns_plan.excluded(YUCHO), "")
        # 日本の会社の発表（.jp）は外さない。海外の会社の日本語のページ（/jp/）は海外として扱う
        self.assertEqual(sns_plan.excluded({"title": "NTT、API の料金を改定", "sourceUrl": "https://group.ntt/jp/x"}), "")
        self.assertTrue(sns_plan.excluded({"title": "Salesforce、Agentforce に新機能", "sourceUrl": "https://www.salesforce.com/jp/news/x"}))
        # 門番（すべての経路）も止める
        text = f"{AWS['title']}\n\nhttps://ai-tech-express.jp/articles/aws-x?utm_source=threads&utm_medium=social&utm_campaign=classic&utm_content=video_body"
        with patch.object(r, "ARTICLES_DIR", Path("/nonexistent")):
            out = r.check_post("threads", text, [], {**AWS, "_virtual": True}, pending_video=True)
        self.assertTrue(any(v.startswith("[ルール10]") for v in out), out)

    def test_candidates_prefer_lanes_and_skip_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            now = datetime.now(timezone.utc).isoformat()
            for a in (AWS, YUCHO, HONDA, {"slug": "plain", "title": "ある会社が新しい取り組みを紹介"}):
                Path(d, f"{a['slug']}.json").write_text(json.dumps({**a, "generatedAt": now, "genreSlug": "business"}, ensure_ascii=False))
            with patch.object(tp, "ARTICLES_DIR", Path(d)), patch.object(sns_plan, "muse_slugs", return_value=set()):
                got = [a["slug"] for a in tp.candidates({"posted": {}}, 24)]
        self.assertNotIn("aws-x", got)
        self.assertEqual(got[:2], ["yucho", "honda"])  # お金（5）> ブランド（4）> レーンなし


class UtmTest(unittest.TestCase):
    def test_every_link_has_type_and_position(self):
        self.assertTrue(tp.utm_link(LINK, "threads", "classic").endswith("utm_content=video_body"))
        self.assertTrue(tp.utm_link(LINK, "x", "classic").endswith("utm_content=video_reply"))
        self.assertTrue(tp.utm_link(LINK, "threads", "digest").endswith("utm_content=digest_body"))
        self.assertIn("utm_campaign=sns_video_full&utm_content=video_body", tp.utm_link(LINK, "threads", "sns_video", "full"))
        self.assertEqual(tp.post_type({**ART, "disaster": True}), "card")
        self.assertEqual(tp.post_type({**ART, "_hookFormat": True}), "hook")

    def test_gate_requires_utm_content(self):
        good = f"{LINK}?utm_source=threads&utm_medium=social&utm_campaign=classic&utm_content=video_body"
        bad = f"{LINK}?utm_source=threads&utm_medium=social&utm_campaign=classic"
        self.assertEqual(r.check_link("threads", f"本文\n{good}", "", [], ["/articles/acme-tool"]), [])
        self.assertTrue(any("ルール11" in v for v in r.check_link("threads", f"本文\n{bad}", "", [], ["/articles/acme-tool"])))

    def test_video_variant_old_and_new(self):
        self.assertEqual(inflow_report.video_variant("sns_video_short", "video_body"), "short")
        self.assertEqual(inflow_report.video_variant("sns_video", "full"), "full")
        self.assertEqual(inflow_report.video_variant("classic", "video_body"), "")
        ts = (ROOT / "cloudflare" / "inflow.ts").read_text("utf-8")
        self.assertIn('campaign === "sns_video_short"', ts)

    def test_followup_keeps_post_type(self):
        report = {"url": LINK, "total": 40, "level": "MUSE"}
        text = f"1行目\n2行目\n記事に\n\n{LINK}?utm_source=threads&utm_medium=social&utm_campaign=classic&utm_content=hook_body"
        new, _ = fu.merged_text(text, report, "short")
        self.assertIn("utm_campaign=sns_video_short&utm_content=hook_body", new)
        self.assertNotIn("動画で解説", new)  # 2026-11-06〜 決まった動画の行は足さない（台帳 S39）


# 2026-11-09 から投稿は動画を待たない（muse.wait_hours=0・台帳 S48）。待ちの仕組みそのものは前の1時間で確かめる
@patch.dict(sns_plan.plan()["muse"], {"wait_hours": 1, "max_wait_hours": 1})
class MuseTest(unittest.TestCase):
    def queue(self, items):
        return patch.object(sns_plan, "load_muse_queue", return_value={"items": items})

    def test_pick_rules(self):
        # 2026-11-05 夕方〜（オーナー「動画を作る記事を限定」）: SNS の予定のうち、ビューを取れる話題（muse_score > 0）だけを
        # 点数の高い順に、枠の日ごとに4本まで。速報と出さない話題は入れない
        now = datetime(2026, 11, 4, 22, 0, tzinfo=timezone.utc)  # 7:00 JST

        def rec(hh, mm, **kw):
            slot = at(5, hh, mm)
            return {"status": "awaiting_video", "dueAt": slot.isoformat(), "pending": {"slot": slot.isoformat(), "inputs": {"threads": {}}}, **kw}

        posted = {"honda": rec(12, 15), "yucho": rec(8, 10), "aws-x": rec(18, 45), "brk": rec(9, 0, breaking=True), "done": {"id": "x", "dueAt": at(5, 8, 0).isoformat()}}
        arts = [YUCHO, HONDA, AWS, {**YUCHO, "slug": "brk"}, {**YUCHO, "slug": "done"}]
        with self.queue([]), patch.object(sns_plan, "muse_slugs", return_value=set()):
            got = muse_queue.pick({"items": []}, now, arts, posted)
        self.assertEqual([g["slug"] for g in got], ["yucho", "honda"])
        self.assertTrue(all(g["status"] == "queued" and g["file"] == f"news-{g['slug']}.mp4" for g in got))
        self.assertEqual(got[0]["url"], "https://ai-tech-express.jp/articles/yucho")
        self.assertEqual(got[0]["slot"], at(5, 8, 10).isoformat())
        self.assertEqual(got[0]["deadline"], (at(5, 8, 10) + timedelta(hours=1)).isoformat())  # 待つのは枠から1時間まで
        self.assertTrue(got[0]["title"])
        self.assertTrue(all(g["score"] > 0 for g in got))
        full = {"items": [{"slug": f"s{i}", "slot": at(5, 7, i).isoformat(), "queuedAt": now.isoformat(), "status": "queued", "score": 8} for i in range(4)]}
        self.assertEqual(muse_queue.pick(full, now, arts, posted), [])  # 枠の日ごとに2本まで（2026-11-06〜・S39）
        # 以前の「すべての投稿を Muse で」の点数0の項目は数えず、選び直す
        old = {"items": [{"slug": f"s{i}", "slot": at(5, 7, i).isoformat(), "queuedAt": now.isoformat(), "status": "queued", "score": 0} for i in range(6)]
                         + [{"slug": "yucho", "slot": at(5, 8, 10).isoformat(), "status": "queued", "score": 0}]}
        self.assertEqual(sorted(g["slug"] for g in muse_queue.pick(old, now, arts, posted)), ["honda", "yucho"])
        # 点数の高い順に選ぶ（上限が残り1本なら yucho（9点）を honda（8点）より先に）
        three = {"items": [{"slug": f"s{i}", "slot": at(5, 7, i).isoformat(), "status": "queued", "score": 8} for i in range(1)]}
        self.assertEqual([g["slug"] for g in muse_queue.pick(three, now, arts, posted)], ["yucho"])
        plain = {**YUCHO, "slug": "plain", "title": "ゆうちょ銀行がお知らせを更新", "lede": "お知らせです。"}
        self.assertEqual(muse_queue.pick({"items": []}, now, [plain], {"plain": rec(12, 15)}), [])  # 立つ数字の無い記事は動画を作らない

    def test_wait_until(self):
        slot = datetime(2026, 11, 5, 3, 15, tzinfo=timezone.utc)
        item = {"slug": "yucho", "status": "queued", "queuedAt": "2026-11-04T22:00:00+00:00", "score": 9}
        data = {"items": [item]}
        self.assertEqual(sns_plan.muse_wait_until("yucho", slot, data=data), slot + timedelta(hours=1))
        self.assertIsNone(sns_plan.muse_wait_until("yucho", slot, data={"items": [{**item, "score": 0}]}))  # 以前の点数0の項目は待たない
        with patch.dict(os.environ, {"MUSE_WAIT_HOURS": "4"}):
            self.assertEqual(sns_plan.muse_wait_until("yucho", slot, data=data), slot + timedelta(hours=1))  # 変数でも1時間より長くしない
        self.assertIsNone(sns_plan.muse_wait_until("yucho", slot, breaking=True, data=data))
        self.assertIsNone(sns_plan.muse_wait_until("other", slot, data=data))

    def test_publish_waits_for_muse_then_falls_back(self):
        slot = datetime(2026, 11, 5, 3, 15, tzinfo=timezone.utc)
        rec = {"id": "", "status": "awaiting_video", "dueAt": slot.isoformat(), "pending": {"slot": slot.isoformat(), "inputs": {"threads": {}}}}
        item = {"slug": "yucho", "status": "queued", "queuedAt": slot.isoformat(), "score": 9}
        with self.queue([item]):
            out = fu.publish_queued({"videos": {}}, {"posted": {"yucho": rec}}, slot + timedelta(minutes=40), {"post": True, "ab_until": "", "after_ab": "short"},
                                    creator=lambda *a: self.fail("送ってはいけない"), issue=lambda *a: self.fail("issue を立ててはいけない"),
                                    eligible=lambda s: True, remote=lambda s: {})
            self.assertIn("Muse の動画", out[0]["why"])
            # 枠の時刻までは自動動画を作らない。枠を過ぎたら Muse が来なかったときの予備を作っておく（2026-11-05〜。投稿は期限まで Muse を待つ）
            posted = {"posted": {"yucho": {**rec, "postedAt": slot.isoformat()}}}
            item_early = {**item, "queuedAt": (slot - timedelta(hours=3)).isoformat()}
            with self.queue([item_early]):
                pick = fu.candidates(posted, {"videos": {}}, slot - timedelta(hours=1), 12, load_article=lambda s: YUCHO, eligible=lambda a: True, score=lambda a: 0)
            self.assertEqual(pick, [])
            pick = fu.candidates(posted, {"videos": {}}, slot + timedelta(minutes=30), 12, load_article=lambda s: YUCHO, eligible=lambda a: True, score=lambda a: 0)
            self.assertEqual(pick, ["yucho"])

    def test_muse_video_passes_quality_bar(self):
        info = {"seconds": 62.0, "width": 1920, "height": 1080, "audio": True, "bytes": 5_000_000, "codec": "h264"}
        rec = muse_ingest.video_record("yucho", info, {"short": "https://ai-tech-express.jp/video/y.mp4"}, YUCHO, datetime.now(timezone.utc), False, "test")
        self.assertTrue(fu.qa_ok(rec["versions"]["short"], env={}))
        self.assertEqual(muse_ingest.problems(info), [])
        self.assertTrue(muse_ingest.problems({**info, "seconds": 20}))
        self.assertTrue(muse_ingest.problems({**info, "width": 1280, "height": 720}))
        self.assertTrue(muse_ingest.problems({**info, "audio": False}))

    def test_apply_state_overrides_auto_video_and_marks_delivered(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "state").mkdir()
            (Path(d) / "state" / "sns_video.json").write_text(json.dumps({"videos": {"yucho": {"status": "ready", "adopted": ""}}}))
            (Path(d) / "state" / "muse_queue.json").write_text(json.dumps({"items": [{"slug": "yucho", "status": "queued"}]}))
            info = {"seconds": 62.0, "width": 1080, "height": 1920, "audio": True, "bytes": 1}
            rec = muse_ingest.video_record("yucho", info, {"short": "u"}, YUCHO, datetime.now(timezone.utc), True, "test")
            muse_ingest.apply_state(Path(d), "yucho", rec, datetime.now(timezone.utc))
            v = json.loads((Path(d) / "state" / "sns_video.json").read_text())
            self.assertEqual(v["videos"]["yucho"]["adopted"], "muse")
            self.assertEqual(v["videos"]["yucho"]["status"], "held")  # --hold は投稿に使わない
            self.assertTrue(v["videosArchive"])
            q = json.loads((Path(d) / "state" / "muse_queue.json").read_text())
            self.assertEqual(q["items"][0]["status"], "delivered")
            muse_ingest.apply_state(Path(d), "yucho", None, datetime.now(timezone.utc), release=True)
            self.assertEqual(json.loads((Path(d) / "state" / "sns_video.json").read_text())["videos"]["yucho"]["status"], "ready")


HOOK3 = "ゆうちょ銀行が、松井証券の議決権の19.99%を取得します。\n口座を持つ人の資産運用の選択肢が広がる可能性があります。\n対象・条件・まだ分からないことは記事にまとめました。"


class FlagsTest(unittest.TestCase):
    def body(self, text: str) -> str:
        return f"{text}\n\n{LINK}?utm_source=threads&utm_medium=social&utm_campaign=classic&utm_content=hook_body"

    def test_flags_default_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SNS_HOOK_FORMAT", None)
            os.environ.pop("THREADS_LINK_AB", None)
            self.assertFalse(sns_plan.hook_format_on())
            self.assertEqual(sns_plan.threads_link_position({"a": {"linkPosition": "body"}}), "body")

    def test_hook_format_only_with_flag(self):
        with patch.object(r, "ARTICLES_DIR", Path("/nonexistent")):
            with patch.dict(os.environ, {"SNS_HOOK_FORMAT": "0"}):
                off = r.check_post("threads", self.body(HOOK3), [], ART, pending_video=True)
            with patch.dict(os.environ, {"SNS_HOOK_FORMAT": "1"}):
                on = r.check_post("threads", self.body(HOOK3), [], ART, pending_video=True)
        self.assertTrue(any("ルール6" in v or "ルール1" in v for v in off), off)  # 今の S1 では止まる
        self.assertEqual(on, [])
        self.assertTrue(r.hook_problems("1行目だけ"))

    def test_compose_hook3_uses_only_article_numbers(self):
        art = {**YUCHO, "workMoney": {"points": ["口座を持つ人の資産運用の選択肢が広がる可能性があります。"]}}
        text = tp.compose_hook3(art)
        self.assertEqual(r.hook_problems(text), [])
        self.assertIn("19.99%", text)
        self.assertFalse(tp.hook3_facts_ok(["ゆうちょ銀行が30%を取得します。"], art))

    def test_link_ab_alternates_and_gate_allows_reply_only_with_flag(self):
        # S31 は 2026-11-05 夕方に終了（オーナー「すべて本文にリンクにしよう今後は」）: 変数が 1 でも返信のリンクは通さない
        reply = f"{LINK}?utm_source=threads&utm_medium=social&utm_campaign=classic&utm_content=video_reply"
        for flag in ("1", "0"):
            with patch.dict(os.environ, {"THREADS_LINK_AB": flag}):
                self.assertEqual(sns_plan.threads_link_position({"a": {"linkPosition": "body"}}), "body")
                self.assertTrue(r.check_link("threads", "本文", reply, [], ["/articles/acme-tool"]))


class FastLangTest(unittest.TestCase):
    def test_japanese_notice_is_japanese(self):
        import web_articles

        self.assertEqual(web_articles.fast_lang({}, {"lang": "ja"}, "https://www.arara.com/x.pdf"), "ja")
        self.assertEqual(web_articles.fast_lang({}, {}, "https://www.biccamera.co.jp/x"), "ja")
        self.assertEqual(web_articles.fast_lang({}, {}, "https://openai.com/x"), "en")
        self.assertEqual(web_articles.fast_lang({"lang": "en"}, {"lang": "ja"}, "https://x.jp/"), "en")


class IndicatorsTest(unittest.TestCase):
    def test_offline_build(self):
        sent = at(5, 12, 15)
        posted = {"posted": {"honda": {"id": "t1", "sentAt": sent.isoformat(), "channels": {"twitter": "x1"}, "metrics": {"views": 2456},
                                       "metricsUpdatedAt": (sent + timedelta(hours=30)).isoformat()},
                             "low": {"id": "t2", "sentAt": sent.isoformat(), "metrics": {"views": 6}}}}
        files = {"threads_posted.json": posted, "sns_video.json": {}, "bluesky_extra.json": {}}
        with patch.object(gi, "load", side_effect=lambda n: files[n]):
            got = gi.build(date(2026, 11, 5), net=False)
        self.assertEqual(got["posts"], {"threads": 2, "x": 1, "facebook": 0, "bluesky": 0, "instagram": 0})
        self.assertEqual(got["views"]["h24_max"], 2456)
        self.assertEqual(got["hits_day"], ["honda"])
        self.assertEqual(gi.target_for(date(2026, 11, 13))[2], "W2")


sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -m unittest tests.X でも同じフォルダの補助を読めるように
import legacy_sns_plan  # noqa: E402  2026-11-08 より前の枠の数で動かす（台帳 S47。今の数は tests/test_sns_volume_20261108.py）


def setUpModule():
    legacy_sns_plan.start()


def tearDownModule():
    legacy_sns_plan.stop()


if __name__ == "__main__":
    unittest.main()
