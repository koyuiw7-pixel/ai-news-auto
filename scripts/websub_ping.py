#!/usr/bin/env python3
"""公開のあと、RSS が新しくなったことを WebSub のハブ（Google の pubsubhubbub.appspot.com）に知らせる。

Google の検索の説明（サイトマップの作成と送信）には「RSS/Atom を使うなら WebSub で変更を知らせる」とある。
サイトマップは Google が1〜2日に1回しか読みに来ない（11/12 Search Console で確認）ので、新しい記事を早く見つけてもらうため。
フィード自体には <atom:link rel="hub"> を入れてある（app/feed.xml/route.ts・app/feeds/news.xml/route.ts）。

  python3 scripts/websub_ping.py            # 送る（失敗しても終了コード0。結果は標準出力に出す）
  python3 scripts/websub_ping.py --dry-run  # 送らずに中身を出す
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request

HUB = "https://pubsubhubbub.appspot.com/"
SITE = "https://ai-tech-express.jp"
FEEDS = ["/feed.xml", "/feeds/news.xml"]


def build_request(feed_url: str) -> urllib.request.Request:
    body = urllib.parse.urlencode({"hub.mode": "publish", "hub.url": feed_url}).encode()
    return urllib.request.Request(
        HUB,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "saisoku-websub/1.0"},
        method="POST",
    )


def ping(feed_url: str, timeout: float = 20.0) -> int:
    try:
        with urllib.request.urlopen(build_request(feed_url), timeout=timeout) as res:
            return res.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # 通信の失敗で公開を止めない
        print(f"websub: {feed_url} error {e}", file=sys.stderr)
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    for path in FEEDS:
        url = SITE + path
        if a.dry_run:
            print(f"websub: would publish {url} to {HUB}")
            continue
        code = ping(url)
        # ハブは受け付けると 204 を返す
        print(f"websub: {url} -> {code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
