#!/usr/bin/env python3
"""LINE公式アカウントへ、主要記事のダイジェストを一斉配信（Messaging API の broadcast）。

LINE_CHANNEL_ACCESS_TOKEN が無ければ何もしない。無料プラン（コミュニケーションプラン）は
月200通（＝配信回数×友だち数）で超過配信ができないため、既定は「週1回（月曜）・直近7日の5本」。
送る前に「今月の残り通数 ≥ 友だち数」を確かめ、足りなければ送らない。

  python3 scripts/line_digest.py --dry-run          # 文面だけ表示
  LINE_DIGEST_DAYS=daily python3 scripts/line_digest.py   # 毎日送る（友だちが6人以下のときだけ現実的）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from digest import JST, article_url, pick_top, site_url, title_of  # noqa: E402

API = "https://api.line.me/v2/bot"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MAX_TEXT = 5000  # LINE のテキストメッセージの上限


def call(path: str, payload: dict | None = None) -> tuple[int, dict]:
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method="POST" if payload is not None else "GET",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read()
            return res.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        return error.code, {"error": error.read()[:300].decode(errors="replace")}


def remaining_quota() -> tuple[int | None, int | None]:
    """(今月の残り通数, 友だち数)。取れなければ None"""
    _, quota = call("/message/quota")
    _, used = call("/message/quota/consumption")
    remaining = None
    if quota.get("type") == "limited" and "totalUsage" in used:
        remaining = int(quota["value"]) - int(used["totalUsage"])
    elif quota.get("type") == "none":
        remaining = 10**9
    # 友だち数は前日分まで（当日は集計前）
    day = (datetime.now(JST) - timedelta(days=1)).strftime("%Y%m%d")
    _, followers = call(f"/insight/followers?date={day}")
    # 実際に届く人数（ブロックを除く）を優先
    reach = followers.get("targetedReaches") or followers.get("followers")
    return remaining, (int(reach) if reach is not None else None)


def compose(articles: list[dict], weekly: bool) -> str:
    jst = datetime.now(JST)
    head = f"📰 サイソク{'週刊まとめ' if weekly else '朝刊'}（{jst.month}/{jst.day}）"
    lines = [head, "押さえておきたいAIニュース" + f"{len(articles)}本です。", ""]
    for i, a in enumerate(articles, 1):
        lines += [f"{i}. {title_of(a)}", article_url(a["slug"], "line", f"{'weekly' if weekly else 'daily'}-{jst:%Y%m%d}"), ""]
    lines.append(f"ほかの記事 → {site_url()}/?utm_source=line&utm_medium=social")
    return "\n".join(lines)[:MAX_TEXT]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="曜日の指定を無視して送る")
    args = parser.parse_args()

    days = (os.environ.get("LINE_DIGEST_DAYS") or "mon").lower()
    weekly = days != "daily"
    today = WEEKDAYS[datetime.now(JST).weekday()]
    if not args.force and not args.dry_run and weekly and today not in days.split(","):
        print(f"[skip] 配信日ではありません（LINE_DIGEST_DAYS={days}、今日={today}）")
        return 0

    articles = pick_top(hours=24 * 7 if weekly else 24, n=5, ai_only=True)
    if not articles:
        print("[skip] 対象記事がありません")
        return 0
    text = compose(articles, weekly)
    if args.dry_run:
        print(text)
        return 0
    if not os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"):
        print("[skip] LINE_CHANNEL_ACCESS_TOKEN が未設定のため、何もしません")
        return 0

    remaining, reach = remaining_quota()
    if remaining is None or reach is None:
        print(f"[skip] 残り通数か友だち数を取得できませんでした（残り={remaining}, 友だち={reach}）")
        return 0
    if reach == 0:
        print("[skip] 友だちが0人です")
        return 0
    if remaining < reach:
        print(f"[skip] 今月の残り通数 {remaining} < 友だち {reach} 人。無料プランは超過配信できないため送りません")
        return 0

    status, body = call("/message/broadcast", {"messages": [{"type": "text", "text": text}]})
    if status != 200:
        print(f"[NG] broadcast {status}: {body}")
        return 1
    print(f"[done] {reach} 人へ配信（残り通数 {remaining - reach}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
