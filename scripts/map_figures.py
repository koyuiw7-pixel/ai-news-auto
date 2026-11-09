#!/usr/bin/env python3
"""
本文の図（Muse さんなどが作った説明の図）を記事 JSON の figures に付ける（任意の段。無ければ何もしない）。

置き方: public/fig/<slug>-fig1.png（.jpg / .webp も可）、public/fig/<slug>-fig2.png …
  - 画像は /fig/<ファイル名> でそのまま配信される（Next の public。/img/ は Workers KV 専用なので使わない）
  - 説明を付けたいときは同じ名前の .json（public/fig/<slug>-fig1.json）に {"alt": "...", "caption": "...", "after_heading": "見出しの文字"} を置く
  - after_heading が無ければ、n 枚目は本文の n 番目の見出し（##）の後ろに置く
画面では lib/figures.ts が、見出しの章の終わり（次の見出しの手前）に出す。AI の図には「図はイメージ（AI生成）」を付けない
（説明の図は写真と取り違えないため）が、caption に出典・作り手を書く。

  python3 scripts/map_figures.py            # 付ける
  python3 scripts/map_figures.py --dry-run  # 表示だけ
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
FIG_DIR = ROOT / "public" / "fig"
NAME = re.compile(r"^(?P<slug>[a-z0-9][a-z0-9-]*)-fig(?P<n>\d{1,2})\.(?:png|jpe?g|webp)$")


def headings(body: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^##\s+(.+?)\s*$", body or "", re.M)]


def figures_for(slug: str, files: list[Path], body: str) -> list[dict]:
    heads = headings(body)
    out = []
    for path in sorted(files, key=lambda p: int(NAME.match(p.name)["n"])):
        n = int(NAME.match(path.name)["n"])
        meta: dict = {}
        side = path.with_suffix(".json")
        if side.exists():
            try:
                meta = json.loads(side.read_text("utf-8"))
            except ValueError:
                meta = {}
        after = meta.get("after_heading") or (heads[n - 1] if 0 < n <= len(heads) else (heads[-1] if heads else ""))
        out.append({
            "src": f"/fig/{path.name}",
            "alt": str(meta.get("alt") or "").strip(),
            "caption": str(meta.get("caption") or "").strip(),
            "after_heading": after,
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not FIG_DIR.exists():
        return 0
    by_slug: dict[str, list[Path]] = {}
    for path in FIG_DIR.iterdir():
        m = NAME.match(path.name)
        if m:
            by_slug.setdefault(m["slug"], []).append(path)
    changed = 0
    for slug, files in sorted(by_slug.items()):
        art = ARTICLES / f"{slug}.json"
        if not art.exists():
            continue
        data = json.loads(art.read_text("utf-8"))
        figs = figures_for(slug, files, data.get("body", ""))
        if data.get("figures") == figs:
            continue
        print(f"figures: {slug} に {len(figs)} 枚")
        changed += 1
        if not args.dry_run:
            data["figures"] = figs
            art.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"figures: {changed} 本を更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
