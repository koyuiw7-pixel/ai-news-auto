"""Bluesky（AT Protocol を直接）に記事を出す。Buffer は使わない

投稿履歴 state/threads_posted.json の各記録（Threads に出したもの）を見て、まだ Bluesky に出していないものを出す:
- 速報（breaking）と朝のまとめ（digest）は すぐ
- 通常の予約は Threads の時刻（dueAt）から DELAY_MIN 分後
1日 PER_DAY 本まで・深夜（1〜5時）は出さない。結果は channels.bluesky に URI を記録。失敗しても他の SNS には影響しない

  python3 scripts/bluesky_post.py --dry-run     # ログインだけ確認し、投稿の JSON を表示（投稿しない）
  python3 scripts/bluesky_post.py               # 投稿（BLUESKY_HANDLE / BLUESKY_APP_PASSWORD が必要）
  python3 scripts/bluesky_post.py --merge FILE  # 手元の記録の channels.bluesky を最新の state に足す
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import threads_post as tp  # noqa: E402

PDS = "https://bsky.social/xrpc"
DELAY_MIN = 20
PER_DAY = int(os.environ.get("BLUESKY_PER_DAY") or 15)
LOOKBACK_H = 3  # これより古い記録は出さない（取りこぼしを後から大量に出さない）
MAX_GRAPHEMES = 300
MAX_BLOB = 1_000_000


def log(message: str) -> None:
    print(message, flush=True)


def xrpc(method: str, body: dict | bytes | None = None, token: str = "", ctype: str = "application/json") -> dict:
    data = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{PDS}/{method}", data=data, method="POST" if data is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", ctype)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read() or b"{}")


def login() -> dict:
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        raise RuntimeError("BLUESKY_HANDLE / BLUESKY_APP_PASSWORD がありません")
    return xrpc("com.atproto.server.createSession", {"identifier": handle, "password": password})


def fetch(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "saisoku-bluesky/1.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read(MAX_BLOB + 1), res.headers.get_content_type()


def upload_thumb(session: dict, urls: list[str]) -> dict | None:
    """1MB 以下の画像をアップロードして blob を返す。どれも無理なら None（カードは画像なし）"""
    for url in urls:
        try:
            data, ctype = fetch(url)
            if len(data) > MAX_BLOB or not ctype.startswith("image/"):
                continue
            return xrpc("com.atproto.repo.uploadBlob", data, session["accessJwt"], ctype)["blob"]
        except Exception as error:  # noqa: BLE001
            log(f"  [bluesky] 画像を使えません {url}: {error}")
    return None


def build_record(text: str, link: str, title: str, desc: str, thumb: dict | None) -> dict:
    """本文＋改行＋リンク。リンクは facet（UTF-8 のバイト位置）とリンクカードの両方で付ける"""
    shown = re.sub(r"^https?://|\?.*$", "", link)  # 表示は短く（リンク先は UTM 付き）
    room = MAX_GRAPHEMES - len(shown) - 1
    text = text.strip()
    if len(text) > room:
        text = text[: room - 1].rstrip() + "…"
    full = f"{text}\n{shown}"
    start = len(f"{text}\n".encode())
    external = {"uri": link, "title": title[:300], "description": desc[:300]}
    if thumb:
        external["thumb"] = thumb
    return {
        "$type": "app.bsky.feed.post",
        "text": full,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "langs": ["ja"],
        "facets": [{
            "index": {"byteStart": start, "byteEnd": start + len(shown.encode())},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
        }],
        "embed": {"$type": "app.bsky.embed.external", "external": external},
    }


def plan(key: str, entry: dict) -> dict | None:
    """投稿の中身（本文・リンク・カード）。出せないもの（アンケートなど）は None"""
    style = entry.get("style")
    if style == "poll":
        return None
    if style == "digest":
        import morning_digest as md
        items = []
        for slug in entry.get("items") or []:
            path = tp.ARTICLES_DIR / f"{slug}.json"
            if path.exists():
                items.append(json.loads(path.read_text("utf-8")))
        if not items:
            return None
        link = tp.utm_link(f"{tp.site_url()}/news", "bluesky", "digest")
        return {"text": md.compose(items), "link": link, "title": "けさのAIニュースまとめ｜サイソクAIニュース",
                "desc": "直近のAIニュースを1分で。", "images": [f"{tp.site_url()}/cover/{items[0]['slug']}"]}
    path = tp.ARTICLES_DIR / f"{key}.json"
    if not path.exists():
        return None
    article = json.loads(path.read_text("utf-8"))
    text = tp.compose(article, [], breaking=bool(entry.get("breaking")))
    text = re.sub(r"\s*👇\s*$", "", text)
    link = tp.utm_link(f"{tp.site_url()}/articles/{key}", "bluesky", entry.get("format") or "classic")
    thumb = str(article.get("thumbnail") or "")
    return {
        "text": text, "link": link, "title": article.get("seoTitle") or article["title"],
        "desc": article.get("description", ""),
        "images": [f"{tp.site_url()}/cover/{key}"] + ([thumb] if thumb.startswith("https://") else []),
    }


def due(entry: dict) -> datetime | None:
    raw = entry.get("dueAt") or entry.get("postedAt")
    if not raw:
        return None
    when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    fast = entry.get("breaking") or entry.get("style") == "digest"
    return when if fast else when + timedelta(minutes=DELAY_MIN)


def posted_today(state: dict, now: datetime) -> int:
    today = now.astimezone(tp.JST).date()
    return sum(
        1 for e in state["posted"].values()
        if (e.get("blueskyAt") or "") and datetime.fromisoformat(e["blueskyAt"]).astimezone(tp.JST).date() == today
    )


def pending(state: dict, now: datetime) -> list[tuple[str, dict]]:
    out = []
    for key, entry in state["posted"].items():
        when = due(entry)
        if not when or (entry.get("channels") or {}).get("bluesky") or entry.get("blueskyFailed"):
            continue
        if when <= now and now - when <= timedelta(hours=LOOKBACK_H):
            out.append((key, entry))
    return sorted(out, key=lambda kv: due(kv[1]))


def merge(mine_path: str) -> int:
    mine = json.loads(Path(mine_path).read_text("utf-8"))
    state = tp.load_state()
    added = 0
    for key, entry in mine.get("posted", {}).items():
        if key not in state["posted"]:
            continue
        for field in ("blueskyAt", "blueskyFailed"):
            if entry.get(field) and not state["posted"][key].get(field):
                state["posted"][key][field] = entry[field]
        uri = (entry.get("channels") or {}).get("bluesky")
        if uri and not (state["posted"][key].get("channels") or {}).get("bluesky"):
            state["posted"][key].setdefault("channels", {})["bluesky"] = uri
            added += 1
    tp.save_state(state)
    log(f"[bluesky] 投稿履歴に {added} 件を足しました")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--merge", default="")
    parser.add_argument("--slug", default="", help="確認用: この記録を対象にする（--dry-run と一緒に）")
    args = parser.parse_args()
    if args.merge:
        return merge(args.merge)
    live = os.environ.get("THREADS_MODE") == "live" and not args.dry_run
    state = tp.load_state()
    now = datetime.now(timezone.utc)
    if now.astimezone(tp.JST).hour in tp.BREAKING_QUIET_HOURS_JST and live:
        log("[bluesky] 深夜のため出しません")
        return 0
    todo = [(args.slug, state["posted"][args.slug])] if args.slug else pending(state, now)
    room = max(0, PER_DAY - posted_today(state, now))
    if not todo and not live:  # 下書きは最新の記事を見本にする
        todo = [kv for kv in state["posted"].items() if not kv[1].get("style")][-1:]
    if not todo:
        log("[bluesky] 出すものはありません")
        return 0
    if not room and not args.slug:
        log(f"[bluesky] 今日の上限 {PER_DAY} 本に到達")
        return 0
    try:
        session = login()
        log(f"[bluesky] ログイン OK: {session.get('handle')} ({session.get('did')})")
    except Exception as error:  # noqa: BLE001  Bluesky の失敗で他を止めない
        log(f"[bluesky] ログイン失敗: {error}")
        return 0
    for key, entry in todo[: max(room, 1 if args.slug or not live else 0)]:
        try:
            p = plan(key, entry)
            if not p:
                entry["blueskyFailed"] = "skip"
                continue
            thumb = upload_thumb(session, p["images"]) if live or args.slug else None
            record = build_record(p["text"], p["link"], p["title"], p["desc"], thumb)
            if not live:
                log(f"--- {key}\n{json.dumps(record, ensure_ascii=False, indent=1)}")
                continue
            res = xrpc("com.atproto.repo.createRecord",
                       {"repo": session["did"], "collection": "app.bsky.feed.post", "record": record}, session["accessJwt"])
            entry.setdefault("channels", {})["bluesky"] = res["uri"]
            entry["blueskyAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            log(f"  [bluesky] {key}: https://bsky.app/profile/{session['handle']}/post/{res['uri'].rsplit('/', 1)[-1]}")
        except Exception as error:  # noqa: BLE001
            log(f"  [bluesky] {key} 失敗: {error}")
            entry["blueskyFailed"] = str(error)[:200]
    if live:
        tp.save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
