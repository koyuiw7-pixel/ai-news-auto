#!/usr/bin/env python3
"""検索された言葉が本文にあるか（SEO A14「検索される言葉を、まず本文に入れる」・2026-11-10）。

content/search_positions.json の各ページの主な検索語を言葉に分け、題名・リード・本文・要点・かんたん版に無い言葉を一覧にする。
本文は書きかえない（足すときは出典で確かめてから。週1回の書き直し scripts/search_refresh.py は「検索された言葉を本文の最初の段落に」と指示する）。
題名（searchTitle・seoTitle）は扱わない（別の作業の受け持ち）。

  python3 scripts/search_words.py --report
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
POSITIONS = ROOT / "content" / "search_positions.json"
# 意味の無い言葉（検索の言い回し）
STOP = {"とは", "は", "の", "を", "で", "に", "が", "と", "はい", "いいえ", "方法", "やり方"}
FIELDS = ("title", "lede", "description", "body", "easy")


def words_of(query: str) -> list[str]:
    out = []
    for w in re.split(r"[\s　]+", (query or "").strip().lower()):
        w = re.sub(r"(とは|って何|って)$", "", w)
        if w and w not in STOP and len(w) >= 2:
            out.append(w)
    return out


def text_of(record: dict) -> str:
    parts = [str(record.get(k) or "") for k in FIELDS] + [str(h) for h in record.get("highlights") or []]
    return " ".join(parts).lower()


def missing_words(record: dict, query: str) -> list[str]:
    text = text_of(record)
    return [w for w in words_of(query) if w not in text]


def report(positions: dict | None = None, articles_dir: Path = ARTICLES) -> list[tuple[str, str, list[str]]]:
    data = positions if positions is not None else json.loads(POSITIONS.read_text("utf-8"))
    out = []
    for slug, row in sorted((data.get("pages") or {}).items()):
        path = articles_dir / f"{slug}.json"
        if not path.exists() or not row.get("query"):
            continue
        miss = missing_words(json.loads(path.read_text("utf-8")), str(row["query"]))
        if miss:
            out.append((slug, str(row["query"]), miss))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if not args.report:
        ap.print_help()
        return 0
    rows = report()
    for slug, query, miss in rows:
        print(f"  {slug}: 「{query}」 本文に無い言葉 {miss}")
    print(f"[search-words] 検索された言葉が本文に無いページ: {len(rows)} 本（本文は書きかえていません）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
