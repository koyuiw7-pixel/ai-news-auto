#!/usr/bin/env python3
"""新着記事を Threads に自動投稿する。

記事の見出しと「3秒でわかる要点」から投稿文を組み立てるので、Gemini は呼ばない。
投稿の経路は2つあり、設定されている方を使う（両方あれば Buffer を優先）。

  1. Buffer 経由（BUFFER_API_KEY）
     Buffer に Threads をつないでおけば、Meta の開発者登録や電話番号の認証が要らない。
     Buffer の API は無料プランでも使える。
  2. Threads 公式 API 経由（scripts/threads_auth.py で取得したトークン）

  python3 scripts/threads_post.py --dry-run        # 投稿文を表示するだけ
  python3 scripts/threads_post.py --check-buffer   # Buffer の接続先を確認するだけ（投稿しない）
  python3 scripts/threads_post.py                  # THREADS_MODE=live のときだけ実際に投稿

THREADS_MODE が live 以外（未設定を含む）なら下書きモード。
Actions ではジョブサマリーに投稿文を書き出すだけで、何も公開しない。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from threads_token import API_BASE, load_token, refresh_if_needed  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
STATE_PATH = ROOT / "state" / "threads_posted.json"

# 公式上限は500文字。絵文字などを2文字と数える場合に備えて余裕を持たせる
MAX_CHARS = 480
# コンテナ作成から公開まで平均30秒待つよう公式ドキュメントが推奨している
PUBLISH_WAIT_SEC = 30
BUFFER_API = "https://api.buffer.com"


def log(message: str) -> None:
    print(message, flush=True)


def site_url() -> str:
    url = os.environ.get("NEXT_PUBLIC_SITE_URL") or "https://ai-tech-express.jp"
    return url.rstrip("/")


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text("utf-8"))
    return {"posted": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compose(article: dict) -> str:
    """見出し → 要点3つ → 誘導 の順。流し読みでも要点だけは伝わる形にする。"""
    label = "【まとめ】" if article.get("type") == "roundup" else "【速報】"
    head = f"{label}{article['title']}"
    tail = "続きはサイソクで👇"
    points = [f"・{h.strip()}" for h in article.get("highlights", [])[:3] if h.strip()]

    # 長すぎる場合は要点を後ろから削る。見出しと誘導は必ず残す
    while points:
        text = "\n\n".join([head, "\n".join(points), tail])
        if len(text) <= MAX_CHARS:
            return text
        points.pop()
    return "\n\n".join([head, tail])[:MAX_CHARS]


def candidates(state: dict, hours: int) -> list[dict]:
    """直近 hours 時間に生成された、未投稿のAI記事。まとめ記事を優先する。"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    posted = state["posted"]
    articles = []
    for path in ARTICLES_DIR.glob("*.json"):
        article = json.loads(path.read_text("utf-8"))
        if article.get("genreSlug") != "ai" or article["slug"] in posted:
            continue
        if datetime.fromisoformat(article["generatedAt"]) < since:
            continue
        articles.append(article)

    # まとめ記事に統合済みの個別記事は、まとめ側を出せば十分なので重ねて流さない
    roundups = {a["slug"] for a in articles if a.get("type") == "roundup"} | set(posted)
    articles = [a for a in articles if a.get("roundupSlug") not in roundups]
    articles.sort(key=lambda a: (a.get("type") == "roundup", a["generatedAt"]), reverse=True)
    return articles


def wait_until_live(url: str, timeout: int) -> bool:
    """Vercel の反映前に投稿するとリンクプレビューが壊れるので、記事が開けるまで待つ。"""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as res:
                if res.status == 200:
                    return True
        except urllib.error.URLError:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(15)


