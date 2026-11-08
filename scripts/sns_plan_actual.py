#!/usr/bin/env python3
"""SNS の「予定と実績」を1つの記録にする（2026-11-08 オーナーの新しい進め方: 予定15本・実績3本のような差をその日のうちに見えるように）。

読むだけ（Buffer・SNS は呼ばない）。手元の投稿の記録から、今日（日本時間）の SNS ごとの
  planned: 枠の時刻（sns_plan の枠）と、その枠に入った記事（Threads は予定・予約の記録から）
  actual:  実際に Buffer に予約した／出した投稿（時刻・記事・Buffer の ID・URL があれば URL）
を state/sns_plan_actual.json に書く。夜の報告はこのファイルを読めばよい。

  python3 scripts/sns_plan_actual.py            # 書いて、要約を表示する
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sns_plan  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
OUT = STATE / "sns_plan_actual.json"
JST = timezone(timedelta(hours=9))
THREADS_PROFILE = "https://www.threads.com/@saisoku637"


def _load(name: str) -> dict:
    try:
        return json.loads((STATE / name).read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _jst(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(JST)


def _today(dt: datetime | None, day: str) -> bool:
    return bool(dt) and dt.strftime("%Y-%m-%d") == day


def _slots(fn) -> list[str]:
    try:
        return [f"{h:02d}:{m:02d}" for h, m in fn()]
    except Exception:  # noqa: BLE001
        return []


def build(now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(JST)
    day = now.strftime("%Y-%m-%d")
    threads = _load("threads_posted.json").get("posted") or {}
    out: dict = {"date": day, "updatedAt": now.isoformat(timespec="seconds"), "sns": {}}

    # Threads: 予定（動画待ち＝まだ Buffer に送っていない）と実績（Buffer に予約済み・手で出したもの）
    t_plan, t_act = [], []
    for slug, rec in threads.items():
        if not isinstance(rec, dict):
            continue
        status = rec.get("status") or ""
        when = _jst((rec.get("pending") or {}).get("slot") or rec.get("dueAt") or rec.get("postedAt") or "")
        if not _today(when, day):
            continue
        row = {"time": when.strftime("%H:%M"), "slug": slug}
        if status == "awaiting_video":
            t_plan.append({**row, "status": "planned"})
            continue
        if status in ("owner_withdrawn",):
            continue
        t_plan.append({**row, "status": status or "scheduled"})
        t_act.append({**row, "status": status or "scheduled", "bufferId": rec.get("id") or "", "via": rec.get("via") or "",
                      "url": rec.get("permalink") or "", "due": "past" if when <= now else "future"})
    out["sns"]["threads"] = {"slots": _slots(sns_plan.slots_jst), "planned": sorted(t_plan, key=lambda r: r["time"]),
                             "actual": sorted(t_act, key=lambda r: r["time"]), "profile": THREADS_PROFILE}

    # Bluesky: threads_posted の channels.bluesky（at:// の URI）
    b_act = []
    for slug, rec in threads.items():
        uri = ((rec or {}).get("channels") or {}).get("bluesky") if isinstance(rec, dict) else ""
        when = _jst((rec or {}).get("blueskyAt") or (rec or {}).get("postedAt") or "") if isinstance(rec, dict) else None
        if uri and _today(when, day):
            b_act.append({"time": when.strftime("%H:%M"), "slug": slug, "url": str(uri)})
    # 2026-11-07〜 Bluesky だけの枠の投稿は state/bluesky_extra.json に残る（ここを読んでいなかったので、11/8 は12本出ていたのに「2本」と出ていた）
    seen = {r["slug"] for r in b_act}
    for slug, rec in _load("bluesky_extra.json").items():
        when = _jst((rec or {}).get("at") or "") if isinstance(rec, dict) else None
        if isinstance(rec, dict) and rec.get("uri") and _today(when, day) and slug not in seen:
            b_act.append({"time": when.strftime("%H:%M"), "slot": rec.get("slot") or "", "slug": slug, "url": str(rec["uri"]),
                          "style": rec.get("style") or ""})
    out["sns"]["bluesky"] = {"slots": _slots(sns_plan.bluesky_slots_jst), "actual": sorted(b_act, key=lambda r: r["time"])}

    # X・Facebook: それぞれの記録（slot は予定の枠）
    for key, name, fn in (("x", "x_posted.json", sns_plan.x_slots_jst), ("facebook", "facebook_posted.json", sns_plan.fb_slots_jst)):
        act = []
        for slug, rec in _load(name).items():
            when = _jst((rec or {}).get("at") or "") if isinstance(rec, dict) else None
            if _today(when, day) and rec.get("id"):
                act.append({"time": when.strftime("%H:%M"), "slot": rec.get("slot") or "", "slug": slug, "bufferId": rec.get("id"),
                            "style": rec.get("style") or ""})
        out["sns"][key] = {"slots": _slots(fn), "actual": sorted(act, key=lambda r: r["time"])}

    for v in out["sns"].values():
        v["summary"] = f"予定の枠 {len(v['slots'])}本・実績 {len(v['actual'])}本"
    return out


def main() -> int:
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    for name, v in data["sns"].items():
        print(f"[plan-actual] {data['date']} {name}: {v['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
