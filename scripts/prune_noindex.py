#!/usr/bin/env python3
"""読まれていない記事を検索から外す一覧（content/noindex_pruned.json）を作り直す（2026-11-28 オーナー承認「根本の見直し」の3）。

記事は消さない。公開したまま・一覧や内部リンクからは読める。検索に出さない（robots noindex・サイトマップ・
ニュース用サイトマップ・IndexNow から外れる）だけ。広告は今までどおり出す（14日間訪問0の一覧 noindex_zero_visit.json とは別）。
元に戻すときは slug を一覧から消すだけ（または記事 JSON に "indexable": true）。

一覧に入れる記事（どちらか）:
  A. 作ってから14日以上たち、窓の間（既定35日）に外からの訪問が0
  B. 作ってから14日以上たった AI・テック・スポーツ・エンタメの記事（新しい軸の外）で、外からの訪問が1以下
外からの訪問 = 自前の計測（/api/aff/inflow、実ブラウザで外から来た入口）のうち、直接・不明（direct）を除いたもの。
  --extra で、計測が始まる前（11/2 まで）の Cloudflare の計測（slug → 回数の JSON）を足せる。
入れない記事:
  - 作って14日たっていない記事（新しく公開した記事はすぐには外さない）
  - 検索・AI の回答から来た訪問が1回でもある記事
  - Search Console の表示・クリックがあった記事（content/search_protected.json・search_positions.json・search_impressions90.json・
    noindex_short_exempt.json）
  - まとめ（type: roundup）・比較や選び方の記事（kind あり）・手で検索の扱いを決めた記事（indexable）
  - サイトが目立つ所からリンクしているお金のページ（lib/・app/・components/・content/guides・content/howto・
    content/money-dates.json・content/evergreen_plan.json・content/next_steps.json に slug が書いてある記事）
  - 14日間訪問0の一覧（noindex_zero_visit.json）に既にある記事（そちらで外れている）
--write では、前の一覧にあって今回は訪問・検索の表示が出た記事を一覧から外す（戻す）。

  python3 scripts/prune_noindex.py                       # 候補の数だけ表示
  python3 scripts/prune_noindex.py --write               # content/noindex_pruned.json と data/noindex_pruned_<日付>.csv を書く
  python3 scripts/prune_noindex.py --write --extra cf.json

鍵 AFF_STATS_TOKEN は環境変数か .env.local から読む（scripts/aff_stats.py と同じ）。
数か月に1度、手で動かす（自動の定期実行には入れていない。外す本数が大きく変わるときはオーナーに確認する）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

ARTICLES = ROOT / "content" / "articles"
OUT = ROOT / "content" / "noindex_pruned.json"
JST = timezone(timedelta(hours=9))
CSV_OUT = ROOT / "data" / f"noindex_pruned_{datetime.now(JST):%Y%m%d}.csv"
MIN_AGE_DAYS = 14
OFF_AXIS_GENRES = {"ai", "tech-gadget", "sports", "entertainment"}
SEARCH_SOURCES = {"google", "yahoo", "bing", "discover", "news", "chatgpt", "perplexity", "copilot", "gemini", "claude",
                  "meta_ai", "deepseek", "grok"}
# 以前に「検索に出す」と決めて印を外した記事（tests/test_guide_not_duplicate_20261110.py の UNMARKED）。一覧に入れない
KEEP = {"docomo-data-leak-what-to-do", "docomo-data-leak-family-lines", "google-ai-news-october-2026",
        "microsoft-foundry-agent-framework-customization"}
LINK_SOURCES = ["lib", "app", "components", "content/guides", "content/howto", "content/money-dates.json",
                "content/evergreen_plan.json", "content/next_steps.json"]


def made_at(record: dict) -> datetime | None:
    for key in ("generatedAt", "publishedAt"):
        value = record.get(key)
        if value:
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def search_signal_slugs() -> set[str]:
    from search_protected import IMPRESSIONS90, protected_slugs  # noqa: PLC0415
    slugs = set(protected_slugs(impressions90=IMPRESSIONS90))
    exempt = json.loads((ROOT / "content" / "noindex_short_exempt.json").read_text("utf-8")).get("slugs") or []
    return slugs | set(exempt)


def linked_text() -> str:
    parts = []
    for rel in LINK_SOURCES:
        path = ROOT / rel
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file() and p.suffix in (".ts", ".tsx", ".json", ".md", ".mjs")]
        for file in files:
            try:
                parts.append(file.read_text("utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(parts)


def fetch_visits(days: list[date]) -> tuple[Counter, Counter, int]:
    """slug → 外からの訪問（direct を除く）、slug → 検索・AI からの訪問、計測があった日数"""
    from aff_stats import load_token  # noqa: PLC0415
    from inflow_report import fetch  # noqa: PLC0415
    token = load_token()
    if not token:
        raise SystemExit("AFF_STATS_TOKEN が無いので数えられません")
    outside: Counter = Counter()
    search: Counter = Counter()
    measured = 0
    for day in days:
        rows = fetch(token, day.isoformat()).get("rows") or []
        if rows:
            measured += 1
        for row in rows:
            page = str(row.get("page") or "")
            source = str(row.get("source") or "")
            n = int(row.get("views") or 0)
            if "--" in page or source == "direct":
                continue
            outside[page] += n
            if source in SEARCH_SOURCES:
                search[page] += n
    return outside, search, measured


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=35)
    parser.add_argument("--extra", help="計測の前の期間の訪問（{slug: 回数} または {slug: {outside, search}} の JSON）")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    today = datetime.now(JST).date()
    days = [today - timedelta(days=i) for i in range(args.days, -1, -1)]
    outside, search, measured = fetch_visits(days)
    if args.extra:
        for slug, value in json.loads(Path(args.extra).read_text("utf-8")).items():
            if isinstance(value, dict):
                outside[slug] += int(value.get("outside") or 0)
                search[slug] += int(value.get("search") or 0)
            else:
                outside[slug] += int(value)

    cutoff = datetime.now(JST) - timedelta(days=MIN_AGE_DAYS)
    signals = search_signal_slugs()
    links = linked_text()
    zero_visit = set(json.loads((ROOT / "content" / "noindex_zero_visit.json").read_text("utf-8")).get("slugs") or [])
    previous = set()
    if OUT.exists():
        previous = set(json.loads(OUT.read_text("utf-8")).get("slugs") or [])

    rows = []
    skipped: Counter = Counter()
    for path in sorted(ARTICLES.glob("*.json")):
        record = json.loads(path.read_text("utf-8"))
        slug = record.get("slug") or path.stem
        genre = record.get("genreSlug") or ""
        made = made_at(record)
        visits = outside.get(slug, 0)
        if made is None or made > cutoff:
            skipped["young"] += 1
            continue
        if record.get("type") == "roundup" or record.get("kind") or isinstance(record.get("indexable"), bool):
            skipped["roundup/kind/manual"] += 1
            continue
        if search.get(slug, 0) > 0 or slug in signals:
            skipped["search-signal"] += 1
            continue
        if re.search(rf"(?<![a-z0-9-]){re.escape(slug)}(?![a-z0-9-])", links):
            skipped["linked-money-page"] += 1
            continue
        if slug in KEEP:
            skipped["keep"] += 1
            continue
        if slug in zero_visit:
            skipped["already-zero-visit"] += 1
            continue
        if visits == 0:
            rule = "zero-visit-35d"
        elif genre in OFF_AXIS_GENRES and visits <= 1:
            rule = "off-axis-le1"
        else:
            skipped["has-visits"] += 1
            continue
        rows.append({"slug": slug, "genre": genre, "publishedAt": made.astimezone(JST).isoformat(timespec="minutes"),
                     "visits": visits, "rule": rule})

    by_genre = Counter(r["genre"] for r in rows)
    print(f"計測のあった日 {measured}/{len(days)}。一覧に入れる {len(rows)} 本（前の一覧 {len(previous)} 本）")
    print("ジャンル別:", dict(by_genre.most_common()))
    print("規則別:", dict(Counter(r["rule"] for r in rows)))
    print("入れなかった理由:", dict(skipped))
    restored = sorted(previous - {r["slug"] for r in rows})
    if restored:
        print(f"一覧から外す（戻す） {len(restored)} 本:", ", ".join(restored[:20]))
    if not args.write:
        return 0
    data = {
        "_note": ("2026-11-28 オーナー承認（根本の見直しの3「読まれていない記事を検索から外す」）。記事は消さず公開したまま、"
                  "検索に出さない（robots noindex・サイトマップ・ニュース用サイトマップ・IndexNow から外す）。広告は出す。"
                  "作り直しは scripts/prune_noindex.py --write。元に戻すときは slug を消すだけ。読む所: lib/indexing.ts（noindexReason の pruned）・"
                  "scripts/indexnow.py（noindex_reason）。"),
        "decidedAt": datetime.now(JST).isoformat(timespec="seconds"),
        "window": {"from": days[0].isoformat(), "to": days[-1].isoformat()},
        "minAgeDays": MIN_AGE_DAYS,
        "criteria": "A: 作って14日以上・窓の間に外からの訪問0（直接は数えない）。B: AI・テック・スポーツ・エンタメで14日以上・訪問1以下。"
                    "検索・AIの回答からの訪問、Search Console の表示がある記事、まとめ・比較、目立つ所からリンクしたお金のページは入れない。",
        "slugs": sorted(r["slug"] for r in rows),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["slug", "genre", "publishedAt", "visits", "rule"])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["genre"], r["slug"])))
    print(f"書きました: {OUT.relative_to(ROOT)}・{CSV_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
