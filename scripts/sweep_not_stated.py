#!/usr/bin/env python3
"""1回だけの掃除（2026-11-10 SEO A4・LLMO-A4。LLM は使わない）: 公開中の記事・ガイドの答えの欄から「書かれていません」を外す。

  python3 scripts/sweep_not_stated.py           # 直す
  python3 scripts/sweep_not_stated.py --dry-run # 数えるだけ

- 記事の「こんな不安ありませんか」（worries）とよくある質問（faq）: 最初の文が「書かれていません」などの問いは外し、
  2文目以降のその文は消す（scripts/nonanswer.py の answer_or_none。言葉は足さない）。不安が2つ未満になったら欄ごと外す
  （画面の lib/depth.ts と同じ。見出し depthHeadings.worries も外す）。
- ガイド（content/howto・guides・buying-guides）のよくある質問: 同じ決まりで外す。使い方ガイド（howto）で外した質問は
  openQuestions に残し、scripts/evergreen.py が次に公式ページを確かめるときに答えを探す（答えは作らない）。
- 記事を消さない。updatedAt・checkedAt は変えない（中身の更新ではなく、答えになっていない文を外しただけ）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nonanswer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
JST = timezone(timedelta(hours=9))


def clean_items(items: list) -> tuple[list, list[str], int]:
    """(残す問い, 外した問い, 文を消した答えの数)"""
    kept, dropped, trimmed = [], [], 0
    for item in items:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        answer = nonanswer.answer_or_none(str(item.get("a") or ""))
        if answer:
            trimmed += answer != item.get("a")
            kept.append(item if answer == item.get("a") else {**item, "a": answer})
        else:
            dropped.append(str(item.get("q") or ""))
    return kept, dropped, trimmed


def sweep_record(kind: str, record: dict, now: str) -> tuple[dict, int, int]:
    """(直した記録, 外した問いの数, 文を消した答えの数)"""
    out = dict(record)
    removed = trimmed = 0
    opened: list[str] = []
    for key in nonanswer.SLOT_DIRS[kind]:
        items = record.get(key)
        if not isinstance(items, list) or not items:
            continue
        kept, dropped, cut = clean_items(items)
        removed += len(dropped)
        trimmed += cut
        if kind == "howto" and key == "faq":
            opened += [q for q in dropped if q]
        if kind == "articles" and key == "worries" and len(kept) < 2:
            out.pop("worries", None)
            heads = dict(out.get("depthHeadings") or {})
            if heads.pop("worries", None) is not None:
                if heads:
                    out["depthHeadings"] = heads
                else:
                    out.pop("depthHeadings", None)
        else:
            out[key] = kept
    if opened:
        have = {o.get("q") for o in out.get("openQuestions") or [] if isinstance(o, dict)}
        out["openQuestions"] = [*(out.get("openQuestions") or []), *({"q": q, "since": now} for q in dict.fromkeys(opened) if q not in have)]
    return out, removed, trimmed


def main() -> int:
    parser = argparse.ArgumentParser(description="答えの欄から「書かれていません」を外す（1回だけ・LLM なし）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    now = datetime.now(JST).isoformat(timespec="seconds")
    total = {"files": 0, "removed": 0, "trimmed": 0}
    for kind in nonanswer.SLOT_DIRS:
        for path in sorted((CONTENT / kind).glob("*.json")):
            raw = path.read_text("utf-8")
            record = json.loads(raw)
            if not isinstance(record, dict):
                continue
            fixed, removed, trimmed = sweep_record(kind, record, now)
            if fixed == record:
                continue
            total["files"] += 1
            total["removed"] += removed
            total["trimmed"] += trimmed
            print(f"{kind}/{path.name}: 外した問い {removed}・文を消した答え {trimmed}")
            if not args.dry_run:
                path.write_text(json.dumps(fixed, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"[sweep] ファイル {total['files']}・外した問い {total['removed']}・文を消した答え {total['trimmed']}"
          + ("（数えただけ）" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
