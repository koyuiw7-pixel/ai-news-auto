#!/usr/bin/env python3
"""IndexNow で検索エンジンに更新を通知する。

Google Search Console は所有者のログインが必要で登録が進まないが、
IndexNow はアカウント不要で Bing / DuckDuckGo / Yandex などに直接通知できる。
新規サイトが「発見されない」状態を、こちら側だけで動かせる唯一の手段。

  python3 scripts/indexnow.py --all      # 全記事を送信（初回用）
  python3 scripts/indexnow.py --hours 12 # 直近12時間に生成された記事だけ
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
PUBLIC_DIR = ROOT / "public"
ENDPOINT = "https://api.indexnow.org/indexnow"
MAX_URLS = 10000  # 1リクエストあたりの上限


def site_url() -> str:
    url = os.environ.get("NEXT_PUBLIC_SITE_URL") or "https://ai-tech-express.jp"
    return url.rstrip("/")


def find_key() -> str | None:
    """public/<key>.txt からキーを読む。ファイル名とその中身が一致している必要がある。"""
    for path in PUBLIC_DIR.glob("*.txt"):
        key = path.stem
        if path.read_text().strip() == key:
            return key
    return None


def collect_urls(base: str, hours: int | None) -> list[str]:
    """インデックス対象（AIジャンル）の記事URLを集める。

    noindex にしている記事を送っても意味がないため、対象から外す。
    """
    threshold = (
        datetime.now(timezone.utc) - timedelta(hours=hours) if hours else None
    )
    urls = [base, f"{base}/articles", f"{base}/genres/ai"]

    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            article = json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError:
            continue
        if article.get("genreSlug") != "ai":
            continue
        if threshold:
            try:
                generated = datetime.fromisoformat(article.get("generatedAt", ""))
            except ValueError:
                continue
            if generated < threshold:
                continue
        urls.append(f"{base}/articles/{article['slug']}")

    return urls[:MAX_URLS]


def submit(base: str, key: str, urls: list[str]) -> int:
    payload = {
        "host": base.split("://", 1)[-1],
        "key": key,
        "keyLocation": f"{base}/{key}.txt",
        "urlList": urls,
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="全記事を送信")
    parser.add_argument("--hours", type=int, default=12, help="直近N時間の記事のみ")
    parser.add_argument("--dry-run", action="store_true", help="送信せず対象を表示")
    args = parser.parse_args()

    key = find_key()
    if not key:
        print("[NG] public/<key>.txt が見つかりません", file=sys.stderr)
        return 1

    base = site_url()
    urls = collect_urls(base, None if args.all else args.hours)

    print(f"[info] 送信先ホスト: {base} / 対象 {len(urls)} 件")
    for url in urls[:5]:
        print("   ", url)
    if len(urls) > 5:
        print(f"    …ほか {len(urls) - 5} 件")

    if args.dry_run:
        print("[dry-run] 送信しませんでした")
        return 0
    if len(urls) <= 3:
        print("[skip] 新規URLがないため送信しません")
        return 0

    try:
        status = submit(base, key, urls)
    except Exception as error:  # noqa: BLE001 - 通知失敗で全体を落とさない
        print(f"[NG] 送信失敗: {error}", file=sys.stderr)
        return 0

    print(f"[done] HTTP {status}（200/202 なら受理）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
