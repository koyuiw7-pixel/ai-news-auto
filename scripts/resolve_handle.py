#!/usr/bin/env python3
"""YouTube のハンドル (@xxx) やチャンネルURLから channel_id を取得するユーティリティ.

使い方:
    python3 scripts/resolve_handle.py @OpenAI @AIatMeta
    python3 scripts/resolve_handle.py https://www.youtube.com/@huggingface

出力された Channel(...) 行を scripts/channels.py に貼り付ける。
"""

from __future__ import annotations

import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
CANONICAL_RE = re.compile(
    r'rel="canonical"\s+href="https://www\.youtube\.com/channel/(UC[A-Za-z0-9_-]{22})"'
)
FEED_TITLE_RE = re.compile(r"<title>([^<]*)</title>")


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def resolve(target: str) -> tuple[str, str] | None:
    """(channel_id, チャンネル名) を返す。失敗時は None。"""
    if target.startswith("UC") and len(target) == 24:
        channel_id = target
    else:
        url = target if target.startswith("http") else f"https://www.youtube.com/{target}"
        match = CANONICAL_RE.search(_fetch(url))
        if not match:
            return None
        channel_id = match.group(1)

    feed = _fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
    title_match = FEED_TITLE_RE.search(feed)
    return channel_id, (title_match.group(1) if title_match else "")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1

    exit_code = 0
    for target in argv:
        try:
            result = resolve(target)
        except Exception as error:  # noqa: BLE001 - CLI なのでまとめて表示
            print(f"[NG] {target}: {error}", file=sys.stderr)
            exit_code = 1
            continue

        if result is None:
            print(f"[NG] {target}: channel_id を抽出できませんでした", file=sys.stderr)
            exit_code = 1
            continue

        channel_id, name = result
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "channel"
        print(f'    Channel(slug="{slug}", name="{name}", channel_id="{channel_id}"),')

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
