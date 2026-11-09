#!/usr/bin/env python3
"""オーナーの Mac で動く運び役（画像）: Muse が描いた表紙の写真をサイトのリポジトリに入れる（2026-11-08 オーナー承認・台帳 I8）。

scripts/muse_articles_push.py（launchd・25分ごと）の回の中で呼ばれる（同じ作業用の写し ~/.saisoku-muse/repo を使う）。
フォルダ ~/Downloads/saisoku-images/:
  requests.md          こちらが書く依頼の一覧（優先の順・SNS・動画に出す記事は「急」）。Muse は書き換えない
  <slug>.jpg           Muse が置く写真（1200×675）
  done-YYYYMMDD.md     Muse が書き足す: 置いたファイル名（- <slug>.jpg）と、描けなかった記事（- <slug>: 理由）
  done/                送った写真（こちらが移す）
  rejected/            使えなかった写真と <名前>.reason.txt（こちらが移す）
流れ: 依頼の一覧（state/muse_images.json。GitHub Actions の scripts/muse_images.py が書く）から requests.md を書き直す →
新しい <slug>.jpg を確かめる（空でない・開ける・幅と縦横の比・ほぼ真っ暗/一色でない。Pillow が無ければ sips で大きさだけ）→
content/muse_images/ に入れ、描けなかった理由は <slug>.skip.txt にして、まとめてコミットし main に push（[no-deploy]）。
記事に付けるのは次の Auto Article Pipeline の回（「Muse images」の段）。結果は ledger.md の「Muse さんの画像」の節に出る。

Google ドライブの受け口（2026-11-10 台帳 I9）: チーム（Muse・Grok など）が同期フォルダ
~/Library/CloudStorage/GoogleDrive-koyuiw7@gmail.com/マイドライブ/サイソク連絡/images/ に置いた <slug>.jpg（.jpeg・.png・.webp も可）と
<slug>-fig<N>.png を、毎回の初めに上のフォルダへ写す（pull_drive。元のファイルは消さない。同じ名前・大きさ・時刻のものは二度写さない）。
あとは Muse の写真と同じ確かめ・同じ流れで記事の表紙（coverImage・「画像はイメージ（AI生成）」）になり、図の表紙より先に出る。

  python3 scripts/muse_images_push.py --no-push   # 1回だけ（push しない。試すとき。ふだんは muse_articles_push.py の回の中で動く）
"""
from __future__ import annotations

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
FOLDER = Path(os.environ.get("MUSE_IMAGES_DIR") or HOME / "Downloads" / "saisoku-images")
BASE = Path(os.environ.get("MUSE_PUSH_HOME") or HOME / ".saisoku-muse")
SENT_NOTES = BASE / "images_notes_sent.json"
DRIVE_DIR = Path(os.environ.get("SAISOKU_DRIVE_IMAGES")
                 or HOME / "Library" / "CloudStorage" / "GoogleDrive-koyuiw7@gmail.com" / "マイドライブ" / "サイソク連絡" / "images")
DRIVE_SEEN = BASE / "drive_images_seen.json"
DRIVE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
DRIVE_README = """サイソクの記事の写真の受け口です（2026-11-10 から）。

- 記事の URL の最後の部分（slug）をファイル名にして置いてください: <slug>.jpg（1200×675 くらいの横長。.png・.webp も可）
  例: https://ai-tech-express.jp/articles/electricity-bill-nov-2026-subsidy-ends → electricity-bill-nov-2026-subsidy-ends.jpg
- 25分ごとに Mac が拾い、確かめてから記事の表紙に付けます（「画像はイメージ（AI生成）」の札が付きます）。
- 説明の図は <slug>-fig1.png の名前で置くと、記事の本文の図になります。
- 写真に文字・実在の人物の顔・ロゴは入れないでください。描き直したら同じ名前で置き直すと替わります。
- 使えなかった写真は ~/Downloads/saisoku-images/rejected/ に理由と一緒に移ります（ここのファイルは消しません）。
"""
JST = timezone(timedelta(hours=9))
SITE = "https://ai-tech-express.jp"
SETTLE_SEC = 90
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,150}$")
# 背景（scripts/muse_images.py と同じ数字。Mac には Pillow が無いことがあるので、ここでは読み込まずに同じ値を持つ）
OUT_W, OUT_H = 1200, 675
MIN_WIDTH = 800
ASPECT_RANGE = (1.5, 2.1)
MIN_BYTES = 10_000
STATUS_JA = {"requested": "依頼中", "delivered": "届いた（反映待ち）", "applied": "記事に付けました", "skipped": "見送り"}


