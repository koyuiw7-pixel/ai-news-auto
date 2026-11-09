#!/usr/bin/env python3
"""
記事が「どこまで読まれたか・どれだけ見られたか・次にどこを押されたか・PR 枠が画面に出たか」を出す（自前計測。2026-11-10〜）。

  python3 scripts/reading_report.py                 # 今日（日本時間・途中まで）
  python3 scripts/reading_report.py --yesterday
  python3 scripts/reading_report.py --date 2026-11-10 --top 10
  python3 scripts/reading_report.py --date 2026-11-10 --json

数えるのは Worker（cloudflare/reading.ts）、送るのは画面の components/ReadingBeacon.tsx、決まりは lib/reading.ts。
1件 = 推定の同じ人 × 同じ記事 × 同じ日（最後の状態）。ブラウザを急に閉じると送れないことがあるので、数は少なめに出る（下限）。
鍵 AFF_STATS_TOKEN は環境変数か .env.local から読む（scripts/aff_stats.py と同じ）。中身は表示しない。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aff_stats import JST, load_token  # noqa: E402
from inflow_report import LABELS, site, title_of  # noqa: E402

ZONES = {"story": "要点の下の「この話の続き」", "nextread": "次に読む記事", "body": "本文とその前後", "header": "上のメニュー・速報の帯", "aside": "横の欄", "footer": "ページの一番下"}
LABELS_ALL = {**LABELS, "internal": "サイト内の移動"}


def fetch(token: str, date: str) -> dict:
    req = urllib.request.Request(
        f"{site()}/api/aff/reading?date={date}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "SaisokuReadingReport/1.0", "X-Saisoku-Internal": "1"},
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


def pct(part: int, whole: int) -> str:
    return f"{round(part * 100 / whole)}%" if whole else "-"


def line(row: dict) -> str:
    v = row.get("views", 0)
    reached, engaged = row.get("reached", {}), row.get("engaged", {})
    ads = row.get("adSeen", {})
    ad_text = "、".join(f"{k} {pct(n, v)}" for k, n in sorted(ads.items(), key=lambda kv: -kv[1])) or "なし"
    return (
        f"{v}件 / 半分まで読んだ {pct(reached.get('d50', 0), v)}・最後まで {pct(reached.get('d100', 0), v)}"
        f" / 30秒以上 {pct(engaged.get('s30', 0), v)}・中央値 {row.get('medianSecondsBucket', 0)}秒台"
        f" / 次に読む記事が見えた {pct(row.get('nextReadSeen', 0), v)}"
        f" / サイト内の次のページへ {pct(row.get('internalClicks', 0), v)}"
        f" / PR 枠が見えた: {ad_text}"
    )


def render(data: dict, top: int = 10) -> str:
    total = data.get("total", {})
    out = [f"■ {data.get('date')}（日本時間）記事の読まれ方（同じ人×同じ記事で1件）: {line(total)}"]
    exits = total.get("exits", {})
    if exits:
        out.append("  次のページへ押した場所: " + " / ".join(f"{ZONES.get(k, k)} {n}" for k, n in sorted(exits.items(), key=lambda kv: -kv[1])))
    if data.get("bySource"):
        out.append("  流入元ごと:")
        out += [f"    {LABELS_ALL.get(r['source'], r['source'])}: {line(r)}" for r in data["bySource"]]
    if data.get("byPage"):
        out.append(f"  記事ごと（上位{top}）:")
        out += [f"    「{title_of(r['page'])}」 {line(r)}" for r in data["byPage"][:top]]
    if data.get("truncated"):
        out.append("  注意: 件数が多すぎて途中までの集計です")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--date")
    ap.add_argument("--yesterday", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    now = datetime.now(JST)
    date = args.date or (now - timedelta(days=1) if args.yesterday else now).strftime("%Y-%m-%d")
    token = load_token()
    if not token:
        print("AFF_STATS_TOKEN がありません（環境変数か .env.local）", file=sys.stderr)
        return 2
    try:
        data = fetch(token, date)
    except urllib.error.HTTPError as error:
        print(f"取得に失敗しました: HTTP {error.code}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=1) if args.json else render(data, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
