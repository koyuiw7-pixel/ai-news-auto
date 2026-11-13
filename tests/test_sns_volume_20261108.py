"""2026-11-08 オーナー承認（「全て承認する」）のまとめのテスト。外部通信なし。
- S47: SNS は Threads・X・Facebook・Bluesky のそれぞれ1日15本（変数 SNS_PER_DAY）。枠は1日の中にならす。動画の失敗では投稿を落とさず写真のカードで出す
- A61: 検索に出さないのは重複・本文が無い・お金にも暮らしにもつながらない話題だけ。取り下げた記事のうちお金・暮らしの話題を戻す
- A62: 古くてもまだ役に立つ公式の知らせ（期限・始まる日がこれから、または過ぎて30日以内）は拾う
- I7: AI の画像の上限でカードにした記事は、次の日に自動で作り直す"""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: E402,F401  unittest でも自動投稿のスイッチを戻したときの決まり（auto_post=true）で動かす（tests/conftest.py・2026-11-10）
import images  # noqa: E402
import indexnow  # noqa: E402
import sns_plan  # noqa: E402
import sns_video_followup as fu  # noqa: E402
import web_articles  # noqa: E402

JST = timezone(timedelta(hours=9))


class SnsVolumeTest(unittest.TestCase):
    def test_fifteen_per_day_on_every_sns(self):
        with patch.dict(os.environ, {"SNS_PER_DAY": "15"}):
            self.assertEqual(sns_plan.per_day(), 15)
            for cap, slots in ((sns_plan.daily_cap, sns_plan.slots_jst), (sns_plan.x_daily_cap, sns_plan.x_slots_jst),
                               (sns_plan.fb_daily_cap, sns_plan.fb_slots_jst), (sns_plan.bluesky_daily_cap, sns_plan.bluesky_slots_jst)):
                self.assertEqual(cap(), 15)
                got = slots()
                self.assertEqual(len(got), 15)
                # 2026-11-10 オーナー決定（台帳 S54）: 朝6時から夜1時台まで。並びは朝6時から（0時・1時台の枠は最後）
                minutes = [sns_plan.day_order(hm) for hm in got]
                self.assertEqual(minutes, sorted(minutes))
                self.assertTrue(all(b - a >= sns_plan.min_gap().total_seconds() / 60 for a, b in zip(minutes, minutes[1:])))
                self.assertGreaterEqual(minutes[0], 0)  # 6:00 より前（2〜5時台）に枠は無い
                self.assertLess(minutes[-1], 20 * 60)  # 最後の枠は 1:59 まで（6:00 から20時間）

    def test_variable_lowers_and_spreads_but_never_raises(self):
        with patch.dict(os.environ, {"SNS_PER_DAY": "5"}):
            self.assertEqual(sns_plan.x_daily_cap(), 5)
            # 2026-11-10（台帳 S54）: 朝6時台から夜0時台まで1日の中でならす
            self.assertEqual(sns_plan.x_slots_jst(), [(6, 30), (12, 30), (17, 30), (21, 30), (0, 30)])
            self.assertIn((7, 15), sns_plan.slots_jst())  # 朝のまとめの枠は残る
            self.assertEqual(len(sns_plan.slots_jst()), 5)
        with patch.dict(os.environ, {"SNS_PER_DAY": "40"}):
            self.assertEqual(sns_plan.daily_cap(), 15)

    def test_workflows_pass_the_variable(self):
        for name in ("x_post", "facebook_post", "bluesky", "breaking_post"):
            self.assertIn("SNS_PER_DAY: ${{ vars.SNS_PER_DAY }}", (ROOT / ".github" / "workflows" / f"{name}.yml").read_text("utf-8"), name)

    def test_breaking_stays_separate(self):
        self.assertTrue(sns_plan.breaking_exempt({"breaking": True}))
        self.assertEqual(sns_plan.count_today({"a": {"id": "1", "breaking": True, "dueAt": "2026-11-08T03:00:00+00:00"}},
                                              datetime(2026, 11, 8).date()), 0)


