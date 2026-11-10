"""scripts/kpi_hourly.py（1時間ごとの数字と遅れの警報）。通信しない（urllib を差し替える）。python3 -m pytest -q tests/test_kpi_hourly.py"""
import io
import json
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kpi_hourly as k  # noqa: E402

JST = timezone(timedelta(hours=9))
BAR = "\uff5c"


def at(h, m=0, day=10):
    return datetime(2026, 11, day, h, m, tzinfo=JST)


def row(country, browser, host, visits, count=None, path="/articles/a"):
    return {"count": visits if count is None else count, "sum": {"visits": visits},
            "dimensions": {"countryName": country, "refererHost": host, "userAgentBrowser": browser, "requestPath": path}}


class FakeRes(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def env(tmp_path, monkeypatch):
    """鍵・通信・ファイルの置き場を全部差し替える"""
    home, drive, repo = tmp_path / "kpi", tmp_path / "drive", tmp_path / "repo"
    drive.mkdir()
    (repo / "state").mkdir(parents=True)
    (repo / "state" / "threads_posted.json").write_text(json.dumps({"posted": {}}), "utf-8")
    (drive / "to-claude.md").write_text("# to-claude\n\n## [G-0242] 2026-11-10 02:42 Grok→Claude 【済】\n- 既存の行\n", "utf-8")
    (drive / "status.md").write_text("# 現状ボード\n- 手動投稿（11/10）：なし\n", "utf-8")
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"days": {"2026-11-10": {"target": 500, "target_multipage_rate": 0.1, "target_ad_clicks_human": 5}}}), "utf-8")
    monkeypatch.setattr(k, "_cf_auth", lambda: ("dummy-token", "acct"))
    monkeypatch.setattr(k, "fetch_ad_clicks", lambda day, errors: (2, {"action-ad": 2}))
    state = {"rows": [], "status": None}

    def urlopen(req, timeout=0):
        if state["status"]:
            code = state["status"].pop(0) if isinstance(state["status"], list) else state["status"]
            if code:
                raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(b""))
        return FakeRes(json.dumps({"data": {"viewer": {"accounts": [{"t": state["rows"]}]}}}).encode())

    monkeypatch.setattr(k.urllib.request, "urlopen", urlopen)
    sleeps = []

    def go(now, **kw):
        return k.run(now, kpi_home=home, drive_dir=drive, metrics_path=metrics, root=repo, sleep=sleeps.append, **kw)

    return {"go": go, "state": state, "home": home, "drive": drive, "repo": repo, "metrics": metrics, "sleeps": sleeps}


def entries(drive):
    return [ln for ln in (drive / "to-claude.md").read_text("utf-8").splitlines() if ln.startswith("## [K-")]


# ---------- 目安の線 ----------

def test_pace_500():
    assert [k.expected_at(500, at(h)) for h in (0, 9, 12, 16, 21)] == [0, 50, 130, 263, 430]
    assert k.expected_at(500, at(23, 59)) <= 500


@pytest.mark.parametrize("target", [300, 1000])
def test_pace_scales(target):
    for h, base in ((9, 50), (12, 130), (21, 430)):
        assert k.expected_at(target, at(h)) == round(base * target / 500)
    assert k.expected_at(target, at(16)) == round(target * (0.46 + 0.2 / 3))


# ---------- 行のふるい分け ----------

def test_rows_only_jp_humans():
    rows = [row("JP", "Chrome", "l.threads.com", 10, 12), row("JP", "HeadlessChrome", "", 50),
            row("JP", "Unknown", "", 7), row("US", "Chrome", "", 30), row("JP", "Safari", "ai-tech-express.jp", 0, 3),
            row("JP", "Safari", "", 5, 5)]
    rows.append(row("JP", "Googlebot", "", 9))
    s = k.summarize(rows)
    # Unknown（Threads のアプリ内ブラウザ）は人として数える。Headless・bot は除く
    assert s["visits"] == 22 and s["pageviews"] == 27
    assert s["by_source"] == {"direct": 12, "threads": 10, "internal": 0}
    assert s["second_page_rate_est"] == round(3 / 22, 4) and s["pv_per_visit"] == round(27 / 22, 3)