def log(message: str) -> None:
    print(f"{datetime.now(JST):%m-%d %H:%M:%S} [画像] {message}", flush=True)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def load_state(clone: Path) -> dict:
    try:
        data = json.loads((clone / "state" / "muse_images.json").read_text("utf-8"))
        return data if isinstance(data.get("items"), dict) else {"items": {}}
    except (OSError, ValueError, AttributeError):
        return {"items": {}}


def article_slugs(clone: Path) -> set[str]:
    return {p.stem for p in (clone / "content" / "articles").glob("*.json")}


# --------------------------------------------------------------------------- requests.md
def requests_md(state: dict, now: datetime | None = None) -> str:
    now = now or datetime.now(JST)
    cap = int(state.get("dailyCap") or 20)
    today = now.strftime("%Y-%m-%d")
    items = state.get("items") or {}
    open_rows = sorted(((s, r) for s, r in items.items() if r.get("status") == "requested"),
                       key=lambda kv: (int(kv[1].get("priority") or 9), str(kv[1].get("requestedAt") or "")))
    used = sum(1 for r in items.values() if r.get("day") == today and r.get("status") in ("requested", "delivered", "applied"))
    lines = [
        "# サイソク 表紙の写真の依頼（Muse さんへ）",
        "",
        f"更新: {now:%Y-%m-%d %H:%M}（25分ごとに自動で書き直します。このファイルは書き換えないでください）",
        f"今日の枚数: {used}/{cap} 枚（1日の上限 {cap} 枚）。上から順に描いてください。「急」は SNS・動画に出す記事です。",
        "",
        "## 置き方",
        "",
        "- このフォルダに `<slug>.jpg`（1200×675 の JPEG）で置く。slug は下の各項目の名前（記事の URL の最後の部分）",
        "- 置いたら `done-YYYYMMDD.md`（今日なら `done-" + now.strftime("%Y%m%d") + ".md`）に1行ずつ書き足す:",
        "  - 置いた写真: `- <slug>.jpg`",
        "  - 描けなかった記事: `- <slug>: 描けなかった理由`",
        "- 記事に合う写真を描いてください（描き方はお任せ。技術的なことは `STYLE.md`：1200×675・写真に文字は不要・実在の人物の顔とロゴは描かない）。",
        "- 描き直したいときは、同じ名前（<slug>.jpg）でもう一度置けば新しい方に替わります",
        "  話題に合う絵が描けないときは描かずに理由を書く（関係の無い絵は描かない）",
        "- 結果（付けた・見送った理由）は `~/Downloads/saisoku-articles/ledger.md` の「Muse さんの画像」の節に出ます",
        "",
        f"## 依頼（{len(open_rows)}件）",
        "",
    ]
    if not open_rows:
        lines.append("- いまはありません")
    for slug, row in open_rows:
        mark = "急 " if row.get("urgent") else ""
        lines += [f"### {mark}{slug}", "", f"- 記事: {row.get('url') or SITE + '/articles/' + slug}", f"- 題名: {row.get('title', '')}"]
        lines += ["- 要点:"] + [f"  - {p}" for p in row.get("points") or []]
        if row.get("angle"):
            lines.append(f"- 読者にとって: {row['angle']}")
        if row.get("had") == "ai":
            lines.append("- いまは別の AI のイメージが付いています。優先が高い記事なので、Muse さんの写真に替えます")
        lines.append("")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- done-YYYYMMDD.md（描けなかった理由）
