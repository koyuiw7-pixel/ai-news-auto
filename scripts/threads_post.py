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
import re
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


def compose(article: dict, recent: list[str] | None = None) -> str:
    """投稿文。記事生成時に作った Threads 用の紹介文（threadsPost）があればそれを使う。

    無い記事（以前の記事など）は、同じ考え方の定型で組み立てる：
    短い見出しで手を止め、要点を2つだけ見せ、残りは記事で読んでもらう。
    """
    custom = str(article.get("threadsPost") or "").strip()
    if custom and len(custom) <= MAX_CHARS:
        return custom

    hook, first = opening_line(article, recent or [])
    article["_hook"] = hook
    title = article.get("seoTitle") or article["title"]
    head = title if hook == "breaking" else f"{first}\n{title}"
    if hook == "breaking":
        head = f"{'【まとめ】' if article.get('type') == 'roundup' else '【速報】'}{title}"
    points = [f"✅ {h.strip()}" for h in article.get("highlights", []) if h.strip()]
    shown, rest = points[:2], points[2:]
    tail = "もう1つの注目点と詳しい数字は記事で👇" if rest else "詳しくは記事で👇"
    text = "\n\n".join([head, "\n".join(shown), tail]) if shown else "\n\n".join([head, tail])
    return text[:MAX_CHARS]


def openers(article: dict) -> list[tuple[str, str]]:
    """紹介文を持たない記事向けの書き出し候補（型, 1行目）。判定から、事実として言えるものだけを作る。"""
    name = re.split(r"[｜|：:？?]", str(article.get("seoTitle") or ""))[0].strip()
    name = re.sub(r"(の仕組み)?を解説$|とは$|まとめ$|入門$", "", name).strip()
    if not name or len(name) > 18:  # 長い名前を文に入れると不自然になるので「これ」で受ける
        name = "これ"
    verdict = article.get("verdict") or {}
    status, japan, free = verdict.get("status"), verdict.get("japan"), verdict.get("free")
    price, audience = str(verdict.get("price") or ""), str(verdict.get("audience") or "")
    found: list[tuple[str, str]] = []
    # 【速報】は、作ってから1日半以内の記事だけ（古い記事を速報と呼ばない）
    generated = article.get("generatedAt")
    if generated and datetime.now(timezone.utc) - datetime.fromisoformat(generated) < timedelta(hours=36):
        found.append(("breaking", "【速報】"))
    if status == "available":
        found.append(("question", f"{name}、もう試しました？"))
        if japan == "ok":
            found.append(("conclusion", "結論：日本からも、もう使えます。"))
    if status == "limited":
        found.append(("caution", f"{name}、使える人はまだ限られています。"))
    if status in ("soon", "demo"):
        found.append(("future", "使えるようになったら、仕事の進め方が変わりそうな発表です。"))
        found.append(("question", f"{name}、いつ使えるようになるか気になってませんか？"))
    if free is True and status == "available":
        found.append(("free", "これ、無料で試せます。"))
    if free is False and price and price not in ("不明", "未発表"):
        found.append(("caution", f"使う前に料金だけ確認を。{price}です。"))
    if audience and len(audience) <= 8:
        found.append(("callout", f"{audience}の人、これはチェックしてほしい。"))
    return found


def opening_line(article: dict, recent: list[str]) -> tuple[str, str]:
    """直近で使った型を避けて、記事ごとに書き出しを変える"""
    options = openers(article)
    if not options:
        options = [("question", "このニュース、もうチェックしました？")]
    fresh = [option for option in options if option[0] not in recent] or options
    # 同じ記事なら毎回同じ結果になるよう、slug から決める
    index = sum(ord(c) for c in article["slug"]) % len(fresh)
    return fresh[index]


def topic_of(article: dict) -> str:
    """Threads のトピック（1つだけ付けられる）。企業名などの最初のタグを使う"""
    tags = [t for t in article.get("tags", []) if t]
    return tags[0][:50] if tags else "AI"


# Threads で反応が取りやすい話題（大手・一般向け）と、取りにくい話題（企業の開発基盤など）
BROAD = re.compile(r"OpenAI|ChatGPT|Google|Gemini|Anthropic|Claude|Apple|iPhone|Meta|Sora|NotebookLM|NVIDIA|GPT|Copilot|画像生成|動画生成|音声")
NICHE = re.compile(r"Azure|SQL|Cosmos|Kubernetes|\.NET|SDK|DevOps|TypeScript|データベース|Foundry|IoT|DB開発|クラウド移行")
WIDE_AUDIENCE = {"一般ユーザー", "ビジネス職", "クリエイター", "デザイナー", "営業職", "経営層"}
# 専門的な記事も投稿する（伝え方を工夫する前提）。スコアは「どれを先に出すか」の順番だけに使う
MIN_SCORE = -99


