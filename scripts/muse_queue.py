#!/usr/bin/env python3
"""とろいも（Muse）に頼む動画の受け渡し（state/muse_queue.json）。2026-11-05 オーナー決定: SNS に出すすべての記事の動画を Muse で。

Muse の受け渡し＝SNS の予定。threads_post が SNS の枠に入れた記事（state/threads_posted.json の「動画待ち」）を、枠の時刻の順に
入れる（枠の日（日本時間）ごとに scripts/sns_plan.json の muse.max_per_day 本＝6本まで）。速報（Muse を待たない）は入れない。

  python3 scripts/muse_queue.py            # 予定に入った記事を足す（auto_run の投稿の段のあと・muse_queue.yml の定期実行）
  python3 scripts/muse_queue.py --dry-run  # 書かずに表示だけ
  python3 scripts/muse_queue.py --list     # 今の待ちの一覧（枠の時刻の順・URL・題名・期限）

項目: slug・url（記事）・title・slot（枠の時刻）・deadline（この時刻まで Muse の動画を待つ＝枠＋ wait_hours）・file（news-<slug>.mp4）。
Claude（対話の回）が Muse に順に渡し、できた動画を `python3 scripts/muse_ingest.py <mp4> <slug>` で取り込む。
期限までに来なければ、その投稿は今の自動動画（同じ検査）で出す（投稿の本数は減らさない。sns_video_followup）。
期限を過ぎて24時間たっても届かなかったものは expired にする。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sns_plan  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
POSTED = ROOT / "state" / "threads_posted.json"
SITE = "https://ai-tech-express.jp"
JST = sns_plan.JST
NUMBER_RE = re.compile(r"[0-9０-９][0-9０-９,，.．]*\s*(?:万|億|兆)?\s*(?:円|ドル|%|％|件|台|人|社|kg|ｋｇ|W|Nm|倍|GB|TB|mAh|インチ|km|店舗|校|自治体|市町村?)")
EXPIRE_H = 24


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def strong_number(article: dict) -> str:
    m = NUMBER_RE.search(f"{article.get('title', '')} {article.get('lede', '')}")
    return m.group(0).strip() if m else ""


def official(article: dict) -> bool:
    url = str(article.get("sourceUrl") or "")
    return article.get("sourceType") == "web" and url.startswith("https://") and "youtube.com" not in url


def muse_score(article: dict) -> tuple[float, str]:
    """(点数, 理由)。条件に合わなければ (0, 理由)"""
    if sns_plan.excluded(article):
        return 0.0, "SNS に出さない話題"
    if not official(article):
        return 0.0, "公式の出どころが無い"
    lane, lane_score = sns_plan.lane_of(article)
    number = strong_number(article)
    if lane not in ("safety", "money", "brand", "consumer_ai") or (lane == "consumer_ai" and not number):
        return 0.0, "ブランド・お金・暮らしの話題ではない"
    if not number:
        return 0.0, "立つ数字が無い"
    score = lane_score + 3 + (1 if sns_plan.japanese_source(article) else 0)
    label = sns_plan.plan()["lanes"][lane]["label"]
    return float(score), f"{label}・数字「{number}」・公式（{article.get('sourceName') or article.get('sourceUrl', '')[:60]}）"


def load_articles(since: datetime) -> list[dict]:
    out = []
    for path in ARTICLES.glob("*.json"):
        try:
            a = json.loads(path.read_text("utf-8"))
            if datetime.fromisoformat(a["generatedAt"]) >= since:
                out.append(a)
        except (ValueError, KeyError):
            continue
    return out


def expire(data: dict, now: datetime) -> int:
    n = 0
    for item in data.get("items", []):
        if item.get("status") != "queued":
            continue
        try:
            queued = datetime.fromisoformat(item.get("deadline") or item["queuedAt"])
        except (KeyError, ValueError):
            continue
        if now - queued > timedelta(hours=EXPIRE_H):
            item.update({"status": "expired", "expiredAt": now.isoformat(timespec="seconds")})
            n += 1
    return n


def slot_of(rec: dict) -> datetime | None:
    raw = (rec.get("pending") or {}).get("slot") or rec.get("dueAt") or ""
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else None


def queued_on(data: dict, day) -> int:
    """その日（日本時間・枠の日）の分として入れた本数"""
    n = 0
    for i in data.get("items", []):
        raw = i.get("slot") or i.get("queuedAt")
        try:
            if raw and datetime.fromisoformat(raw).astimezone(JST).date() == day:
                n += 1
        except ValueError:
            continue
    return n


def queued_today(data: dict, now: datetime) -> int:
    return queued_on(data, now.astimezone(JST).date())


def pick(data: dict, now: datetime, articles: list[dict] | dict | None, posted: dict) -> list[dict]:
    """SNS の予定（動画待ち）に入った記事を、枠の時刻の順に入れる。枠の日ごとに max_per_day 本まで。
    もう出た・速報・オーナーの保留・SNS に出さない話題・枠から wait_hours を過ぎたものは入れない"""
    m = sns_plan.plan()["muse"]
    cap = int(m["max_per_day"])
    wait = float(m["wait_hours"])
    taken = {i["slug"] for i in data.get("items", [])}
    by_slug = {a["slug"]: a for a in articles} if isinstance(articles, list) else dict(articles or {})
    rows = []
    for slug, rec in (posted or {}).items():
        if rec.get("status") != "awaiting_video" or slug in taken or rec.get("ownerHold") or rec.get("breaking") or rec.get("urgent"):
            continue
        slot = slot_of(rec)
        if not slot or now - slot > timedelta(hours=wait):
            continue  # 待つ期限をもう過ぎた（自動動画で出す）
        article = by_slug.get(slug)
        if article is None:
            path = ARTICLES / f"{slug}.json"
            try:
                article = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
        if sns_plan.excluded(article):
            continue
        rows.append((slot, slug, article))
    out = []
    per_day: dict = {}
    for slot, slug, a in sorted(rows, key=lambda r: r[0]):
        day = slot.astimezone(JST).date()
        per_day.setdefault(day, queued_on(data, day))
        if per_day[day] >= cap:
            continue
        per_day[day] += 1
        queued_at = now
        deadline = max(slot, queued_at) + timedelta(hours=float(os.environ.get("MUSE_WAIT_HOURS") or wait))
        score, why = muse_score(a)
        out.append({"slug": slug, "url": f"{SITE}/articles/{slug}", "title": a.get("title", ""),
                    "slot": slot.isoformat(timespec="seconds"), "slotJst": slot.astimezone(JST).strftime("%m/%d %H:%M"),
                    "deadline": deadline.isoformat(timespec="seconds"), "deadlineJst": deadline.astimezone(JST).strftime("%m/%d %H:%M"),
                    "reason": why if score > 0 else "SNS の予定に入った記事（すべての投稿を Muse で）", "score": score,
                    "lane": sns_plan.lane_of(a)[0], "breaking": False,
                    "file": f"news-{slug}.mp4", "queuedAt": queued_at.isoformat(timespec="seconds"), "status": "queued"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    data = sns_plan.load_muse_queue()
    data.setdefault("items", [])
    if args.list:
        rows = sorted((i for i in data["items"] if i.get("status") == "queued"), key=lambda i: i.get("slot") or i.get("queuedAt") or "")
        for i in rows:
            print(f"枠 {i.get('slotJst', '?'):11} 期限 {i.get('deadlineJst', '?'):11} {i['slug']}\n          {i.get('title', '')}\n          {i.get('url')}")
        return 0
    expired = expire(data, now)
    posted = (json.loads(POSTED.read_text("utf-8")) if POSTED.exists() else {}).get("posted") or {}
    new = pick(data, now, None, posted)
    for i in new:
        log(f"[muse] 候補: {i['slug']}（{i['reason']}）")
    if not new and not expired:
        log("[muse] 新しい候補はありません")
        return 0
    data["items"] = (data["items"] + new)[-60:]
    data["updatedAt"] = now.isoformat(timespec="seconds")
    if args.dry_run:
        print(json.dumps(new, ensure_ascii=False, indent=2))
        return 0
    sns_plan.MUSE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    sns_plan.MUSE_QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    log(f"[muse] {len(new)}本を足し、{expired}本を期限切れにしました（state/muse_queue.json）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
