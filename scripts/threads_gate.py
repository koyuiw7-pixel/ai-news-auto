#!/usr/bin/env python3
"""Threads の投稿の間隔と、新しい書き方の承認待ち（台帳 S47・S46）。

Threads に投稿を作る経路はすべて threads_post.create_post（Buffer）か threads_post.publish（公式 API の予備）を通る。
その2か所がここを呼ぶ（経路ごとに別の決まりを書かない）。

  1. 間隔（ずっと）: Threads の投稿どうしは sns_plan.min_gap()（sns_plan.json の min_gap_min＝45分。台帳 S47）以上あける。速報も数える。
     近すぎる投稿は「遅らせる」だけで落とさない（速報は本数に関係なく出す＝S41 のまま）。Buffer の予約の時刻を後ろにずらす（gap_shift）。
     ミサイル・地震・津波などの急ぎの安全の知らせ（sns_rules.is_urgent）だけは遅らせない（遅れると読者に害がある）。
  2. 新しい書き方の承認待ち（2026-11-07 夜 オーナー・台帳 S46）: state/threads_hold.json の held が true の間は、Threads の自動投稿を
     出さない（通常の投稿・速報・朝のまとめのすべて。ミサイル・地震・津波などの急ぎの安全の知らせだけは出す）。
     朝のまとめは新しい書き方の外なので、held を false にしても digest が true になるまで出さない。
  2026-11-08 の台帳の見直し（オーナー承認）: 11/6 夜の止め・11/7 の様子見（旧 S44）と30分の間隔は外した（S47 の45分に一本化）。

  python scripts/threads_gate.py --status   # 今の状態を表示するだけ
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
POSTED_PATH = ROOT / "state" / "threads_posted.json"
VIDEO_PATH = ROOT / "state" / "sns_video.json"
HOLD_PATH = ROOT / "state" / "threads_hold.json"
JST = timezone(timedelta(hours=9))

class ThreadsHeld(RuntimeError):
    """いまは Threads に投稿を出さない（新しい書き方の承認待ち・間隔が近すぎる公式 API の予備の経路）。記事は落とさず、次の回にもう一度"""


class AutoPostOff(ThreadsHeld):
    """この SNS への記事の自動投稿は止めている（sns_plan.json の auto_post。2026-11-10 オーナー決定「今後は全て手投稿にしよう」）"""


def log(message: str) -> None:
    print(message, flush=True)


# ---- 時刻 ----

def _dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def intended_time(post_input: dict, now: datetime | None = None) -> datetime:
    """この投稿が Threads に出る時刻（予約なら dueAt、いますぐなら今）"""
    now = now or datetime.now(timezone.utc)
    if post_input.get("mode") == "customScheduled":
        return _dt(post_input.get("dueAt")) or now
    return now


# ---- 速報・急ぎの知らせ（止めない投稿） ----

def is_priority(article: dict | None, record: dict | None = None) -> bool:
    """本数に数えない・遅らせ方を分けて記録する投稿か: 速報（S41）・ミサイル・災害・急ぎの安全の知らせ。
    記録（state/threads_posted.json）があれば記録の breaking を見る（速報の記事でも、ふつうの枠に回したものは通常の投稿）"""
    import sns_plan
    import sns_rules

    if article and (sns_plan.cap_exempt(article) or sns_rules.is_urgent(article)):
        return True
    if record is not None:
        return bool(sns_plan.breaking_exempt(record) or sns_plan.cap_exempt(record) or record.get("urgent"))
    return bool((article or {}).get("breaking"))


def record_of(article: dict | None, posted: dict | None = None) -> dict | None:
    """state/threads_posted.json のこの記事の記録（無ければ None）"""
    slug = (article or {}).get("slug")
    if not slug:
        return None
    posted = posted if posted is not None else (_load(POSTED_PATH).get("posted") or {})
    return posted.get(slug)


# ---- 新しい書き方の承認待ち（台帳 S46） ----

def style_hold(article: dict | None, kind: str = "article", hold: dict | None = None) -> str:
    """いま Threads に出してはいけない理由（新しい書き方の承認待ち・朝のまとめ）。出してよければ ""。
    ファイルが読めないときは止める（承認の前に古い書き方が出ないように）"""
    import sns_rules

    if kind == "article" and article and sns_rules.is_urgent(article):
        return ""  # 急ぎの安全の知らせは止めない（遅れると読者に害がある）
    data = hold if hold is not None else _load(HOLD_PATH)
    if not data or data.get("held", True):
        return "Threads の自動投稿は、新しい書き方の最初の3本をオーナーが承認するまで止めています（state/threads_hold.json・台帳 S46）"
    if kind == "digest" and not data.get("digest"):
        return "朝のまとめは新しい書き方の外なので、Threads には出しません（state/threads_hold.json の digest・台帳 S46）"
    return ""


# ---- 間隔（ずっと） ----

def threads_times(api_key: str, channel_id: str, now: datetime | None = None) -> list[datetime]:
    """Threads の前後48時間の投稿の時刻（Buffer の予約中・送信中・出した投稿と、この実行で作った投稿）＋手元の記録で作ったもの"""
    import threads_post as tp

    out: list[datetime] = []
    if api_key and channel_id:
        tp.recent_channel_posts(api_key, channel_id)  # 1回の実行で1回だけ読む（作る直前の確かめと同じ読み）
        out += [when for _, when in tp._BUFFER_DUE.get(channel_id, []) if when]
    for rec in ((_load(VIDEO_PATH).get("queued") or {}).values()):
        if (rec or {}).get("status") == "created" and rec.get("id"):
            when = _dt(rec.get("dueAt"))
            if when:
                out.append(when)
    return out


def min_gap() -> timedelta:
    """Threads の投稿どうしの最短の間隔（sns_plan.json の min_gap_min。台帳 S47）"""
    import sns_plan

    return sns_plan.min_gap()


def gap_shift(when: datetime, others: list[datetime], gap: timedelta | None = None) -> datetime:
    """others のどれとも gap 以上はなれる、when 以降のいちばん早い時刻（前にずらさない＝遅らせるだけ）"""
    gap = gap or min_gap()
    shifted = when
    for _ in range(200):
        near = [t for t in others if abs((shifted - t).total_seconds()) < gap.total_seconds()]
        if not near:
            return shifted
        shifted = max(near) + gap
    return shifted


def enforce(api_key: str, post_input: dict, article: dict | None, *, kind: str = "article", source: str = "",
            now: datetime | None = None, others: list[datetime] | None = None) -> datetime:
    """threads_post.create_post が Threads に作る直前に呼ぶ。
    通常の投稿で今は出せない → ThreadsHeld。近すぎる → post_input の予約の時刻を後ろにずらす（落とさない）。出す時刻を返す"""
    now = now or datetime.now(timezone.utc)
    when = intended_time(post_input, now)
    posted = _load(POSTED_PATH).get("posted") or {}
    if why := style_hold(article, kind):
        raise ThreadsHeld(why)
    record = record_of(article, posted) if kind == "article" else None
    priority = kind == "article" and is_priority(article, record)
    if article and sns_rules_urgent(article):
        return when  # 急ぎの安全の知らせは遅らせない
    if others is None:
        others = threads_times(api_key, str(post_input.get("channelId") or ""), now)
    shifted = gap_shift(when, others)
    if shifted != when:
        post_input["mode"] = "customScheduled"
        post_input["dueAt"] = shifted.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        label = "速報" if priority else "通常の投稿"
        log(f"  [threads] 前の Threads の投稿から{int(min_gap().total_seconds() // 60)}分あけるため、{label}を "
            f"{when.astimezone(JST):%H:%M} → {shifted.astimezone(JST):%H:%M} に遅らせます（落とさない・台帳 S47・{source}）")
    return shifted


def sns_rules_urgent(article: dict | None) -> bool:
    import sns_rules

    return sns_rules.is_urgent(article)


def enforce_direct(article: dict | None, now: datetime | None = None) -> None:
    """公式 API の予備の経路（threads_post.publish）。予約できないので、近すぎる・止めている間は ThreadsHeld（次の回にもう一度）"""
    now = now or datetime.now(timezone.utc)
    posted = _load(POSTED_PATH).get("posted") or {}
    if why := style_hold(article):
        raise ThreadsHeld(why)
    if sns_rules_urgent(article):
        return
    recent = [w for w in threads_times("", "", now)]
    for rec in posted.values():
        if rec.get("id"):
            when = _dt(rec.get("dueAt") or rec.get("postedAt"))
            if when:
                recent.append(when)
    if gap_shift(now, recent) != now:
        raise ThreadsHeld(f"前の Threads の投稿から{int(min_gap().total_seconds() // 60)}分たっていないので、次の回に出します（台帳 S47）")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="（旧 S44 の様子見。2026-11-08 に外した。何もしない）")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.check:
        return 0
    print(json.dumps({"now": now.astimezone(JST).isoformat(timespec="minutes"), "minGapMin": int(min_gap().total_seconds() // 60),
                      "styleHold": style_hold(None)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
