#!/usr/bin/env python3
"""
記事ページの右側（PC）の「よく読まれている記事」の一覧を作る（content/popular.json）。

数えるのは自前の計測（scripts/inflow_report.py と同じ /api/aff/inflow。実ブラウザで外から来た人だけ）の、
今日と昨日（日本時間）の記事ごとの訪問の合計。公開中の記事だけを多い順に最大 10 本。
鍵（AFF_STATS_TOKEN）が無い・計測が取れないときは何も書き換えない（今の一覧のまま。一覧が無ければ画面は新着に切り替える）。

  python3 scripts/popular_articles.py            # content/popular.json を更新
  python3 scripts/popular_articles.py --dry-run  # 表示だけ
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aff_stats import JST, load_token  # noqa: E402
from inflow_report import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
OUT = ROOT / "content" / "popular.json"
LIMIT = 10


def rank(rows_by_day: list[list[dict]], live: set[str], limit: int = LIMIT) -> list[dict]:
    views: dict[str, int] = {}
    for rows in rows_by_day:
        for row in rows:
            page = str(row.get("page") or "")
            if page in live:
                views[page] = views.get(page, 0) + int(row.get("views") or 0)
    best = sorted(views.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"slug": slug, "views": n} for slug, n in best if n > 0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    token = load_token()
    if not token:
        print("popular: AFF_STATS_TOKEN が無いので更新しません")
        return 0
    today = datetime.now(JST).date()
    days = [today, today - timedelta(days=1)]
    rows_by_day: list[list[dict]] = []
    for day in days:
        try:
            rows_by_day.append(fetch(token, day.isoformat()).get("rows") or [])
        except Exception as exc:  # noqa: BLE001 — 計測が取れない日は今の一覧のまま
            print(f"popular: {day} の計測を取れませんでした（{type(exc).__name__}）。更新しません")
            return 0
    live = {p.stem for p in ARTICLES.glob("*.json")}
    items = rank(rows_by_day, live)
    if not items:
        print("popular: 訪問のある記事がまだ無いので更新しません")
        return 0
    data = {"updatedAt": datetime.now(JST).isoformat(timespec="seconds"), "days": [d.isoformat() for d in days], "items": items}
    for item in items:
        print(f"  {item['views']:>5}  {item['slug']}")
    if not args.dry_run:
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
        print(f"popular: {OUT.relative_to(ROOT)} を {len(items)} 本で更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
