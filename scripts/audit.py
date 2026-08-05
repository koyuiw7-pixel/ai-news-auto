#!/usr/bin/env python3
"""公開済み記事をジャンル基準で再判定し、対象外を除去・誤分類を訂正する。

API を一切使わない（無料枠を消費しない）。scripts/topics.py のルールで判定する。
topic_guard を導入する前に生成された記事の掃除に使う。

  python3 scripts/audit.py --dry-run   # 判定結果を表示するだけ
  python3 scripts/audit.py             # 実際に削除・訂正を反映
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from genres import GENRES_BY_SLUG  # noqa: E402
from topics import classify, is_off_topic  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"



def log(message: str) -> None:
    print(message, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="判定するだけで書き換えない")
    args = parser.parse_args()

    files = sorted(ARTICLES_DIR.glob("*.json"))
    if not files:
        log("記事がありません")
        return 0

    rejected: list[tuple[Path, str]] = []
    moved: list[tuple[Path, str, str, str]] = []

    for path in files:
        record = json.loads(path.read_text("utf-8"))
        title = record.get("title", "")
        current = record.get("genreSlug", "")

        if is_off_topic(title, record.get("description", "")):
            rejected.append((path, title))
            continue

        slug, scores = classify(
            title, record.get("description", ""), record.get("body", "")
        )
        # 「現在のジャンルより明確に強い手がかりが出た」場合だけ動かす。
        # 僅差や判定不能はそのままにして、既存の分類を尊重する。
        if slug and slug != current and scores[slug] > scores.get(current, 0):
            target = GENRES_BY_SLUG.get(slug)
            if target:
                moved.append((path, record.get("genre", "?"), target.name, title))
                if not args.dry_run:
                    record["genre"] = target.name
                    record["genreSlug"] = target.slug
                    record["disclaimer"] = target.disclaimer
                    path.write_text(
                        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )

    log("■ 取り下げ（ジャンル外）")
    for _, title in rejected:
        log(f"   ✗ {title[:56]}")

    log("\n■ 再分類")
    for _, before, after, title in moved:
        log(f"   {before} → {after} | {title[:46]}")

    if not args.dry_run:
        for path, _ in rejected:
            path.unlink()
        if rejected:
            log("\n（削除した動画は state.json に処理済みとして残るため、再生成されません）")

    log(
        f"\n[done] 取り下げ {len(rejected)} 本 / 再分類 {len(moved)} 本 / "
        f"据え置き {len(files) - len(rejected) - len(moved)} 本"
        + ("  ※ --dry-run のため未反映" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
