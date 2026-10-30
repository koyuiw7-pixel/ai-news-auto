#!/usr/bin/env python3
"""発表から公開までの速さを測る（速報レーンの効果を見る）。

  python3 scripts/latency.py record --out live.json     # デプロイ直後に、開けるようになった記事の時刻を記録（deploy_cloudflare.yml）
  python3 scripts/latency.py merge live.json            # 記録を state/live_log.json に足す（push の衝突対策）
  python3 scripts/latency.py report                     # 直近7日の中央値など（夜の報告・Actions のまとめ用）
  python3 scripts/latency.py report --days 1 --markdown

使う時刻（記事 JSON と state）:
  sourcePublishedAt … 保存した出典日時。発表日時の精度・推定の有無をそれだけでは保証しない
  state/source_time_reviews.json … 元記事の日時・URLに一致する一次資料照合だけを確認済みとする
  detectedAt        … こちらが見つけた時刻（速報レーンは Worker、通常の回はフィードを読んだ時刻）
  generatedAt       … 記事ができた時刻
  liveAt            … デプロイ後にURLのHTTP 200を初めて確認した時刻（厳密な公開時刻ではない）
  postedAt          … 速報として SNS に出した時刻（state/threads_posted.json の breaking: true）
標準ライブラリだけで動く。
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
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
SOURCE_REVIEWS_PATH = ROOT / "state" / "source_time_reviews.json"
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
    # 古い発表の回収も実績。7日超という理由だけで遅い記録を消さない。
    return value if value >= 0 else None


def date_only(dt: datetime | None) -> bool:
    # 元の精度が残らない旧データは、現地/UTCの零時を保守的に除外する。
    # 近い時刻に検知できても、日付だけでない証拠にはならない。
    return bool(dt) and (dt.strftime("%H:%M:%S") == "00:00:00"
                         or dt.astimezone(timezone.utc).strftime("%H:%M:%S") == "00:00:00")


def load_source_reviews() -> dict:
    try:
        return json.loads(SOURCE_REVIEWS_PATH.read_text("utf-8")).get("reviews", {})
    except (OSError, ValueError, AttributeError):
        return {}


def source_time(article: dict, reviews: dict) -> tuple[datetime | None, str]:
    raw = article.get("sourcePublishedAt")
    # publishedAt は検知時刻による代用を含むので、欠測を補うために使わない。
    if not raw:
        return None, "missing_source_timestamp"
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None, "invalid_source_timestamp"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(raw)):
        return None, "date_only_or_midnight"
    if not dt.tzinfo:
        return None, "source_timezone_unknown"
    review = reviews.get(article.get("slug"), {})
    matches = (review.get("articleSourcePublishedAt") == raw
               and review.get("sourceUrl") == article.get("sourceUrl"))
    if matches and review.get("status") == "conflict":
        return None, "source_timestamp_conflict"
    if (matches and review.get("status") == "verified" and parse(review.get("checkedAt"))
            and review.get("precision") == "timestamp"
            and parse(review.get("officialPublishedAt")) == dt):
        return dt, "verified"
    if date_only(dt):
        return None, "date_only_or_midnight"
    # 時刻入りでも原RSS/HTMLを照合していない記録は確認済みの実績へ入れない。
    return dt, "unverified_stored_timestamp"


def collect(days: int, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    live = load_live()["live"]
    reviews = load_source_reviews()
    try:
        posted = json.loads(POSTED_PATH.read_text("utf-8")).get("posted", {})
    except Exception:  # noqa: BLE001
        posted = {}
    rows = []
    for article in articles(now - timedelta(days=days)):
        gen = parse(article.get("generatedAt"))
        if article.get("sourceType") != "web" or not gen or gen > now:
            continue
        src, source_status = source_time(article, reviews)
        verified_src = src if source_status == "verified" else None
        det = parse(article.get("detectedAt"))
        liv = parse((live.get(article["slug"]) or {}).get("liveAt"))
        post = posted.get(article["slug"]) or {}
        sns = parse(post.get("postedAt")) if post.get("breaking") else None
        row = {
            "slug": article["slug"], "fast": bool(article.get("fastLane")),
            "breaking": bool(article.get("breaking")), "source_status": source_status,
            "has_detected": det is not None, "has_live": liv is not None,
            "metric_exclusions": {},
        }
        pairs = {
            "publish_to_live": (verified_src, liv, True),
            "publish_to_generated": (verified_src, gen, True),
            "publish_to_detect": (verified_src, det, True),
            "detect_to_generated": (det, gen, False),
            "detect_to_live": (det, liv, False),
            "generated_to_live": (gen, liv, False),
            "publish_to_sns": (verified_src, sns, True),
            "recorded_publish_to_live": (src, liv, False),
        }
        for key, (begin, finish, needs_verified) in pairs.items():
            reason = None
            if not begin:
                reason = source_status if key.startswith(("publish_", "recorded_publish_")) else "missing_start"
            elif not finish:
                reason = "missing_end"
            elif finish > now:
                reason = "future_observation"
            elif finish < begin:
                reason = "negative_interval"
            # 未監査の時刻を別集計へ出し、確認済み分母に混ぜない。
            if needs_verified and source_status != "verified":
                reason = source_status
            row[key] = None if reason else minutes(begin, finish)
            if reason:
                row["metric_exclusions"][key] = reason
        rows.append(row)
    return rows


METRICS = [
    ("publish_to_live", "確認済み発表→公開確認"),
    ("publish_to_generated", "確認済み発表→記事化"),
    ("publish_to_detect", "確認済み発表→検知"),
    ("detect_to_generated", "検知→記事化"),
    ("detect_to_live", "検知→公開確認"),
    ("generated_to_live", "記事化→公開確認"),
    ("publish_to_sns", "確認済み発表→SNS記録"),
    ("recorded_publish_to_live", "保存出典日時→公開確認（精度未監査を含む）"),
]
GROUPS = [("fast", "速報レーン（一次・二次情報を含む）"),
          ("breaking", "速報（SNS 即時投稿の対象）"),
          ("all", "Web出典の記事すべて（公式発表に限定しない）")]


def summarize(rows: list[dict]) -> dict:
    out = {}
    for group, _ in GROUPS:
        chosen = [r for r in rows if group == "all" or r[group]]
        stats = {"articles": len(chosen),
                 "coverage": {"detected": sum(r["has_detected"] for r in chosen),
                              "liveObserved": sum(r["has_live"] for r in chosen),
                              "sourceTimestampStatus": dict(Counter(r["source_status"] for r in chosen))}}
        for key, _ in METRICS:
            values = sorted(v for r in chosen if (v := r[key]) is not None)
            # nearest-rank: 昇順の ceil(0.9*n) 番目。小標本では最大値になり得る。
            metric = {"n": len(values), "excluded": dict(Counter(
                r["metric_exclusions"][key] for r in chosen if key in r["metric_exclusions"]))}
            if values:
                within30 = sum(v <= 30 for v in values)
                metric.update({"median": round(statistics.median(values), 1),
                               "p90": round(values[math.ceil(0.9 * len(values)) - 1], 1),
                               "within30Count": within30,
                               "within30Pct": round(100 * within30 / len(values), 1)})
            stats[key] = metric
        out[group] = stats
    return out


def report(days: int, fmt: str) -> int:
    now = datetime.now(timezone.utc)
    summary = summarize(collect(days, now))
    notes = [
        "対象は生成日時によるコホート。公開確認はURLのHTTP 200初観測で、厳密な初公開時刻や本文一致を保証しない。",
        "確認済み発表は現在の一次資料日時と元記事のURL/日時が一致する監査済み例だけ。原資料の歴史的初出や全件の精度を保証しない。",
        "sourcePublishedAt欠測の代用なし。日付精度・日時不一致・負値は除外理由を表示し、遅さが7日超という理由では除外しない。",
        "30分以内率の分母は各指標の有効n。欠測を含む全記事や未記事化の発表の達成率ではない。P90はnearest-rank ceil(0.9*n)。",
        "速報レーン・速報グループは重複し得る。SNS記録は配信完了の保証ではない。"
    ]
    if fmt == "json":
        json.dump({"days": days, "asOf": now.isoformat(),
                   "generatedFrom": (now - timedelta(days=days)).isoformat(),
                   "p90Method": "nearest-rank: ceil(0.9*n), one-based",
                   "notes": notes, **summary}, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    lines = [f"発表・検知から公開確認まで（直近{days}日生成、分）", ""]
    for group, label in GROUPS:
        stats = summary[group]
        coverage = stats["coverage"]
        lines += [f"{'### ' if fmt == 'markdown' else ''}{label}（{stats['articles']}本）",
                  f"検知記録 {coverage['detected']}/{stats['articles']}、公開確認記録 {coverage['liveObserved']}/{stats['articles']}。",
                  "出典日時: " + json.dumps(coverage["sourceTimestampStatus"], ensure_ascii=False)]
        if fmt == "markdown":
            lines += ["", "| 指標 | 有効n | 中央値 | P90 | 30分以内 | 除外理由別件数 |",
                      "|---|---:|---:|---:|---:|---|"]
        for key, metric in METRICS:
            s = stats[key]
            excluded = ", ".join(f"{k}: {v}" for k, v in s["excluded"].items()) or "なし"
            median = str(s["median"]) if s["n"] else "未算出"
            p90 = str(s["p90"]) if s["n"] else "未算出"
            rate = f"{s['within30Count']}/{s['n']} ({s['within30Pct']}%)" if s["n"] else "未算出"
            if fmt == "markdown":
                lines.append(f"| {metric} | {s['n']} | {median} | {p90} | {rate} | {excluded} |")
            else:
                lines.append(f"  {metric}: n={s['n']}、中央値 {median}、P90 {p90}、30分以内 {rate}、除外 {excluded}")
        lines.append("")
    lines += notes
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
