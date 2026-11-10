"""一度だけ: 発表の時刻（sourcePublishedAt・publishedAt）が9時間先にずれた記事を直す（2026-11-10 SEO A5）。

原因: scripts/feeds.py _parse_date が、フィードの「Mon, 09 Nov 2026 17:00:00 JST」（金融庁）と日付だけの「2026-11-10」
（総務省統計局）を UTC として読んでいた（日本時間の17時が、翌日2時に見えていた）。読み方は直したので、今ある記事だけ直す。

直すのは、発信元のフィードで日本時間の書き方だと確かめた記事だけ（2026-11-10 にフィードを取得して確認）:
  - 金融庁 https://www.fsa.go.jp/fsaNewsListAll_rss2.xml … 全項目の pubDate が「… JST」。
    fsa-solvency-regulation-amendment-draft はフィードに「Mon, 09 Nov 2026 17:00:00 JST」とある
  - 総務省統計局 https://www.stat.go.jp/whatsnew/news.rdf … dc:date が日付だけ（joukyou/12.html は「2026-11-10」）
フィードに「+0000」と書かれている記事（Google・Samsung など）や、今のフィードの日付が変わった記事は、
確かめられないので直さない（画面では掲載の時刻で止める。lib/articles.ts announcedAt）。

既定は下見だけ。--apply で書き込む。値が想定どおり（ずれたまま）のときだけ直すので、二度動かしても同じ。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"

# slug → ずれた値（UTC として読んだ日本時間）
CONFIRMED = {
    "fsa-solvency-regulation-amendment-draft": "2026-11-09T17:00:00+00:00",
    "fsa-comment-letter-efrag-esrs40a": "2026-10-30T17:00:00+00:00",
    "fsa-personal-info-leak-consultation": "2026-10-30T18:00:00+00:00",
    "household-consumption-survey-september-2026": "2026-11-10T00:00:00+00:00",
}
SHIFT = timedelta(hours=9)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fix(slug: str, wrong: str) -> tuple[bool, str]:
    path = ARTICLES / f"{slug}.json"
    if not path.exists():
        return False, "記事が無い"
    data = json.loads(path.read_text("utf-8"))
    changed = {}
    right = (_parse(wrong) - SHIFT).astimezone(timezone.utc).isoformat(timespec="seconds")
    for key in ("sourcePublishedAt", "publishedAt"):
        if data.get(key) == wrong:
            changed[key] = right
    if not changed:
        return False, f"直す値が無い（sourcePublishedAt={data.get('sourcePublishedAt')}）"
    generated = data.get("generatedAt")
    if generated and _parse(right) > _parse(generated):
        return False, f"直しても掲載（{generated}）より後になる。手で確かめる"
    data.update(changed)
    return True, json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="書き込む（既定は下見）")
    args = parser.parse_args()
    for slug, wrong in CONFIRMED.items():
        ok, out = fix(slug, wrong)
        if not ok:
            print(f"見送り {slug}: {out}")
            continue
        print(f"{'直した' if args.apply else '直す'} {slug}: {wrong} → {(_parse(wrong) - SHIFT).isoformat()}")
        if args.apply:
            (ARTICLES / f"{slug}.json").write_text(out, "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
