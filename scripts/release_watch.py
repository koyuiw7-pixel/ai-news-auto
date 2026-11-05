#!/usr/bin/env python3
"""発表時刻が決まった速報（統計・決算）の見張り（2026-11-05 オーナー承認・台帳 W35）。

予定表 scripts/release_calendar.json の発表時刻の前後だけ GitHub Actions（.github/workflows/release_watch.yml）で動き、
公式の資料（PDF）が新しい対象期間で出たのを見つけたら、速報レーン（auto_run.yml の fast_url）を起こす。

オーナーの決まり（速さより正確さ）:
  - 数字は公式の資料から取り出せたときだけ速報にする。PDF が読めない・対象の期間が違う・決まった数字の行が見つからないときは
    速報を出さない（予想や空欄の型で先に出すこともしない）。見張りは失敗として終わり、記事は通常の回に任せる。
  - 取り出した資料の文字を、そのまま記事の材料（fast_meta の text）として渡す。記事の数字はこの文字と照合する
    （scripts/release_quality.py。題名・リード・要点の数字・単位・増減の向き・比べる基準・速報値・予想の言い方）。
  - 二重に起こさない: 同じ URL の速報レーンの実行が既にあれば起こさない。起こした実行が待ちの間に取り消されたら（同じ
    concurrency の後の回に押し出されたとき）起こし直す（3回まで）。

  python scripts/release_watch.py run                  # 今の時刻に見張る予定があれば見張る（GitHub Actions の schedule）
  python scripts/release_watch.py run --dry-run        # 見つけても速報レーンを起こさない（何を渡すかだけ出す）
  python scripts/release_watch.py sample --event maikin-2026-09   # 前回の発表で読み取りを試す（何も起こさない）
  python scripts/release_watch.py crons                # 予定表から作った cron を出す
  python scripts/release_watch.py sync-workflow        # release_watch.yml の cron を予定表に合わせて書き直す
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pdf_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CALENDAR_PATH = ROOT / "scripts" / "release_calendar.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release_watch.yml"
JST = timezone(timedelta(hours=9))
UTC = timezone.utc
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36 saisoku-release-watch"
REPO = os.environ.get("GITHUB_REPOSITORY") or "koyuiw7-pixel/ai-news-auto"
TEXT_CAP = 12_000  # feeds.TEXT_CAP と同じ（記事の材料に渡す長さ）
# GitHub の schedule は数分〜十数分遅れることがあるので、見張りの始まりより前に何回か起動を置く（後の回は前の回が済ませていればすぐ終わる）
CRON_LEADS = (25, 17, 10, 4)
REDISPATCH_MAX = 3
CRON_BEGIN = "# BEGIN release_calendar crons（scripts/release_watch.py sync-workflow が書く。手で直さない）"
CRON_END = "# END release_calendar crons"


# --------------------------------------------------------------------------- #
# 予定表
# --------------------------------------------------------------------------- #


def load_calendar(path: Path = CALENDAR_PATH) -> dict:
    return json.loads(path.read_text("utf-8"))


def _jst(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=JST)


def window(event: dict) -> tuple[datetime, datetime]:
    """見張る時間（日本時間の aware datetime の組）"""
    if event.get("kind") == "tdnet":
        start, end = event["window_jst"]
        return _jst(f"{event['date']}T{start}"), _jst(f"{event['date']}T{end}")
    at = _jst(event["at"])
    before, after = event.get("window") or [-3, 30]
    return at + timedelta(minutes=before), at + timedelta(minutes=after)


def crons(calendar: dict) -> list[str]:
    """予定表から作った GitHub Actions の cron（UTC。日付つきで、その日だけ動く）"""
    out = set()
    for event in calendar["events"]:
        if not enabled(event):
            continue
        start, _ = window(event)
        for lead in CRON_LEADS:
            t = (start - timedelta(minutes=lead)).astimezone(UTC)
            out.add(f"{t.minute} {t.hour} {t.day} {t.month} *")
    return sorted(out, key=lambda c: tuple(int(x) for x in reversed(c.split()[:4])))


def workflow_crons(path: Path = WORKFLOW_PATH) -> list[str]:
    text = path.read_text("utf-8")
    block = text.split(CRON_BEGIN, 1)[1].split(CRON_END, 1)[0]
    return re.findall(r'cron:\s*"([^"]+)"', block)


def sync_workflow(path: Path = WORKFLOW_PATH, calendar: dict | None = None) -> bool:
    calendar = calendar or load_calendar()
    text = path.read_text("utf-8")
    head, rest = text.split(CRON_BEGIN, 1)
    _, tail = rest.split(CRON_END, 1)
    indent = re.search(r"([ \t]*)$", head).group(1)
    lines = "".join(f'{indent}- cron: "{c}"\n' for c in crons(calendar))
    new = f"{head}{CRON_BEGIN}\n{lines}{indent}{CRON_END}{tail}"
    if new != text:
        path.write_text(new, "utf-8")
        return True
    return False


def active_events(calendar: dict, now: datetime, lead_minutes: int = 30, only: str = "") -> list[dict]:
    """今から lead_minutes 分以内に始まるか、今見張っている予定"""
    out = []
    for event in calendar["events"]:
        if not enabled(event) or (only and event["id"] != only):
            continue
        start, end = window(event)
        if start - timedelta(minutes=lead_minutes) <= now <= end:
            out.append(event)
    return out


# --------------------------------------------------------------------------- #
# 取得と読み取り
# --------------------------------------------------------------------------- #


def fetch(url: str, timeout: int = 20) -> tuple[int, bytes]:
    """(HTTP の状態, 中身)。404 などは例外にせず状態を返す"""
    req = urllib.request.Request(url.split("#")[0], headers={"User-Agent": UA, "Cache-Control": "no-cache", "Pragma": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as error:
        return error.code, b""


def norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


class NotYet(Exception):
    """まだ新しい発表が出ていない（404・前の期間のまま）"""


class Unreadable(Exception):
    """発表は出たが、数字を確かに読めない（速報にしない）"""


def keep_parts(text: str, patterns: list[str]) -> str:
    """表の並びが崩れる資料は、確かな部分（総額の行・説明の文）だけを残す"""
    parts = []
    for pattern in patterns:
        m = re.search(pattern, text, re.S)
        if m:
            parts.append(m.group(0).strip())
    return "\n\n".join(parts)


def read_pdf_release(event: dict, url: str | None = None, period_re: str | None = None, keep: list[str] | None = None) -> str:
    """決まった URL の PDF を読み、新しい対象期間で、決まった数字の行が全部あれば本文（文字）を返す。
    まだなら NotYet、出ているのに読めない・数字の行が無いなら Unreadable"""
    status, data = fetch(url or event["url"])
    if status == 404 or (status == 200 and not data):
        raise NotYet(f"HTTP {status}")
    if status != 200:
        raise NotYet(f"HTTP {status}（一時的なものとみなして見張りを続ける）")
    if data[:5] != b"%PDF-":
        raise NotYet("PDF ではない（公開前の案内ページなど）")
    try:
        text = pdf_text.extract(data)
    except pdf_text.PdfTextError as error:
        raise Unreadable(f"PDF の文字を取り出せない: {error}") from error
    if not re.search(period_re or event["period_re"], text):
        # 同じ URL の中身を毎月上書きする資料（家計調査・消費者物価）は、発表までは前の期間のまま
        raise NotYet("対象の期間ではない（前の発表のまま）")
    missing = [p for p in event.get("require") or [] if not re.search(p, text, re.S)]
    if missing:
        raise Unreadable(f"決まった数字の行が見つからない（{' / '.join(m[:40] for m in missing)}）")
    keep = keep if keep is not None else event.get("keep")
    if keep:
        kept = keep_parts(text, keep)
        if not kept:
            raise Unreadable("残すと決めた部分（総額の行など）が見つからない")
        missing = [p for p in event.get("require") or [] if not re.search(p, kept, re.S)]
        if missing:
            raise Unreadable(f"残した部分に決まった数字の行が無い（{' / '.join(m[:40] for m in missing)}）")
        text = kept
    return text[:TEXT_CAP]


def enabled(event: dict) -> bool:
    return event.get("enabled", True) is not False


def tdnet_rows(calendar: dict, day: datetime) -> list[dict]:
    """その日の適時開示の一覧の行（{time, code, company, title, url}）。ページが続く限り読む"""
    conf = calendar["tdnet"]
    ymd = day.astimezone(JST).strftime("%Y%m%d")
    rows: list[dict] = []
    for page in range(1, 30):
        status, data = fetch(conf["list_url"].format(page=page, yyyymmdd=ymd))
        if status != 200 or not data:
            break
        html_text = data.decode("utf-8", "ignore")
        found = 0
        for tr in re.findall(r"<tr.*?</tr>", html_text, re.S):
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td.*?</td>", tr, re.S)]
            href = re.findall(r'href="([^"]+\.pdf)"', tr)
            if len(cells) < 4 or not href:
                continue
            found += 1
            rows.append({"time": cells[0], "code": cells[1], "company": cells[2], "title": cells[3], "url": conf["base_url"] + href[0]})
        if not found or f"I_list_{page + 1:03d}_{ymd}" not in html_text:
            break
    return rows


def tdnet_hits(calendar: dict, event: dict, rows: list[dict]) -> list[dict]:
    conf = calendar["tdnet"]
    out = []
    for row in rows:
        name = event["companies"].get(row["code"])
        if not name or not re.search(conf["title_re"], row["title"]) or re.search(conf["exclude_re"], row["title"]):
            continue
        out.append({**row, "name": name})
    return out


def read_tdnet_pdf(calendar: dict, url: str) -> str:
    status, data = fetch(url, timeout=40)
    if status != 200:
        raise NotYet(f"HTTP {status}")
    try:
        text = pdf_text.extract(data)
    except pdf_text.PdfTextError as error:
        raise Unreadable(f"決算短信の文字を取り出せない: {error}") from error
    text = text[:TEXT_CAP]  # 記事に渡す範囲で確かめる
    missing = [p for p in calendar["tdnet"]["require"] if not re.search(p, text)]
    if missing:
        raise Unreadable(f"決算短信の決まった語が無い（{' / '.join(missing)}）")
    return text[:TEXT_CAP]


# --------------------------------------------------------------------------- #
# 速報レーンを起こす
# --------------------------------------------------------------------------- #


def release_info(calendar: dict, event: dict, publisher: str = "") -> dict:
    """記事の書き方（scripts/release_quality.py が読む）。fast_meta の release に入れる"""
    art = dict(event.get("article") or calendar["tdnet"]["article"])
    return {
        "id": event["id"], "name": event.get("name", ""), "kind": event["kind"],
        "publisher": publisher or art.get("publisher", ""), "basis": art.get("basis", ""),
        "preliminary": bool(art.get("preliminary")), "figures": list(art.get("figures") or []),
        "leadRule": art.get("lead_rule", ""), "notes": art.get("notes", ""),
        "hosts": sorted({urllib.parse.urlsplit(u).hostname for u in [event.get("url"), event.get("page_url"), event.get("dispatch_url")] if u}
                        or {"www.release.tdnet.info"}),
    }


def build_meta(calendar: dict, event: dict, url: str, title: str, source_name: str, text: str, published: datetime,
               detected: datetime, publisher: str = "") -> dict:
    return {
        "url": url, "title": title, "sourceName": source_name, "lang": "ja",
        "publishedAt": published.astimezone(UTC).isoformat(), "detectedAt": detected.astimezone(UTC).isoformat(),
        "text": text, "release": release_info(calendar, event, publisher),
        # 記事のジャンル（統計＝ビジネス・経済、決算＝投資・マネー。台帳 A23・A30）。scripts/web_articles.py がその形で書く
        "genre": event.get("genre") or calendar["tdnet"].get("genre") or "business",
    }


def gh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args, "-R", REPO], capture_output=True, text=True, timeout=60)


def fast_runs(url: str) -> list[dict]:
    """同じ URL の速報レーンの実行（auto_run.yml の run-name「速報レーン <URL>」）"""
    res = gh(["run", "list", "--workflow", "auto_run.yml", "--limit", "60", "--json", "databaseId,displayTitle,status,conclusion,createdAt"])
    if res.returncode != 0:
        raise RuntimeError(f"gh run list に失敗: {res.stderr.strip()[:200]}")
    return [r for r in json.loads(res.stdout or "[]") if r.get("displayTitle") == f"速報レーン {url}"]


def run_state(runs: list[dict]) -> str:
    """none（まだ無い）/ alive（待ち・実行中・済み）/ cancelled（全部取り消された）"""
    if not runs:
        return "none"
    if all(r.get("status") == "completed" and r.get("conclusion") in ("cancelled", "skipped") for r in runs):
        return "cancelled"
    return "alive"


def dispatch(meta: dict) -> None:
    res = gh(["workflow", "run", "auto_run.yml", "-f", "mode=web", "-f", "max_articles=1",
              "-f", f"fast_url={meta['url']}", "-f", f"fast_meta={json.dumps(meta, ensure_ascii=False)}"])
    if res.returncode != 0:
        raise RuntimeError(f"速報レーンを起こせない: {res.stderr.strip()[:200]}")


def ensure_fast_run(meta: dict, log=print, sleep=time.sleep, clock=time.monotonic, start_wait: int = 1500) -> bool:
    """速報レーンの実行を1つ確かに走らせる。同じ URL の実行が既にあれば起こさない。起こした実行が待ちの間に取り消されたら
    （同じ concurrency の後の回に押し出されたとき）起こし直す。実行が始まる（in_progress）か済めば True"""
    tries = 0
    began = clock()
    empty_since = None
    while True:
        runs = fast_runs(meta["url"])
        state = run_state(runs)
        if any(r.get("status") == "in_progress" or (r.get("status") == "completed" and r.get("conclusion") not in ("cancelled", "skipped"))
               for r in runs):
            log(f"   速報レーンの実行: {[(r['databaseId'], r['status'], r.get('conclusion')) for r in runs][:3]}")
            return True
        need = state == "cancelled" or (state == "none" and (tries == 0 or (empty_since is not None and clock() - empty_since > 120)))
        if need:
            if tries > REDISPATCH_MAX:
                log("   速報レーンが取り消され続けたので、起こし直しをやめる")
                return False
            log(f"   速報レーンを起こす（{tries + 1}回目）: {meta['url']}")
            dispatch(meta)
            tries += 1
            empty_since = clock()
        elif state != "none":
            empty_since = None
        if clock() - began > start_wait:
            # 待ちの列に入ったまま（前の記事づくりの回が長い）。列にあれば順番に動くので、見張りはここで終える
            log(f"   速報レーンは待ちの列にあります: {[(r['databaseId'], r['status']) for r in runs][:3]}")
            return state == "alive"
        sleep(20)


# --------------------------------------------------------------------------- #
# 見張り
# --------------------------------------------------------------------------- #


def summary(lines: list[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def run(calendar: dict, dry_run: bool = False, only: str = "", now_fn=lambda: datetime.now(JST), sleep=time.sleep,
        log=print, deliver=None) -> int:
    """見張る。0 = 予定どおり（速報を起こした・予定が無い）/ 1 = 発表が出たのに読めなかった・見つからないまま時間切れ"""
    def show(meta: dict) -> bool:
        log("   （試し）速報レーンに渡す内容: " + json.dumps({k: v for k, v in meta.items() if k != "text"}, ensure_ascii=False))
        log(f"   本文 {len(meta['text'])}字（先頭）: {meta['text'][:400]!r}")
        return True

    raw_deliver = deliver or (show if dry_run else (lambda meta: ensure_fast_run(meta, log, sleep)))

    def deliver(meta: dict) -> bool:
        try:
            return bool(raw_deliver(meta))
        except Exception as error:  # noqa: BLE001 - gh の失敗など。見張りは続ける（失敗として残す）
            log(f"   速報レーンを起こせない: {str(error)[:200]}")
            return False
    now = now_fn()
    events = active_events(calendar, now, only=only)
    if not events:
        log(f"{now:%m-%d %H:%M} 見張る予定はありません")
        return 0
    done: dict[str, str] = {}  # 予定 id（tdnet は id:コード）→ 結果
    problems: dict[str, str] = {}
    log(f"{now:%m-%d %H:%M} 見張る予定: {', '.join(e['id'] for e in events)}{'（試し・起こさない）' if dry_run else ''}")
    while True:
        now = now_fn()
        pending = 0
        for event in events:
            start, end = window(event)
            if event["kind"] == "pdf":
                if event["id"] in done:
                    continue
                if now < start:
                    pending += 1
                    continue
                if now > end:
                    problems.setdefault(event["id"], "見張りの時間内に新しい発表を見つけられなかった")
                    done[event["id"]] = "timeout"
                    continue
                pending += 1
                try:
                    text = read_pdf_release(event)
                except NotYet:
                    continue
                except Unreadable as error:
                    # 読めないものは速報にしない（オーナーの決まり）。資料の差し替えで直ることがあるので時間内は読み直す
                    problems[event["id"]] = str(error)
                    log(f"{now:%H:%M:%S} {event['id']}: {error}（速報にしない。時間内は読み直す）")
                    continue
                problems.pop(event["id"], None)
                url = event.get("dispatch_url") or event["url"]
                at = _jst(event["at"])
                # 発表の時刻は公式の予定の時刻（予定より前に出ていたら見つけた時刻）
                meta = build_meta(calendar, event, url, event["title"], event["source_name"], text, at if now >= at else now, now)
                log(f"{now:%H:%M:%S} {event['id']}: 新しい発表を読めた（{len(text)}字）。速報レーンへ: {url}")
                if deliver(meta):
                    done[event["id"]] = "dispatched"
                    pending -= 1
                else:
                    problems[event["id"]] = "速報レーンを起こせなかった（時間内は起こし直す）"
            else:  # tdnet
                codes = [c for c in event["companies"] if f"{event['id']}:{c}" not in done]
                if not codes or now > end:
                    continue
                if now < start:
                    pending += 1
                    continue
                pending += 1
                try:
                    rows = tdnet_rows(calendar, now)
                except Exception as error:  # noqa: BLE001
                    log(f"{now:%H:%M:%S} 適時開示の一覧を読めない: {str(error)[:120]}")
                    continue
                for hit in tdnet_hits(calendar, event, rows):
                    key = f"{event['id']}:{hit['code']}"
                    if key in done:
                        continue
                    try:
                        text = read_tdnet_pdf(calendar, hit["url"])
                    except NotYet:
                        continue
                    except Unreadable as error:
                        problems[key] = f"{hit['name']}: {error}"
                        done[key] = "unreadable"
                        log(f"{now:%H:%M:%S} {hit['name']}: {error}（速報にしない）")
                        continue
                    meta = build_meta(calendar, event, hit["url"], f"{hit['name']} {hit['title']}", f"{hit['name']}（TDnet 適時開示）",
                                      text, _jst(f"{event['date']}T{hit['time']}") if re.fullmatch(r"\d{2}:\d{2}", hit["time"]) else now,
                                      now, publisher=hit["name"])  # 発表の時刻は適時開示の一覧の時刻
                    log(f"{now:%H:%M:%S} {hit['name']}: {hit['title']}（{len(text)}字）。速報レーンへ: {hit['url']}")
                    if deliver(meta):
                        done[key] = "dispatched"
                        problems.pop(key, None)
                    else:
                        problems[key] = f"{hit['name']}: 速報レーンを起こせなかった（時間内は起こし直す）"
        if pending <= 0:
            break
        sleep(calendar.get("tdnet_poll_seconds", 40) if all(e["kind"] == "tdnet" for e in events)
              else calendar.get("poll_seconds", 15))
    lines = ["## 発表時刻が決まった速報の見張り", ""] + [f"- {k}: {v}" for k, v in done.items()]
    if problems:
        lines += ["", "### 速報にしなかったもの（数字を確かに読めなかった・見つからなかった）", ""] + [f"- {k}: {v}" for k, v in problems.items()]
    summary(lines)
    for line in lines:
        log(line)
    return 1 if problems else 0


def sample(calendar: dict, event_id: str, log=print) -> int:
    """前回の発表で読み取りを試す（何も起こさない）"""
    event = next(e for e in calendar["events"] if e["id"] == event_id)
    conf = event.get("sample") or {}
    try:
        text = read_pdf_release(event, conf.get("url"), conf.get("period_re"), conf.get("keep"))
    except (NotYet, Unreadable) as error:
        log(f"{event_id}: 読めない（{type(error).__name__}: {error}）")
        return 1
    meta = build_meta(calendar, event, event.get("dispatch_url") or event["url"], event["title"], event["source_name"], text,
                      datetime.now(JST), datetime.now(JST))
    log(json.dumps({k: v for k, v in meta.items() if k != "text"}, ensure_ascii=False, indent=1))
    log(f"--- 本文 {len(text)}字 ---\n{text[:3000]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["run", "sample", "crons", "sync-workflow"])
    parser.add_argument("--event", default="", help="この予定だけ")
    parser.add_argument("--dry-run", action="store_true", help="速報レーンを起こさない")
    args = parser.parse_args()
    calendar = load_calendar()
    if args.command == "crons":
        print("\n".join(crons(calendar)))
        return 0
    if args.command == "sync-workflow":
        print("書き直しました" if sync_workflow(calendar=calendar) else "変更なし")
        return 0
    if args.command == "sample":
        return sample(calendar, args.event)
    return run(calendar, dry_run=args.dry_run, only=args.event)


if __name__ == "__main__":
    sys.exit(main())
