#!/usr/bin/env python3
"""ノワールの記事（layout: "noir"）のうち、表紙に写真を出してよいか（heroOk）が未判定のものを1回だけ判定する（台帳 W36）。

新しい記事は scripts/images.py が公式の写真を付けるときに決める。これは、その仕組みより前に出たノワールの記事の後追い用。
判定は images.hero_ok（無料の画像判定 Workers AI と、名前・形の目安）。迷ったら・判定できないときは False
（公式の写真はそのまま出さず、表紙用の AI のイメージにする。scripts/noir_cover.py）。

  python3 scripts/noir_hero_backfill.py            # 判定だけ表示（書き込まない）
  python3 scripts/noir_hero_backfill.py --apply    # 記事 JSON に heroOk を書く
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import images  # noqa: E402

ARTICLES = Path(__file__).resolve().parent.parent / "content" / "articles"


def targets() -> list[Path]:
    out = []
    for path in sorted(ARTICLES.glob("*.json")):
        article = json.loads(path.read_text("utf-8"))
        if article.get("layout") == "noir" and "heroOk" not in article:
            out.append(path)
    return out


def decide(article: dict) -> tuple[bool, str]:
    credit = article.get("imageCredit") or {}
    if credit.get("kind") != "official" or not article.get("thumbnail"):
        return False, "公式の写真ではない"
    data, _, _ = images.http_get(article["thumbnail"], timeout=30)
    image = images.open_image(data)
    return images.hero_ok(image, credit.get("imageKind") or "photo", credit.get("original") or article["thumbnail"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    for path in targets():
        article = json.loads(path.read_text("utf-8"))
        try:
            ok, why = decide(article)
        except Exception as error:  # noqa: BLE001 - 取れなければ公式の写真は表紙に出さない
            ok, why = False, f"画像を読めない（{str(error)[:80]}）"
        print(f"{path.stem}: heroOk={ok}（{why}）")
        if args.apply:
            article["heroOk"] = ok
            path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
