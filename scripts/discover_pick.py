#!/usr/bin/env python3
"""Google Discover に向く記事に印を付ける（2026-11-07 夜 オーナー承認・台帳 A57）。

1日（日本時間）に DISCOVER_DAILY_MAX 本（既定 5）まで、今日作った記事のうち次をすべて満たすものに
"discoverCandidate": true を付け、ログに一覧を出す。新しい仕組みは作らない（記事の JSON の欄を1つ足すだけ）。
  ・自前の大きな画像（/img/ の幅 1200px の写真・表紙。scripts/images.py が作る）がある。ロゴだけの画像は外す
  ・題名に数字が1つ以上ある（いつから・いくら・何件）
  ・あおりの言い方（！・？・衝撃・まさか・必見・知らないと損 など）と「｜」が無い
  ・海外の企業向け・開発者向けの発表ではない（一般の読者向け）
  ・検索に出す記事（取り下げ・重複・noindex でない）。「速報ではない」形（late）の記事は外す
並び: 暮らし・お金の種類（scripts/news_mix.py の life_group）→ 品質の点数の高い順。
LLM を使わない・通信しない。
使い方: python3 scripts/discover_pick.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
ARTICLES_DIR = ROOT / "content" / "articles"
JST = timezone(timedelta(hours=9))
DISCOVER_DAILY_MAX = int(os.environ.get("DISCOVER_DAILY_MAX", "5"))
FIELD = "discoverCandidate"

CLICKBAIT_RE = re.compile(r"[!！?？]|衝撃|驚愕|驚き|まさか|ヤバ|やば|必見|絶対|知らないと損|損する|閲覧注意|話題沸騰|ついに|とんでもない|最強|[｜|]")
DIGIT_RE = re.compile(r"\d")
OWN_IMAGE_RE = re.compile(r"/img/[^\s\"']+\.(?:jpe?g|png|webp)", re.I)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or ""))


def _jst_date(value: str):
    try:
        at = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(JST).date()


def has_large_image(article: dict) -> bool:
    """自前の 1200px の画像があるか（scripts/images.py は写真を幅 1200px・表紙を 1200×630 で置く）。ロゴだけの画像は外す"""
    credit = article.get("imageCredit") or {}
    if isinstance(credit, dict) and str(credit.get("kind") or "") == "logo":
        return False
    return any(OWN_IMAGE_RE.search(str(article.get(key) or "")) for key in ("coverImage", "thumbnail"))


def problem(article: dict) -> str | None:
    """Discover の候補にしない理由（候補にしてよければ None）"""
    title = _norm(article.get("title"))
    if not title:
        return "題名が無い"
    if article.get("late") or article.get("type") == "roundup":
        return "速報ではない形・まとめ"
    if article.get("duplicateOf") and article.get("duplicateOf") != article.get("slug"):
        return "重複の記事"
    if not has_large_image(article):
        return "大きな画像が無い"
    if not DIGIT_RE.search(title):
        return "題名に数字が無い"
    if m := CLICKBAIT_RE.search(title):
        return f"あおりの言い方（{m.group(0)}）"
    try:
        import news_mix  # noqa: PLC0415

        if news_mix.classify({"title": article.get("title"), "channelSlug": article.get("channelSlug")}) == "enterprise_dev":
            return "海外の企業向け・開発者向けの発表（一般の読者向けではない）"
    except Exception:  # noqa: BLE001
        pass
    try:
        import indexnow  # noqa: PLC0415 - 検索に出さない記事は外す

        reason = indexnow.noindex_reason(article)
    except Exception:  # noqa: BLE001
        reason = None
    if reason:
        return f"検索に出さない記事（{str(reason)[:40]}）"
    return None


def rank(article: dict) -> tuple:
    try:
        import news_mix  # noqa: PLC0415

        life = (news_mix.classify({"title": article.get("title"), "channelSlug": article.get("channelSlug")}) in news_mix.life_group())
    except Exception:  # noqa: BLE001
        life = False
    return (0 if life else 1, -(article.get("qualityScore") or 0), str(article.get("generatedAt") or ""))


def pick(articles: list[dict], now: datetime | None = None, limit: int = DISCOVER_DAILY_MAX) -> tuple[list[dict], list[dict]]:
    """(今日すでに印のある記事, 今回新しく印を付ける記事)"""
    today = (now or datetime.now(JST)).astimezone(JST).date()
    todays = [a for a in articles if _jst_date(a.get("generatedAt") or "") == today]
    marked = [a for a in todays if a.get(FIELD)]
    room = max(0, limit - len(marked))
    fresh = sorted((a for a in todays if not a.get(FIELD) and problem(a) is None), key=rank)
    return marked, fresh[:room]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    paths = {}
    articles = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            paths[data.get("slug") or path.stem] = path
            articles.append(data)
    marked, new = pick(articles)
    for article in new:
        article[FIELD] = True
        if not args.dry_run:
            path = paths[article.get("slug")]
            path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    chosen = marked + new
    print(f"[discover] 今日の Discover の候補 {len(chosen)} / {DISCOVER_DAILY_MAX} 本"
          + ("（dry-run）" if args.dry_run else "")
          + "".join(f"\n  - {a.get('slug')}: {_norm(a.get('title'))[:60]}" for a in chosen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
