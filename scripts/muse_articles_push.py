#!/usr/bin/env python3
"""オーナーの Mac で動く運び役: Muse が置いた記事のファイルをサイトのリポジトリの受け箱に入れる（2026-11-08 オーナー承認・台帳 A59）。

Muse には鍵を渡さない（オーナー決定）。Muse は ~/Downloads/saisoku-articles/ に .md を置くだけ。このスクリプトが:
  1. 専用の作業用の写し（~/.saisoku-muse/repo。ASCII のパス＝launchd が非ASCIIのパスを扱えないため）を origin/main にそろえる
  2. 前に送ったファイル（sent/）の結果を state/muse_articles.json で見て、公開 → done/、見送り → rejected/ と <名前>.reason.txt
  3. 新しい .md を形だけ確かめ（scripts/muse_format.py）、だめなら rejected/ に理由つきで戻す。よければ content/muse_inbox/ に入れて
     コミットし main に push（Mac の git の認証。[no-deploy]。記事にするのは次の Auto Article Pipeline の回）。元のファイルは sent/ へ
  4. FORMAT.md（書式）と ledger.md（この7日の記事の題名と URL・Muse の入稿の結果）を書き直す。Muse は書く前に ledger.md を読む
launchd（~/Library/LaunchAgents/com.komuro.saisoku-muse-articles.plist）で25分ごと。ログは ~/.saisoku-muse/push.log。

  python3 scripts/muse_articles_push.py             # 1回動かす
  python3 scripts/muse_articles_push.py --install   # 作業用の写しを作り、launchd に登録して読み込む（最初の1回）
  python3 scripts/muse_articles_push.py --no-push   # 受け箱に入れるがコミット・push しない（試すとき）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home()
FOLDER = Path(os.environ.get("MUSE_ARTICLES_DIR") or HOME / "Downloads" / "saisoku-articles")
BASE = Path(os.environ.get("MUSE_PUSH_HOME") or HOME / ".saisoku-muse")
CLONE = BASE / "repo"
REMOTE = "https://github.com/koyuiw7-pixel/ai-news-auto.git"
SITE = "https://ai-tech-express.jp"
LABEL = "com.komuro.saisoku-muse-articles"
PLIST = HOME / "Library" / "LaunchAgents" / f"{LABEL}.plist"
INTERVAL_SEC = 25 * 60
JST = timezone(timedelta(hours=9))
SPARSE = ["content/articles", "content/muse_inbox", "content/muse_images", "scripts", "state"]
SKIP_NAMES = {"FORMAT.md", "ledger.md", "README.md"}
SETTLE_SEC = 90  # 書き込み中のファイルを持っていかない（最後の変更からこの秒数たったものだけ）
LEDGER_DAYS = 7
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}


def log(message: str) -> None:
    print(f"{datetime.now(JST):%m-%d %H:%M:%S} {message}", flush=True)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(CLONE), *args], capture_output=True, text=True, env=GIT_ENV, check=check, timeout=300)


def ensure_clone() -> None:
    if (CLONE / ".git").exists():
        git("fetch", "--quiet", "origin", "main")
        git("reset", "--quiet", "--hard", "origin/main")  # 専用の写し（オーナーの作業用の checkout ではない）
        if set(git("sparse-checkout", "list").stdout.split()) != set(SPARSE):
            git("sparse-checkout", "set", *SPARSE)  # 足した置き場（Muse の画像 content/muse_images・台帳 I8）
        return
    BASE.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--sparse", REMOTE, str(CLONE)], check=True, env=GIT_ENV, timeout=600)
    git("sparse-checkout", "set", *SPARSE)
    git("config", "user.name", "koyuiw7-pixel")
    git("config", "user.email", "koyuiw7@gmail.com")


def load_muse_format():
    sys.path.insert(0, str(CLONE / "scripts"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import muse_format  # noqa: PLC0415

    return muse_format


def results() -> dict:
    try:
        return (json.loads((CLONE / "state" / "muse_articles.json").read_text("utf-8")).get("items")) or {}
    except (OSError, ValueError):
        return {}


def move(src: Path, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / src.name
    if dest.exists():
        dest = folder / f"{src.stem}-{int(time.time())}{src.suffix}"
    shutil.move(str(src), str(dest))
    return dest


def write_reason(dest_md: Path, reason: str) -> None:
    dest_md.with_suffix(".reason.txt").write_text(
        f"見送りの理由（{datetime.now(JST):%Y-%m-%d %H:%M}）\n\n{reason}\n\n直し方は FORMAT.md を見てください。直したら新しいファイルとして置き直してください。\n",
        encoding="utf-8")


def settle_results(items: dict) -> list[str]:
    """sent/ のファイルを、結果に合わせて done/・rejected/ に移す"""
    notes = []
    sent = FOLDER / "sent"
    if not sent.exists():
        return notes
    for path in sorted(sent.glob("*.md")):
        row = items.get(nfc(path.name))
        if not row or row.get("status") == "waiting":
            continue
        if row.get("status") == "published":
            move(path, FOLDER / "done")
            notes.append(f"公開: {path.name} → {row.get('url')}")
        elif row.get("status") == "rejected":
            dest = move(path, FOLDER / "rejected")
            write_reason(dest, str(row.get("reason") or "理由の記録がありません"))
            notes.append(f"見送り: {path.name}（{str(row.get('reason'))[:80]}）")
    return notes


def pick_new(mf, items: dict) -> list[tuple[Path, str]]:
    """新しい入稿 [(元のファイル, 受け箱での名前)]。形のだめなものはここで rejected/ に戻す"""
    out = []
    now = time.time()
    for path in sorted(FOLDER.glob("*.md")):
        if path.name in SKIP_NAMES or path.name.startswith("."):
            continue
        # 記事は「YYYYMMDD-….md」だけ。共有の記録（discrepancies.md・usage.md など）は記事として扱わない（2026-11-08）
        if not re.match(r"^\d{8}-", unicodedata.normalize("NFC", path.name)):
            continue
        if now - path.stat().st_mtime < SETTLE_SEC:
            log(f"書き込み中かもしれないので次の回に回します: {path.name}")
            continue
        name = nfc(path.name)
        try:
            data = mf.parse(path.read_text("utf-8"))
            problems = mf.problems(data, name)
        except (OSError, UnicodeDecodeError) as error:
            problems = [f"ファイルを読めません（{error}）"]
        except mf.FormatError as error:
            problems = [str(error)]
        if problems:
            dest = move(path, FOLDER / "rejected")
            write_reason(dest, "書式: " + "\n".join(f"- {p}" for p in problems))
            log(f"書式で見送り: {name}（{problems[0][:80]}）")
            continue
        if name in items or (CLONE / "content" / "muse_inbox" / name).exists():
            stem = name[:-3]
            name = f"{stem}-{datetime.now(JST):%H%M}.md"  # 同じ名前の入稿が前にあった（結果の取り違えを防ぐ）
        out.append((path, name))
    return out


def push(message: str) -> bool:
    for attempt in range(1, 4):
        got = git("push", "--quiet", "origin", "HEAD:main", check=False)
        if got.returncode == 0:
            return True
        log(f"push に失敗（{attempt}回目）: {got.stderr.strip()[-200:]}")
        git("fetch", "--quiet", "origin", "main", check=False)
        rebased = git("rebase", "--quiet", "origin/main", check=False)
        if rebased.returncode != 0:
            git("rebase", "--abort", check=False)
            return False
        time.sleep(5 * attempt)
    return False


def article_rows(days: int = LEDGER_DAYS) -> list[dict]:
    since = datetime.now(JST) - timedelta(days=days)
    rows = []
    for path in (CLONE / "content" / "articles").glob("*.json"):
        try:
            a = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        stamp = str(a.get("generatedAt") or a.get("publishedAt") or "")
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(JST)
        except ValueError:
            continue
        if when >= since:
            rows.append({"when": when, "title": str(a.get("title") or ""), "slug": a.get("slug") or path.stem,
                         "muse": a.get("writer") == "muse", "genre": a.get("genre") or ""})
    return sorted(rows, key=lambda r: r["when"], reverse=True)


def write_ledger(items: dict, pending: list[str], extra: list[str] | None = None) -> None:
    now = datetime.now(JST)
    lines = [
        "# サイソク 記事の台帳（Muse さんが書く前に読む）",
        "",
        f"更新: {now:%Y-%m-%d %H:%M}（25分ごとに自動で書き直します。この台帳は書き換えないでください）",
        "",
        "同じ話題（同じ発表・同じ数字）の記事は重複として見送られます。下の題名と重ならない話題を選んでください。",
        "",
        "## Muse さんの入稿の結果（新しい順）",
        "",
        "| 日時 | ファイル | 結果 | 題名 | URL・理由 |",
        "|---|---|---|---|---|",
    ]
    status_ja = {"published": "公開", "rejected": "見送り", "waiting": "順番待ち"}
    for name in pending:
        lines.append(f"| {now:%m/%d %H:%M} | {name} | 審査中 | | 次の記事づくりの回（20分ごと）で審査します |")
    for name, row in sorted(items.items(), key=lambda kv: str(kv[1].get("at") or ""), reverse=True)[:60]:
        try:
            at = datetime.fromisoformat(str(row.get("at"))).astimezone(JST).strftime("%m/%d %H:%M")
        except ValueError:
            at = ""
        tail = row.get("url") or str(row.get("reason") or "").replace("|", "／").replace("\n", " ")[:200]
        lines.append(f"| {at} | {name} | {status_ja.get(row.get('status'), row.get('status'))} | "
                     f"{str(row.get('title') or '').replace('|', '／')} | {tail} |")
    rows = article_rows()
    today = [r for r in rows if r["when"].date() == now.date()]
    lines += ["", f"## 今日（{now:%m/%d}）サイトに出た・出る予定の記事（{len(today)}本）", ""]
    lines += [f"- {r['when']:%H:%M} {r['title']}{'（Muse）' if r['muse'] else ''} {SITE}/articles/{r['slug']}" for r in today] or ["- まだありません"]
    lines += ["", f"## この{LEDGER_DAYS}日の記事（今日を除く・新しい順・{len(rows) - len(today)}本）", ""]
    lines += [f"- {r['when']:%m/%d} {r['title']}{'（Muse）' if r['muse'] else ''} {SITE}/articles/{r['slug']}" for r in rows if r not in today]
    lines += extra or []  # Muse さんの画像の結果（scripts/muse_images_push.py・台帳 I8）
    (FOLDER / "ledger.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def images(no_push: bool) -> list[str]:
    """Muse の表紙の写真（~/Downloads/saisoku-images/）を送る（scripts/muse_images_push.py・台帳 I8）。ledger.md に足す行"""
    try:
        sys.path.insert(0, str(CLONE / "scripts"))
        import muse_images_push  # noqa: PLC0415

        return muse_images_push.run(CLONE, git=git, push=push, no_push=no_push)
    except Exception as error:  # noqa: BLE001 - 画像で失敗しても記事の入稿は止めない
        log(f"Muse の画像でエラー: {str(error)[:200]}")
        return []


def run(no_push: bool = False) -> int:
    FOLDER.mkdir(parents=True, exist_ok=True)
    ensure_clone()
    mf = load_muse_format()
    fmt = FOLDER / "FORMAT.md"
    if not fmt.exists() or fmt.read_text("utf-8") != mf.FORMAT_MD:
        fmt.write_text(mf.FORMAT_MD, encoding="utf-8")
    items = {nfc(k): v for k, v in results().items()}
    for note in settle_results(items):
        log(note)
    new = pick_new(mf, items)
    pending = [p.name for p in sorted((FOLDER / "sent").glob("*.md"))] if (FOLDER / "sent").exists() else []
    pending = [n for n in pending if nfc(n) not in items or items[nfc(n)].get("status") == "waiting"]
    if new:
        inbox = CLONE / "content" / "muse_inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        for src, name in new:
            shutil.copyfile(src, inbox / name)
        if no_push:
            log(f"受け箱に入れました（push なし）: {', '.join(n for _, n in new)}")
        else:
            git("add", "content/muse_inbox")
            message = f"chore(muse): Muse の記事の入稿 (+{len(new)}本) [no-deploy]"
            git("commit", "--quiet", "-m", message)
            if not push(message):
                log("push できなかったので、ファイルはフォルダに残して次の回にもう一度送ります")
                git("reset", "--quiet", "--hard", "origin/main", check=False)
                write_ledger(items, pending, images(no_push))
                return 1
            for src, name in new:
                dest = move(src, FOLDER / "sent")
                if dest.name != name:
                    dest.rename(dest.with_name(name))
                pending.append(name)
            log(f"入稿を送りました: {', '.join(n for _, n in new)}")
    write_ledger(items, pending, images(no_push))
    return 0


PLIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <!-- サイソク: Muse の記事の入稿を運ぶ（台帳 A59）。パスは ASCII（launchd は非ASCIIのパスを扱えない） -->
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>{script}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartInterval</key>
  <integer>{interval}</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


def install() -> int:
    ensure_clone()
    python = shutil.which("python3") or "/usr/bin/python3"
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_text(PLIST_XML.format(label=LABEL, python=python, script=CLONE / "scripts" / "muse_articles_push.py",
                                      interval=INTERVAL_SEC, log=BASE / "push.log"), encoding="utf-8")
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)], check=True)
    log(f"launchd に登録しました: {PLIST}（{INTERVAL_SEC // 60}分ごと・ログ {BASE / 'push.log'}）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()
    if args.install:
        return install()
    try:
        return run(no_push=args.no_push)
    except subprocess.CalledProcessError as error:
        log(f"git でエラー: {' '.join(error.cmd)[-120:]} {str(error.stderr or '')[-300:]}")
        return 1
    except PermissionError as error:
        log(f"フォルダを読めません（macOS の許可が要るかもしれません。システム設定 > プライバシーとセキュリティ > フルディスクアクセス）: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
