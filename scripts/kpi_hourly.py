#!/usr/bin/env python3
"""1時間ごとの3つの数字の記録と、遅れの警報（ローカルの launchd で動かす。GitHub Actions では動かさない）。

  python3 scripts/kpi_hourly.py              # 計測して記録する（~/.saisoku-kpi/kpi_hourly.jsonl に1行足す）
  python3 scripts/kpi_hourly.py --dry-run    # 計測して表示するだけ（何も書かない）
  python3 scripts/kpi_hourly.py --now 2026-11-10T16:05:00+09:00   # 時刻を決めて動かす（試験・やり直し用）

記録するもの
  1. 日本の人の訪問（Cloudflare Web Analytics の RUM。国=JP、自動ブラウザ（Headless など）を除く。Unknown は Threads の
     アプリ内ブラウザなので数える）と流入元の内訳
  2. 2ページ目に進んだ人の割合（推定）: RUM には訪問ごとのページ数がないので、
     「サイト内から来たページ表示 ÷ 訪問」を推定値として記録する。1訪問あたりのページ数（推定）も記録する
  3. 人による広告クリック（自前の計測 /api/aff/stats。既知の自動アクセスを除いた数）
  4. 今日の Threads 投稿（state/threads_posted.json の Buffer 分 + status.md の「- 手動投稿（」の行の時刻）

警報（Googleドライブ「サイソク連絡/to-claude.md」に追記するだけ。ほかの行は書き換えない）
  - 12:00・16:00・20:00（日本時間）を過ぎた最初の回に、目安より少ないときだけ1件（1日1回ずつ）
  - Threads の直近3時間の「1投稿あたりの訪問」が今日のこれまでの中央値の半分未満、かつ5人未満のとき（3時間に1回まで、6:00〜23:59）
  - 最新の表は「サイソク連絡/kpi-hourly.md」に上書きする（status.md は Claude が30分ごとに上書きするので触らない）

鍵: Cloudflare は scripts/images.cf_token('analytics')（CLOUDFLARE_API_TOKEN か wrangler のログイン）。
    広告クリックは AFF_STATS_TOKEN（scripts/aff_stats.load_token。無ければメインのフォルダの .env.local）。
    鍵の中身は表示しない・記録しない。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
HOME = Path.home()
KPI_HOME = Path(os.environ.get("KPI_HOME") or HOME / ".saisoku-kpi")
MAIN_DIR = Path(os.environ.get("SAISOKU_MAIN_DIR") or HOME / "自動きじ")
DRIVE_DIR = Path(os.environ.get("SAISOKU_DRIVE_DIR") or HOME / "Library/CloudStorage/GoogleDrive-koyuiw7@gmail.com/マイドライブ/サイソク連絡")
METRICS = Path(os.environ.get("SAISOKU_METRICS") or MAIN_DIR / ".claude" / "metrics.json")
SITE_HOST = "ai-tech-express.jp"
GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
DEFAULT_TARGET = 500
DEFAULT_MULTIPAGE = 0.10
CHECKPOINTS = (12, 16, 20)
# 500人の日の目安（9時50・12時130・15時230・18時330・21時430・24時500）を割合にしたもの
PACE = ((0, 0.0), (9, 0.10), (12, 0.26), (15, 0.46), (18, 0.66), (21, 0.86), (24, 1.0))
THREADS_WINDOW_H = 3
THREADS_MIN_POSTS = 2
THREADS_FLOOR = 5.0  # 昼の投稿1本あたりの訪問の中央値（毎日の手順の基準）
LIMIT = 5000

# 自動ブラウザだけを除く。「Unknown」は除かない: 11/10 の実測で日本の Unknown 116訪問のうち112が l.threads.com から
# （Threads のアプリ内ブラウザ）で、人の訪問。引き継ぎ書6章の手作業の数え方（Headless を含む行だけ捨てる）とも同じ
HEADLESS = re.compile(r"headless|bot|crawler|spider|lighthouse|pagespeed", re.I)
try:
    from article_style import ZAKKURI_RE  # noqa: E402
except Exception:  # noqa: BLE001
    ZAKKURI_RE = re.compile("ざっ" + "くり")
BAR = "\uff5c"
AI_HOSTS = ("chatgpt", "openai", "perplexity", "meta.ai", "gemini", "copilot", "claude.ai", "you.com", "phind", "felo")


# ---------- 計算 ----------

def pace_fraction(hour: float) -> float:
    hour = max(0.0, min(24.0, hour))
    for (h0, f0), (h1, f1) in zip(PACE, PACE[1:]):
        if h0 <= hour <= h1:
            return f0 + (f1 - f0) * (hour - h0) / (h1 - h0)
    return 1.0


def expected_at(target: float, now_jst: datetime) -> int:
    return round(target * pace_fraction(now_jst.hour + now_jst.minute / 60))


def classify(host: str | None) -> str:
    h = (host or "").strip().lower()
    if not h:
        return "direct"
    if h == SITE_HOST or h.endswith("." + SITE_HOST):
        return "internal"
    if "threads" in h:
        return "threads"
    if any(a in h for a in AI_HOSTS):
        return "ai"
    if "google" in h:
        return "google"
    if "yahoo" in h:
        return "yahoo"
    if h in ("t.co", "x.com", "twitter.com") or h.endswith((".x.com", ".twitter.com")):
        return "x"
    if "bsky" in h:
        return "bluesky"
    return "other"


def summarize(rows: list[dict]) -> dict:
    """RUM の行から、日本の人だけの訪問・ページ表示・流入元・2ページ目率（推定）を出す"""
    visits = pageviews = internal_pv = 0
    by_source: dict[str, int] = {}
    for r in rows:
        dim = r.get("dimensions") or {}
        if dim.get("countryName") != "JP":
            continue
        if HEADLESS.search(dim.get("userAgentBrowser") or ""):
            continue
        v = int((r.get("sum") or {}).get("visits") or 0)
        c = int(r.get("count") or 0)
        src = classify(dim.get("refererHost"))
        visits += v
        pageviews += c
        by_source[src] = by_source.get(src, 0) + v
        if src == "internal":
            internal_pv += c
    return {
        "visits": visits,
        "pageviews": pageviews,
        "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        "internal_pageviews": internal_pv,
        "second_page_rate_est": round(internal_pv / visits, 4) if visits else None,
        "pv_per_visit": round(pageviews / visits, 3) if visits else None,
    }


# ---------- 取得 ----------

def cf_query(start_utc: datetime, end_utc: datetime, account: str) -> str:
    f = "%Y-%m-%dT%H:%M:%SZ"
    return ('{viewer{accounts(filter:{accountTag:"%s"}){\n'
            't:rumPageloadEventsAdaptiveGroups(limit:%d,filter:{datetime_geq:"%s",datetime_lt:"%s"})'
            '{count sum{visits} dimensions{countryName refererHost userAgentBrowser requestPath}}\n}}}'
            % (account, LIMIT, start_utc.strftime(f), end_utc.strftime(f)))


def _cf_auth() -> tuple[str, str]:
    try:
        import images

        return images.cf_token("analytics"), images.ACCOUNT_ID
    except Exception:  # noqa: BLE001
        return os.environ.get("CLOUDFLARE_API_TOKEN", ""), os.environ.get("CLOUDFLARE_ACCOUNT_ID", "51e37d82e15d397b9666dc3d09bd5b92")


def fetch_rum(start_utc: datetime, end_utc: datetime, errors: list[str], sleep=time.sleep) -> list[dict] | None:
    """失敗しても落ちない。401 はログイン切れ、429 は5分待って1回だけやり直す"""
    token, account = _cf_auth()
    if not token:
        errors.append("Cloudflare login expired (no token)")
        return None
    body = json.dumps({"query": cf_query(start_utc, end_utc, account)}).encode()
    for attempt in range(2):
        req = urllib.request.Request(GRAPHQL, data=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                data = json.loads(res.read())
        except urllib.error.HTTPError as e:
            if e.code == 401 or e.code == 403:
                errors.append("Cloudflare login expired")
                return None
            if e.code == 429 and attempt == 0:
                sleep(300)
                continue
            errors.append(f"Cloudflare HTTP {e.code}" + (" rate limited, gave up this hour" if e.code == 429 else ""))
            return None
        except Exception as e:  # noqa: BLE001
            errors.append(f"Cloudflare {type(e).__name__}: {str(e)[:100]}")
            return None
        if data.get("errors"):
            msg = str(data["errors"][0].get("message", ""))[:120]
            if re.search(r"auth|token|unauthori", msg, re.I):
                errors.append("Cloudflare login expired")
            else:
                errors.append(f"Cloudflare GraphQL: {msg}")
            return None
        try:
            rows = data["data"]["viewer"]["accounts"][0]["t"]
        except (KeyError, IndexError, TypeError):
            errors.append("Cloudflare: unexpected response shape")
            return None
        if len(rows) >= LIMIT:
            errors.append(f"Cloudflare rows hit limit {LIMIT} (counts may be low)")
        return rows
    return None


def aff_token() -> str:
    try:
        import aff_stats

        token = aff_stats.load_token()
        if token:
            return token
    except Exception:  # noqa: BLE001
        pass
    path = MAIN_DIR / ".env.local"
    try:
        for line in path.read_text("utf-8").splitlines():
            m = re.match(r"^AFF_STATS_TOKEN=(.+)$", line.strip())
            if m:
                return m.group(1).strip().strip("\"'")
    except OSError:
        pass
    return ""


def fetch_ad_clicks(day: str, errors: list[str]) -> tuple[int | None, dict]:
    token = aff_token()
    if not token:
        errors.append("AFF_STATS_TOKEN missing: ad clicks not measured")
        return None, {}
    try:
        import aff_stats

        data = aff_stats.fetch(token, day)
        by_pos: dict[str, int] = {}
        for row in data.get("byPosition") or []:
            g = aff_stats.position_group(str(row.get("pos", "other")))
            by_pos[g] = by_pos.get(g, 0) + int(row.get("clicks", 0))
        return int(data.get("clicks") or 0), by_pos
    except urllib.error.HTTPError as e:
        errors.append(f"aff stats HTTP {e.code}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"aff stats {type(e).__name__}: {str(e)[:100]}")
    return None, {}


# ---------- 投稿・目標 ----------

def buffer_post_times(now_jst: datetime, root: Path = ROOT) -> list[datetime]:
    try:
        posted = json.loads((root / "state" / "threads_posted.json").read_text("utf-8")).get("posted", {})
    except Exception:  # noqa: BLE001
        return []
    out = []
    for entry in posted.values():
        if not isinstance(entry, dict) or "pending" in entry:
            continue
        if entry.get("status") not in (None, "scheduled", "sent", "posted"):
            continue
        raw = entry.get("sentAt") or entry.get("dueAt")
        if not raw:
            continue
        try:
            t = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(JST)
        except ValueError:
            continue
        if t.date() == now_jst.date() and t <= now_jst:
            out.append(t)
    return out


def manual_post_times(now_jst: datetime, status_path: Path) -> list[datetime]:
    """status.md の「- 手動投稿（11/10）：7:47電気代・…」から時刻だけ読む（「次は13:20すぎに」のような予定は数えない）"""
    try:
        lines = status_path.read_text("utf-8").splitlines()
    except OSError:
        return []
    line = next((ln for ln in lines if ln.startswith("- 手動投稿（")), "")
    m = re.match(r"- 手動投稿（(\d{1,2})/(\d{1,2})", line)
    if not m or (int(m.group(1)), int(m.group(2))) != (now_jst.month, now_jst.day):
        return []
    out = set()
    for hm in re.finditer(r"(次は)?(\d{1,2}):(\d{2})(すぎ)?", line):
        if hm.group(1) or hm.group(4):
            continue
        h, mi = int(hm.group(2)), int(hm.group(3))
        if h > 23 or mi > 59:
            continue
        t = now_jst.replace(hour=h, minute=mi, second=0, microsecond=0)
        if t <= now_jst:
            out.add(t)
    return sorted(out)


def load_targets(day: str, metrics_path: Path = METRICS) -> dict:
    try:
        days = json.loads(metrics_path.read_text("utf-8")).get("days", {})
    except Exception:  # noqa: BLE001
        days = {}
    entry = days.get(day) if isinstance(days.get(day), dict) else None
    if not entry or "target" not in entry:
        earlier = sorted(k for k, v in days.items() if k < day and isinstance(v, dict) and "target" in v)
        entry = days[earlier[-1]] if earlier else {}
    return {
        "target": entry.get("target", DEFAULT_TARGET),
        "target_multipage_rate": entry.get("target_multipage_rate", DEFAULT_MULTIPAGE),
        "target_ad_clicks_human": entry.get("target_ad_clicks_human"),
    }


# ---------- 記録の読み書き ----------

def read_history(path: Path, day: str) -> list[dict]:
    out = []
    try:
        for line in path.read_text("utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("date_jst") == day:
                out.append(row)
    except OSError:
        pass
    return out


def threads_window(now_jst: datetime, threads_now: int | None, history: list[dict], posts: list[datetime]) -> dict | None:
    """直近3時間の Threads からの訪問 ÷ その間の投稿数。3時間前の記録がなければ出さない"""
    if threads_now is None:
        return None
    start = now_jst - timedelta(hours=THREADS_WINDOW_H)
    midnight = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    if start <= midnight:
        start, base = midnight, 0
    else:
        best = None
        for row in history:
            if row.get("visits") is None:
                continue
            t = datetime.fromisoformat(row["at"]).astimezone(JST)
            gap = abs((t - start).total_seconds())
            if gap <= 40 * 60 and (best is None or gap < best[0]):
                best = (gap, row, t)
        if best is None:
            return None
        start, base = best[2], int((best[1].get("by_source") or {}).get("threads", 0))
    in_window = [p for p in posts if start < p <= now_jst]
    visits = max(0, threads_now - base)
    return {
        "start": start.strftime("%H:%M"), "end": now_jst.strftime("%H:%M"),
        "visits": visits, "posts": len(in_window), "post_times": [p.strftime("%H:%M") for p in sorted(in_window)],
        "per_post": round(visits / len(in_window), 2) if len(in_window) >= THREADS_MIN_POSTS else None,
    }


def threads_alarm(now_jst: datetime, window: dict | None, history: list[dict], last_alarm: str | None) -> dict | None:
    if not window or window.get("per_post") is None or now_jst.hour < 6:
        return None
    if last_alarm:
        try:
            if now_jst - datetime.fromisoformat(last_alarm).astimezone(JST) < timedelta(hours=THREADS_WINDOW_H):
                return None
        except ValueError:
            pass
    earlier = [r["threads_window"]["per_post"] for r in history if (r.get("threads_window") or {}).get("per_post") is not None]
    if not earlier:
        return None
    median = statistics.median(earlier)
    pp = window["per_post"]
    if pp < 0.5 * median and pp < THREADS_FLOOR:
        return {**window, "median": round(median, 2)}
    return None


def safe_text(text: str) -> str:
    text = text.replace(BAR, "・")
    text = ZAKKURI_RE.sub("要約すると", text)
    assert BAR not in text and not ZAKKURI_RE.search(text)
    return text


def entry_text(now_jst: datetime, snap: dict, behind: bool, alarm: dict | None, login_expired: bool) -> str:
    hm = now_jst.strftime("%H:%M")
    lines = []
    if login_expired:
        lines.append("Cloudflare login expired：ログインが切れて訪問を数えられません。npx -y wrangler whoami で更新してください")
    if behind:
        gap = snap["expected_now"] - snap["visits"]
        lines.append(f"{hm} 訪問 {snap['visits']}人（目安{snap['expected_now']}人より{gap}人少ない。今日の目標{snap['target']}人）")
        rate = snap.get("second_page_rate_est")
        goal = snap.get("target_multipage_rate") or DEFAULT_MULTIPAGE
        if rate is not None:
            lines.append(f"2ページ目に進んだ人（推定）{rate * 100:.1f}%（目標{goal * 100:.0f}%）")
        ads = snap.get("ad_clicks_human")
        ad_goal = snap.get("target_ad_clicks_human")
        if ads is None:
            lines.append("人による広告クリック：数えられませんでした（鍵が見つからないか取得に失敗）")
        else:
            lines.append(f"人による広告クリック {ads}回" + (f"（目標{ad_goal}回）" if ad_goal is not None else ""))
        th = (snap.get("by_source") or {}).get("threads", 0)
        if snap["visits"]:
            lines.append(f"Threadsからの訪問 {th}人（全体の{th * 100 // snap['visits']}%）、今日の投稿{snap['threads_posts_today']}本")
    if alarm:
        lines.append(f"Threads 直近3時間（{alarm['start']}〜{alarm['end']}）：投稿{alarm['posts']}本で訪問{alarm['visits']}人、"
                     f"1本あたり{alarm['per_post']:.1f}人（今日のこれまでの中央値{alarm['median']:.1f}人の半分未満）")
        lines.append("この間の投稿：" + "・".join(alarm["post_times"]))
    head = f"## [K-{now_jst.strftime('%H%M')}] {now_jst.strftime('%Y-%m-%d %H:%M')} 計測（自動）→Claude 【未対応】"
    body = "\n".join(f"- {ln}" for ln in lines[:6])
    return safe_text(f"\n{head}\n{body}\n")


def hourly_md(day: str, rows: list[dict]) -> str:
    out = [f"# 1時間ごとの数字（{day}・自動）", "",
           "日本の人の訪問（自動の巡回を除く）。2ページ目率と1訪問あたりのページ数は推定です（RUM の集計から計算）。", "",
           "| 時刻 | 訪問 | 目安 | 差 | Threads | 検索 | 直接 | 2ページ目（推定） | 1訪問のページ（推定） | 広告クリック（人） | Threads投稿 | メモ |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        t = datetime.fromisoformat(r["at"]).astimezone(JST).strftime("%H:%M")
        src = r.get("by_source") or {}
        rate = r.get("second_page_rate_est")
        cells = [t, r.get("visits"), r.get("expected_now"), r.get("pace_gap"), src.get("threads", 0),
                 src.get("google", 0) + src.get("yahoo", 0), src.get("direct", 0),
                 "" if rate is None else f"{rate * 100:.1f}%", "" if r.get("pv_per_visit") is None else r["pv_per_visit"],
                 "" if r.get("ad_clicks_human") is None else r["ad_clicks_human"], r.get("threads_posts_today", 0),
                 "・".join(r.get("errors") or [])]
        out.append("| " + " | ".join("" if c is None else str(c).replace("|", "/") for c in cells) + " |")
    return safe_text("\n".join(out) + "\n")


# ---------- 本体 ----------

def git_pull(root: Path = ROOT) -> None:
    """専用の写し（~/.saisoku-kpi/repo）のときだけ最新にする。メインのフォルダには触らない"""
    try:
        if KPI_HOME.resolve() not in root.resolve().parents and os.environ.get("KPI_PULL") != "1":
            return
        subprocess.run(["git", "-C", str(root), "pull", "-q", "--ff-only"], capture_output=True, timeout=90)
    except Exception:  # noqa: BLE001
        pass


def run(now_jst: datetime, dry_run: bool = False, kpi_home: Path = KPI_HOME, drive_dir: Path = DRIVE_DIR,
        metrics_path: Path = METRICS, root: Path = ROOT, sleep=time.sleep) -> dict:
    errors: list[str] = []
    day = now_jst.date().isoformat()
    midnight = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = fetch_rum(midnight.astimezone(timezone.utc), now_jst.astimezone(timezone.utc), errors, sleep=sleep)
    s = summarize(rows) if rows is not None else {"visits": None, "pageviews": None, "by_source": {}, "internal_pageviews": None,
                                                    "second_page_rate_est": None, "pv_per_visit": None}
    ads, ads_pos = fetch_ad_clicks(day, errors)
    posts = sorted(buffer_post_times(now_jst, root) + manual_post_times(now_jst, drive_dir / "status.md"))
    targets = load_targets(day, metrics_path)
    expected = expected_at(targets["target"], now_jst)
    snap = {
        "at": now_jst.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "date_jst": day,
        "visits": s["visits"], "pageviews": s["pageviews"], "by_source": s["by_source"],
        "second_page_rate_est": s["second_page_rate_est"], "pv_per_visit": s["pv_per_visit"],
        "estimate_note": "second_page_rate_est = internal-referer pageloads / visits; pv_per_visit = pageloads / visits (estimates)",
        "ad_clicks_human": ads, "ad_clicks_by_position": ads_pos,
        "threads_posts_today": len(posts), "threads_post_times": [p.strftime("%H:%M") for p in posts],
        "target": targets["target"], "target_multipage_rate": targets["target_multipage_rate"],
        "target_ad_clicks_human": targets["target_ad_clicks_human"],
        "expected_now": expected, "pace_gap": None if s["visits"] is None else s["visits"] - expected,
        "errors": errors,
    }
    jsonl = kpi_home / "kpi_hourly.jsonl"
    history = read_history(jsonl, day)
    snap["threads_window"] = threads_window(now_jst, (s["by_source"] or {}).get("threads", 0) if s["visits"] is not None else None, history, posts)

    state_path = kpi_home / "alerts_sent.json"
    try:
        state = json.loads(state_path.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        state = {}
    today_state = state.setdefault(day, {})
    due = [c for c in CHECKPOINTS if now_jst.hour >= c and str(c) not in today_state.get("checkpoints", {})]
    behind = False
    if due and s["visits"] is not None:
        cp = due[-1]
        behind = s["visits"] < expected
        for c in due:
            today_state.setdefault("checkpoints", {})[str(c)] = ("behind" if behind else "on_pace") if c == cp else "skipped"
    alarm = threads_alarm(now_jst, snap["threads_window"], history, today_state.get("threads_alarm_at"))
    if alarm:
        today_state["threads_alarm_at"] = now_jst.isoformat()
    login_expired = any("login expired" in e for e in errors) and not today_state.get("login_expired")
    if login_expired:
        today_state["login_expired"] = now_jst.isoformat()
    snap["alert"] = {"behind": behind, "threads_alarm": bool(alarm), "login_expired": login_expired}
    entry = entry_text(now_jst, snap, behind, alarm, login_expired) if (behind or alarm or login_expired) else ""

    if dry_run:
        print(json.dumps(snap, ensure_ascii=False, indent=1))
        if entry:
            print("--- to-claude.md に足す予定の文（dry-run なので書きません）---" + entry)
        return snap
    kpi_home.mkdir(parents=True, exist_ok=True)
    with jsonl.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    for old in [k for k in state if k < (now_jst.date() - timedelta(days=14)).isoformat()]:
        state.pop(old, None)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), "utf-8")
    try:
        if entry:
            with (drive_dir / "to-claude.md").open("a", encoding="utf-8") as f:
                f.write(entry)
        (drive_dir / "kpi-hourly.md").write_text(hourly_md(day, history + [snap]), "utf-8")
    except OSError as e:
        print(f"[kpi] Googleドライブに書けませんでした: {type(e).__name__}", file=sys.stderr)
    print(f"[kpi] {now_jst:%Y-%m-%d %H:%M} 訪問 {snap['visits']} / 目安 {expected} / 広告 {ads} / 投稿 {len(posts)} / 警報 {'あり' if entry else 'なし'}"
          + (f" / 問題 {'・'.join(errors)}" if errors else ""))
    return snap


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="計測して表示するだけ（何も書かない）")
    p.add_argument("--now", help="ISO 時刻（例 2026-11-10T16:05:00+09:00）。時差なしは日本時間とみなす")
    a = p.parse_args(argv)
    if a.now:
        now = datetime.fromisoformat(a.now)
        now = now.replace(tzinfo=JST) if now.tzinfo is None else now.astimezone(JST)
    else:
        now = datetime.now(JST)
    try:
        if not a.dry_run:
            git_pull()
        run(now.replace(microsecond=0), dry_run=a.dry_run)
    except Exception as e:  # noqa: BLE001  1時間ごとの仕事なので落とさない
        print(f"[kpi] 予期しない問題: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
