"""Instagram の直接投稿（scripts/instagram_post.py・2026-11-05 オーナー承認・台帳 S36）を外部通信なしで検証する。

- 門番（sns_rules）: 本文に URL を書かない・「記事はプロフィールのリンクから」の案内・記事のリンク（utm_source=instagram）・ハッシュタグ3個まで
- 文面は Threads・Bluesky と同じ予定の本文（bluesky_post.plan）。動画（リール）だけ・朝のまとめは号の画像（JPEG）
- 選び方: 枠の13分後・1日6本（まとめを除く）・40分あける・同じ記事は1回だけ
- 投稿: 門番 → 自分の直近の投稿の確かめ → コンテナ → 処理を待つ → 公開。トークンの問題は記事の失敗にしない
- 切り替え: INSTAGRAM_MODE=off（既定）は何もしない・dry はコンテナも作らない
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import instagram_post as ig  # noqa: E402
import sns_rules as r  # noqa: E402

NOW = datetime(2026, 11, 5, 4, 0, tzinfo=timezone.utc)  # 13:00 JST
ART = {"slug": "acme-tool", "title": "Acme が新しいAIツールを公開", "genreSlug": "ai", "_virtual": True}
LINK = "https://ai-tech-express.jp/articles/acme-tool?utm_source=instagram&utm_medium=social&utm_campaign=sns_video_short&utm_content=video_body"
GOOD = (
    "会議のメモを取っている人、これは要チェックです。\n\n"
    "Acmeが会議の内容を自動でまとめるAIを公開しました。\n"
    "月額は1人1,000円で、日本語にも対応しています。\n\n"
    "あなたの職場では、会議の議事録を誰が書いていますか？"
)
VIDEO = [{"type": "video", "url": "https://ai-tech-express.jp/video/acme-tool-0123456789.mp4", "width": 1920, "height": 1080}]


def iso(dt):
    return dt.isoformat(timespec="seconds")


def check(text, media=VIDEO, links=(LINK,), **kw):
    return r.check_post("instagram", text, media, ART, links=list(links), measurer=lambda url: (1200, 675), **kw)


class GateTest(unittest.TestCase):
    def test_good_caption_passes(self):
        self.assertEqual(check(ig.caption(GOOD)), [])
        self.assertIn("instagram", r.PLATFORMS)
        self.assertEqual(r.norm_platform("ig"), "instagram")

    def test_url_in_caption_is_stopped(self):
        text = f"{GOOD}\n\n{r.INSTAGRAM_LINK_LINE}\nhttps://ai-tech-express.jp/articles/acme-tool"
        self.assertTrue(any("Instagram の本文に URL を書かない" in v for v in check(text)))

    def test_profile_line_and_article_link_are_required(self):
        self.assertTrue(any(r.INSTAGRAM_LINK_LINE in v for v in check(GOOD)))
        self.assertTrue(any("記事のリンク（links）がない" in v for v in check(ig.caption(GOOD), links=())))
        bad = LINK.replace("utm_source=instagram", "utm_source=bluesky")
        self.assertTrue(any("utm_source=instagram" in v for v in check(ig.caption(GOOD), links=(bad,))))

    def test_hashtags_capped(self):
        text = ig.caption(GOOD) + "\n#AI #a #b #c"
        self.assertTrue(any("ハッシュタグが多すぎる" in v for v in check(text)))
        self.assertLessEqual(len(r.HASHTAG_RE.findall(ig.caption(GOOD + "\n\n#AI #仕事 #お金 #副業"))), r.INSTAGRAM_HASHTAG_MAX)

    def test_article_posts_need_video_like_other_channels(self):
        card = [{"type": "image", "url": ig.jpeg_url("https://ai-tech-express.jp/card/acme-tool")}]
        self.assertTrue(any("[ルール8]" in v for v in check(ig.caption(GOOD), media=card)))

    def test_summary_lead_and_rules_are_the_shared_ones(self):
        self.assertTrue(any("ルール13" in v for v in check(ig.caption(GOOD.replace("Acmeが", "要約すると、Acmeが")))))

    def test_jpeg_transform_is_checked_as_the_original_image(self):
        url = ig.jpeg_url("https://ai-tech-express.jp/cover/acme-tool")
        self.assertTrue(url.startswith("https://ai-tech-express.jp/cdn-cgi/image/format=jpeg"))
        self.assertEqual(r.unwrap_transform(url), "https://ai-tech-express.jp/cover/acme-tool")
        self.assertTrue(r.is_text_band(url))  # 見出し入りのカバーは JPEG にしても使わない（ルール2）
        self.assertEqual(r.known_size(ig.jpeg_url("https://ai-tech-express.jp/card/x")), r.known_size("https://ai-tech-express.jp/card/x"))
        self.assertEqual(ig.jpeg_url("https://example.com/a.png"), "https://example.com/a.png")

    def test_already_posted_reads_channels_instagram(self):
        state = {"posted": {"acme-tool": {"channels": {"instagram": "1789"}}}}
        self.assertTrue(r.already_posted("instagram", ART, "article", state))
        self.assertFalse(r.already_posted("instagram", ART, "article", {"posted": {"acme-tool": {"channels": {"bluesky": "at://x"}}}}))


class CaptionTest(unittest.TestCase):
    def test_no_url_profile_line_and_credit(self):
        text = ig.caption(f"{GOOD}\n\nhttps://ai-tech-express.jp/articles/acme-tool\n👇", credit="VOICEVOX:ずんだもん")
        self.assertNotIn("http", text)
        self.assertIn(r.INSTAGRAM_LINK_LINE, text)
        self.assertTrue(text.endswith("音声：VOICEVOX:ずんだもん"))


def mirror(minutes_ago, **extra):
    entry = {"style": "standalone", "dueAt": iso(NOW - timedelta(minutes=minutes_ago))}
    entry.update(extra)
    return entry


class ChooseTest(unittest.TestCase):
    def setUp(self):
        p = patch.object(ig.bp, "video_of", lambda slug, videos=None: {"url": f"https://ai-tech-express.jp/video/{slug}.mp4", "variant": "short"})
        p.start()
        self.addCleanup(p.stop)
        q = patch.object(ig.bp, "muse_until", lambda *a, **k: None)
        q.start()
        self.addCleanup(q.stop)

    def test_waits_delay_after_slot(self):
        early = {"posted": {"a": mirror(ig.DELAY_MIN - 1)}}
        self.assertEqual(ig.choose(early, NOW), [])
        ready = {"posted": {"a": mirror(ig.DELAY_MIN + 1)}}
        self.assertEqual([k for k, _ in ig.choose(ready, NOW)], ["a"])
        self.assertNotEqual(ig.DELAY_MIN, ig.bp.DELAY_MIN)  # Bluesky と同じ分に並ばない

    def test_skips_done_failed_and_holds(self):
        state = {"posted": {
            "done": mirror(30, channels={"instagram": "1"}),
            "fail": mirror(30, instagramFailed="x"),
            "hold": mirror(30, ownerHold=True),
            "poll": mirror(30, style="poll"),
        }}
        self.assertEqual(ig.choose(state, NOW), [])

    def test_gap_and_daily_cap_without_digest(self):
        state = {"posted": {"a": mirror(30), "b": mirror(90, instagramAt=iso(NOW - timedelta(minutes=10)))}}
        self.assertEqual(ig.choose(state, NOW), [])
        today = NOW.replace(hour=0)
        full = {f"p{i}": mirror(600, instagramAt=iso(today)) for i in range(ig.PER_DAY)}
        full["dg"] = {"style": "digest", "dueAt": iso(today), "instagramAt": iso(today), "channels": {"instagram": "D1"}}
        self.assertEqual(ig.posted_today({"posted": full}, NOW), ig.PER_DAY)  # まとめは数えない
        self.assertEqual(ig.choose({"posted": {**full, "a": mirror(30)}}, NOW), [])
        self.assertLessEqual(ig.PER_DAY, ig.tp.sns_plan.daily_cap())

    def test_digest_goes_first_even_at_cap(self):
        today = NOW.replace(hour=0)
        full = {f"p{i}": mirror(600, instagramAt=iso(today)) for i in range(ig.PER_DAY)}
        full["digest-20261105"] = {"style": "digest", "dueAt": iso(NOW - timedelta(minutes=1))}
        self.assertEqual([k for k, _ in ig.choose({"posted": full}, NOW)], ["digest-20261105"])


class BuildTest(unittest.TestCase):
    def test_article_is_a_reel_with_the_planned_text(self):
        plan = {"text": GOOD, "link": "x", "title": "t", "desc": "", "images": [], "gate": ART}
        with patch.object(ig.bp, "plan", lambda key, entry, platform="bluesky": plan if platform == "instagram" else None), \
             patch.object(ig.bp, "video_of", lambda slug, videos=None: {"url": "https://ai-tech-express.jp/video/acme-tool-1.mp4", "variant": "short", "credit": ""}):
            item = ig.build("acme-tool", {"style": "standalone"})
        self.assertEqual(item["params"]["media_type"], "REELS")
        self.assertEqual(item["params"]["video_url"], "https://ai-tech-express.jp/video/acme-tool-1.mp4")
        self.assertIn("utm_source=instagram", item["link"])
        self.assertIn(r.INSTAGRAM_LINK_LINE, item["caption"])
        self.assertEqual(check(item["caption"], media=item["media"], links=(item["link"],)), [])

    def test_no_video_means_no_post(self):
        plan = {"text": GOOD, "link": "x", "title": "t", "desc": "", "images": ["https://ai-tech-express.jp/card/acme-tool"], "gate": ART}
        with patch.object(ig.bp, "plan", lambda *a, **k: plan), patch.object(ig.bp, "video_of", lambda *a, **k: {}):
            self.assertIn("skip", ig.build("acme-tool", {"style": "standalone"}))

    def test_digest_uses_the_issue_image_as_jpeg(self):
        page = "https://ai-tech-express.jp/digest/20261105"
        plan = {"text": "今朝のAIニュース3本", "link": page + "?utm_source=instagram", "kind": "digest",
                "images": [f"{page}/share.png?v=1", "https://ai-tech-express.jp/card/a"], "gate": {"link": page, "items": []}}
        with patch.object(ig.bp, "plan", lambda *a, **k: plan):
            item = ig.build("digest-20261105", {"style": "digest"})
        self.assertEqual(item["params"], {"image_url": "https://ai-tech-express.jp/cdn-cgi/image/format=jpeg,quality=88/digest/20261105/share.png?v=1"})

    def test_plan_utm_follows_platform(self):
        import bluesky_post as bp

        p = bp.plan("digest-20261030", {"style": "digest", "items": [], "postPlan": {"text": "今朝のAIニュース", "link": "https://ai-tech-express.jp/digest/20261030"}},
                    platform="instagram")
        self.assertIn("utm_source=instagram", p["link"])


class FakeGraph:
    def __init__(self, statuses=("IN_PROGRESS", "FINISHED"), media=()):
        self.calls, self.statuses, self.media = [], list(statuses), list(media)

    def __call__(self, method, path, params=None, token=""):
        self.calls.append((method, path, dict(params or {})))
        if path.endswith("/media") and method == "GET":
            return {"data": self.media}
        if path.endswith("/media") and method == "POST":
            return {"id": "C1"}
        if path == "C1":
            return {"status_code": self.statuses.pop(0)}
        if path.endswith("/media_publish"):
            return {"id": "M1"}
        if path == "M1":
            return {"permalink": "https://www.instagram.com/reel/abc/"}
        raise AssertionError(path)


ITEM = {"caption": None, "media": VIDEO, "gate": ART, "kind": "article", "link": LINK,
        "params": {"media_type": "REELS", "video_url": VIDEO[0]["url"], "share_to_feed": "true"}}


class PublishTest(unittest.TestCase):
    def item(self):
        return {**ITEM, "caption": ig.caption(GOOD)}

    def test_gate_then_container_then_publish(self):
        fake = FakeGraph()
        order = []
        with patch.object(ig.sns_rules, "enforce", lambda *a, **k: order.append("gate")):
            res = ig.publish("IG", "T", "acme-tool", self.item(), call=fake, sleep=lambda s: None)
        self.assertEqual(order, ["gate"])
        self.assertEqual(res, {"id": "M1", "permalink": "https://www.instagram.com/reel/abc/"})
        paths = [(m, p) for m, p, _ in fake.calls]
        self.assertEqual(paths[:3], [("GET", "IG/media"), ("POST", "IG/media"), ("GET", "C1")])
        self.assertIn(("POST", "IG/media_publish"), paths)
        self.assertEqual(fake.calls[1][2]["caption"], self.item()["caption"])

    def test_gate_violation_creates_nothing(self):
        fake = FakeGraph()
        bad = {**self.item(), "caption": GOOD}  # 案内の行が無い
        with patch.dict(os.environ, {"SNS_RULES_NO_ISSUE": "1"}), self.assertRaises(r.SnsRuleViolation):
            ig.publish("IG", "T", "acme-tool", bad, call=fake, sleep=lambda s: None)
        self.assertEqual(fake.calls, [])

    def test_existing_same_caption_is_not_posted_again(self):
        fake = FakeGraph(media=[{"id": "OLD", "caption": self.item()["caption"]}])
        with patch.object(ig.sns_rules, "enforce", lambda *a, **k: None):
            res = ig.publish("IG", "T", "acme-tool", self.item(), call=fake, sleep=lambda s: None)
        self.assertTrue(res["existing"])
        self.assertFalse(any(p.endswith("media_publish") or (m == "POST") for m, p, _ in fake.calls))

    def test_container_error_and_timeout(self):
        with patch.object(ig.sns_rules, "enforce", lambda *a, **k: None):
            with self.assertRaises(RuntimeError):
                ig.publish("IG", "T", "a", self.item(), call=FakeGraph(statuses=["ERROR"]), sleep=lambda s: None)
            fake = FakeGraph(statuses=["IN_PROGRESS"] * 100)
            with self.assertRaises(TimeoutError):
                ig.publish("IG", "T", "a", self.item(), call=fake, sleep=lambda s: None)
            self.assertFalse(any(p.endswith("media_publish") for _, p, _ in fake.calls))

    def test_quota(self):
        call = lambda *a, **k: {"data": [{"quota_usage": 99, "config": {"quota_total": 100}}]}  # noqa: E731
        self.assertEqual(ig.quota_left("IG", "T", call), 1)


class ModeTest(unittest.TestCase):
    def run_main(self, env, argv=()):
        with patch.dict(os.environ, env, clear=False), patch.object(sys, "argv", ["instagram_post.py", *argv]), \
             patch.object(ig, "graph", side_effect=AssertionError("通信してはいけない")), \
             patch.object(ig.tp, "save_state", side_effect=AssertionError("記録してはいけない")):
            return ig.main()

    def test_off_by_default_and_missing_secret_is_a_noop(self):
        env = {k: v for k, v in os.environ.items() if k not in ("INSTAGRAM_MODE", "IG_ACCESS_TOKEN", "IG_USER_ID")}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(ig.mode(), "off")
            self.assertEqual(self.run_main({}), 0)
            self.assertEqual(self.run_main({"INSTAGRAM_MODE": "live"}), 0)  # トークンが無ければ何もしない
            self.assertEqual(ig.test_container("image"), 1)

    def test_dry_creates_no_container(self):
        env = {"INSTAGRAM_MODE": "dry", "IG_USER_ID": "", "IG_ACCESS_TOKEN": ""}
        with patch.object(ig, "choose", lambda state, now: []), patch.object(ig.tp, "load_state", lambda: {"posted": {}}):
            self.assertEqual(self.run_main(env), 0)

    def test_auth_error_does_not_mark_the_entry(self):
        state = {"posted": {"acme-tool": mirror(30)}}
        saved = []
        env = {"INSTAGRAM_MODE": "live", "IG_USER_ID": "IG", "IG_ACCESS_TOKEN": "T"}

        def boom(*a, **k):
            raise ig.GraphError("bad token", 190, 400)

        with patch.dict(os.environ, env), patch.object(sys, "argv", ["instagram_post.py"]), \
             patch.object(ig.tp, "load_state", lambda: state), patch.object(ig.tp, "save_state", saved.append), \
             patch.object(ig, "choose", lambda s, n: [("acme-tool", state["posted"]["acme-tool"])]), \
             patch.object(ig, "quota_left", lambda *a, **k: 10), patch.object(ig, "build", lambda k, e: {**ITEM, "caption": "x"}), \
             patch.object(ig, "publish", boom), patch.object(ig.tp, "JST", timezone(timedelta(hours=12))):
            with patch.object(ig.tp, "BREAKING_QUIET_HOURS_JST", range(0)):
                self.assertEqual(ig.main(), 0)
        self.assertNotIn("instagramFailed", state["posted"]["acme-tool"])

    def test_merge_records_instagram_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "state.json"
            mine = Path(tmp) / "mine.json"
            live.write_text(json.dumps({"posted": {"a": {"channels": {"bluesky": "at://x"}}}}), "utf-8")
            mine.write_text(json.dumps({"posted": {"a": {"channels": {"instagram": "M1"}, "instagramAt": "t", "instagramPermalink": "p"}}}), "utf-8")
            with patch.object(ig.tp, "STATE_PATH", live):
                self.assertEqual(ig.bp.merge(str(mine), channel="instagram"), 0)
            got = json.loads(live.read_text("utf-8"))["posted"]["a"]
        self.assertEqual(got["channels"], {"bluesky": "at://x", "instagram": "M1"})
        self.assertEqual((got["instagramAt"], got["instagramPermalink"]), ("t", "p"))


class TokenTest(unittest.TestCase):
    """60日で切れるトークン（2026-11-05）: 読むだけの確かめ・期限の記録・7日未満で知らせる・秘密があるときだけ自動で延ばす"""

    def fake(self, expires_in_days=None, valid=True, debug_ok=True):
        now = NOW

        def call(method, path, params=None, token=""):
            self.assertEqual(method, "GET")  # 健康診断は読むだけ
            if path == "IG":
                if not valid:
                    raise ig.GraphError("bad", 190, 400)
                return {"username": "saisoku637"}
            if path == "debug_token":
                if not debug_ok:
                    raise ig.GraphError("no", 100, 400)
                exp = int((now + timedelta(days=expires_in_days)).timestamp()) if expires_in_days is not None else 0
                return {"data": {"is_valid": valid, "expires_at": exp, "scopes": ["instagram_basic", "instagram_content_publish"]}}
            if path == "oauth/access_token":
                return {"access_token": "NEW"}
            raise AssertionError(path)
        return call

    def run_check(self, call, env=None, prev=None):
        alerts = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "instagram_token.json"
            if prev:
                path.write_text(json.dumps(prev), "utf-8")
            base = {"IG_USER_ID": "IG", "IG_ACCESS_TOKEN": "TOKEN", "META_APP_SECRET": "", "GH_SECRETS_TOKEN": "", "GITHUB_ACTIONS": "true"}
            with patch.dict(os.environ, {**base, **(env or {})}), \
                 patch.object(ig, "token_alert", lambda body, close=False, gh=None: alerts.append((close, body))):
                self.assertEqual(ig.token_check(NOW, call=call, path=path), 0)
            rec = json.loads(path.read_text("utf-8"))
        return rec, alerts

    def test_records_expiry_and_closes_when_healthy(self):
        rec, alerts = self.run_check(self.fake(30))
        self.assertTrue(rec["valid"])
        self.assertEqual(rec["username"], "saisoku637")
        self.assertFalse(rec["estimated"])
        self.assertNotIn("TOKEN", json.dumps(rec))  # トークンそのものは記録しない
        self.assertEqual([c for c, _ in alerts], [True])

    def test_alerts_under_seven_days_without_secret(self):
        rec, alerts = self.run_check(self.fake(5))
        self.assertEqual(len(alerts), 1)
        self.assertFalse(alerts[0][0])
        self.assertIn("あと5.0日", alerts[0][1])
        self.assertNotIn("refreshedAt", rec)

    def test_invalid_token_alerts(self):
        rec, alerts = self.run_check(self.fake(30, valid=False))
        self.assertFalse(rec["valid"])
        self.assertIn("使えません", alerts[0][1])

    def test_estimates_sixty_days_when_debug_token_unreadable(self):
        first = iso(NOW - timedelta(days=55)).replace("+00:00", "Z")
        prev = {"fingerprint": ig.fingerprint("TOKEN"), "firstSeenAt": first}
        rec, alerts = self.run_check(self.fake(debug_ok=False), prev=prev)
        self.assertTrue(rec["estimated"])
        self.assertEqual(rec["firstSeenAt"], first)
        self.assertIn("見込み", alerts[0][1])
        rec2, _ = self.run_check(self.fake(debug_ok=False), prev={"fingerprint": "other", "firstSeenAt": first})
        self.assertNotEqual(rec2["firstSeenAt"], first)  # 新しいトークンなら数え直す

    def test_auto_refresh_only_with_both_secrets(self):
        stored = []
        with patch.object(ig, "store_secret", stored.append):
            rec, alerts = self.run_check(self.fake(3), env={"META_APP_SECRET": "s", "GH_SECRETS_TOKEN": "g"})
        self.assertEqual(stored, ["NEW"])
        self.assertIn("refreshedAt", rec)
        self.assertIn("自動で延ばしました", alerts[0][1])
        with patch.object(ig, "store_secret", side_effect=AssertionError("延ばしてはいけない")):
            self.run_check(self.fake(3), env={"META_APP_SECRET": "s"})

    def test_workflow_runs_token_check_daily_regardless_of_mode(self):
        text = (ROOT / ".github" / "workflows" / "instagram.yml").read_text("utf-8")
        self.assertIn('cron: "17 0 * * *"', text)
        self.assertIn("--token-check", text)
        self.assertIn("secrets.META_APP_SECRET", text)
        token_job = text.split("\n  token:", 1)[1]
        self.assertNotIn("INSTAGRAM_MODE", token_job)


class WorkflowTest(unittest.TestCase):
    def test_workflow_is_off_by_default_and_has_safe_inputs(self):
        text = (ROOT / ".github" / "workflows" / "instagram.yml").read_text("utf-8")
        self.assertIn("vars.INSTAGRAM_MODE || 'off'", text)
        self.assertIn("test_container", text)
        self.assertIn("dry_run", text)
        self.assertIn("ref: main", text)
        self.assertIn("--merge", text)
        self.assertIn("secrets.IG_ACCESS_TOKEN", text)
        self.assertIn('cron: "5-59/10 * * * *"', text)  # Bluesky（*/10）とずらす
        self.assertIn("tests.test_instagram_post", (ROOT / ".github" / "workflows" / "sns_rules.yml").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
