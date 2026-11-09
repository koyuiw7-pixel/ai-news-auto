#!/usr/bin/env python3
"""止まりの見張り（2026-11-09 オーナー「作業止まるみたいなこと多いからなくして」）。

30分ごと（.github/workflows/stall_watch.yml）と、記事づくりの回（auto_run.yml の最後のほう）で動き、次のどれかがあれば
GitHub の issue（ラベル stall。オーナーにメールが届く）を立てて、state/stall.json に1行残す。全部直ったら issue を閉じる。

  1. 新しい記事が90分出ていない（日本時間 6:00〜24:00 のあいだだけ。main に入った記事＝content/state.json で数える。
     push できずに消えた記事は数えないので、11/9 のように「作ったのにテストで push が止まった」ときも気づける）
  2. 公開（deploy_cloudflare.yml）の最新の回が失敗している
  3. main のテストが落ちている（all_tests.yml の最新の回が失敗、または公開と同じテスト scripts/deploy_tests.py がここで落ちる）
     ・記事づくりの回（auto_run.yml）の最新の回が失敗している（11/9 02:40・03:20 はテストで push が止まり、記事4本が消えた）
  4. SNS の枠を30分以上過ぎても投稿が無い（直近3時間の枠。state/sns_plan_actual.json の予定と実績）

テストは消さない・飛ばさない（落ちたら公開を止めるのは正しい）。そのかわり、落ちたらすぐ知らせる。

  python3 scripts/stall_watch.py                 # 調べて表示するだけ
  python3 scripts/stall_watch.py --issue --state # issue を開く・閉じる、state/stall.json に書く
  python3 scripts/stall_watch.py --skip-tests    # 公開と同じテストを動かさない（記事づくりの回の中など）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "content" / "state.json"
OUT = ROOT / "state" / "stall.json"
SNS_PATH = ROOT / "state" / "sns_plan_actual.json"
JST = timezone(timedelta(hours=9))

ARTICLE_GAP_MIN = 90
DAY_START_HOUR = 6
SNS_LATE_MIN = 30
SNS_LOOKBACK_MIN = 180
SNS_MATCH_BEFORE_MIN = 60  # 枠より早めに出した投稿もその枠の分に数える（Threads は枠の前後にずらして予約する）
LOG_KEEP = 200
LABEL = "stall"
WORKFLOWS = (("deploy", "deploy_cloudflare.yml", "公開（Deploy to Cloudflare Workers）"),
             ("tests", "all_tests.yml", "main のテスト（All tests）"),
             ("auto_run", "auto_run.yml", "記事づくりの回（Auto Article Pipeline）"))


def log(message: str) -> None:
    print(message, flush=True)


def _parse(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=JST)


# --------------------------------------------------------------------------- #
# 1. 記事
# --------------------------------------------------------------------------- #

def last_article_at(state: dict) -> datetime | None:
    """main に入った一番新しい記事を作った時刻（processed_web の slug があるもの）"""
    latest = None
    for value in (state.get("processed_web") or {}).values():
        if isinstance(value, dict) and value.get("slug"):
            at = _parse(value.get("at") or "")
            if at and (latest is None or at > latest):
                latest = at
    return latest


def article_alert(state: dict, now: datetime) -> dict | None:
    now = now.astimezone(JST)
    if now.hour < DAY_START_HOUR:
        return None
    day_start = now.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    last = last_article_at(state)
    since = max(last.astimezone(JST), day_start) if last else day_start
    gap = (now - since).total_seconds() / 60
    if gap < ARTICLE_GAP_MIN:
        return None
    last_text = last.astimezone(JST).strftime("%m/%d %H:%M") if last else "記録なし"
    return {"kind": "no_article", "message": f"新しい記事が {int(gap)} 分出ていません（最後の記事 {last_text}・基準 {ARTICLE_GAP_MIN} 分）"}


# --------------------------------------------------------------------------- #
# 2・3. 公開・テスト・記事づくりの回
# --------------------------------------------------------------------------- #

def _gh_json(args: list[str]) -> list | dict | None:
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60, check=True).stdout
        return json.loads(out or "null")
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        log(f"[stall] gh を使えません（{str(error)[:120]}）")
        return None


def latest_run(workflow: str) -> dict | None:
    runs = _gh_json(["run", "list", "--workflow", workflow, "--branch", "main", "--status", "completed", "--limit", "5",
                     "--json", "databaseId,conclusion,createdAt,url,displayTitle"])
    # 取り消し・飛ばしは数えない（次の回に置き換わっただけ）
    for run in runs or []:
        if run.get("conclusion") in ("success", "failure", "timed_out", "startup_failure"):
            return run
    return None


def workflow_alerts() -> list[dict]:
    alerts = []
    for kind, workflow, label in WORKFLOWS:
        run = latest_run(workflow)
        if run and run.get("conclusion") != "success":
            at = _parse(run.get("createdAt") or "")
            when = at.astimezone(JST).strftime("%m/%d %H:%M") if at else "?"
            alerts.append({"kind": f"{kind}_failed", "message": f"{label} の最新の回が失敗しています（{when} 開始・{run.get('conclusion')}）: {run.get('url')}"})
    return alerts


def deploy_tests_alert() -> dict | None:
    """公開と同じテスト（scripts/deploy_tests.py）をここで動かす。落ちたら push も公開も止まるので、すぐ知らせる"""
    try:
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "deploy_tests.py")], cwd=ROOT, capture_output=True,
                              text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as error:
        return {"kind": "tests_failing", "message": f"公開と同じテストを動かせませんでした（{str(error)[:120]}）"}
    if done.returncode == 0:
        return None
    lines = [line for line in (done.stdout + done.stderr).splitlines() if "失敗" in line or line.startswith(("FAIL", "ERROR", "AssertionError"))]
    return {"kind": "tests_failing", "message": "公開と同じテストが main で落ちています（このままだと記事の push と公開が止まります）: "
            + " / ".join(lines[:4])[:600]}


# --------------------------------------------------------------------------- #
# 4. SNS
# --------------------------------------------------------------------------- #

def _at(day: datetime, hhmm: str) -> datetime | None:
    try:
        hour, minute = (int(x) for x in str(hhmm).split(":")[:2])
    except ValueError:
        return None
    return day.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)


def sns_alerts(plan: dict, now: datetime) -> list[dict]:
    now = now.astimezone(JST)
    if plan.get("date") != now.strftime("%Y-%m-%d"):
        return []
    alerts = []
    for network, row in (plan.get("sns") or {}).items():
        actual = [t for t in (_at(now, a.get("time") or "") for a in row.get("actual") or []) if t]
        missed = []
        for slot in row.get("slots") or []:
            at = _at(now, slot)
            if not at or not (now - timedelta(minutes=SNS_LOOKBACK_MIN) <= at <= now - timedelta(minutes=SNS_LATE_MIN)):
                continue
            if not any(at - timedelta(minutes=SNS_MATCH_BEFORE_MIN) <= t <= at + timedelta(minutes=SNS_LATE_MIN) for t in actual):
                missed.append(slot)
        if missed:
            alerts.append({"kind": f"sns_missed_{network}",
                           "message": f"{network} の枠 {'・'.join(missed)} を{SNS_LATE_MIN}分以上過ぎても投稿がありません"})
    return alerts


def refresh_sns_plan() -> None:
    """予定と実績の記録を手元の投稿の記録から作り直す（読むだけ。Buffer・SNS は呼ばない）"""
    try:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "sns_plan_actual.py")], cwd=ROOT, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        pass


# --------------------------------------------------------------------------- #
# 出力
# --------------------------------------------------------------------------- #

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def write_state(alerts: list[dict], now: datetime) -> bool:
    """state/stall.json に今の結果と、止まりがあった回の1行を書く（止まりが無いままの回は書かない＝コミットを増やさない）。書いたら True"""
    old = load_json(OUT)
    if not alerts and not old.get("alerts") and OUT.exists():
        return False
    history = list(old.get("log") or [])
    if alerts:
        history.append({"at": now.isoformat(timespec="seconds"), "kinds": sorted(a["kind"] for a in alerts),
                        "messages": [a["message"][:300] for a in alerts]})
    elif old.get("alerts"):
        history.append({"at": now.isoformat(timespec="seconds"), "kinds": [], "messages": ["直りました"]})
    data = {"checkedAt": now.isoformat(timespec="seconds"), "ok": not alerts, "alerts": alerts, "log": history[-LOG_KEEP:]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return True


def _gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60).stdout.strip()


MARK = "<!-- stall-kinds: {} -->"


def _last_kinds(number: str, base: list[str]) -> str | None:
    """issue の本文・コメントに残した、最後に知らせた止まりの種類（同じ内容を何度もコメントしないため）"""
    raw = _gh(["issue", "view", number, "--json", "body,comments", *base])
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        return None
    texts = [data.get("body") or ""] + [c.get("body") or "" for c in data.get("comments") or []]
    found = None
    for text in texts:
        if "<!-- stall-kinds: " in text:
            found = text.split("<!-- stall-kinds: ", 1)[1].split(" -->", 1)[0]
    return found


def sync_issue(alerts: list[dict]) -> None:
    """止まりがあれば issue（ラベル stall）を開くか、中身が変わったときだけコメントを足す。無ければ閉じる"""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    base = ["--repo", repo] if repo else []
    _gh(["label", "create", LABEL, "--color", "D93F0B", "--description", "記事・公開・テスト・SNS が止まっている", *base])
    number = _gh(["issue", "list", "--label", LABEL, "--state", "open", "--json", "number", "-q", ".[0].number // empty", *base])
    if not alerts:
        if number:
            _gh(["issue", "close", number, "--comment", "止まりが直ったので閉じます（scripts/stall_watch.py）", *base])
            log(f"[stall] issue #{number} を閉じました")
        return
    kinds = ",".join(sorted(a["kind"] for a in alerts))
    body = "\n".join(f"- {a['message']}" for a in alerts) + "\n\n" + MARK.format(kinds)
    now = datetime.now(JST).strftime("%m/%d %H:%M")
    if not number:
        _gh(["issue", "create", "--label", LABEL, "--title", f"止まりを検知（{now}）: {kinds.replace(',', '・')[:80]}",
             "--body", f"{body}\n\n見張り: scripts/stall_watch.py（30分ごと・記事づくりの回）。直ると自動で閉じます。", *base])
        log("[stall] issue を立てました")
    elif _last_kinds(number, base) != kinds:
        _gh(["issue", "comment", number, "--body", f"{now} の確認:\n{body}", *base])
        log(f"[stall] issue #{number} にコメントしました")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--issue", action="store_true", help="issue（ラベル stall）を開く・閉じる")
    parser.add_argument("--state", action="store_true", help="state/stall.json に書く")
    parser.add_argument("--skip-tests", action="store_true", help="公開と同じテストを動かさない")
    parser.add_argument("--skip-gh", action="store_true", help="GitHub の実行の結果を見ない（手元の確認）")
    args = parser.parse_args()
    now = datetime.now(JST)

    alerts: list[dict] = []
    if hit := article_alert(load_json(STATE_PATH), now):
        alerts.append(hit)
    if not args.skip_gh:
        alerts += workflow_alerts()
    if not args.skip_tests and (hit := deploy_tests_alert()):
        alerts.append(hit)
    refresh_sns_plan()
    alerts += sns_alerts(load_json(SNS_PATH), now)

    for a in alerts:
        log(f"[stall] {a['kind']}: {a['message']}")
    if not alerts:
        log("[stall] 止まりはありません（記事・公開・テスト・SNS）")
    if args.state:
        write_state(alerts, now)
    if args.issue:
        sync_issue(alerts)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## 止まりの見張り\n" + ("\n".join(f"- {a['message']}" for a in alerts) or "- 止まりはありません") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
