#!/usr/bin/env python3
"""Threads の投稿の間隔と、表示0からの立て直しの計画（2026-11-06 22:40 オーナー承認・台帳 S44）。

Threads に投稿を作る経路はすべて threads_post.create_post（Buffer）か threads_post.publish（公式 API の予備）を通る。
その2か所がここを呼ぶ（経路ごとに別の決まりを書かない）。

  1. 間隔（ずっと）: Threads の投稿どうしは MIN_GAP（30分）以上あける。速報も数える。近すぎる投稿は「遅らせる」だけで
     落とさない（速報は本数に関係なく出す＝S41 のまま）。Buffer の予約の時刻を後ろにずらす（gap_shift）。
     ミサイル・地震・津波などの急ぎの安全の知らせ（sns_rules.is_urgent）だけは遅らせない（遅れると読者に害がある）。
  2. 今夜の止め（日付つき）: PAUSE_START〜PAUSE_END（2026-11-06 22:00〜11-07 07:00）は通常の投稿を出さない。速報・急ぎの知らせは出す。
  3. 11/7 の様子見（日付つき）: PROBE_DAY は、まずその日いちばん強い通常の投稿を1本だけ出す（7:15 の枠。朝のまとめはこの日は Threads に出さない）。
     出てから CHECK_AFTER（30分）後に表示数を Buffer から読み、
       表示 > 0 → 立て直せた（その日の残りの枠はいつもどおり）
       表示 = 0 → その日の通常の投稿は止める＋オーナー向けの issue（やさしい日本語）。0 と数えるのは、出てから20分以上たって更新された数字だけ
       数字が確かめられない（更新されないまま CHECK_GIVE_UP を過ぎた）→ 止めない（"unconfirmed"。いつもの予定に戻す。issue なし）
     （Buffer の数字は1日1回の更新で、その場で取り直す API は無い＝2026-11 の API の説明。だから「確かめられない」がふつうに起こる）
     結果は state/threads_recovery.json に残す（`python scripts/threads_gate.py --check`。記事の自動処理の毎回で動き、時刻が来た回だけ読む）。
  PROBE_DAY を過ぎたら 2・3 は何もしない（ずっと続く止めにはしない）。1 はずっと続く。

  python scripts/threads_gate.py --status   # 今の状態を表示するだけ
  python scripts/threads_gate.py --check    # 様子見の1本の表示を確かめる（時刻が来ていなければ何もしない）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
POSTED_PATH = ROOT / "state" / "threads_posted.json"
VIDEO_PATH = ROOT / "state" / "sns_video.json"
RECOVERY_PATH = ROOT / "state" / "threads_recovery.json"
JST = timezone(timedelta(hours=9))

MIN_GAP = timedelta(minutes=30)
PAUSE_START = datetime(2026, 11, 6, 22, 0, tzinfo=JST)
PAUSE_END = datetime(2026, 11, 7, 7, 0, tzinfo=JST)
PROBE_DAY = date(2026, 11, 7)
PROBE_SLOT_JST = (7, 15)  # 様子見の1本の枠（朝のまとめの枠を使う）
PROBE_PLAN_AHEAD = timedelta(minutes=90)  # 様子見の1本はこの時間前から選ぶ（夜のあいだに出た記事も候補に入れる）
CHECK_AFTER = timedelta(minutes=30)
FRESH_AFTER = timedelta(minutes=20)  # 出てからこれだけたって更新された数字だけを信じる
CHECK_GIVE_UP = timedelta(hours=3)  # 数字が確かめられないままこれだけ過ぎたら、止めずにいつもの予定に戻す（"unconfirmed"。締めすぎない）
ISSUE_LABEL = "threads-recovery"


class ThreadsHeld(RuntimeError):
    """いまは Threads に通常の投稿を出さない（今夜の止め・11/7 の様子見の結果待ち・立て直せていない日）。記事は落とさず、次の回にもう一度"""


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


def load_recovery(path: Path | None = None) -> dict:
    return _load(path or RECOVERY_PATH)


def save_recovery(data: dict, path: Path | None = None) -> None:
    path = path or RECOVERY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")


def intended_time(post_input: dict, now: datetime | None = None) -> datetime:
    """この投稿が Threads に出る時刻（予約なら dueAt、いますぐなら今）"""
    now = now or datetime.now(timezone.utc)
    if post_input.get("mode") == "customScheduled":
        return _dt(post_input.get("dueAt")) or now
    return now


# ---- 速報・急ぎの知らせ（止めない投稿） ----

def is_priority(article: dict | None, record: dict | None = None) -> bool:
    """今夜の止め・様子見で止めない投稿か: 速報（S41）・ミサイル・災害・急ぎの安全の知らせ。
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