class CardFallbackTest(unittest.TestCase):
    SLOT = datetime(2026, 11, 8, 3, 15, tzinfo=timezone.utc)

    def run_publish(self, creator, state=None):
        s = self.SLOT.isoformat()
        rec = {"id": "", "status": "awaiting_video", "dueAt": s, "pending": {"slot": s, "inputs": {"threads": {"channelId": "t", "text": "x"}}}}
        video = {"status": "ready", "urls": {"short": "https://ai-tech-express.jp/video/a.mp4"},
                 "versions": {"short": {"ok": True, "post": {"url": "https://ai-tech-express.jp/articles/a"}}}}
        state = state or {"videos": {"a": video}}
        issues = []
        with patch.object(sns_plan, "load_muse_queue", return_value={"items": []}), patch.object(fu, "qa_ok", return_value=True), \
                patch.object(fu, "probe_buffer", return_value={"probed": False}), patch.object(fu, "video_input", side_effect=lambda *a: {"video": True}):
            out = fu.publish_queued(state, {"posted": {"a": rec}}, self.SLOT + timedelta(minutes=5), {"post": True, "ab_until": "", "after_ab": "short"},
                                    creator=creator, issue=lambda *a: issues.append(a), eligible=lambda s: True, remote=lambda s: {})
        return out, issues, state

    def test_video_failure_posts_the_card_in_the_same_run(self):
        sent = []

        def creator(service, inp, article):
            sent.append(bool(inp.get("video")))
            if inp.get("video"):
                raise RuntimeError("Buffer: video processing failed")
            return "id-card"

        out, issues, _ = self.run_publish(creator)
        self.assertEqual(sent, [True, False])
        self.assertEqual(out[0]["status"], "created")
        self.assertEqual(out[0]["media"], "card")
        self.assertEqual(issues, [])

    def test_failed_post_is_retried_with_the_card_not_skipped(self):
        out, issues, state = self.run_publish(lambda *a: (_ for _ in ()).throw(RuntimeError("Scheduled time must be in the future")))
        self.assertEqual(out[0]["status"], "waiting")
        self.assertTrue(out[0]["forceCard"])
        self.assertEqual(issues, [])
        sent = []
        out, _, _ = self.run_publish(lambda s, i, a: sent.append(bool(i.get("video"))) or "id2", state=state)
        self.assertEqual(sent, [False])  # 次の回は写真のカードで
        self.assertEqual(out[0]["status"], "created")


