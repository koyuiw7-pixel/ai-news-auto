#!/usr/bin/env python3
"""発表から公開までの速さを測る（速報レーンの効果を見る）。

  python3 scripts/latency.py record --out live.json     # デプロイ直後に、開けるようになった記事の時刻を記録（deploy_cloudflare.yml）
  python3 scripts/latency.py merge live.json            # 記録を state/live_log.json に足す（push の衝突対策）
  python3 scripts/latency.py report                     # 直近7日の中央値など（夜の報告・Actions のまとめ用）
  python3 scripts/latency.py report --days 1 --markdown

使う時刻（記事 JSON と state）:
  sourcePublishedAt … 発表の時刻（フィードの公開日時。日付だけの発信元は 00:00 になるので「発表→」の集計から外す）
  detectedAt        … こちらが見つけた時刻（速報レーンは Worker、通常の回はフィードを読んだ時刻）
  generatedAt       … 記事ができた時刻
  liveAt            … サイトで開けるようになった時刻（state/live_log.json。デプロイ直後に記録）
  postedAt          … 速報として SNS に出した時刻（state/threads_posted.json の breaking: true）
標準ライブラリだけで動く。
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
LIVE_PATH = ROOT / "state" / "live_log.json"
POSTED_PATH = ROOT / "state" / "threads_posted.json"
KEEP_DAYS = 30
RECORD_HOURS = 36  # この時間内に作った記事だけ確かめる
JST = timezone(timedelta(hours=9))


def log(message: str) -> None:
    print(message, flush=True)


def site_url() -> str:
    return (os.environ.get("NEXT_PUBLIC_SITE_URL") or "https://ai-tech-express.jp").rstrip("/")


def parse(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_live() -> dict:
    try:
        data = json.loads(LIVE_PATH.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        data = {}
    data.setdefault("live", {})
    return data


def save_live(data: dict) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    live = {k: v for k, v in data.get("live", {}).items() if (parse(v.get("liveAt")) or since) >= since}
    LIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIVE_PATH.write_text(json.dumps({"live": live}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")


def articles(since: datetime) -> list[dict]:
    rows = []
    for path in ARTICLES_DIR.glob("*.json"):
        try:
            article = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        generated = parse(article.get("generatedAt"))
        if generated and generated >= since:
            rows.append(article)
    return rows


# --------------------------------------------------------------------------- #
# record / merge
# --------------------------------------------------------------------------- #


def is_live(url: str) -> bool:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "SaisokuLatency/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read(512)
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def record(out: str, wait: int) -> int:
    """直近 RECORD_HOURS 時間に作った記事のうち、まだ記録の無いものを開いてみて、開けたら今の時刻を残す。
    速報レーンの記事が開けないときだけ wait 秒まで待つ（デプロイ直後のキャッシュ切り替え待ち）"""
    now = datetime.now(timezone.utc)
    live = load_live()["live"]
    # detectedAt の無い記事（この仕組みより前の記事）は、公開の時刻が分からないので記録しない
    todo = [a for a in articles(now - timedelta(hours=RECORD_HOURS)) if a.get("slug") and a.get("detectedAt") and a["slug"] not in live]
    found: dict[str, dict] = {}
    deadline = time.monotonic() + wait
    while todo:
        rest = []
        for article in todo:
            if is_live(f"{site_url()}/articles/{article['slug']}"):
                found[article["slug"]] = {"liveAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            elif article.get("fastLane") or article.get("breaking"):
                rest.append(article)
        if not rest or time.monotonic() >= deadline:
            break
        todo = rest
        time.sleep(15)
    for slug, entry in found.items():
        log(f"[live] {slug} {entry['liveAt']}")
    log(f"[live] 新しく公開を確認 {len(found)} 本")
    Path(out).write_text(json.dumps({"live": found}, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return 0


def merge(path: str) -> int:
    mine = json.loads(Path(path).read_text("utf-8")).get("live", {})
    data = load_live()
    added = 0
    for slug, entry in mine.items():
        if slug not in data["live"]:
            data["live"][slug] = entry
            added += 1
    save_live(data)
    log(f"[live] state/live_log.json に {added} 件を足しました")
    return 0


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #


def minutes(a: datetime | None, b: datetime | None) -> float | None:
    if not a or not b:
        return None
    value = (b - a).total_seconds() / 60
    # 負の値・1週間超は時刻の取り違え（日付だけのフィード等）とみなして外す
    return value if 0 <= value <= 7 * 24 * 60 else None


def date_only(dt: datetime | None) -> bool:
    return bool(dt) and dt.astimezone(timezone.utc).strftime("%H:%M:%S") == "00:00:00"


def collect(days: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    live = load_live()["live"]
    try:
        posted = json.loads(POSTED_PATH.read_text("utf-8")).get("posted", {})
    except Exception:  # noqa: BLE001
        posted = {}
    rows = []
    for article in articles(now - timedelta(days=days)):
        if article.get("sourceType") != "web":
            continue
        # 以前の記事は sourcePublishedAt が無いが、web 記事の publishedAt は発表の時刻なので代わりに使う
        src = parse(article.get("sourcePublishedAt") or article.get("publishedAt"))
        det = parse(article.get("detectedAt"))
        gen = parse(article.get("generatedAt"))
        liv = parse((live.get(article["slug"]) or {}).get("liveAt"))
        post = posted.get(article["slug"]) or {}
        sns = parse(post.get("postedAt")) if post.get("breaking") else None
        # 日付だけ（00:00:00）の時刻は使わない。ただし検知がその30分以内なら本当の時刻とみなす
        src_ok = src if src and (not date_only(src) or (det and timedelta(0) <= det - src <= timedelta(minutes=30))) else None
        rows.append({
            "slug": article["slug"],
            "fast": bool(article.get("fastLane")),
            "breaking": bool(article.get("breaking")),
            "publish_to_live": minutes(src_ok, liv),
            "detect_to_live": minutes(det, liv),
            "publish_to_detect": minutes(src_ok, det),
            "detect_to_generated": minutes(det, gen),
            "publish_to_generated": minutes(src_ok, gen),
            "publish_to_sns": minutes(src_ok, sns),
        })
    return rows


METRICS = [
    ("publish_to_live", "発表→公開"),
    ("publish_to_generated", "発表→記事化"),
    ("publish_to_detect", "発表→検知"),
    ("detect_to_generated", "検知→記事化"),
    ("detect_to_live", "検知→公開"),
    ("publish_to_sns", "発表→SNS"),
]
GROUPS = [("fast", "速報レーン"), ("breaking", "速報（SNS 即時投稿の対象）"), ("all", "公式発表の記事すべて")]


def summarize(rows: list[dict]) -> dict:
    out = {}
    for group, _ in GROUPS:
        chosen = [r for r in rows if group == "all" or r[group]]
        stats = {"articles": len(chosen)}
        for key, _ in METRICS:
            values = sorted(v for r in chosen if (v := r[key]) is not None)
            if values:
                p90 = values[min(len(values) - 1, int(round(0.9 * (len(values) - 1))))]
                stats[key] = {"n": len(values), "median": round(statistics.median(values), 1), "p90": round(p90, 1)}
        out[group] = stats
    return out


def report(days: int, fmt: str) -> int:
    summary = summarize(collect(days))
    if fmt == "json":
        json.dump({"days": days, **summary}, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    lines = []
    if fmt == "markdown":
        lines += [f"### 発表から公開までの速さ（直近{days}日・中央値／90%）", ""]
        lines += ["| | 本数 | " + " | ".join(label for _, label in METRICS) + " |", "|---|---:|" + "---:|" * len(METRICS)]
    else:
        lines.append(f"発表から公開までの速さ（直近{days}日・分。中央値／90パーセンタイル・件数）")
    for group, label in GROUPS:
        stats = summary[group]
        cells = []
        for key, _ in METRICS:
            s = stats.get(key)
            cells.append(f"{s['median']:.0f}分 / {s['p90']:.0f}分 ({s['n']})" if s else "-")
        if fmt == "markdown":
            lines.append(f"| {label} | {stats['articles']} | " + " | ".join(cells) + " |")
        else:
            lines.append(f"  {label}（{stats['articles']}本）")
            for (key, metric), cell in zip(METRICS, cells):
                lines.append(f"    {metric}: {cell}")
    if fmt == "markdown":
        lines += ["", "公開時刻はデプロイ直後の確認（state/live_log.json）。日付だけの発表時刻は「発表→」から外す。"]
    print("\n".join(lines))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_record = sub.add_parser("record", help="開けるようになった記事の時刻を記録")
    p_record.add_argument("--out", required=True)
    p_record.add_argument("--wait", type=int, default=120)
    p_merge = sub.add_parser("merge", help="記録を state/live_log.json に足す")
    p_merge.add_argument("path")
    p_report = sub.add_parser("report", help="直近の速さの集計")
    p_report.add_argument("--days", type=int, default=7)
    group = p_report.add_mutually_exclusive_group()
    group.add_argument("--markdown", action="store_true")
    group.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.cmd == "record":
        return record(args.out, args.wait)
    if args.cmd == "merge":
        return merge(args.path)
    return report(args.days, "json" if args.json else "markdown" if args.markdown else "text")


if __name__ == "__main__":
    raise SystemExit(main())