NOTE_RE = re.compile(r"^\s*(?:[-*・]|\d+[.)])?\s*`?([a-z0-9][a-z0-9-]{2,150})(\.jpe?g)?`?\s*[:：\-－]?\s*(.*)$")


def muse_skips(folder: Path, known: set[str]) -> dict[str, str]:
    """done-*.md の中の「描けなかった記事: 理由」{slug: 理由}（.jpg の行は置いた写真なので除く）"""
    out: dict[str, str] = {}
    for path in sorted(folder.glob("done-*.md")):
        try:
            text = path.read_text("utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            match = NOTE_RE.match(nfc(line))
            if not match or match.group(2) or match.group(1) not in known:
                continue
            reason = match.group(3).strip()
            if reason:
                out[match.group(1)] = reason[:300]
    return out


def load_sent_notes() -> dict:
    try:
        return json.loads(SENT_NOTES.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------- 写真の確かめ
def sips_size(path: Path) -> tuple[int, int] | None:
    try:
        out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)], capture_output=True, text=True, timeout=60).stdout
        w = int(re.search(r"pixelWidth:\s*(\d+)", out).group(1))
        h = int(re.search(r"pixelHeight:\s*(\d+)", out).group(1))
        return w, h
    except Exception:  # noqa: BLE001
        return None


def check_image(path: Path, dest: Path) -> list[str]:
    """確かめて、よければ dest に 1200×675 の JPEG を書く。だめな理由の一覧（空ならよい）"""
    data = path.read_bytes()
    if len(data) < MIN_BYTES:
        return [f"ファイルが空か小さすぎます（{len(data)} バイト）"]
    try:
        from PIL import Image  # noqa: PLC0415

        sys.path.insert(0, str(dest.parents[2] / "scripts"))
        import muse_images  # noqa: PLC0415 （GitHub Actions と同じ確かめ）

        with Image.open(path) as opened:
            image = opened.convert("RGB")
        problems = muse_images.image_problems(image)
        if not problems:
            muse_images.fit_size(image).save(dest, "JPEG", quality=90)
        return problems
    except ImportError:
        pass
    except Exception as error:  # noqa: BLE001
        return [f"画像を開けません（{str(error)[:80]}）"]
    size = sips_size(path)
    if not size:
        return ["画像を開けません（JPEG で置いてください）"]
    w, h = size
    problems = []
    if w < MIN_WIDTH:
        problems.append(f"小さすぎます（幅 {w}px。{OUT_W}×{OUT_H} で置いてください）")
    if not ASPECT_RANGE[0] <= (w / h if h else 0) <= ASPECT_RANGE[1]:
        problems.append(f"縦横の比が 16:9 から遠すぎます（{w}×{h}。{OUT_W}×{OUT_H} で置いてください）")
    if not problems:
        shutil.copyfile(path, dest)  # 大きさ・暗さは GitHub Actions でも確かめ、1200×675 にそろえる
    return problems


