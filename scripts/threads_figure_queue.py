#!/usr/bin/env python3
"""夜の図つき Threads 投稿（本文＋図、返信に記事のリンク）を Buffer に予約する道具。まずは下見だけ（2026-11-10・ops O2）。

  python3 scripts/threads_figure_queue.py --spec content/sns_reposts/figure-20261110.json                  # 下見だけ（Buffer を呼ばない・何も書かない）
  python3 scripts/threads_figure_queue.py --spec ... --taken 19:20 --taken 21:05 --last-cluster 年金       # 手で出した投稿の時刻・話題の群れ
  python3 scripts/threads_figure_queue.py --spec ... --live                                               # 予約する（下の条件がすべてそろったときだけ）

予約（--live）の条件: spec の ownerApproved が空でない・環境変数 THREADS_MODE=live・BUFFER_API_KEY がある・その投稿の決まりがすべて通る。
Buffer へは threads_post.create_post（門番 threads_gate・sns_rules・重複の確かめ）だけを通す。ほかの呼び方はしない。

spec の形（content/sns_reposts/figure-<日付>.json）:
  {"date": "YYYY-MM-DD", "ownerApproved": "<リーダーが書く。--live に必須>",
   "posts": [{"key", "slug", "image", "text1", "text2", "opener"（threads_hooks.HOOKS の key）, "cluster"（年金・医療・介護 など）,
              "audience"（"employee" か "general"）, "topic"（省略可。既定は threads_post.topic_of(記事)）}]}
  text2 は返信の文。記事の URL（utm_campaign=<slug>&utm_content=reader_reply）はこの道具が足す（text2 が「→」で終われば同じ行・ほかは改行）。

枠: 19:00〜23:30（日本時間）。間隔は max(40分, threads_gate.min_gap())。すでにある時刻（state/threads_posted.json・state/threads_control.json・
この道具の台帳・--taken・予約のときは Buffer の予約）から間隔をあけた、いちばん早い時刻に spec の順で入れる。入らなければ「枠なし」。

投稿ごとの決まり（1つでも通らなければ、その投稿は予約しない。下見では理由を並べる）:
  1. 全角の縦棒と、記事の決まり A4 で使わない言葉（article_style.ZAKKURI_RE）を使わない（text1・text2・トピック）
  2. 書き出しの型（opener）が直前の投稿と違う・text1 の最初の12字が直近5本の書き出しと違う
  3. 話題の群れ（cluster）が直前の投稿と違う（--last-cluster は手で出した直前の投稿の群れ）
  4. 夜の投稿の3本続きのどこにも、会社員向け（audience=employee）が1本は入る
  5. 記事（content/articles/<slug>.json）があり、記事の URL が 200 を返す（--offline で通信を省く）
  6. Buffer に送る入力そのものが sns_rules の門番（kind="reader"）を通る。門番はゆるめない（通らなければ理由を出す）
台帳: state/threads_figure.json（key ごとに1回だけ予約。10分以内に迫った枠は使わない）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sns_rules  # noqa: E402
import threads_gate  # noqa: E402
import threads_hooks  # noqa: E402
import threads_post as tp  # noqa: E402

try:
    from article_style import ZAKKURI_RE  # noqa: E402
except Exception:  # noqa: BLE001 - 記事の決まりの部品が読めなくても同じ言葉を止める
    ZAKKURI_RE = re.compile("ざっ" + "くり")

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "state" / "threads_figure.json"
CONTROL_LEDGER = ROOT / "state" / "threads_control.json"
READER_STATE = ROOT / "state" / "threads_reader.json"
JST = timezone(timedelta(hours=9))
EVENING_START = (19, 0)
EVENING_END = (23, 30)
BASE_GAP = timedelta(minutes=40)
MIN_LEAD = timedelta(minutes=10)
QUIET_HOURS_JST = range(2, 6)  # 投稿は 6:00〜1:59（台帳 S54）
OPENER_HEAD = 12
RECENT_OPENERS = 5
CLUSTERS = ("年金", "医療・介護", "子ども・出産", "税・控除", "雇用・退職", "電気・エネルギー", "ふるさと納税", "相続")
AUDIENCES = ("employee", "general")
VBAR = "\uff5c"
IMAGE_LIMIT = 1_048_576


# ---- 時刻 ----

def gap() -> timedelta:
    return max(BASE_GAP, threads_gate.min_gap())


def evening(day: Date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, *EVENING_START, tzinfo=JST)
    end = datetime(day.year, day.month, day.day, *EVENING_END, tzinfo=JST)
    return start, end


def parse_hm(day: Date, hm: str) -> datetime:
    """--taken の HH:MM（日本時間）。0時・1時台は次の日の夜の続き"""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(hm))
    if not m:
        raise SystemExit(f"[figure] --taken は HH:MM で書いてください（{hm}）")
    h, mi = int(m.group(1)), int(m.group(2))
    when = datetime(day.year, day.month, day.day, h, mi, tzinfo=JST)
    return when + timedelta(days=1) if h < 6 else when


def in_posting_hours(when: datetime) -> bool:
    return when.astimezone(JST).hour not in QUIET_HOURS_JST


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def local_taken(day: Date, ledger: dict | None = None, skip_keys: set[str] | None = None) -> list[datetime]:
    """手元の記録にある、その日の夕方〜夜の Threads の投稿の時刻（dueAt・sentAt）"""
    lo, hi = evening(day)
    lo, hi = lo - timedelta(hours=3), hi + timedelta(hours=3)
    out: list[datetime] = []
    rows = list((_load(tp.STATE_PATH).get("posted") or {}).values()) + list((_load(CONTROL_LEDGER).get("posts") or {}).values())
    rows += [v for k, v in ((ledger or {}).get("posts") or {}).items() if k not in (skip_keys or set())]
    for rec in rows:
        for field in ("dueAt", "sentAt"):
            when = threads_gate._dt((rec or {}).get(field))
            if when and lo <= when <= hi:
                out.append(when)
    return sorted(set(out))


def plan_slots(n: int, day: Date, taken: list[datetime], *, now: datetime | None = None, step: timedelta | None = None) -> list[datetime | None]:
    """n 本を spec の順に、間隔 step をあけたいちばん早い時刻に入れる。19:00〜23:30 に入らなければ None（枠なし）"""
    step = step or gap()
    start, end = evening(day)
    if now is not None:
        start = max(start, now + MIN_LEAD)
    others = list(taken)
    out: list[datetime | None] = []
    for _ in range(n):
        when = threads_gate.gap_shift(start, others, step)
        if when > end or not in_posting_hours(when):
            out.append(None)
            continue
        out.append(when)
        others.append(when)
    return out


# ---- 決まり ----

def banned_words(post: dict) -> list[str]:
    out = []
    for field in ("text1", "text2", "topic"):
        value = str(post.get(field) or "")
        if VBAR in value:
            out.append(f"[決まり1] {field} に全角の縦棒（U+FF5C）がある（使わない）")
        if ZAKKURI_RE.search(value):
            out.append(f"[決まり1] {field} に使わない言葉（記事の決まり A4）がある。「要約すると」にする")
    return out


def recent_heads(ledger: dict | None = None) -> list[str]:
    """直近の Threads の書き出し（最初の12字）。出した新しい書き方の投稿（state/threads_reader.json）と、この道具で予約したもの"""
    rows = []
    for rec in (_load(READER_STATE).get("posts") or {}).values():
        if rec.get("status") == "posted" and rec.get("main"):
            rows.append((str(rec.get("at") or ""), str(rec["main"])))
    for rec in ((ledger or {}).get("posts") or {}).values():
        if rec.get("text1"):
            rows.append((str(rec.get("dueAt") or rec.get("at") or ""), str(rec["text1"])))
    rows.sort(reverse=True)
    return [head(text) for _, text in rows[:RECENT_OPENERS]]


def head(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))[:OPENER_HEAD]


def sequence_problems(posts: list[dict], *, last_opener: str = "", last_cluster: str = "", heads: list[str] | None = None) -> list[list[str]]:
    """決まり2〜4（書き出し・話題の群れ・会社員向け）。posts は夜の順。投稿ごとの理由の一覧"""
    out: list[list[str]] = [[] for _ in posts]
    heads = list(heads or [])
    prev_opener, prev_cluster = last_opener, last_cluster
    for i, post in enumerate(posts):
        opener = str(post.get("opener") or "")
        cluster = str(post.get("cluster") or "")
        if opener not in threads_hooks.HOOK_KEYS:
            out[i].append(f"[決まり2] opener「{opener}」は threads_hooks の型にない（{', '.join(threads_hooks.HOOK_KEYS)}）")
        elif prev_opener and opener == prev_opener:
            out[i].append(f"[決まり2] 書き出しの型が直前の投稿と同じ（{opener}）")
        h = head(post.get("text1"))
        if h and h in heads[:RECENT_OPENERS]:
            out[i].append(f"[決まり2] 書き出しの最初の{OPENER_HEAD}字が直近の投稿と同じ（「{h}」）")
        if not cluster:
            out[i].append("[決まり3] cluster（話題の群れ）がない")
        elif prev_cluster and cluster == prev_cluster:
            out[i].append(f"[決まり3] 同じ話題の群れが2本続く（{cluster}）")
        if post.get("audience") not in AUDIENCES:
            out[i].append(f"[決まり4] audience は employee か general（{post.get('audience')}）")
        if i >= 2 and not any(p.get("audience") == "employee" for p in posts[i - 2:i + 1]):
            out[i].append("[決まり4] 3本続けて会社員向けがない（3本に1本は audience=employee）")
        prev_opener, prev_cluster = opener, cluster
        heads.insert(0, h)
    return out


def check_url(url: str, *, image: bool = False, opener=None) -> str:
    """URL が 200 を返すか（画像なら画像の種類か）。問題があれば理由。先頭の1MBまでしか読まない"""
    if not str(url or "").startswith("https://"):
        return "公開の URL（https://）が要る（手元のファイルは予約に使えない。記事の図 imageFocus.src などを指す）"
    opener = opener or urllib.request.urlopen
    headers = {"User-Agent": "saisoku-figure-queue/1.0", "X-Saisoku-Internal": "1"}
    if image:
        headers["Range"] = f"bytes=0-{IMAGE_LIMIT - 1}"
    try:
        with opener(urllib.request.Request(url, headers=headers), timeout=20) as res:
            status = getattr(res, "status", 200)
            ctype = str(res.headers.get("Content-Type") or "")
            res.read(IMAGE_LIMIT if image else 65536)
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"
    except (OSError, ValueError) as error:
        return f"開けない（{type(error).__name__}）"
    if status not in (200, 206):
        return f"HTTP {status}"
    if image and not ctype.startswith("image/"):
        return f"画像ではない（{ctype or '種類なし'}）"
    return ""


def article_link(slug: str) -> str:
    return tp.utm_link(f"{tp.site_url()}/articles/{slug}", "threads", slug, "reader_reply")


def reply_with_link(text2: str, slug: str) -> str:
    body = str(text2 or "").replace("\\n", "\n").rstrip()
    joiner = " " if body.endswith("→") else "\n"
    return f"{body}{joiner}{article_link(slug)}"


def build_input(post: dict, article: dict, due: datetime, channel_id: str = "preview") -> dict:
    """threads_post.publish_via_buffer（hook_thread）と同じ形: 本文＋画像、返信に記事のリンク"""
    text1 = str(post["text1"]).replace("\\n", "\n").strip()
    return {
        "channelId": channel_id, "text": text1, "schedulingType": "automatic", "mode": "customScheduled",
        "dueAt": tp.utc_z(due), "assets": [],
        "metadata": {"threads": {"topic": str(post.get("topic") or tp.topic_of(article)), "thread": [
            {"text": text1, "assets": [{"image": {"url": str(post["image"])}}]},
            {"text": reply_with_link(post["text2"], str(post["slug"])), "assets": []},
        ]}},
    }


def gate_problems(inp: dict, article: dict, measurer=None) -> list[str]:
    """送る入力が門番（sns_rules・kind="reader"）を通るか。enforce_buffer と同じく返信は1行目で見る"""
    text, reply, media, links = sns_rules.buffer_parts("threads", inp)
    reply = reply.split("\n")[0] if reply else ""
    return sns_rules.check_post("threads", text, media, article, kind="reader", reply_text=reply, links=links, history=True, measurer=measurer)


def load_article(slug: str) -> dict | None:
    path = tp.ARTICLES_DIR / f"{slug}.json"
    try:
        return json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return None


# ---- 計画 ----

def load_spec(path: Path) -> dict:
    spec = json.loads(Path(path).read_text("utf-8"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(spec.get("date") or "")):
        raise SystemExit("[figure] spec の date（YYYY-MM-DD）がない")
    posts = spec.get("posts") or []
    if not posts:
        raise SystemExit("[figure] spec の posts が空")
    keys = [str(p.get("key") or "") for p in posts]
    for i, post in enumerate(posts):
        missing = [k for k in ("key", "slug", "image", "text1", "text2", "opener", "cluster", "audience") if not str(post.get(k) or "").strip()]
        if missing:
            raise SystemExit(f"[figure] posts[{i}] に足りないもの: {', '.join(missing)}")
    if len(set(keys)) != len(keys):
        raise SystemExit("[figure] posts の key が重なっている")
    return spec


def make_plan(spec: dict, *, taken: list[datetime] | None = None, last_cluster: str = "", last_opener: str | None = None,
              offline: bool = False, now: datetime | None = None, ledger: dict | None = None, measurer=None,
              url_opener=None, gate_others: list[datetime] | None = None) -> list[dict]:
    """投稿ごとの計画（枠・決まりの結果）。Buffer は呼ばない"""
    day = Date.fromisoformat(spec["date"])
    ledger = ledger if ledger is not None else _load(LEDGER)
    booked = (ledger.get("posts") or {})
    posts = spec["posts"]
    all_taken = sorted(set(local_taken(day, ledger, skip_keys=set()) + list(taken or [])))
    fresh = [p for p in posts if not (booked.get(p["key"]) or {}).get("id")]
    slots = iter(plan_slots(len(fresh), day, all_taken, now=now))
    if last_opener is None:
        last_opener = (tp.recent_openers(1) or [""])[0]
    seq = sequence_problems(posts, last_opener=last_opener, last_cluster=last_cluster, heads=recent_heads(ledger))
    rows: list[dict] = []
    assigned: list[datetime] = []
    for post, problems in zip(posts, seq):
        row = {"post": post, "problems": list(problems), "booked": "", "slot": None, "input": None, "imageNote": ""}
        rec = booked.get(post["key"]) or {}
        if rec.get("id"):
            row["booked"] = rec["id"]
            row["slot"] = threads_gate._dt(rec.get("dueAt"))
            rows.append(row)
            continue
        row["problems"] += banned_words(post)
        slot = next(slots)
        row["slot"] = slot
        if slot is None:
            row["problems"].append("[枠] 19:00〜23:30 に間隔をあけて入る枠がない（枠なし）")
        else:
            assigned.append(slot)
            if not in_posting_hours(slot):
                row["problems"].append("[枠] 6:00〜1:59 の外")
            others = [t for t in (gate_others if gate_others is not None else all_taken) + assigned if t != slot]
            if threads_gate.gap_shift(slot, others, threads_gate.min_gap()) != slot:
                row["problems"].append("[枠] threads_gate がこの時刻をずらす（ほかの投稿に近すぎる）")
        article = load_article(post["slug"])
        if article is None:
            row["problems"].append(f"[決まり5] 記事が見つからない（content/articles/{post['slug']}.json）")
        elif not offline:
            if why := check_url(f"{tp.site_url()}/articles/{post['slug']}", opener=url_opener):
                row["problems"].append(f"[決まり5] 記事の URL: {why}")
        image = str(post.get("image") or "")
        if not image.startswith("https://"):
            row["imageNote"] = "公開の URL が要る"
            row["problems"].append("[画像] 公開の URL が要る（手元のファイルは予約に使えない。記事の図 imageFocus.src などを指す）")
        elif not offline:
            if why := check_url(image, image=True, opener=url_opener):
                row["imageNote"] = why
                row["problems"].append(f"[画像] {why}")
            else:
                row["imageNote"] = "OK"
        else:
            row["imageNote"] = "（通信を省いた）"
        if article is not None:
            inp = build_input(post, article, slot or evening(day)[0])
            row["input"] = inp
            row["problems"] += [f"[門番] {p}" for p in gate_problems(inp, article, measurer=measurer)]
        rows.append(row)
    return rows


def print_plan(rows: list[dict], spec: dict) -> None:
    print(f"=== 図つき Threads の予定 {spec['date']}（19:00〜23:30・間隔 {int(gap().total_seconds() // 60)}分）")
    for i, row in enumerate(rows, 1):
        post = row["post"]
        slot = row["slot"].astimezone(JST).strftime("%H:%M") if row["slot"] else "枠なし"
        aud = "会社員向け" if post.get("audience") == "employee" else "一般"
        state = f"予約済み（{row['booked']}）" if row["booked"] else ("OK" if not row["problems"] else f"止まる（{len(row['problems'])}件）")
        print(f"\n{i}. {slot}  {post['key']}  記事 {post['slug']}")
        print(f"   群れ {post.get('cluster')}・{aud}・書き出し {post.get('opener')}・画像 {row['imageNote'] or '-'}・結果 {state}")
        for p in row["problems"]:
            print(f"   - {p}")


# ---- 予約 ----

def live_ready(spec: dict) -> list[str]:
    out = []
    if not str(spec.get("ownerApproved") or "").strip():
        out.append("spec の ownerApproved が空")
    if os.environ.get("THREADS_MODE") != "live":
        out.append("THREADS_MODE=live ではない")
    if not os.environ.get("BUFFER_API_KEY", "").strip():
        out.append("BUFFER_API_KEY がない")
    return out


def book(rows: list[dict], spec: dict, api_key: str, channel_id: str, ledger: dict, now: datetime) -> int:
    """決まりがすべて通った投稿だけを create_post（kind="reader"。用意した文面のまま門番に通す）で予約する"""
    booked = 0
    for row in rows:
        post = row["post"]
        if row["booked"] or row["problems"] or not row["slot"] or row["input"] is None:
            continue
        if row["slot"] - now < MIN_LEAD:
            print(f"[figure] {post['key']}: 枠が10分以内に迫っているので出しません")
            continue
        inp = row["input"]
        inp["channelId"] = channel_id
        planned = inp["dueAt"]
        article = load_article(post["slug"])
        post_id = tp.create_post(api_key, inp, service="threads", article=article, source="threads_figure_queue", kind="reader")
        if inp.get("dueAt") != planned:
            print(f"[figure] {post['key']}: 門番が時刻を {planned} → {inp.get('dueAt')} にずらしました（予約 {post_id}）")
        ledger.setdefault("posts", {})[post["key"]] = {
            "id": post_id, "slug": post["slug"], "dueAt": inp.get("dueAt"), "cluster": post.get("cluster"),
            "audience": post.get("audience"), "opener": post.get("opener"), "text1": inp.get("text"),
            "ownerApproved": spec["ownerApproved"], "at": now.isoformat(timespec="seconds"),
        }
        LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"[figure] 予約しました: {post['key']} → {post_id}")
        booked += 1
    return booked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--taken", action="append", default=[], help="手で出した（出す）投稿の時刻 HH:MM（日本時間）。何回でも")
    parser.add_argument("--last-cluster", default="", help="手で出した直前の投稿の話題の群れ")
    parser.add_argument("--last-opener", default=None, help="直前の投稿の書き出しの型（省略すると state/threads_posted.json から）")
    parser.add_argument("--offline", action="store_true", help="記事と画像の URL を確かめない（テスト用）")
    parser.add_argument("--live", action="store_true", help="Buffer に予約する（ownerApproved・THREADS_MODE=live・BUFFER_API_KEY が要る）")
    args = parser.parse_args(argv)
    spec = load_spec(Path(args.spec))
    day = Date.fromisoformat(spec["date"])
    taken = []
    for value in args.taken:
        taken += [parse_hm(day, v) for v in str(value).split(",") if v.strip()]
    now = datetime.now(timezone.utc)
    ledger = _load(LEDGER) or {"posts": {}}
    if args.live:
        missing = live_ready(spec)
        if missing:
            print("[figure] 予約しません: " + "・".join(missing))
            return 2
        api_key = os.environ["BUFFER_API_KEY"].strip()
        channel = tp.buffer_channels(api_key)["threads"]["id"]
        taken += [w for w in (threads_gate._dt(p.get("dueAt")) for p in tp.scheduled_in_buffer(api_key, channel, now)) if w]
        gate_others = threads_gate.threads_times(api_key, channel, now) + local_taken(day, ledger) + taken
        rows = make_plan(spec, taken=taken, last_cluster=args.last_cluster, last_opener=args.last_opener, offline=args.offline,
                         now=now, ledger=ledger, gate_others=gate_others)
        print_plan(rows, spec)
        n = book(rows, spec, api_key, channel, ledger, now)
        print(f"\n[figure] 予約 {n} 本")
        return 0 if all(not r["problems"] for r in rows if not r["booked"]) else 1
    rows = make_plan(spec, taken=taken, last_cluster=args.last_cluster, last_opener=args.last_opener, offline=args.offline,
                     now=now, ledger=ledger)
    print_plan(rows, spec)
    ok = sum(1 for r in rows if not r["problems"] and not r["booked"])
    print(f"\n[figure] 下見だけ（Buffer は呼んでいない・何も書いていない）。予約できる {ok} 本 / {len(rows)} 本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