# ---- 11/7 の様子見 ----

def _jst_date(when: datetime) -> date:
    return when.astimezone(JST).date()


def in_pause(when: datetime) -> bool:
    return PAUSE_START <= when < PAUSE_END


def probe_slot() -> datetime:
    h, m = PROBE_SLOT_JST
    return datetime(PROBE_DAY.year, PROBE_DAY.month, PROBE_DAY.day, h, m, tzinfo=JST)


def _skipped(rec: dict, slug: str, video: dict) -> bool:
    if str(rec.get("status") or "").startswith("skipped") or rec.get("status") == "owner_withdrawn":
        return True
    return ((video.get("queued") or {}).get(slug) or {}).get("status") == "skipped"


def probe_slug(posted: dict | None = None, video: dict | None = None) -> str:
    """様子見の1本の記事（PROBE_DAY に予定した、いちばん早い通常の投稿。出さなかったものは除く）"""
    import sns_plan

    posted = posted if posted is not None else (_load(POSTED_PATH).get("posted") or {})
    video = video if video is not None else _load(VIDEO_PATH)
    rows = []
    for slug, rec in (posted or {}).items():
        if rec.get("style") == "digest" or sns_plan.breaking_exempt(rec) or sns_plan.cap_exempt(rec) or rec.get("urgent"):
            continue
        when = _dt((rec.get("pending") or {}).get("slot") or rec.get("dueAt"))
        if not when or _jst_date(when) != PROBE_DAY or _skipped(rec, slug, video):
            continue
        rows.append((when, slug))
    return min(rows)[1] if rows else ""


def result(recovery: dict | None = None) -> str:
    """様子見の結果: "recovered" / "not_recovered" / "unconfirmed"（確かめられない＝止めない） / ""（まだ）"""
    rec = (recovery if recovery is not None else load_recovery()).get("probe") or {}
    return str(rec.get("result") or "") if rec.get("day") == PROBE_DAY.isoformat() else ""


def normal_hold(when: datetime, article: dict | None = None, *, posted: dict | None = None, video: dict | None = None,
                recovery: dict | None = None) -> str:
    """通常の投稿を when に Threads へ出してはいけない理由（出してよければ ""）。速報・急ぎの知らせはここを呼ばない"""
    if in_pause(when):
        return f"今夜（{PAUSE_START:%m/%d %H:%M}〜{PAUSE_END:%m/%d %H:%M}）は Threads の通常の投稿を止めています（表示0の立て直し・台帳 S44）"
    if _jst_date(when) != PROBE_DAY:
        return ""
    res = result(recovery)
    if res in ("recovered", "unconfirmed"):
        return ""
    if res == "not_recovered":
        return f"{PROBE_DAY:%m/%d} の様子見の1本の表示が0だったので、この日の Threads の通常の投稿は止めています（台帳 S44）"
    probe = probe_slug(posted, video)
    if probe and (article or {}).get("slug") == probe:
        return ""
    if probe:
        return f"{PROBE_DAY:%m/%d} は様子見の1本（{probe}）の表示を確かめるまで、ほかの通常の投稿は出しません（台帳 S44）"
    return f"{PROBE_DAY:%m/%d} の様子見の1本はまだ選んでいません（7:15 の枠のいちばん強い記事だけ。台帳 S44）"