def move(src: Path, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / src.name
    if dest.exists():
        dest = folder / f"{src.stem}-{int(time.time())}{src.suffix}"
    shutil.move(str(src), str(dest))
    return dest


def reject(path: Path, problems: list[str]) -> None:
    dest = move(path, FOLDER / "rejected")
    dest.with_suffix(".reason.txt").write_text(
        f"使えなかった理由（{datetime.now(JST):%Y-%m-%d %H:%M}）\n\n" + "\n".join(f"- {p}" for p in problems)
        + "\n\n直したら同じ名前（<slug>.jpg）で置き直してください。\n", encoding="utf-8")
    log(f"使えない写真: {path.name}（{problems[0][:80]}）")


# --------------------------------------------------------------------------- ledger.md の節
def ledger_section(state: dict, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(JST)
    since = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = sorted(((s, r) for s, r in (state.get("items") or {}).items() if str(r.get("day") or "") >= since and r.get("status") != "requested"),
                  key=lambda kv: str(kv[1].get("at") or kv[1].get("requestedAt") or ""), reverse=True)
    lines = ["", "## Muse さんの画像（きのうと今日）", "",
             f"依頼は `~/Downloads/saisoku-images/requests.md`。今日の上限 {int(state.get('dailyCap') or 20)} 枚。", ""]
    if not rows:
        return lines + ["- まだありません"]
    lines += ["| 記事 | 結果 | 写真・理由 |", "|---|---|---|"]
    for slug, row in rows[:40]:
        tail = row.get("image") or str(row.get("reason") or "").replace("|", "／").replace("\n", " ")[:160]
        lines.append(f"| {SITE}/articles/{slug} | {STATUS_JA.get(row.get('status'), row.get('status'))} | {tail} |")
    return lines


# --------------------------------------------------------------------------- 1回分
def pull_drive(drive: Path | None = None, folder: Path | None = None, seen_path: Path | None = None, now: float | None = None) -> list[str]:
    """Google ドライブの受け口（DRIVE_DIR）の新しい写真・図を受け箱（FOLDER）へ写す。写した名前の一覧（台帳 I9）。
    書き込み中かもしれない新しすぎるファイルは次の回に回す。JPEG 以外の写真は sips で JPEG にする（Pillow が無くてもよい）"""
    drive = drive or DRIVE_DIR
    folder = folder or FOLDER
    seen_path = seen_path or DRIVE_SEEN
    now = now or time.time()
    try:
        drive.mkdir(parents=True, exist_ok=True)
        readme = drive / "README.txt"
        if not readme.exists():
            readme.write_text(DRIVE_README, encoding="utf-8")
        files = sorted(drive.iterdir())
    except OSError as error:
        log(f"Google ドライブの受け口を開けません（{str(error)[:100]}）")
        return []
    try:
        seen = json.loads(seen_path.read_text("utf-8"))
    except (OSError, ValueError):
        seen = {}
    copied: list[str] = []
    folder.mkdir(parents=True, exist_ok=True)
    for path in files:
        name = nfc(path.name)
        if not path.is_file() or name.startswith(".") or path.suffix.lower() not in DRIVE_EXTS:
            continue
        stat = path.stat()
        key = f"{stat.st_size}:{int(stat.st_mtime)}"
        if seen.get(name) == key or now - stat.st_mtime < SETTLE_SEC:
            continue
        stem = nfc(path.stem).strip().lower()
        try:
            if re.search(r"-fig\d+$", stem):
                if path.suffix.lower() != ".png":
                    continue  # 説明の図は PNG だけ
                dest = folder / f"{stem}.png"
                shutil.copyfile(path, dest)
            elif path.suffix.lower() in (".jpg", ".jpeg"):
                dest = folder / f"{stem}.jpg"
                shutil.copyfile(path, dest)
            else:
                dest = folder / f"{stem}.jpg"
                done = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90", str(path), "--out", str(dest)],
                                      capture_output=True, text=True, timeout=120)
                if done.returncode != 0 or not dest.exists():
                    log(f"Google ドライブの {name} を JPEG にできません（{(done.stderr or '')[:80]}）")
                    continue
            os.utime(dest, (stat.st_mtime, stat.st_mtime))  # 受け箱の「書き込み中」の待ちを、元のファイルの時刻で数える
        except OSError as error:
            log(f"Google ドライブの {name} を写せません（{str(error)[:80]}）")
            continue
        seen[name] = key
        copied.append(name)
    if copied:
        seen_path.parent.mkdir(parents=True, exist_ok=True)
        seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"Google ドライブから受け箱へ写しました: {', '.join(copied)}")
    return copied