def score(article: dict) -> int:
    """フォロワーが少ないうちは「誰でも反応できる話題」だけを流す。専門的すぎる発表は記事に任せる。"""
    text = f"{article.get('title', '')} {article.get('seoTitle', '')} {' '.join(article.get('tags', []))}"
    verdict = article.get("verdict") or {}
    value = 0
    if BROAD.search(text):
        value += 3
    if NICHE.search(text):
        value -= 5
    if verdict.get("status") == "available" and verdict.get("japan") != "no":
        value += 2
    if verdict.get("free") is True:
        value += 1
    if verdict.get("audience") in WIDE_AUDIENCE:
        value += 1
    if article.get("type") == "roundup":
        value += 2
    # 有名な製品・企業の話でも、一般向けでもない技術解説は、フォロワーが育つまで見送る
    if not BROAD.search(text) and verdict.get("audience") not in WIDE_AUDIENCE:
        value -= 2
    return value


def candidates(state: dict, hours: int) -> list[dict]:
    """直近 hours 時間に生成された未投稿のAI記事を、Threads で反応が取れそうな順に並べる。"""
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
    articles = [a for a in articles if score(a) >= MIN_SCORE]
    articles.sort(key=lambda a: (score(a), a["generatedAt"]), reverse=True)
    return articles


# 投稿する時間帯（日本時間）。通勤・昼休み・夜に寄せ、1日3本までにする
SLOTS_JST = [(7, 30), (12, 30), (20, 30)]
JST = timezone(timedelta(hours=9))
LOOKAHEAD_HOURS = 10


def next_free_slot(state: dict, now: datetime | None = None) -> datetime | None:
    """これから LOOKAHEAD_HOURS 時間以内で、まだ予約していない投稿枠（UTC）"""
    now = now or datetime.now(timezone.utc)
    taken = {p.get("dueAt") for p in state["posted"].values() if p.get("dueAt")}
    base = now.astimezone(JST).replace(second=0, microsecond=0)
    for day in range(2):
        for hour, minute in SLOTS_JST:
            slot = (base + timedelta(days=day)).replace(hour=hour, minute=minute)
            if slot < base + timedelta(minutes=20) or slot > base + timedelta(hours=LOOKAHEAD_HOURS):
                continue
            iso = slot.astimezone(timezone.utc).isoformat(timespec="seconds")
            if iso not in taken:
                return slot.astimezone(timezone.utc)
    return None


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


