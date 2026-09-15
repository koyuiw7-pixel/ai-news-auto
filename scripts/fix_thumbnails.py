#!/usr/bin/env python3
"""サムネイルの画像切れを検出して直す。

YouTube の高解像度サムネイル（maxresdefault）は、動画側の事情で後から消えることがある。
生成時に存在を確かめていても、数日後に 404 になる場合があるため、定期的に点検できるようにする。

直し方の優先順:
  1. 標準画質（hqdefault）に切り替える
  2. まとめ記事なら、元記事のうち読み込める画像を使う

  python3 scripts/fix_thumbnails.py --dry-run   # 点検だけ
  python3 scripts/fix_thumbnails.py             # 直して保存
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"


def reachable(url: str) -> bool:
    if not url:
        return False
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="点検だけで保存しない")
    args = parser.parse_args()

    paths = sorted(ARTICLES_DIR.glob("*.json"))
    articles = {p: json.loads(p.read_text("utf-8")) for p in paths}
    by_slug = {a["slug"]: a for a in articles.values()}

    with cf.ThreadPoolExecutor(16) as pool:
        status = dict(zip(paths, pool.map(lambda p: reachable(articles[p].get("thumbnail", "")), paths)))

    broken = [p for p in paths if articles[p].get("thumbnail") and not status[p]]
    print(f"[check] {len(paths)} 本中、画像切れ {len(broken)} 本")

    fixed = 0
    blanked = 0
    for path in broken:
        article = articles[path]
        current = article.get("thumbnail", "")
        candidates = []
        if "maxresdefault" in current:
            candidates.append(current.replace("maxresdefault", "hqdefault"))
        if article.get("type") == "roundup":
            for source in article.get("sources", []):
                member = by_slug.get(source.get("slug", ""))
                if member and member.get("thumbnail"):
                    candidates.append(member["thumbnail"])

        replacement = next((url for url in candidates if url != current and reachable(url)), None)
        title = article.get("title", "")[:36]
        if not replacement:
            print(f"  [空欄化] 代わりの画像なし（元動画の削除・非公開と推定） | {title}")
            blanked += 1
            if not args.dry_run:
                article["thumbnail"] = ""
                path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            continue

        print(f"  [OK] {title}\n       {current}\n    →  {replacement}")
        fixed += 1
        if not args.dry_run:
            article["thumbnail"] = replacement
            path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[done] 差し替え {fixed} 本 / 空欄化 {blanked} 本" + ("（--dry-run のため未保存）" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
