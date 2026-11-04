"""Buffer API の呼び出し回数の見張り（全スクリプト共通。threads_post.buffer_graphql から必ず通る）

2026-11-03 に Buffer の 24時間の上限（HTTP 429 RATE_LIMIT_EXCEEDED, window=24h）に当たり、予約・確認・動画の差し替えが
全部止まった。原因は、空き枠が無い回でも毎回 Buffer に問い合わせていたこと（反応の学習・チャンネルの確認・見張り）。

ここで守ること:
- 1日（UTC）の呼び出し回数を数え、上限 BUFFER_DAILY_CAP（既定 250）を超えたら呼ばない。
  見張り・学習などの「読むだけ」（role=monitor）は BUFFER_MONITOR_CAP（既定 80）まで。予約（role=book）を優先する
- Buffer の応答ヘッダー（RateLimit / RateLimit-Policy）で残り回数を覚え、残りが少なければ読むだけの呼び出しを止める
- 429 を受けたら Retry-After（秒）の時刻まで一切呼ばない（ループで再試行しない）。429 自体は Buffer の上限に数えられない

Buffer の公式の上限（https://developers.buffer.com/guides/api-limits.html、2026-11-03 確認）:
  窓は 15分・24時間・30日の3つ。プランで違う。無料プランは 150回/15分・600回/24時間・1チャンネル1,000回/30日（最大3,000）。
  API キーと MCP の接続で1つの枠を共有する。429 の本文に extensions.code=RATE_LIMIT_EXCEEDED と extensions.window。
  待つ秒数は Retry-After ヘッダー（本文には無い）。成功した応答は RateLimit: r=残り, t=リセットまでの秒。

記録は state/buffer_calls/<書き手>.json（書き手ごとに別ファイル。複数のワークフローが同時に push しても衝突しない）。
書き手の名前は環境変数 BUFFER_LEDGER（ワークフローで設定）。未設定（手元・テスト）のときはファイルを読み書きせず、
そのプロセスの中だけで数える。

2026-11-05（オーナー承認）: 30日の窓の 429（Retry-After 約16日）に当たった。無料プランの 3,000回/30日を約2週間で使い切った。
- 30日の合計（全部の書き手・全部のワークフローの記録 days を足す）を数え、ソフトの上限 BUFFER_30D_CAP を超えたら
  「優先の投稿を作る呼び出し」（with priority("high")）だけ通す。ハードの上限（ソフトの110%）を超えたら何も呼ばない。
  上限の既定: BUFFER_30D_CAP があればそれ。無ければ Buffer が教えた30日の窓の上限 q の8割（プランを上げれば自動で上がる）。
  それも分からなければ 7,000（2026-11-05 夜にオーナーが Essentials＝7,500回/30日 に上げた）。
- 読むだけ（monitor）は30日でソフトの上限の15%まで（BUFFER_30D_MONITOR_SHARE）。
- 429 は Retry-After のとおり待つ（最大31日。以前の7日の上限は、待ちが明ける前に呼んでまた 429 になるのでやめた）。
  その間も6時間に1回だけ、軽い問い合わせ1回（probe）で上限が解けたかを確かめる（プランを上げたらすぐ再開するため）。
  probe も回数に数える。成功した呼び出し（lastOk）が 429 より後にあれば、その 429 の待ちは解けたとみなす。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = ROOT / "state" / "buffer_calls"

ROLES = ("book", "monitor")
# 429 で Retry-After が無いときの待ち時間（窓ごと）
DEFAULT_WAIT = {"15m": 900, "24h": 3 * 3600, "30d": 12 * 3600}
MAX_WAIT = 31 * 24 * 3600  # Retry-After のとおり待つ（30日の窓より長くはしない）
PROBE_EVERY = timedelta(hours=6)  # 止まっている間の確かめは6時間に1回
DEFAULT_30D_CAP = 7000  # Essentials（7,500回/30日）。無料に戻すなら BUFFER_30D_CAP=2400
WINDOW_30D = "2592000"
KEEP_DAYS = 32


class BufferUnavailable(RuntimeError):
    """今は Buffer を呼ばない（上限・待ち時間）。RuntimeError の仲間なので、今までの except RuntimeError でも拾える"""


class BufferRateLimited(BufferUnavailable):
    pass


class BufferBudgetExceeded(BufferUnavailable):
    pass


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name) or default))
    except ValueError:
        return default


def daily_cap() -> int:
    # 1日の上限: 30日の上限を均した量の2倍（Essentials で約466回。Buffer の24時間の窓より小さい）
    return _int_env("BUFFER_DAILY_CAP", max(40, cap_30d() * 2 // 30))


def monitor_cap() -> int:
    return _int_env("BUFFER_MONITOR_CAP", max(10, monitor_cap_30d() // 30 * 2))


def window_quota_30d(windows: dict | None = None) -> int:
    """Buffer が応答ヘッダーで教えた30日の窓の上限（q）。分からなければ0"""
    info = (windows if windows is not None else status()["windows"]).get(WINDOW_30D) or {}
    try:
        return int(info.get("q") or 0)
    except (TypeError, ValueError):
        return 0


def cap_30d(windows: dict | None = None) -> int:
    """30日のソフトの上限。BUFFER_30D_CAP → Buffer の30日の上限の8割 → 既定 7,000"""
    raw = (os.environ.get("BUFFER_30D_CAP") or "").strip()
    if raw.isdigit():
        return int(raw)
    q = window_quota_30d(windows)
    return int(q * 0.8) if q else DEFAULT_30D_CAP


def hard_cap_30d(windows: dict | None = None) -> int:
    soft = cap_30d(windows)
    q = window_quota_30d(windows)
    hard = int(soft * 1.1)
    return min(hard, q - 30) if q else hard


def monitor_cap_30d(windows: dict | None = None) -> int:
    try:
        share = float(os.environ.get("BUFFER_30D_MONITOR_SHARE") or 0.15)
    except ValueError:
        share = 0.15
    return int(cap_30d(windows) * share)


def writer() -> str:
    name = re.sub(r"[^A-Za-z0-9_-]", "-", os.environ.get("BUFFER_LEDGER", "").strip())[:40]
    return name


def persist() -> bool:
    return bool(writer())


_role = os.environ.get("BUFFER_ROLE", "book").strip() if os.environ.get("BUFFER_ROLE", "").strip() in ROLES else "book"
_memory: dict = {}
_priority = ["normal"]


class priority:
    """with priority("high"): この中の呼び出しは、30日のソフトの上限を超えても通す（優先の枠の投稿を作るとき。読むだけには使わない）"""

    def __init__(self, level: str = "high"):
        self.level = level

    def __enter__(self):
        _priority.append(self.level)
        return self

    def __exit__(self, *exc):
        _priority.pop()
        return False


def current_priority() -> str:
    return _priority[-1]


def set_role(role: str) -> None:
    """このプロセスの読むだけの呼び出しの扱い（monitor: 見張り・学習・点検。book: 予約に要る読み取り）"""
    global _role
    _role = role if role in ROLES else "book"


def current_role(write: bool = False) -> str:
    return "book" if write else _role


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _day(now: datetime) -> str:
    return now.astimezone(timezone.utc).date().isoformat()


def _parse_time(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def _empty(now: datetime) -> dict:
    return {"day": _day(now), "calls": {r: 0 for r in ROLES}, "blockedUntil": None, "windows": {}}


def _path() -> Path:
    return LEDGER_DIR / f"{writer()}.json"


def _load_mine(now: datetime) -> dict:
    data = None
    if persist():
        try:
            data = json.loads(_path().read_text("utf-8"))
        except (OSError, ValueError):
            data = None
    else:
        data = _memory.get("mine")
    if not isinstance(data, dict):
        data = _empty(now)
    if data.get("day") != _day(now):
        # 日が変わったら回数だけ0に戻す（待ち時間と残り回数の記録は残す）
        keep = {k: data[k] for k in ("blockedUntil", "windows", "last429", "days", "lastOk", "lastProbe", "probe") if k in data}
        data = {**_empty(now), **keep}
    data.setdefault("calls", {r: 0 for r in ROLES})
    data.setdefault("windows", {})
    _days_of(data)
    return data


def _days_of(data: dict) -> dict:
    """{日付(UTC): {book, monitor, create, probe}}。古い形（day・calls だけ）の記録はその日の分として読む"""
    days = data.get("days")
    if not isinstance(days, dict):
        days = {}
        if data.get("day") and isinstance(data.get("calls"), dict):
            days[str(data["day"])] = {r: int(data["calls"].get(r, 0) or 0) for r in ROLES}
        data["days"] = days
    return days


def _save_mine(data: dict) -> None:
    if not persist():
        _memory["mine"] = data
        return
    try:
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        _path().write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        _memory["mine"] = data


def _all(now: datetime) -> list[dict]:
    """全部の書き手の記録（自分の分は最新のもの）"""
    out = []
    if persist() and LEDGER_DIR.is_dir():
        mine = _path().name
        for path in sorted(LEDGER_DIR.glob("*.json")):
            if path.name == mine:
                continue
            try:
                data = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                out.append(data)
    out.append(_load_mine(now))
    return out


def status(now: datetime | None = None) -> dict:
    """今日（UTC）の回数の合計・いつまで待つか・Buffer が最後に教えた残り回数"""
    now = _now(now)
    calls = {r: 0 for r in ROLES}
    used30 = {r: 0 for r in ROLES}
    kinds30: dict = {}
    blocked: datetime | None = None
    last429: dict | None = None
    windows: dict = {}
    datas = _all(now)
    first_day = (now.astimezone(timezone.utc).date() - timedelta(days=29)).isoformat()
    last_ok = max((t for d in datas if (t := _parse_time(d.get("lastOk")))), default=None)
    last_probe = max((t for d in datas if (t := _parse_time(d.get("lastProbe")))), default=None)
    for data in datas:
        if data.get("day") == _day(now):
            for role in ROLES:
                calls[role] += int((data.get("calls") or {}).get(role, 0) or 0)
        for day, counts in _days_of(data).items():
            if first_day <= day <= _day(now) and isinstance(counts, dict):
                for k, v in counts.items():
                    if k in ROLES:
                        used30[k] += int(v or 0)
                    else:
                        kinds30[k] = kinds30.get(k, 0) + int(v or 0)
        until = _parse_time(data.get("blockedUntil"))
        hit = _parse_time((data.get("last429") or {}).get("at"))
        if until and last_ok and hit and last_ok > hit:
            until = None  # 429 のあとに成功した呼び出しがある（プランを上げた・窓が明けた）→ その待ちは解けた
        if until and (blocked is None or until > blocked):
            blocked, last429 = until, data.get("last429")
        for w, info in (data.get("windows") or {}).items():
            if not isinstance(info, dict):
                continue
            if w not in windows or str(info.get("at", "")) > str(windows[w].get("at", "")):
                windows[w] = info
    total30 = sum(used30.values())
    # Buffer が教えた30日の残り（q - r）がこちらの記録より多ければ、そちらを使う（MCP などほかの使い方も入る）
    w30 = windows.get(WINDOW_30D) or {}
    at30 = _parse_time(w30.get("at"))
    try:
        if at30 and now - at30 < timedelta(days=30) and str(w30.get("q") or "").isdigit():
            total30 = max(total30, int(w30["q"]) - int(w30.get("r") or 0))
    except (TypeError, ValueError):
        pass
    return {"calls": calls, "total": sum(calls.values()), "blockedUntil": blocked if blocked and blocked > now else None, "windows": windows,
            "used30": total30, "used30ByRole": used30, "kinds30": kinds30, "last429": last429, "lastOk": last_ok, "lastProbe": last_probe}


def probe_due(now: datetime | None = None) -> bool:
    """止まっている（429 の待ちの間）で、前の確かめ（429 か probe）から6時間たったか"""
    now = _now(now)
    s = status(now)
    if not s["blockedUntil"]:
        return False
    hit = _parse_time((s["last429"] or {}).get("at"))
    marks = [t for t in (hit, s["lastProbe"]) if t]
    return not marks or now - max(marks) >= PROBE_EVERY


def next_probe_at(now: datetime | None = None) -> datetime | None:
    now = _now(now)
    s = status(now)
    if not s["blockedUntil"]:
        return None
    hit = _parse_time((s["last429"] or {}).get("at"))
    marks = [t for t in (hit, s["lastProbe"]) if t]
    return max(marks) + PROBE_EVERY if marks else now


def mark_probe(now: datetime | None = None) -> None:
    """probe を送る直前に記録する（落ちても6時間に1回を守る）"""
    now = _now(now)
    data = _load_mine(now)
    data["lastProbe"] = now.isoformat(timespec="seconds")
    _save_mine(data)


def _live_windows(windows: dict, now: datetime) -> list[dict]:
    """まだリセットされていない窓の、最後に分かった残り回数"""
    out = []
    for w, info in windows.items():
        at = _parse_time(info.get("at"))
        try:
            remaining, reset = int(info.get("r")), int(info.get("t"))
        except (TypeError, ValueError):
            continue
        if at and at + timedelta(seconds=reset) > now:
            out.append({"w": w, "r": remaining, "q": info.get("q"), "resetAt": at + timedelta(seconds=reset)})
    return out


def check(role: str = "book", now: datetime | None = None, probe: bool | str = False) -> None:
    """呼んでよいか。だめなら BufferUnavailable を投げる（Buffer には何も送らない）。
    probe=True: 止まっている間の6時間に1回の確かめ（probe_due のときだけ通す。30日の上限の判定は受ける）。
    probe="force": 手で頼んだ1回の確かめ（6時間を待たない。回数には数える）"""
    now = _now(now)
    s = status(now)
    if s["blockedUntil"] and not (probe == "force" or (probe and probe_due(now))):
        raise BufferRateLimited(f"Buffer の上限で {s['blockedUntil'].isoformat(timespec='minutes')} まで呼び出しを止めています"
                                f"（次の確かめ {(next_probe_at(now) or now).isoformat(timespec='minutes')}）")
    soft, hard = cap_30d(s["windows"]), hard_cap_30d(s["windows"])
    if s["used30"] >= hard:
        raise BufferBudgetExceeded(f"Buffer の30日の呼び出しが上限 {hard} 回に達しました（{s['used30']} 回）")
    if s["used30"] >= soft and not (role == "book" and current_priority() == "high"):
        raise BufferBudgetExceeded(f"Buffer の30日の呼び出しがソフトの上限 {soft} 回を超えました（{s['used30']} 回）。優先の枠の投稿だけ作ります")
    if role != "book" and s["used30ByRole"].get("monitor", 0) >= monitor_cap_30d(s["windows"]):
        raise BufferBudgetExceeded(f"読むだけの Buffer 呼び出しが30日の上限 {monitor_cap_30d(s['windows'])} 回に達しました")
    if s["total"] >= daily_cap():
        raise BufferBudgetExceeded(f"Buffer の呼び出しが今日の上限 {daily_cap()} 回に達しました（UTC の日付が変わるまで止めます）")
    if role != "book" and s["calls"]["monitor"] >= monitor_cap():
        raise BufferBudgetExceeded(f"読むだけの Buffer 呼び出しが今日の上限 {monitor_cap()} 回に達しました（予約の分を残すため）")
    for win in _live_windows(s["windows"], now):
        quota = int(win["q"]) if str(win.get("q") or "").isdigit() else 0
        reserve = max(20, quota // 4) if role != "book" else 3
        if win["r"] <= reserve:
            raise BufferBudgetExceeded(
                f"Buffer の残り回数が少ない（窓 {win['w']}秒: 残り {win['r']}回、{win['resetAt'].isoformat(timespec='minutes')} にリセット）"
            )


_ITEM = re.compile(r'\s*(?:"([^"]*)"|([^;,\s]+))((?:\s*;\s*[A-Za-z]+=[^;,]*)*)')


def _parse_items(value: str) -> list[tuple[str, dict]]:
    out = []
    for part in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", value or ""):
        m = _ITEM.match(part)
        if not m:
            continue
        name = m.group(1) if m.group(1) is not None else m.group(2)
        params = {}
        for kv in (m.group(3) or "").split(";"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k.strip()] = v.strip().strip('"')
        out.append((name, params))
    return out


def parse_headers(headers) -> dict:
    """RateLimit / RateLimit-Policy ヘッダーから {窓の秒数: {r, t, q}}。窓は w（900/86400/2592000）で見分ける"""
    get = (lambda k: headers.get(k)) if headers is not None else (lambda k: None)
    policies = {name: p for name, p in _parse_items(get("RateLimit-Policy") or "")}
    out: dict = {}
    for name, p in _parse_items(get("RateLimit") or ""):
        if "r" not in p:
            continue
        pol = policies.get(name, {})
        w = pol.get("w") or name
        entry = {"r": p.get("r"), "t": p.get("t", "0")}
        if pol.get("q"):
            entry["q"] = pol["q"]
        out[str(w)] = entry
    return out


def record(role: str = "book", headers=None, now: datetime | None = None, kind: str = "", ok: bool = True) -> None:
    """Buffer に1回送った（成功・失敗とも数える。429 だけは record_429）。kind: create（投稿を作る）・probe（確かめ）など"""
    now = _now(now)
    role = role if role in ROLES else "book"
    data = _load_mine(now)
    data["calls"][role] = int(data["calls"].get(role, 0) or 0) + 1
    days = _days_of(data)
    today = days.setdefault(_day(now), {})
    today[role] = int(today.get(role, 0) or 0) + 1
    if kind:
        today[kind] = int(today.get(kind, 0) or 0) + 1
    for old in sorted(days)[:-KEEP_DAYS]:
        days.pop(old, None)
    for w, entry in parse_headers(headers).items():
        data["windows"][w] = {**entry, "at": now.isoformat(timespec="seconds")}
    if ok:
        data["lastOk"] = now.isoformat(timespec="seconds")
        if kind == "probe":
            data["probe"] = {"at": now.isoformat(timespec="seconds"), "result": "ok"}
        blocked = _parse_time(data.get("blockedUntil"))
        if blocked and blocked > now:
            data["blockedUntil"] = None  # 呼べた＝上限は解けた（ほかの書き手の待ちも lastOk で解ける）
            data["unblockedAt"] = now.isoformat(timespec="seconds")
    _save_mine(data)


def record_429(headers=None, body: str = "", now: datetime | None = None, probe: bool = False) -> datetime:
    """429 を受けた。Retry-After の秒数（無ければ窓ごとの既定）だけ、全部の呼び出しを止める。止める時刻を返す"""
    now = _now(now)
    window = ""
    m = re.search(r'"window"\s*:\s*"([^"]+)"', body or "")
    if m:
        window = m.group(1)
    wait = None
    raw = headers.get("Retry-After") if headers is not None else None
    if raw:
        try:
            wait = int(float(raw))
        except ValueError:
            when = None
            try:
                from email.utils import parsedate_to_datetime

                when = parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                when = None
            if when:
                wait = int((when - now).total_seconds())
    if wait is None or wait <= 0:
        wait = DEFAULT_WAIT.get(window, 3600)
    until = now + timedelta(seconds=min(wait, MAX_WAIT))
    data = _load_mine(now)
    old = _parse_time(data.get("blockedUntil"))
    # 新しい 429 は今の Buffer の答え。前の待ちより短くても新しい方を使う（probe の結果で待ちが変わる）
    data["blockedUntil"] = until.isoformat(timespec="seconds")
    data["last429"] = {"at": now.isoformat(timespec="seconds"), "window": window, "retryAfter": raw or "",
                       "retryAt": until.isoformat(timespec="seconds"), **({"previousBlockedUntil": old.isoformat(timespec="seconds")} if old else {})}
    if probe:
        data["probe"] = {"at": now.isoformat(timespec="seconds"), "result": "429", "retryAfter": raw or "", "window": window}
    _save_mine(data)
    return until


def summary(now: datetime | None = None) -> dict:
    """今の状態（報告・ログ用）"""
    now = _now(now)
    s = status(now)
    return {"used30": s["used30"], "cap30": cap_30d(s["windows"]), "hard30": hard_cap_30d(s["windows"]),
            "today": s["total"], "dailyCap": daily_cap(), "blockedUntil": s["blockedUntil"].isoformat(timespec="minutes") if s["blockedUntil"] else None,
            "nextProbe": (next_probe_at(now).isoformat(timespec="minutes") if s["blockedUntil"] else None), "last429": s["last429"], "kinds30": s["kinds30"]}


def clear_blocks(now: datetime | None = None) -> list[str]:
    """確かめ（probe）が通ったあと、全部の書き手の記録の待ち（blockedUntil）を消す。消したファイル名を返す（手元・テストでは自分の分だけ）"""
    now = _now(now)
    done = []
    if not persist():
        data = _load_mine(now)
        if data.get("blockedUntil"):
            data["blockedUntil"] = None
            _save_mine(data)
            done.append("memory")
        return done
    for path in sorted(LEDGER_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("blockedUntil"):
            data["blockedUntil"] = None
            data["unblockedAt"] = now.isoformat(timespec="seconds")
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            done.append(path.name)
    return done


def reset_memory() -> None:
    """テスト用"""
    _memory.clear()
    _priority[:] = ["normal"]
    set_role(os.environ.get("BUFFER_ROLE", "book"))


if __name__ == "__main__":
    print(json.dumps(summary(), ensure_ascii=False, indent=2, default=str))