class IndexRelaxTest(unittest.TestCase):
    BODY = "## 概要\n" + "あ" * 900

    def test_only_duplicates_empty_and_unrelated_are_noindex(self):
        a = {"slug": "x", "title": "釣八の塩さばフィーレに原産地表示違反　対象商品と農水省の指示", "genreSlug": "lifestyle", "body": self.BODY}
        self.assertIsNone(indexnow.noindex_reason(a))
        self.assertEqual(indexnow.noindex_reason({**a, "body": "短い"}), "no-body")
        self.assertEqual(indexnow.noindex_reason({**a, "duplicateOf": "y"}), "duplicate")
        self.assertIsNone(indexnow.noindex_reason({**a, "channelSlug": "prtimes"}))
        # 2026-11-13 オーナー「とにかく数字」: 公開した記事は題名の語で検索から外さない（軸から外れた話題は公開前の門で止める）
        self.assertIsNone(indexnow.noindex_reason({**a, "title": "レイカーズが開幕戦に勝利", "genreSlug": "sports"}))
        self.assertIsNone(indexnow.noindex_reason({**a, "title": "レイカーズ戦のチケットを12月に発売", "genreSlug": "sports"}))
        self.assertIsNone(indexnow.noindex_reason({**a, "title": "『新作RPG』の新モードは月額500円", "genreSlug": "entertainment"}))
        self.assertIsNone(indexnow.noindex_reason({**a, "title": "『新作RPG』の新キャラクターを紹介", "genreSlug": "entertainment"}))

    def test_publish_gate_keeps_its_old_basis(self):
        a = {"slug": "x", "title": "サンゴリアス 新ジャージーデザイン決定のお知らせ", "genreSlug": "lifestyle", "channelSlug": "suntory", "body": self.BODY * 2}
        self.assertEqual(indexnow.publish_block_reason(a), "off-focus")

    def test_restored_article_is_live(self):
        retired = json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"]
        self.assertNotIn("tsuruhachi-labeling-violation-maff", retired)
        art = json.loads((ROOT / "content" / "articles" / "tsuruhachi-labeling-violation-maff.json").read_text("utf-8"))
        self.assertIsNone(indexnow.noindex_reason(art))

    def test_retired_left_are_only_unrelated_or_kept_by_rule(self):
        keep = {"inaccurate", "press-source", "investment-advice", "duplicate", "creator-video", "creator-roundup",
                # 2026-11-12 オーナー承認（案B）: 検索の表示も読者も0の記事は、暮らしとお金の題名でも取り下げる
                "zero-search-zero-reader"}
        for slug, rec in json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"].items():
            if rec.get("reason") in keep or rec.get("reason", "").startswith("notice") or rec.get("redirect") or rec.get("redirectPath") or rec.get("replacedBy"):
                continue
            if slug in ("coast-fire-guide-investment-balance", "covid19-bankruptcy-october-2026", "nli-electronic-waste-recycling-challenges",
                        "nli-ai-agent-explained", "eurozone-gdp-2026-q3-slowdown"):
                continue  # 今の決まり（題名の「とは？」・調査会社の記事の免責文）に合わないので戻さない
            if slug in ("reiwa-8-autumn-shoubo-houshou", "reiwa-8-culture-merit-recipients"):
                continue  # 11/3 に薄い記事として取り下げた受章者の一覧。2026-11-13 から新しく作るのは通すが、取り下げた分は戻さない（戻すかはオーナーの判断）
            if slug == "biztex-executive-ai-1day-training":
                continue  # 有料講習のプレスリリースの言い換え（A10）。前の転送先に BizteX・Claude Code が無く、転送を外した（2026-11-09 台帳 A68）
            self.assertFalse(indexnow.life_link(rec.get("title", "")), slug)


class OldNoticeTest(unittest.TestCase):
    def item(self, title, days):
        return {"title": title, "summary": "", "published_at": datetime.now(timezone.utc) - timedelta(days=days), "source_slug": "nta", "lang": "ja"}

    def test_still_relevant_old_notice_is_kept(self):
        future = (datetime.now(JST) + timedelta(days=20)).date()
        self.assertTrue(web_articles.life_late_ok(self.item(f"e-Taxの申請受付を{future.month}月{future.day}日まで延長", 20)))

    def test_expired_or_unrelated_old_notice_is_dropped(self):
        past = (datetime.now(JST) - timedelta(days=45)).date()
        self.assertFalse(web_articles.life_late_ok(self.item(f"申請の受付は{past.month}月{past.day}日で終了", 50)))
        future = (datetime.now(JST) + timedelta(days=20)).date()
        self.assertFalse(web_articles.life_late_ok(self.item(f"新キャラクターを{future.month}月{future.day}日に公開", 20)))
        self.assertFalse(web_articles.life_late_ok(self.item(f"e-Taxの申請受付を{future.month}月{future.day}日まで延長", web_articles.RELEVANT_LATE_DAYS + 5)))


class ImageRetryTest(unittest.TestCase):
    def test_capped_card_is_retried_the_next_day(self):
        card = {"imageCredit": {"kind": "card", "aiCapped": True, "at": "2026-11-07T20:00:00+00:00"}}
        self.assertTrue(images.capped_retry(card, "2026-11-08"))
        self.assertFalse(images.capped_retry(card, "2026-11-07"))  # 同じ日はまだ上限
        self.assertFalse(images.capped_retry({"imageCredit": {"kind": "card", "at": "2026-11-01T00:00:00+00:00"}}, "2026-11-08"))

    def test_cap_marks_the_card(self):
        with patch.object(images, "AI_CAPPED", True):
            article = {"slug": "s", "thumbnail": ""}
            images.use_card(Path("/nonexistent.json"), article, {"dry_run": True})
        self.assertTrue(article["imageCredit"]["aiCapped"])


if __name__ == "__main__":
    unittest.main()
