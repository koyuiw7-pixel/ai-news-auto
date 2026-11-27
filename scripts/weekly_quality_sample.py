#!/usr/bin/env python3
"""週に1回の記事の質の抜き取り（2026-11-28 見直し「あなたの数字のニュース」）。

直近7日に公開した記事から10本をくじで選び、記事の8つの基準（scripts/quality_bar.py）と
あなたの数字の4つ（scripts/your_number.py: 数字・期限・窓口と公式の URL・公式の出典）で点を付け、
会議で読む日本語のレポートを state/quality_weekly/YYYY-MM-DD.md に書く。LLM は使わない（費用0円）。

  python3 scripts/weekly_quality_sample.py                 # 今日の日付のレポート
  python3 scripts/weekly_quality_sample.py --k 10 --days 7 --seed 1 --out /tmp/test.md

週のまとめのワークフロー（.github/workflows/weekly.yml）が毎週月曜の朝に動かしてコミットする。
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quality_bar  # noqa: E402
import your_number  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "state" / "quality_weekly"  # out/ は git に入らないので、会議が読めるよう state/ に置く（毎週コミット）
JST = timezone(timedelta(hours=9))
SITE = "https://ai-tech-express.jp"
KIND_LABEL = {"money": "家計のお金・制度", "alert": "注意（リコール・流出・障害）", "safety": "安全の速報", None: "軸の外"}


def recent(articles: list[dict], now: datetime, days: int) -> list[dict]:
    since = now - timedelta(days=days)
    rows = [a for a in articles if (t := quality_bar._published(a)) and since <= t <= now and a.get("type") != "roundup"]  # noqa: SLF001
    return sorted(rows, key=lambda a: a.get("publishedAt") or "")


def score(a: dict, pool: dict | None = None) -> dict:
    bar = quality_bar.check(a, pool=pool)
    num = your_number.check(a)
    num_total = 4 if num["applies"] else 0
    num_ok = num_total - len(num["missing"])
    return {"bar": bar, "num": num, "points": bar["score"] + num_ok, "total": 8 + num_total}


def report(articles: list[dict], now: datetime, k: int = 10, days: int = 7, seed: int | None = None) -> str:
    rows = recent(articles, now, days)
    day = now.astimezone(JST).strftime("%Y-%m-%d")
    rng = random.Random(seed if seed is not None else day)
    pick = rng.sample(rows, min(k, len(rows))) if rows else []
    pool = quality_bar.corpus(articles)
    lines = [f"# 記事の質の抜き取り（{day}・直近{days}日）", "",
             f"この{days}日に公開した記事 {len(rows)} 本から、くじで {len(pick)} 本を選んで点を付けました。",
             "点の付け方は、記事の8つの基準（8点）と、あなたの数字の4つ（家計のお金・注意の記事だけ。4点）です。", ""]
    if rows:
        all_scores = [score(a, pool) for a in rows]
        axis = [s for s in all_scores if s["num"]["applies"]]
        full = [s for s in axis if not s["num"]["missing"]]
        per_day = len(rows) / days
        lines += ["## この週の全体", "",
                  f"- 公開した記事: {len(rows)} 本（1日あたり約 {per_day:.0f} 本）",
                  f"- 家計のお金・注意の記事: {len(axis)} 本。そのうち4つ（数字・期限・窓口・公式の出典）がそろった記事: {len(full)} 本",
                  f"- 軸の外の記事（新しい決まりでは自動で作らない話題）: {sum(1 for s in all_scores if s['num']['kind'] is None)} 本", ""]
        counts = {key: sum(1 for s in axis if key in s["num"]["missing"]) for key in your_number.REQUIREMENTS}
        if any(counts.values()):
            lines.append("足りなかったもの（家計のお金・注意の記事のうち）:")
            for key, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                if n:
                    lines.append(f"- {your_number.REQUIREMENTS[key]}: {n} 本")
            lines.append("")
    lines += ["## 選んだ記事", ""]
    for a in pick:
        s = score(a, pool)
        bar, num = s["bar"], s["num"]
        lines += [f"### {a.get('title')}", "",
                  f"- ページ: {SITE}/articles/{a.get('slug')}",
                  f"- 話題: {KIND_LABEL.get(num['kind'], '軸の外')}・書き手: {a.get('writer') or '自動'}・本文 {len(a.get('body') or '')}字",
                  f"- 点数: {s['points']} / {s['total']}", ""]
        lines += ["| 基準 | 結果 |", "|---|---|"]
        for p, name in quality_bar.POINTS.items():
            lines.append(f"| {p}. {name} | {'○' if p not in bar['notes'] else '× ' + bar['notes'][p][:60]} |")
        if num["applies"]:
            for key, name in your_number.REQUIREMENTS.items():
                lines.append(f"| {key}. {name.split('（')[0]} | {'○' if key not in num['notes'] else '× ' + num['notes'][key][:60]} |")
        else:
            lines.append("| あなたの数字の4つ | 求めない記事（家計のお金・注意の話ではない） |")
        lines.append("")
    if not pick:
        lines.append("この期間に公開した記事はありません。")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    text = report(quality_bar.load_articles(), now, args.k, args.days, args.seed)
    out = Path(args.out) if args.out else OUT_DIR / f"{now.astimezone(JST).strftime('%Y-%m-%d')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, "utf-8")
    print(text)
    print(f"[done] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
