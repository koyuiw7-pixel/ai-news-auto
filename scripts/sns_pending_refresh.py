#!/usr/bin/env python3
"""動画待ちの投稿（state/threads_posted.json の status=awaiting_video）の文面を、今の決まりと今の記事で直す（投稿しない・Buffer を呼ばない）。

2026-11-05 オーナー判断・指摘（台帳 S4・S34・S35）を、もう予約の順番に入っている文面にも当てるため:
  - 「要約すると、」を外す（全部の SNS）
  - 災害・事故・安全の話題は呼びかけ・問いかけ・絵文字を付けない
  - 本当の速報でない記事の【速報】を外す・#AI は AI の話だけ・決まった「詳しくはこちら👇（かんたん版あり）」をやめる
  - 記事が書き直されていれば（アララの 77百万件 → 7,700万件・個人向けの書き出し）、今の記事から作り直す

作り直し（rebuild）は threads_post.rebuild_pending_inputs（枠・リンクの位置の組・utm・SNS ごとの時刻のずれはそのまま）。
作り直せなければ、門番の autofix だけ当てる（文は変えずに前置き・数字の単位などを直す）。

  python3 scripts/sns_pending_refresh.py                # 直す前と後を表示するだけ
  python3 scripts/sns_pending_refresh.py --apply        # state/threads_posted.json に書く
  python3 scripts/sns_pending_refresh.py --slug a --slug b --apply
  python3 scripts/sns_pending_refresh.py --autofix-only --apply   # 作り直さず autofix だけ
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sns_rules  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state" / "threads_posted.json"
ARTICLES = ROOT / "content" / "articles"


def awaiting(rec: dict) -> bool:
    return rec.get("status") == "awaiting_video" and bool((rec.get("pending") or {}).get("inputs"))


def texts_of(rec: dict) -> dict[str, str]:
    return {s: str(inp.get("text") or "") for s, inp in ((rec.get("pending") or {}).get("inputs") or {}).items()}


def autofix_record(rec: dict, article: dict | None) -> list[str]:
    """入力ごとに autofix（本文と metadata の thread の1件目）。直したことの一覧"""
    changes: list[str] = []
    for service, inp in ((rec.get("pending") or {}).get("inputs") or {}).items():
        changes += sns_rules.autofix_buffer_input(service, inp, article)
    return list(dict.fromkeys(changes))


def refresh_record(slug: str, rec: dict, article: dict | None, rebuild: bool = True, use_llm: bool = False) -> str:
    """1件を直す。"rebuilt"（今の記事から作り直した）・"autofixed"（autofix だけ）・"" （直すところなし）"""
    if rebuild and article:
        import threads_post as tp  # noqa: PLC0415

        try:
            new = tp.rebuild_pending_inputs(rec, article, use_llm=use_llm)
        except Exception as error:  # noqa: BLE001
            print(f"[refresh] {slug}: 作り直せませんでした（autofix だけ当てます）: {str(error)[:200]}", file=sys.stderr)
        else:
            info = rec.pop("_rebuilt", {}) or {}
            pending = rec["pending"]
            pending["inputs"] = new
            pending["articleHash"] = info.get("articleHash") or tp.article_hash(article)
            if info.get("question"):
                rec["question"], rec["questionText"] = True, info["question"]
            else:
                rec["question"] = False
                for k in ("questionText", "questionPattern"):
                    rec.pop(k, None)
            for key, field in (("summaryLead", "summaryLead"), ("opener", "opener")):
                if info.get(key):
                    rec[field] = info[key]
                else:
                    rec.pop(field, None)
            return "rebuilt"
    return "autofixed" if autofix_record(rec, article) else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="state/threads_posted.json に書く")
    parser.add_argument("--slug", action="append", default=[], help="この記事だけ（くり返し指定できる）")
    parser.add_argument("--autofix-only", action="store_true", help="作り直さず autofix だけ")
    parser.add_argument("--state", default=str(STATE_PATH))
    args = parser.parse_args(argv)
    path = Path(args.state)
    state = json.loads(path.read_text("utf-8"))
    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    changed = 0
    for slug, rec in (state.get("posted") or {}).items():
        if not awaiting(rec) or (args.slug and slug not in args.slug):
            continue
        art_path = ARTICLES / f"{slug}.json"
        article = json.loads(art_path.read_text("utf-8")) if art_path.exists() else None
        before = texts_of(rec)
        how = refresh_record(slug, rec, article, rebuild=not args.autofix_only, use_llm=use_llm)
        after = texts_of(rec)
        if not how or before == after:
            print(f"[refresh] {slug}: 直すところはありません")
            continue
        changed += 1
        print(f"===== {slug}（{how}）")
        for service in after:
            print(f"--- {service} 前:\n{before.get(service, '')}\n--- {service} 後:\n{after[service]}\n")
    if args.apply and changed:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"[refresh] {changed} 件を書きました: {path}")
    elif changed:
        print(f"[refresh] {changed} 件（--apply で書きます）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
