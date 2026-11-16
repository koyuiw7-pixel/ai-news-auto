#!/usr/bin/env python3
"""デプロイを保留した記事の控え（state/deploy_held.json）。保留した記事は、期限までに必ずデプロイに載せる（2026-11-17）。

きっかけ（2026-11-17 07:13 JST）: Muse の記事（lawson-morisugi-challenge-nov17）を公開した回が、前回のデプロイから8分しか
たっていないので [no-deploy] で保留した。保留の印は state/deploy_pending（0/1 の1文字）だったが、
  1. Muse の保留を出すのは「55分ごとのまとめ」だけで、15分の決まりで出す回が無かった（コメントの「次の Muse の回が出す」は
     次の Muse の回が新しく公開したときだけだった）
  2. 保留の印「1」は、読み込んだときの値も「1」だったので、push の3方向マージ（scripts/git_safe_push.py）で「変えていない」と
     見なされ、同じころに別の回がデプロイを呼んで書いた「0」に負けて消えた。そのデプロイは Lawson の記事より前の版を出していた
→ 本番で 404 のまま、手で Deploy を呼ぶまで15分以上残った。

このファイルは「記事ごと」の控え（{"held": {"<slug>": {"by", "at", "due"}}}）にする。JSON の項目ごとの3方向マージなので、
別の回が「空にした」のと同時に足された記事は消えない（足した項目は main 側の新しい項目として残る）。
  - 保留する回: add（足した・直した記事を控え、期限 due＝この時刻までにデプロイする）
  - デプロイを呼ぶ回: clear（読み込んだときにあった控えは、その回の push のあとに呼ぶデプロイが HEAD を出すので必ず載る）
  - 記事づくりの回（auto_run.yml・15〜20分ごと）と Muse の回: due（期限が来た控えがあれば 1）→ 1 ならデプロイする

  python3 scripts/deploy_hold.py add --by muse --due 1794600000 --staged   # git add 済みの記事を控える
  python3 scripts/deploy_hold.py add --by muse --due 1794600000 --slugs a,b
  python3 scripts/deploy_hold.py due [--now 1794600000]                  # 1 = 期限が来た控えがある / 0 = ない
  python3 scripts/deploy_hold.py clear
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "state" / "deploy_held.json"


def load(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or PATH).read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    held = data.get("held") if isinstance(data, dict) else None
    return {"held": dict(held) if isinstance(held, dict) else {}}


def save(data: dict, path: Path | None = None) -> None:
    target = path or PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")


def add(data: dict, keys: list[str], by: str, due: int, now: int) -> dict:
    """控えを足す。もう控えてある記事は、早いほうの期限のまま（後の保留で先送りにしない）"""
    for key in keys:
        old = data["held"].get(key) or {}
        old_due = old.get("due") if isinstance(old.get("due"), int) else None
        data["held"][key] = {"by": old.get("by") or by, "at": old.get("at") or now,
                             "due": min(due, old_due) if old_due is not None else due}
    return data


def due_keys(data: dict, now: int) -> list[str]:
    """期限が来た（due <= now）控え。期限の読めない控えは、来たものとして扱う（出し忘れより出しすぎのほうがよい）"""
    out = []
    for key, row in sorted(data["held"].items()):
        due = row.get("due") if isinstance(row, dict) else None
        if not isinstance(due, int) or due <= now:
            out.append(key)
    return out


def staged_slugs() -> list[str]:
    """git add 済みで、足した・直した記事（content/articles/*.json）の slug"""
    got = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=AM", "--", "content/articles/*.json"],
                         capture_output=True, text=True, cwd=ROOT, check=False)
    return [Path(line).stem for line in got.stdout.split() if line.endswith(".json")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--by", required=True)
    a.add_argument("--due", type=int, required=True)
    a.add_argument("--slugs", default="")
    a.add_argument("--staged", action="store_true")
    a.add_argument("--now", type=int, default=0)
    d = sub.add_parser("due")
    d.add_argument("--now", type=int, default=0)
    sub.add_parser("clear")
    args = parser.parse_args(argv)
    now = getattr(args, "now", 0) or int(time.time())

    data = load()
    if args.cmd == "add":
        keys = [s.strip() for s in args.slugs.split(",") if s.strip()]
        if args.staged:
            keys += staged_slugs()
        keys = list(dict.fromkeys(keys)) or [f"{args.by}@{now}"]  # 記事が分からない保留（追記だけ等）も控える
        save(add(data, keys, args.by, args.due, now))
        print(f"保留を控えました: {len(keys)} 件（期限 {time.strftime('%H:%M:%S', time.gmtime(args.due))} UTC）", file=sys.stderr)
        return 0
    if args.cmd == "due":
        keys = due_keys(data, now)
        print(f"保留の控え: {len(data['held'])} 件 / 期限が来た: {len(keys)} 件 {' '.join(keys[:5])}".rstrip(), file=sys.stderr)
        print("1" if keys else "0")
        return 0
    if args.cmd == "clear":
        save({"held": {}})
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
