#!/usr/bin/env python3
"""
朝のまとめ投稿「今朝のAIニュース3本」（毎朝 7:30）と、週2回の問いかけ投稿（火・金 12:15）。日本時間。Threads と X に出す。

  python3 scripts/morning_digest.py --dry-run                      # 朝のまとめの文面と選んだ記事を表示するだけ
  python3 scripts/morning_digest.py --kind poll --dry-run --force  # 問いかけ投稿の文面を表示（曜日・時刻を問わない）
  python3 scripts/morning_digest.py [--kind poll]                  # THREADS_MODE=live のときだけ投稿（Buffer で枠の時刻に予約）
  python3 scripts/morning_digest.py --test-draft [--kind poll]     # Buffer に下書きを作って消す（公開しない）
  python3 scripts/morning_digest.py --merge mine.json              # 投稿の記録をいまの state に足す（push の衝突対策）

問いかけ投稿: Buffer の API は Threads のアンケート（poll）に対応していない（2026-10-29 にスキーマで確認）ため、
「①②③で答えてもらう」問いかけの投稿で代わりにする。その週の話題（トピックの多い AI・気になった記事）から作る

決まりごと:
- 対象は直近 HOURS 時間に作った AI の記事（地震・津波などの災害記事は除く）。速報 → 投稿向きの点数 → Threads の閲覧数の順に選ぶ
- 同じ話題（Threads のトピック）が重ならないように3本選ぶ。2本未満なら出さない
- 本文は見出しを1行ずつ（煽らない）。リンクは自分への返信に置く（Threads はリンクカード）
- 7:30 は通常の予約枠から外してある（threads_post.DIGEST_SLOT_JST）ので、1日の本数は増えない
- 1日1本だけ。state/threads_posted.json に digest-YYYYMMDD（style: digest）で記録する
- SNS_DIGEST=0 なら何もしない
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
import threads_post as tp  # noqa: E402

HOURS = 12
MIN_ITEMS = 2
MAX_ITEMS = 3
ITEM_MAX = 40
# 本文の話題（1つだけ）
TOPIC = "AI"
REPLY_LINES = [
    "ほかの新着もサイトにまとめています👇",
    "昨夜からの新着はこちらから👇",
    "全部の記事はこちらから読めます👇",
]
# 日本語の間の空白で区切る（見出しの後半「〜の仕組み」などを落とす）。英語名の中の空白では切らない
SPLIT_RE = re.compile(r"(?<=[^\x00-\x7F])[ 　](?=[^\x00-\x7F])")


def log(message: str) -> None:
    print(message, flush=True)


def one_line(article: dict) -> str:
    """見出しを1行に（前半だけ・長ければ句読点で切る）"""
    title = str(article.get("title") or article.get("seoTitle") or "").strip()
    head = SPLIT_RE.split(title)[0].strip()
    if len(head) > ITEM_MAX:
        cut = max(head.rfind(c, 0, ITEM_MAX) for c in "、，！？")
        head = head[:cut] if cut >= 15 else head[: ITEM_MAX - 1] + "…"
    return head.rstrip("、，。")


def views(state: dict, slug: str) -> float:
    metrics = (state["posted"].get(slug) or {}).get("metrics") or {}
    for key in ("views", "impressions", "reach"):
        if key in metrics:
            return float(metrics[key])
    return 0.0


def pick(state: dict, now: datetime) -> list[dict]:
    since = now - timedelta(hours=HOURS)
    found = []
    for path in tp.ARTICLES_DIR.glob("*.json"):
        article = json.loads(path.read_text("utf-8"))
        if article.get("genreSlug") != "ai" or article.get("disaster") or article.get("type") == "roundup":
            continue
        if datetime.fromisoformat(article["generatedAt"]) < since:
            continue
        found.append(article)
    found.sort(
        key=lambda a: (bool(a.get("breaking")), tp.score(a) + min(views(state, a["slug"]) / 200, 3), a["generatedAt"]),
        reverse=True,
    )
    chosen: list[dict] = []
    topics: set[str] = set()
    for article in found:
        topic = tp.topic_of(article)
        if topic in topics and topic not in ("AI", "生成AI"):
            continue
        if any(tp.overlap(one_line(article), one_line(c)) >= 12 for c in chosen):
            continue
        chosen.append(article)
        topics.add(topic)
        if len(chosen) == MAX_ITEMS:
            break
    return chosen


def compose(items: list[dict]) -> str:
    head = f"今朝のAIニュース{len(items)}本"
    return "\n".join([head, "", *(f"・{one_line(a)}" for a in items)])


def compose_x(items: list[dict], link: str) -> str:
    """X は1本で（全角2・URL 23 の280字）。入らなければ後ろの項目から落とす"""
    for n in range(len(items), 0, -1):
        text = f"{compose(items[:n])}\n\n{link}\n#AI"
        if tp.x_weight_url(text) <= tp.X_LIMIT:
            return text
    return f"今朝のAIニュース\n{link}"


ASSISTANTS = ["ChatGPT", "Gemini", "Claude", "Copilot"]
POLL_ENDINGS = ["番号でコメントしてもらえるとうれしいです。", "番号だけでも大歓迎です。理由もあればぜひ。", "コメントで教えてください。"]


def week_articles(state: dict, now: datetime) -> list[dict]:
    """直近7日の AI 記事（気になる順）"""
    since = now - timedelta(days=7)
    found = []
    for path in tp.ARTICLES_DIR.glob("*.json"):
        article = json.loads(path.read_text("utf-8"))
        if article.get("genreSlug") == "ai" and not article.get("disaster") and article.get("type") != "roundup":
            if datetime.fromisoformat(article["generatedAt"]) >= since:
                found.append(article)
    found.sort(key=lambda a: (bool(a.get("breaking")), tp.score(a) + min(views(state, a["slug"]) / 200, 3)), reverse=True)
    return found


def compose_poll(state: dict, now: datetime) -> str:
    """問いかけ投稿（2〜4択）。火曜は今週の話題、金曜は使い方の話を中心に、週ごとに入れ替える"""
    jst = now.astimezone(tp.JST)
    week = jst.isocalendar()[1]
    articles = week_articles(state, now)
    counts: dict[str, int] = {}
    for a in articles:
        counts[tp.topic_of(a)] = counts.get(tp.topic_of(a), 0) + 1
    ending = POLL_ENDINGS[(week * 2 + (jst.weekday() == 4)) % len(POLL_ENDINGS)]
    headlines: list[str] = []
    topics: set[str] = set()
    for a in articles:
        if tp.topic_of(a) in topics or any(tp.overlap(one_line(a), h) >= 12 for h in headlines):
            continue
        headlines.append(one_line(a))
        topics.add(tp.topic_of(a))
        if len(headlines) == 3:
            break
    # 今週よく話題になった AI（足りなければ定番で埋める）
    assistants = sorted(ASSISTANTS, key=lambda t: -counts.get(t, 0))[:3]
    marks = "①②③④"
    if jst.weekday() != 4 and week % 2 == 0 and len(headlines) >= 2:
        body = "\n".join(f"{marks[i]}{h}" for i, h in enumerate(headlines))
        return f"今週のAIニュースで、いちばん気になったのは？\n\n{body}\n\n{ending}"
    if jst.weekday() != 4:
        return f"仕事で使うならどれ？\n\n{'／'.join(assistants)}\n\n{ending}使い分けている人は、その分け方もぜひ。"
    evergreen = [
        ("ふだんAIをいちばん使う場面は？", ["調べもの", "文章づくり", "プログラミング", "画像・動画づくり"]),
        ("AIの新機能が出たら？", ["すぐ試す", "評判を見てから", "あまり使わない"]),
        (f"今週いちばん話題になったのは{assistants[0]}。ふだん使っているAIは？", assistants + ["特に使っていない"]),
    ]
    question, options = evergreen[week % len(evergreen)]
    body = "\n".join(f"{marks[i]}{o}" for i, o in enumerate(options[:4]))
    return f"{question}\n\n{body}\n\n{ending}"


def slot_due(slot: tuple[int, int], now: datetime) -> datetime | None:
    """枠の時刻より前に動いたらその時刻に予約、過ぎていたらいますぐ（None）"""
    hour, minute = slot
    when = now.astimezone(tp.JST).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return when.astimezone(timezone.utc) if when - now > timedelta(minutes=3) else None


def due_time(now: datetime) -> datetime | None:
    return slot_due(tp.DIGEST_SLOT_JST, now)


def merge(mine_path: str) -> int:
    mine = json.loads(Path(mine_path).read_text("utf-8"))
    state = tp.load_state()
    added = 0
    for key, entry in mine.get("posted", {}).items():
        if entry.get("style") in ("digest", "poll") and key not in state["posted"]:
            state["posted"][key] = entry
            added += 1
    tp.save_state(state)
    log(f"[digest] 投稿履歴に {added} 件を足しました")
    return 0


def delete_post(api_key: str, post_id: str) -> None:
    tp.buffer_graphql(
        api_key,
        """mutation($input: DeletePostInput!) { deletePost(input: $input) { __typename ... on MutationError { message } } }""",
        {"input": {"id": post_id}},
    )


def build(kind: str, state: dict, now: datetime) -> dict | None:
    """投稿の中身（Threads の本文・返信・X の本文・記録用の情報）。出さないなら None"""
    jst = now.astimezone(tp.JST)
    if kind == "poll":
        text = compose_poll(state, now)
        x_text = f"{text}\n\n#AI"
        return {
            "key": f"poll-{jst:%Y%m%d}", "text": text, "reply": "", "link": "",
            "x_text": x_text if tp.x_weight_url(x_text) <= tp.X_LIMIT else "",
            "slot": tp.POLL_SLOT_JST, "items": [],
        }
    items = pick(state, now)
    if len(items) < MIN_ITEMS:
        log(f"[digest] 直近{HOURS}時間の記事が {len(items)} 本しかないため出しません")
        return None
    link = f"{tp.site_url()}/news"
    for a in items:
        log(f"  {a['slug']} (速報={bool(a.get('breaking'))} 点={tp.score(a)} トピック={tp.topic_of(a)})")
    return {
        "key": f"digest-{jst:%Y%m%d}", "text": compose(items),
        "reply": REPLY_LINES[jst.toordinal() % len(REPLY_LINES)], "link": link,
        "x_text": compose_x(items, tp.utm_link(link, "x", "digest")),
        "slot": tp.DIGEST_SLOT_JST, "items": [a["slug"] for a in items],
    }


def threads_input(channel_id: str, post: dict, when: dict) -> dict:
    thread = [{"text": post["text"], "assets": []}]
    if post["reply"]:
        thread.append({"text": post["reply"], "assets": [], "metadata": {"threads": {"linkAttachment": {
            "url": tp.utm_link(post["link"], "threads", "digest"),
            "title": "サイソクAIニュース 新着一覧",
            "description": "AI・テックの公式発表を、速く・分かりやすく。",
            "thumbnail": {"url": f"{tp.site_url()}/logo.png"},
        }}}})
    return {
        "channelId": channel_id, "text": post["text"], "schedulingType": "automatic", "assets": [], **when,
        "metadata": {"threads": {"topic": TOPIC, "thread": thread}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kind", choices=["digest", "poll"], default="digest")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-draft", action="store_true", help="Buffer に下書きを作って消す（公開しない）")
    parser.add_argument("--merge", default="")
    parser.add_argument("--force", action="store_true", help="曜日・時刻の条件を問わない（確認用。--dry-run / --test-draft と一緒に）")
    args = parser.parse_args()
    if args.merge:
        return merge(args.merge)
    if not tp.DIGEST_ON:
        log("[digest] SNS_DIGEST=0 のため出しません")
        return 0

    live = os.environ.get("THREADS_MODE") == "live" and not args.dry_run and not args.test_draft
    if args.force and live:
        log("[digest] --force は確認用です（--dry-run か --test-draft と一緒に使う）")
        return 1
    now = datetime.now(timezone.utc)
    jst = now.astimezone(tp.JST)
    state = tp.load_state()
    minutes = jst.hour * 60 + jst.minute
    # Actions の遅れを見込んだ時間帯だけ（朝のまとめ 6:30〜10:00、問いかけは火・金の 11:00〜14:00）
    if args.kind == "poll":
        in_time = jst.weekday() in tp.POLL_WEEKDAYS_JST and 11 * 60 <= minutes < 14 * 60
    else:
        in_time = 6 * 60 + 30 <= minutes < 10 * 60
    if not in_time and not args.force:
        log(f"[{args.kind}] いまは出す時間ではありません（{jst:%a %H:%M}）")
        return 0
    post = build(args.kind, state, now)
    if post is None:
        return 0
    if post["key"] in state["posted"] and not args.test_draft:
        log(f"[{args.kind}] 今日の分は投稿済みです: {post['key']}")
        return 0
    log(f"--- {post['key']}\n{post['text']}\n[返信]\n{post['reply']}\n{post['link']}\n[X]\n{post['x_text'] or '（X には出さない）'}\n")
    tp.write_summary([f"### {post['key']} {'（投稿）' if live else '（下書き・未投稿）'}", "", "```", post["text"], "---", post["reply"], post["link"], "```", ""])
    if not live and not args.test_draft:
        return 0
    api_key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not api_key:
        log("[digest] BUFFER_API_KEY が無いため投稿できません")
        return 0 if live else 1
    channels = tp.buffer_channels(api_key)
    if "threads" not in channels:
        log("[digest] Buffer に Threads のチャンネルが見つかりません")
        return 1

    if args.test_draft:
        draft = {"mode": "addToQueue", "saveToDraft": True}
        created = {"threads": tp.create_post(api_key, threads_input(channels["threads"]["id"], post, draft))}
        if "twitter" in channels and post["x_text"]:
            created["twitter"] = tp.create_post(api_key, {
                "channelId": channels["twitter"]["id"], "text": post["x_text"], "schedulingType": "automatic", "assets": [], **draft,
            })
        log(f"[test] 下書きを作りました: {created}")
        for post_id in created.values():
            delete_post(api_key, post_id)
        log("[test] 下書きを削除しました")
        return 0

    due = slot_due(post["slot"], now)
    when = {"mode": "customScheduled", "dueAt": tp.utc_z(due)} if due else {"mode": "shareNow"}
    result = {"id": tp.create_post(api_key, threads_input(channels["threads"]["id"], post, when)), "via": "buffer", "permalink": "", "channels": {}}
    log(f"  [threads] 予約しました: {result['id']}")
    if "twitter" in channels and post["x_text"]:
        x_when = {"mode": "customScheduled", "dueAt": tp.utc_z(due + timedelta(minutes=2))} if due else {"mode": "shareNow"}
        try:
            result["channels"]["twitter"] = tp.create_post(api_key, {
                "channelId": channels["twitter"]["id"], "text": post["x_text"], "schedulingType": "automatic", "assets": [], **x_when,
            })
            log(f"  [twitter] 予約しました: {result['channels']['twitter']}")
        except RuntimeError as error:  # X の失敗で Threads の記録を止めない
            log(f"  [twitter] 失敗: {error}")
    state["posted"][post["key"]] = {
        **result,
        "style": args.kind,
        "format": args.kind,
        "hook": args.kind,
        "question": args.kind == "poll",
        "topic": TOPIC,
        "items": post["items"],
        "dueAt": (due or now).isoformat(timespec="seconds"),
        "postedAt": now.isoformat(timespec="seconds"),
    }
    tp.save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