def plan_slot_ok(slot: datetime, now: datetime, posted: dict | None = None, video: dict | None = None,
                 recovery: dict | None = None) -> bool:
    """threads_post.free_slots が通常の枠 slot を予定に使ってよいか（今夜の止め・11/7 は様子見の1本だけ）。
    様子見の1本は PROBE_DAY のまだ間に合ういちばん早い枠（ふつうは 7:15＝朝のまとめの枠）で、その枠の PROBE_PLAN_AHEAD 前から選ぶ
    （7:15 を取り逃したら次の枠が様子見になる＝その日が丸ごと空かない）"""
    if in_pause(slot):
        return False
    if _jst_date(slot) != PROBE_DAY:
        return True
    res = result(recovery)
    if res:
        return res != "not_recovered"
    if probe_slug(posted, video):
        return False  # 様子見の1本はもう予定にある。結果が出るまでほかの枠は使わない
    import sns_plan

    day_slots = [datetime(PROBE_DAY.year, PROBE_DAY.month, PROBE_DAY.day, h, m, tzinfo=JST) for h, m in sns_plan.slots_jst()]
    open_slots = [s for s in day_slots if s >= now + timedelta(minutes=20) and not in_pause(s)]
    if not open_slots:
        return False
    first = min(open_slots)
    return abs((slot - first).total_seconds()) < 60 and now >= first - PROBE_PLAN_AHEAD


def is_probe_slot(slot: datetime, now: datetime, posted: dict | None = None, video: dict | None = None,
                  recovery: dict | None = None) -> bool:
    """slot が様子見の1本の枠か（朝のまとめの枠でも、この日は様子見の1本に使う）"""
    return _jst_date(slot) == PROBE_DAY and not result(recovery) and plan_slot_ok(slot, now, posted, video, recovery)


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


def gap_shift(when: datetime, others: list[datetime], gap: timedelta = MIN_GAP) -> datetime:
    """others のどれとも gap 以上はなれる、when 以降のいちばん早い時刻（前にずらさない＝遅らせるだけ）"""
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
    record = record_of(article, posted) if kind == "article" else None
    priority = kind == "article" and is_priority(article, record)
    if not priority:
        why = normal_hold(when, article if kind == "article" else None, posted=posted)
        if why:
            raise ThreadsHeld(why)
    if article and sns_rules_urgent(article):
        return when  # 急ぎの安全の知らせは遅らせない
    if others is None:
        others = threads_times(api_key, str(post_input.get("channelId") or ""), now)
    shifted = gap_shift(when, others)
    if shifted != when:
        post_input["mode"] = "customScheduled"
        post_input["dueAt"] = shifted.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        label = "速報" if priority else "通常の投稿"
        log(f"  [threads] 前の Threads の投稿から{int(MIN_GAP.total_seconds() // 60)}分あけるため、{label}を "
            f"{when.astimezone(JST):%H:%M} → {shifted.astimezone(JST):%H:%M} に遅らせます（落とさない・台帳 S44・{source}）")
    return shifted


def sns_rules_urgent(article: dict | None) -> bool:
    import sns_rules

    return sns_rules.is_urgent(article)


def enforce_direct(article: dict | None, now: datetime | None = None) -> None:
    """公式 API の予備の経路（threads_post.publish）。予約できないので、近すぎる・止めている間は ThreadsHeld（次の回にもう一度）"""
    now = now or datetime.now(timezone.utc)
    posted = _load(POSTED_PATH).get("posted") or {}
    if not is_priority(article, record_of(article, posted)):
        why = normal_hold(now, article, posted=posted)
        if why:
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
        raise ThreadsHeld(f"前の Threads の投稿から{int(MIN_GAP.total_seconds() // 60)}分たっていないので、次の回に出します（台帳 S44）")


# ---- 11/7 の確かめ（30分後に表示を読む） ----

def views_of(metrics: dict) -> float | None:
    for key in ("views", "impressions", "reach"):
        if key in (metrics or {}) and metrics[key] is not None:
            try:
                return float(metrics[key])
            except (TypeError, ValueError):
                return None
    return None