@pytest.mark.parametrize("host,src", [("threads.net", "threads"), ("l.threads.com", "threads"), ("t.co", "x"), ("x.com", "x"),
                                      ("", "direct"), (None, "direct"), ("ai-tech-express.jp", "internal"), ("chatgpt.com", "ai"),
                                      ("www.google.com", "google"), ("search.yahoo.co.jp", "yahoo"), ("bsky.app", "bluesky"),
                                      ("example.com", "other")])
def test_classify(host, src):
    assert k.classify(host) == src


# ---------- 目標 ----------

def test_target_lookup(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"days": {"2026-11-09": {"target": 300}, "2026-11-10": {"target": 500, "target_ad_clicks_human": 5}}}), "utf-8")
    assert k.load_targets("2026-11-10", p)["target"] == 500
    assert k.load_targets("2026-11-10", p)["target_ad_clicks_human"] == 5
    assert k.load_targets("2026-11-11", p)["target"] == 500
    p.write_text(json.dumps({"days": {"2026-11-09": {"target": 300}, "2026-11-10": {"note": "x"}}}), "utf-8")
    assert k.load_targets("2026-11-10", p)["target"] == 300
    p.write_text(json.dumps({"days": {}}), "utf-8")
    assert k.load_targets("2026-11-10", p)["target"] == 500
    assert k.load_targets("2026-11-10", tmp_path / "none.json")["target"] == 500


# ---------- 警報の重複なし ----------