def publish_via_buffer(
    api_key: str,
    channel_id: str,
    text: str,
    link: str,
    article: dict,
    due_at: datetime | None = None,
    draft: bool = False,
) -> dict:
    """Buffer に予約投稿する。

    本文にはリンクを付けず、独自カバー画像を添える。記事へのリンクは、すぐ下に続く返信（スレッドの2件目）に置く。
    リンクだけの投稿は反応が付きにくく、表示が伸びにくいと言われているため。
    """
    cover = f"{site_url()}/cover/{article['slug']}"
    title = article.get("seoTitle") or article["title"]
    thread = [
        {"text": text, "assets": [{"image": {"url": cover}}]},
        {
            "text": "記事はこちら👇",
            "assets": [],
            "metadata": {
                "threads": {
                    "linkAttachment": {
                        "url": link,
                        "title": title,
                        "description": article.get("description", "")[:120],
                        "thumbnail": {"url": cover},
                    }
                }
            },
        },
    ]
    post_input = {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "assets": [],
        "metadata": {
            "threads": {
                # トピックを付けると、そのトピックに関心のある人のフィードに載りやすくなる
                "topic": topic_of(article),
                "thread": thread,
            }
        },
    }
    if draft:
        # 動作確認用：公開せず下書きとして保存する
        post_input["mode"] = "addToQueue"
        post_input["saveToDraft"] = True
    elif due_at:
        post_input["mode"] = "customScheduled"
        post_input["dueAt"] = due_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    else:
        post_input["mode"] = "shareNow"
    data = buffer_graphql(
        api_key,
        """mutation($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess { post { id } }
            ... on MutationError { message }
          }
        }""",
        {"input": post_input},
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
    parser.add_argument("--hours", type=int, default=36, help="何時間前までに生成された記事を対象にするか")
    parser.add_argument("--wait", type=int, default=600, help="記事の公開を待つ最大秒数")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず文面だけ表示する")
    parser.add_argument("--check-buffer", action="store_true", help="Buffer の接続先を確認するだけ")
    parser.add_argument("--test-draft", action="store_true", help="投稿形式の確認用に、Buffer へ下書きを作って消す")
    args = parser.parse_args()

    live = os.environ.get("THREADS_MODE") == "live" and not args.dry_run
    state = load_state()
    buffer_key = os.environ.get("BUFFER_API_KEY", "").strip()
    if buffer_key and not buffer_key.isascii():
        # クリップボードの取り違えなどで、キー以外の文字列が登録されているとき
        log("[error] BUFFER_API_KEY の形式が不正です（日本語などが含まれています）。キーを登録し直してください")
        buffer_key = ""

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
    if args.test_draft:
        # 新しい投稿形式（画像つき本文＋リンクは返信）が Buffer に受け付けられるかを、下書きを作って消すことで確かめる
        if not buffer_channel:
            return 1
        sample = (candidates(state, 24 * 30) or [None])[0]
        if sample is None:
            log("[test] 確認に使える記事がありません")
            return 1
        result = publish_via_buffer(
            buffer_key, buffer_channel["id"], compose(sample), f"{site_url()}/articles/{sample['slug']}", sample, draft=True
        )
        log(f"[test] 下書きの作成に成功しました: {result['id']}")
        deleted = buffer_graphql(
            buffer_key,
            """mutation($input: DeletePostInput!) {
              deletePost(input: $input) { __typename ... on MutationError { message } }
            }""",
            {"input": {"id": result["id"]}},
        )
        log(f"[test] 下書きを削除しました: {deleted}")
        return 0

    token = None
    if live and not buffer_channel:
        token = load_token()
        if token is None:
            log("[skip] 投稿経路が未設定です（Buffer の API キー、または scripts/threads_auth.py のトークン）")
            return 0
        # 投稿が無い回でも期限（60日）を延ばし続ける
        token = refresh_if_needed(token)

    # Buffer 経由では、次の投稿枠（朝・昼・夜）に1本だけ予約する。枠が無ければ今回は見送る
    due_at = next_free_slot(state) if buffer_channel else None
    if buffer_channel and due_at is None:
        log("[done] 直近の投稿枠はすべて予約済みです")
        return 0
    limit = 1 if buffer_channel else args.max
    # 直近で使った書き出しの型と同じ型の記事は後回しにする（同じ型が続くと読み飛ばされるため）
    history = sorted(state["posted"].values(), key=lambda p: p.get("postedAt", ""), reverse=True)
    recent_hooks = [p["hook"] for p in history if p.get("hook")][:3]

    def varied(articles: list[dict]) -> list[dict]:
        return sorted(articles, key=lambda a: a.get("threadsHook") in recent_hooks)

    targets = varied(candidates(state, args.hours))[:limit]
    if not targets:
        # 新着に Threads 向きの記事が無いときは、直近2週間のまだ投稿していない記事から選ぶ
        # （新着が専門的な記事ばかりの日に、投稿が丸1日止まらないように）
        targets = varied(candidates(state, 14 * 24))[:limit]
        if targets:
            log("[fallback] 新着に Threads 向きの記事が無いため、直近2週間の記事から選びました")
    if not targets:
        log("[done] Threads 向きの新着記事はありません（専門的な記事は記事ページだけに出します）")
        return 0
    if due_at:
        log(f"[slot] {due_at.astimezone(JST):%m/%d %H:%M} に予約します")

    summary = [f"### Threads {'投稿' if live else '下書き（未投稿）'}", ""]
    # 直近の投稿で使った書き出しの型（同じ型を続けないため）
    history = sorted(state["posted"].values(), key=lambda p: p.get("postedAt", ""), reverse=True)
    recent = [p["hook"] for p in history if p.get("hook")][:4]
    for article in targets:
        link = f"{site_url()}/articles/{article['slug']}"
        text = compose(article, recent)
        hook = article.get("threadsHook") or article.get("_hook", "")
        if hook:
            recent = [hook, *recent][:4]
        log(f"--- {article['slug']} ({len(text)}文字)\n{text}\n{link}\n")
        summary += [f"**{article['slug']}**", "", "```", text, link, "```", ""]
        if not live:
            continue

        if not wait_until_live(link, args.wait):
            log(f"  [skip] 記事がまだ公開されていません。次回に回します: {link}")
            continue
        try:
            if buffer_channel:
                result = publish_via_buffer(buffer_key, buffer_channel["id"], text, link, article, due_at)
            else:
                result = publish(token, text, link)
        except RuntimeError as error:
            # 1本の失敗でパイプライン全体を止めない。未投稿のまま次回再挑戦する
            log(f"  [error] {error}")
            continue
        state["posted"][article["slug"]] = {
            **result,
            "hook": hook,
            "score": score(article),
            **({"dueAt": due_at.isoformat(timespec="seconds")} if due_at and buffer_channel else {}),
            "postedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        save_state(state)
        log(f"  [posted] {result['permalink'] or result['id']}")

    write_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
