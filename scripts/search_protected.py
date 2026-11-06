#!/usr/bin/env python3
"""検索から人が来ている記事を、掃除（取り下げ・削除）から守る（2026-11-06 オーナー決定・台帳 A46）。

11/3 の掃除（価値の低い記事342本・検索に出していない記事112本・お知らせの転載14本）で、Google 検索のクリックがあった記事まで
取り下げてしまい、検索からの流入の約4分の1を失った。これからは、Search Console で直近28日にクリックがある、または表示が多い記事は
取り下げずに書き直す（今の品質の基準に合わせ、同じ URL のまま）。

守る記事の一覧は content/search_protected.json（slug → 直近28日のクリック数・表示回数）。
取り下げの道具（scripts/retire_articles.py のすべての区分・scripts/audit.py）は、この一覧の記事を取り下げない。

一覧の更新のしかた（Search Console）:
  1. 検索パフォーマンス → 期間「過去28日間」→「ページ」タブを開き、エクスポート（CSV）する
  2. /articles/<slug> のうち、クリックが1以上、または表示回数が20以上の記事を content/search_protected.json の "articles" に足す
     （{"clicks": n, "impressions": n, "title": "…"}。"updatedAt" と "window" も直す）
  3. 足した記事が掃除の対象になっていたら、取り下げずに scripts/rewrite_types.py などで書き直す

  python3 scripts/search_protected.py   # 守る記事の一覧と、記事が今あるかを表示
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "content" / "search_protected.json"


def load(path: Path = PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def protected_slugs(path: Path = PATH) -> set[str]:
    """守る記事の slug"""
    return {str(s) for s in (load(path).get("articles") or {})}


def split(slugs, path: Path = PATH) -> tuple[list[str], list[str]]:
    """(取り下げてよい slug, 守るので取り下げない slug)。順番はそのまま"""
    keep = protected_slugs(path)
    allowed = [s for s in slugs if s not in keep]
    refused = [s for s in slugs if s in keep]
    return allowed, refused


def main() -> int:
    data = load()
    articles = data.get("articles") or {}
    print(f"[protected] {len(articles)} 本（{data.get('window', '')}・更新 {data.get('updatedAt', '')}）")
    for slug, row in sorted(articles.items(), key=lambda kv: -int((kv[1] or {}).get("clicks") or 0)):
        live = (ROOT / "content" / "articles" / f"{slug}.json").exists()
        print(f"  {'○' if live else '×'} {slug:55} クリック {row.get('clicks', 0):>3} / 表示 {row.get('impressions', 0):>4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