def test_alert_dedupe_and_format(env):
    env["state"]["rows"] = [row("JP", "Chrome", "threads.net", 200), row("JP", "Chrome", "", 41)]
    before = (env["drive"] / "to-claude.md").read_text("utf-8")
    env["go"](at(16, 5))
    env["go"](at(17, 5))
    heads = entries(env["drive"])
    assert len(heads) == 1
    text = (env["drive"] / "to-claude.md").read_text("utf-8")
    assert text.startswith(before)  # 既存の行は書き換えない
    assert heads[0] == "## [K-1605] 2026-11-10 16:05 計測（自動）→Claude 【未対応】"
    exp = k.expected_at(500, at(16, 5))
    assert f"16:05 訪問 241人（目安{exp}人より{exp - 241}人少ない" in text
    assert BAR not in text and not k.ZAKKURI_RE.search(text)
    lines = (env["home"] / "kpi_hourly.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == 2
    snap = json.loads(lines[0])
    for key in ("at", "date_jst", "visits", "pageviews", "by_source", "second_page_rate_est", "pv_per_visit", "ad_clicks_human",
                "threads_posts_today", "target", "expected_now", "pace_gap", "errors"):
        assert key in snap
    md = (env["drive"] / "kpi-hourly.md").read_text("utf-8")
    assert "推定" in md and md.count("\n| 1") == 2 and BAR not in md


def test_on_pace_writes_nothing(env):
    env["state"]["rows"] = [row("JP", "Chrome", "threads.net", 400)]
    env["go"](at(16, 5))
    env["go"](at(20, 5))
    assert entries(env["drive"]) == []


def test_status_md_untouched(env):
    env["state"]["rows"] = [row("JP", "Chrome", "threads.net", 10)]
    before = (env["drive"] / "status.md").read_text("utf-8")
    env["go"](at(12, 3))
    assert (env["drive"] / "status.md").read_text("utf-8") == before
    assert len(entries(env["drive"])) == 1


def test_dry_run_writes_nothing(env, capsys):
    env["state"]["rows"] = [row("JP", "Chrome", "threads.net", 10)]
    before = (env["drive"] / "to-claude.md").read_text("utf-8")
    env["go"](at(16, 5), dry_run=True)
    assert not env["home"].exists()
    assert (env["drive"] / "to-claude.md").read_text("utf-8") == before
    assert not (env["drive"] / "kpi-hourly.md").exists()
    assert '"visits": 10' in capsys.readouterr().out


# ---------- Threads の警報 ----------

def write_posts(env, times):
    posted = {f"p{i}": {"via": "buffer", "sentAt": t.astimezone(timezone.utc).isoformat()} for i, t in enumerate(times)}
    (env["repo"] / "state" / "threads_posted.json").write_text(json.dumps({"posted": posted}), "utf-8")


def test_threads_alarm_fires_on_drop(env):
    # 9:00〜12:00 に3本で36人（1本12人）。12:00〜15:00 に3本で9人（1本3人）
    write_posts(env, [at(9, 30), at(10, 30), at(11, 30), at(12, 30), at(13, 30), at(14, 30)])
    for h, threads in ((9, 0), (12, 36), (15, 45)):
        env["state"]["rows"] = [row("JP", "Chrome", "threads.net", threads), row("JP", "Chrome", "", 500)]  # 目安より多い（遅れの警報は出ない）
        env["go"](at(h, 0))
    heads = entries(env["drive"])
    assert heads == ["## [K-1500] 2026-11-10 15:00 計測（自動）→Claude 【未対応】"]
    text = (env["drive"] / "to-claude.md").read_text("utf-8")
    assert "12:00〜15:00" in text and "投稿3本で訪問9人" in text and "3.0人" in text and "12.0人" in text
    assert "12:30・13:30・14:30" in text and "下げ" not in text


def test_threads_alarm_needs_two_posts(env):
    write_posts(env, [at(9, 30), at(10, 30), at(11, 30), at(13, 30)])
    for h, threads in ((9, 0), (12, 36), (15, 38)):
        env["state"]["rows"] = [row("JP", "Chrome", "threads.net", threads), row("JP", "Chrome", "", 500)]
        env["go"](at(h, 0))
    assert entries(env["drive"]) == []


def test_threads_alarm_quiet_at_night():
    window = {"start": "23:00", "end": "02:00", "visits": 3, "posts": 3, "post_times": [], "per_post": 1.0}
    history = [{"threads_window": {"per_post": 12.0}}]
    assert k.threads_alarm(at(2, 0), window, history, None) is None
    assert k.threads_alarm(at(14, 0), window, history, None) is not None
    assert k.threads_alarm(at(14, 0), window, history, at(12, 30).isoformat()) is None


def test_manual_posts_parsed(tmp_path):
    p = tmp_path / "status.md"
    p.write_text("- 手動投稿（11/10）：7:47電気代・8:24児童手当。次は13:20すぎに障害／13:19 障害（定番）／14:00 高額療養費\n", "utf-8")
    got = [t.strftime("%H:%M") for t in k.manual_post_times(at(13, 50), p)]
    assert got == ["07:47", "08:24", "13:19"]
    assert k.manual_post_times(at(13, 50, day=11), p) == []


# ---------- 失敗しても落ちない ----------

def test_401_recorded(env):
    env["state"]["status"] = 401
    snap = env["go"](at(16, 5))
    assert "Cloudflare login expired" in snap["errors"] and snap["visits"] is None
    text = (env["drive"] / "to-claude.md").read_text("utf-8")
    assert "Cloudflare login expired" in text and "wrangler whoami" in text
    env["go"](at(17, 5))
    assert len(entries(env["drive"])) == 1


def test_429_waits_once_then_gives_up(env):
    env["state"]["status"] = [429, 429]
    snap = env["go"](at(10, 5))
    assert env["sleeps"] == [300]
    assert any("429" in e for e in snap["errors"])
    env["state"]["status"] = [429, 0]
    env["state"]["rows"] = [row("JP", "Chrome", "", 80)]
    assert env["go"](at(11, 5))["visits"] == 80


def test_main_exits_zero(monkeypatch):
    monkeypatch.setattr(k, "run", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(k, "git_pull", lambda *a, **kw: None)
    assert k.main(["--now", "2026-11-10T16:05:00+09:00"]) == 0


def test_safe_text():
    assert BAR not in k.safe_text(f"a{BAR}b")
    assert not k.ZAKKURI_RE.search(k.safe_text("ざっ" + "くり言うと"))