def fetch_post(api_key: str, post_id: str) -> dict:
    """Buffer の投稿1件の状態と数字（読むだけ・1回）"""
    import buffer_budget
    import threads_post as tp

    buffer_budget.set_role("monitor")
    data = tp.buffer_graphql(
        api_key,
        "query($id: PostId!) { post(input: { id: $id }) { id status dueAt sentAt externalLink metricsUpdatedAt metrics { type value } } }",
        {"id": post_id},
    )
    node = data.get("post") or {}
    node["metrics"] = {m["type"]: m["value"] for m in node.get("metrics") or []}
    return node


def find_probe(posted: dict | None = None, video: dict | None = None) -> dict:
    """様子見の1本の記事・Buffer の ID・出る時刻（まだ作っていなければ id は空）"""
    posted = posted if posted is not None else (_load(POSTED_PATH).get("posted") or {})
    video = video if video is not None else _load(VIDEO_PATH)
    slug = probe_slug(posted, video)
    if not slug:
        return {}
    q = (video.get("queued") or {}).get(slug) or {}
    rec = posted.get(slug) or {}
    post_id = q.get("id") if q.get("status") == "created" else ""
    post_id = post_id or rec.get("id") or ""
    due = q.get("dueAt") or rec.get("dueAt") or (rec.get("pending") or {}).get("slot")
    return {"slug": slug, "id": post_id, "dueAt": due}


ISSUE_TITLE = "Threads の表示がまだ0のままです（11/7 の様子見の1本）"


def issue_body(probe: dict, why: str) -> str:
    due = _dt(probe.get("dueAt"))
    when = f"{due.astimezone(JST):%m月%d日 %H:%M}" if due else "けさ"
    return (
        "## 結論\n"
        f"Threads はまだ元に戻っていません。{when} に出した様子見の1本（記事 `{probe.get('slug')}`）を30分後に確かめたところ、"
        f"見られた回数が0でした（{why}）。\n\n"
        "## いま止めていること\n"
        f"- {PROBE_DAY:%m月%d日} の Threads の通常の投稿は、このあと出しません（記事はサイトには出ています）。\n"
        "- 速報は今までどおり出します（台帳 S41）。ただし前の Threads の投稿から30分はあけます。\n"
        "- Bluesky・X・Facebook はいつもどおりです。\n\n"
        "## このあと\n"
        f"- {PROBE_DAY + timedelta(days=1):%m月%d日} からは、いつもの予定に自動で戻ります（止めたままにはなりません）。\n"
        "- 続けて止めたい・やり方を変えたいときは、このページに書いてください。\n\n"
        "（自動の確かめ: `scripts/threads_gate.py`・台帳 S44）"
    )


def open_issue(probe: dict, why: str) -> str:
    """オーナー向けの issue を1つだけ立てる（Actions の中だけ）。URL を返す"""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        log("[threads-gate] Actions の外なので issue は立てません")
        return ""
    try:
        subprocess.run(["gh", "label", "create", ISSUE_LABEL, "--color", "D93F0B", "--description", "Threads の表示0からの立て直し", "--force"],
                       check=False, capture_output=True, text=True, timeout=60)
        res = subprocess.run(["gh", "issue", "create", "--title", ISSUE_TITLE, "--label", ISSUE_LABEL, "--body", issue_body(probe, why)],
                             check=False, capture_output=True, text=True, timeout=60)
        return (res.stdout or "").strip()
    except Exception as error:  # noqa: BLE001
        log(f"[threads-gate] issue を立てられませんでした: {type(error).__name__}")
        return ""