def api(method: str, path: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        request = urllib.request.Request(f"{API_BASE}/{path}?{data.decode()}")
    else:
        request = urllib.request.Request(f"{API_BASE}/{path}", data=data, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Threads API {error.code}: {error.read().decode()[:300]}") from error


def publish(token: dict, text: str, link: str) -> dict:
    user_id, access_token = token["user_id"], token["access_token"]
    container = api("POST", f"{user_id}/threads", {
        "media_type": "TEXT",
        "text": text,
        "link_attachment": link,
        "access_token": access_token,
    })
    time.sleep(PUBLISH_WAIT_SEC)

    # 処理が終わっていないと公開に失敗することがあるので、少し待って再試行する
    for attempt in range(1, 4):
        try:
            result = api("POST", f"{user_id}/threads_publish", {
                "creation_id": container["id"],
                "access_token": access_token,
            })
            break
        except RuntimeError as error:
            if attempt == 3:
                raise
            log(f"  [retry {attempt}/3] {error}")
            time.sleep(20)

    detail = api("GET", result["id"], {"fields": "permalink", "access_token": access_token})
    return {"id": result["id"], "permalink": detail.get("permalink", "")}


def buffer_graphql(api_key: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(
        BUFFER_API,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as res:
            payload = json.loads(res.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Buffer API {error.code}: {error.read().decode()[:300]}") from error
    if payload.get("errors"):
        raise RuntimeError(f"Buffer API: {json.dumps(payload['errors'], ensure_ascii=False)[:300]}")
    return payload["data"]


def buffer_threads_channel(api_key: str) -> dict | None:
    """Buffer につながっている Threads のチャンネルを探す（IDを手で設定しなくて済むように）"""
    orgs = buffer_graphql(api_key, "query { account { organizations { id } } }")
    for org in orgs["account"]["organizations"]:
        # ID の型名に依存しないよう、値をクエリに直接埋め込む（JSON文字列としてエスケープ済み）
        data = buffer_graphql(
            api_key,
            f"query {{ channels(input: {{ organizationId: {json.dumps(org['id'])} }}) "
            "{ id name displayName service isQueuePaused } }",
        )
        for channel in data["channels"]:
            if str(channel.get("service", "")).lower() == "threads":
                return channel
    return None


def publish_via_buffer(api_key: str, channel_id: str, text: str, link: str, article: dict) -> dict:
    """Buffer に「今すぐ投稿」で渡す。リンクは Threads のリンクカード（独自カバー画像つき）にする"""
    data = buffer_graphql(
        api_key,
        """mutation($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess { post { id } }
            ... on MutationError { message }
          }
        }""",
        {
            "input": {
                "channelId": channel_id,
                "text": text,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "assets": [],
                "metadata": {
                    "threads": {
                        "linkAttachment": {
                            "url": link,
                            "title": article.get("seoTitle") or article["title"],
                            "description": article.get("description", "")[:120],
                            "thumbnail": {"url": f"{site_url()}/cover/{article['slug']}"},
                        }
                    }
                },
            }
        },
    )
    result = data["createPost"]
    if "message" in result:
        raise RuntimeError(f"Buffer: {result['message']}")
    return {"id": result["post"]["id"], "via": "buffer", "permalink": ""}


def write_summary(lines: list[str]) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max", type=int, default=2, help="1回で投稿する最大本数")
    parser.add_argument("--hours", type=int, default=24, help="何時間前までに生成された記事を対象にするか")
    parser.add_argument("--wait", type=int, default=600, help="記事の公開を待つ最大秒数")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず文面だけ表示する")
    parser.add_argument("--check-buffer", action="store_true", help="Buffer の接続先を確認するだけ")
    args = parser.parse_args()

    live = os.environ.get("THREADS_MODE") == "live" and not args.dry_run
    state = load_state()
    buffer_key = os.environ.get("BUFFER_API_KEY", "").strip()

    # Buffer がつながっていれば、毎回接続先を確認してログに残す（下書きモードでも）
    buffer_channel = None
    if buffer_key:
        try:
            buffer_channel = buffer_threads_channel(buffer_key)
        except RuntimeError as error:
            log(f"[warn] Buffer に接続できません: {error}")
        if buffer_channel:
            log(f"[buffer] 投稿先: {buffer_channel.get('displayName') or buffer_channel.get('name')} (Threads)")
        else:
            log("[buffer] Buffer に Threads のチャンネルが見つかりません（Buffer で Threads を接続してください）")
    if args.check_buffer:
        return 0 if buffer_channel else 1

    token = None
    if live and not buffer_channel:
        token = load_token()
        if token is None:
            log("[skip] 投稿経路が未設定です（Buffer の API キー、または scripts/threads_auth.py のトークン）")
            return 0
        # 投稿が無い回でも期限（60日）を延ばし続ける
        token = refresh_if_needed(token)

    targets = candidates(state, args.hours)[: args.max]
    if not targets:
        log("[done] 投稿する新着記事はありません")
        return 0

    summary = [f"### Threads {'投稿' if live else '下書き（未投稿）'}", ""]
    for article in targets:
        link = f"{site_url()}/articles/{article['slug']}"
        text = compose(article)
        log(f"--- {article['slug']} ({len(text)}文字)\n{text}\n{link}\n")
        summary += [f"**{article['slug']}**", "", "```", text, link, "```", ""]
        if not live:
            continue

        if not wait_until_live(link, args.wait):
            log(f"  [skip] 記事がまだ公開されていません。次回に回します: {link}")
            continue
        try:
            if buffer_channel:
                result = publish_via_buffer(buffer_key, buffer_channel["id"], text, link, article)
            else:
                result = publish(token, text, link)
        except RuntimeError as error:
            # 1本の失敗でパイプライン全体を止めない。未投稿のまま次回再挑戦する
            log(f"  [error] {error}")
            continue
        state["posted"][article["slug"]] = {
            **result,
            "postedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        save_state(state)
        log(f"  [posted] {result['permalink'] or result['id']}")

    write_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
