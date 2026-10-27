"""
指定した記事を、いますぐ Threads・X・Facebook に出す（臨時の投稿用）。
GitHub Actions の「Post now」から記事の slug と本文を渡して使う。投稿履歴にも記録する。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import threads_post as tp  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--text", required=True, help="Threads・Facebook の本文（X は自動で短くする）")
    args = parser.parse_args()

    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not key:
        raise SystemExit("BUFFER_API_KEY が未設定です")
    path = tp.ARTICLES_DIR / f"{args.slug}.json"
    article = json.loads(path.read_text("utf-8"))
    link = f"{tp.site_url()}/articles/{args.slug}"
    text = args.text.replace("\\n", "\n").strip()

    channels = tp.buffer_channels(key)
    due = datetime.now(timezone.utc) + timedelta(minutes=2)
    result = tp.publish_via_buffer(key, channels["threads"]["id"], text, link, article, due_at=due)
    extra = tp.publish_extra_channels(key, channels, text, link, article, due_at=due)

    state = tp.load_state()
    state["posted"][args.slug] = {
        **result, "dueAt": due.isoformat(timespec="seconds"), "channels": extra, "manual": True,
    }
    tp.save_state(state)
    print(f"[post-now] {args.slug}: threads {result.get('id')} / {extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