def run(clone: Path, git=None, push=None, no_push: bool = False) -> list[str]:
    """requests.md を書き、新しい写真と描けなかった理由を送る。ledger.md に足す行を返す"""
    FOLDER.mkdir(parents=True, exist_ok=True)
    pull_drive()
    state = load_state(clone)
    (FOLDER / "requests.md").write_text(requests_md(state), encoding="utf-8")
    known = article_slugs(clone)
    inbox = clone / "content" / "muse_images"
    inbox.mkdir(parents=True, exist_ok=True)
    sent_notes = load_sent_notes()
    notes = {s: r for s, r in muse_skips(FOLDER, known).items()
             if sent_notes.get(s) != r and (state.get("items", {}).get(s) or {}).get("status") not in ("applied", "skipped")}
    new: list[tuple[Path, str]] = []
    now = time.time()
    for path in sorted(FOLDER.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".jpg", ".jpeg") or path.name.startswith("."):
            continue
        if now - path.stat().st_mtime < SETTLE_SEC:
            continue  # 書き込み中かもしれない
        slug = nfc(path.stem).strip().lower()
        if not SLUG_RE.match(slug) or slug not in known:
            reject(path, [f"この名前（{path.stem}）の記事がありません。requests.md の slug（記事の URL の最後の部分）で置いてください"])
            continue
        problems = check_image(path, inbox / f"{slug}.jpg")
        if problems:
            reject(path, problems)
            continue
        new.append((path, slug))
    for slug, reason in notes.items():
        (inbox / f"{slug}.skip.txt").write_text(reason + "\n", encoding="utf-8")
    # 2026-11-09: Muse の説明の図（<slug>-fig<N>.png）を public/fig/ に送る（scripts/map_figures.py が記事の figures に付け、X・記事の本文で使う）
    figs: list[Path] = []
    fig_dir = clone / "public" / "fig"
    for path in sorted(FOLDER.glob("*-fig*.png")):
        if path.name.startswith(".") or now - path.stat().st_mtime < SETTLE_SEC:
            continue
        m = re.match(r"^(.+)-fig(\d+)$", nfc(path.stem).strip().lower())
        if not m or m.group(1) not in known:
            continue  # 記事の slug でない名前（例: docomo-followup-fig1）は送らずに残す
        fig_dir.mkdir(parents=True, exist_ok=True)
        dest = fig_dir / f"{m.group(1)}-fig{m.group(2)}.png"
        # 送り済みかは「git に入っているか」で見る（前の回の失敗で作業場所に残ったファイルを送り済みと見なさない・2026-11-09）
        tracked = subprocess.run(["git", "-C", str(clone), "ls-files", "--error-unmatch", str(dest.relative_to(clone))],
                                 capture_output=True).returncode == 0
        if tracked and dest.exists() and dest.read_bytes() == path.read_bytes():
            continue
        shutil.copyfile(path, dest)
        figs.append(path)
    if not new and not notes and not figs:
        return ledger_section(state)
    names = [s for _, s in new] + [f.name for f in figs]
    if no_push or git is None or push is None:
        log(f"受け箱に入れました（push なし）: 写真 {', '.join(names) or 'なし'}・描けなかった {', '.join(notes) or 'なし'}")
        return ledger_section(state)
    git("add", "content/muse_images")
    if figs:
        git("add", "public/fig")
    git("commit", "--quiet", "-m", f"chore(muse): Muse の表紙の写真 (+{len(new)}枚・説明の図 +{len(figs)}枚・描けなかった {len(notes)}件) [no-deploy]")
    if not push("muse images"):
        log("push できなかったので、写真はフォルダに残して次の回にもう一度送ります")
        git("reset", "--quiet", "--hard", "origin/main", check=False)
        return ledger_section(state)
    for path, _ in new:
        move(path, FOLDER / "done")
    sent_notes.update(notes)
    BASE.mkdir(parents=True, exist_ok=True)
    SENT_NOTES.write_text(json.dumps(sent_notes, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"送りました: 写真 {', '.join(names) or 'なし'}・描けなかった {', '.join(notes) or 'なし'}（記事に付くのは次の記事づくりの回）")
    return ledger_section(state)


if __name__ == "__main__":
    print("\n".join(run(Path(os.environ.get("MUSE_CLONE") or BASE / "repo"), no_push=True)))