def check(api_key: str, now: datetime | None = None, *, fetch=None, issue=None, posted: dict | None = None,
          video: dict | None = None, path: Path | None = None) -> dict:
    """様子見の1本の表示を確かめる。何度呼んでもよい（時刻が来ていない・もう結果がある回は何もしない）。state に残した内容を返す"""
    now = now or datetime.now(timezone.utc)
    fetch = fetch or fetch_post
    issue = issue or open_issue
    data = load_recovery(path)
    rec = data.setdefault("probe", {"day": PROBE_DAY.isoformat()})
    if rec.get("day") != PROBE_DAY.isoformat():
        rec.clear()
        rec["day"] = PROBE_DAY.isoformat()
    if rec.get("result") or _jst_date(now) < PROBE_DAY or now > probe_slot() + timedelta(days=1):
        return data
    probe = find_probe(posted, video)
    if not probe:
        rec.update({"status": "waiting", "why": "様子見の1本はまだ予定にありません", "checkedAt": now.isoformat(timespec="seconds")})
        save_recovery(data, path)
        return data
    rec.update({k: probe.get(k) for k in ("slug", "id", "dueAt")})
    due = _dt(probe.get("dueAt"))
    if not probe.get("id") or not due:
        rec.update({"status": "waiting", "why": "様子見の1本はまだ Buffer に作っていません", "checkedAt": now.isoformat(timespec="seconds")})
        save_recovery(data, path)
        return data
    if now < due + CHECK_AFTER:
        rec.update({"status": "waiting", "why": f"{(due + CHECK_AFTER).astimezone(JST):%H:%M} に表示を確かめます",
                    "checkAt": (due + CHECK_AFTER).isoformat(timespec="seconds")})
        save_recovery(data, path)
        return data
    try:
        node = fetch(api_key, probe["id"]) if api_key else None
    except Exception as error:  # noqa: BLE001 - 読めなければ次の回にもう一度
        node = None
        rec["error"] = f"{type(error).__name__}: {str(error)[:160]}"
    views = views_of((node or {}).get("metrics") or {}) if node else None
    sent = _dt((node or {}).get("sentAt"))
    updated = _dt((node or {}).get("metricsUpdatedAt"))
    rec.update({"checkedAt": now.isoformat(timespec="seconds"), "views": views, "status": "checking",
                "bufferStatus": (node or {}).get("status"), "sentAt": (node or {}).get("sentAt"),
                "metricsUpdatedAt": (node or {}).get("metricsUpdatedAt")})
    decided, why = "", ""
    if views is not None and views > 0:
        decided = "recovered"
    elif views is not None and sent and updated and updated >= sent + FRESH_AFTER:
        # 数字が出てからしばらくたって更新された 0 だけを「0」と数える（更新前の 0 で決めない）
        decided, why = "not_recovered", f"表示 {int(views)}"
    elif now >= due + CHECK_GIVE_UP:
        # 2026-11-06 オーナーの「締めすぎない」: 確かめられないだけでは止めない。いつもの予定に戻し、記録だけ残す（issue なし）
        decided, why = "unconfirmed", f"{int(CHECK_GIVE_UP.total_seconds() // 3600)}時間たっても表示の数字が更新されなかった（確かめられないので止めない）"
    if decided:
        rec.update({"result": decided, "decidedAt": now.isoformat(timespec="seconds"), "status": "done"})
        if why:
            rec["why"] = why
        if decided == "not_recovered" and not rec.get("issue"):
            rec["issue"] = issue(probe, why) or ""
        label = {"recovered": "立て直せた（通常の投稿を再開）", "unconfirmed": "確かめられない（止めずに通常の投稿を再開）",
                 "not_recovered": "立て直せていない（この日は止める）"}[decided]
        log(f"[threads-gate] 様子見の1本 {probe['slug']}: 表示 {views} → {label}")
    else:
        rec["why"] = "表示の数字がまだ更新されていないので、次の回にもう一度確かめます"
    save_recovery(data, path)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.check:
        data = check(os.environ.get("BUFFER_API_KEY", "").strip(), now)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    probe = find_probe()
    print(json.dumps({"now": now.astimezone(JST).isoformat(timespec="minutes"), "pause": in_pause(now),
                      "probe": probe, "recovery": load_recovery(), "holdNow": normal_hold(now)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
