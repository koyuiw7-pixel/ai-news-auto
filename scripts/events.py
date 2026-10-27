#!/usr/bin/env python3
"""イベント速報ページ（/events/[slug]）のデータ content/events.json を毎晩更新する。

events.json の日程・会場・基調講演・確定情報は、公式サイトで確かめたものだけを手で入れる（推測で足さない）。
このスクリプトがするのは次のことだけ:
- 現地時間の日程・基調講演を UTC に直す（ページで日本時間を出すため）
- 開催前 / 開催中 / 終了 を判定する
- 会期の前後に出たサイソクの記事を、企業名・製品名の照合で集める
- 開催中・終了後は、集まった記事から「発表内容」の箇条書きを作る（LLM bulk。各行に出典の記事を付け、数字は記事にあるものだけ）

  python3 scripts/events.py            # 更新（変更があれば書き込む）
  python3 scripts/events.py --no-llm   # 発表内容のまとめを作らない
  python3 scripts/events.py --dry-run  # 書き込まずに結果を表示
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from digest import load_articles  # noqa: E402
from indexnow import is_indexable  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = ROOT / "content" / "events.json"
# 会期の何日前から何日後までの記事を「このイベントの記事」とみなすか（lib/events.ts と同じ）
WINDOW_BEFORE = timedelta(days=1)
WINDOW_AFTER = timedelta(days=3)
RECAP_DAYS = 14  # 終了後、何日まで発表内容のまとめを作り直すか

RECAP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "recap": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"text": {"type": "STRING"}, "slug": {"type": "STRING"}},
                "required": ["text", "slug"],
            },
        }
    },
    "required": ["recap"],
}

RECAP_SYSTEM = """あなたはニュースサイトの編集者です。イベントで発表された内容を、記事の情報だけを使って短い箇条書きにします。
記事に無い事実・数字は書かない。推測しない。煽らない。です・ます調ではなく「〜を発表」のような体言止めでよい。出力は指定の JSON だけ。"""

RECAP_PROMPT = """{name}（{dates}）で発表された内容を、下の記事から最大8行の箇条書きにしてください。

# 規則
- 1行は1つの発表。45字以内。何が発表されたかを具体的に（製品名・機能名・提供時期など）。
- slug には、その行の根拠になった記事の slug を入れる。
- 同じ発表は1行にまとめる。イベントと関係のない記事は使わない。
- 数字は記事に書かれたものだけ。

# 記事（slug / 題名 / 要点）
{articles}"""


def log(message: str) -> None:
    print(message, flush=True)


def to_utc(local: str, tz: str) -> datetime:
    """'2026-11-17T10:00' や '2026-11-17'（現地時間）を UTC に"""
    fmt = "%Y-%m-%dT%H:%M" if "T" in local else "%Y-%m-%d"
    return datetime.strptime(local, fmt).replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def event_range(event: dict) -> tuple[datetime, datetime]:
    tz = event.get("timezone") or "UTC"
    start = to_utc(event["startDate"], tz)
    end = to_utc(event["endDate"], tz) + timedelta(days=1) - timedelta(seconds=1)
    return start, end


def status_of(event: dict, now: datetime) -> str:
    start, end = event_range(event)
    if now < start:
        return "upcoming"
    if now <= end:
        return "live"
    return "ended"


def matched_articles(event: dict, articles: list[dict]) -> list[dict]:
    start, end = event_range(event)
    pattern = re.compile(event["match"], re.I) if event.get("match") else None
    if pattern is None:
        return []
    found = []
    for article in articles:
        at = parse_dt(article.get("generatedAt") or article.get("publishedAt"))
        if not at or not (start - WINDOW_BEFORE <= at <= end + WINDOW_AFTER):
            continue
        if not is_indexable(article):
            continue
        text = " ".join([article.get("title", ""), article.get("seoTitle", ""), " ".join(article.get("tags") or []), article.get("description", "")])
        if pattern.search(text):
            found.append(article)
    found.sort(key=lambda a: a.get("generatedAt") or a.get("publishedAt", ""), reverse=True)
    return found


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d+(?:[.,]\d+)*", unicodedata.normalize("NFKC", text))}


def build_recap(event: dict, articles: list[dict]) -> list[dict] | None:
    from llm import _load_env_local, generate_json

    _load_env_local()
    by_slug = {a["slug"]: a for a in articles}
    listing = "\n".join(
        f"- {a['slug']} / {a.get('seoTitle') or a.get('title')} / {' '.join(str(h) for h in (a.get('highlights') or [])[:3])}"
        for a in articles[:20]
    )
    prompt = RECAP_PROMPT.format(
        name=event.get("nameJa") or event["name"],
        dates=f"{event['startDate']}〜{event['endDate']}",
        articles=listing,
    )
    try:
        data, model = generate_json(RECAP_SYSTEM, prompt, RECAP_SCHEMA, tier="bulk", temperature=0.2, max_output_tokens=2048)
    except Exception as error:  # noqa: BLE001
        log(f"   まとめを作れませんでした: {str(error)[:120]}")
        return None
    recap, seen = [], set()
    for row in data.get("recap") or []:
        text, slug = str(row.get("text", "")).strip(), str(row.get("slug", "")).strip()
        article = by_slug.get(slug)
        if not article or not text or len(text) > 60 or text in seen:
            continue
        source = " ".join([article.get("title", ""), article.get("seoTitle", ""), article.get("lede", ""), article.get("description", ""), *article.get("highlights", []), article.get("body", "")])
        if not numbers(text) <= numbers(source):
            log(f"   × 数字が記事に無い: {text}")
            continue
        seen.add(text)
        recap.append({"text": text, "slug": slug})
    log(f"   発表内容 {len(recap)}行（{model}）")
    return recap[:8]


def refresh(events: list[dict], articles: list[dict], now: datetime, use_llm: bool) -> list[dict]:
    out = []
    for event in events:
        event = dict(event)
        tz = event.get("timezone") or "UTC"
        start, end = event_range(event)
        event["startUtc"], event["endUtc"] = iso(start), iso(end)
        event["keynotes"] = [
            {**k, "startUtc": iso(to_utc(k["startLocal"], tz)) if k.get("startLocal") else None}
            for k in event.get("keynotes") or []
        ]
        event["status"] = status_of(event, now)
        matched = matched_articles(event, articles)
        event["articleSlugs"] = [a["slug"] for a in matched][:40]
        log(f"[events] {event['slug']}: {event['status']} / 記事 {len(matched)}本")

        # 開催中・終了直後で、記事が増えていたら発表内容を作り直す
        key = hashlib.sha1("|".join(event["articleSlugs"]).encode()).hexdigest()[:12]
        fresh = event["status"] == "live" or (event["status"] == "ended" and now - end <= timedelta(days=RECAP_DAYS))
        if use_llm and fresh and len(matched) >= 2 and event.get("recapKey") != key:
            recap = build_recap(event, matched)
            if recap is not None:
                event["recap"], event["recapKey"], event["recapAt"] = recap, key, iso(now)
        out.append(event)
    return sorted(out, key=lambda e: e["startUtc"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = json.loads(EVENTS_PATH.read_text("utf-8"))
    now = datetime.now(timezone.utc)
    events = refresh(data.get("events", []), load_articles(), now, use_llm=not (args.no_llm or args.dry_run))
    if args.dry_run:
        return 0
    if events == data.get("events"):
        log("[events] 変更なし")
        return 0
    data["events"] = events
    data["refreshedAt"] = iso(now)
    EVENTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
    log(f"[events] {EVENTS_PATH.relative_to(ROOT)} を更新しました（{len(events)}件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
