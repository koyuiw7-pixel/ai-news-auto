#!/usr/bin/env python3
"""画像の無い記事の見張り（2026-11-10 オーナー「画像がない記事が結構多いから対策しっかりね」。台帳 I9）。

直近 --hours 時間（既定 24）に公開した記事のうち、読者に見せる画像が何も無い記事を数える。
「画像がある」は、サイトの一覧・表紙が写真を出せること（lib/article-index.mjs の photoOf・lib/noir.ts の noirCover と同じ考え）:
  - 表紙用の AI のイメージ（coverImage・coverCredit.kind = ai。Muse・Workers AI）
  - 記事の写真（thumbnail）。ただし文字だけのカード（imageCredit.kind = card）・公式のロゴ／サイト共通の画像（imageKind logo・generic）・
    ほかの記事のために保存した画像（/img/ の名前がその記事の slug で始まらない）は「無い」と数える
  - 図の表紙（imageCredit.kind = figure・imageKind = cover。scripts/figure_cover.py）は「図」として別に数える（写真ではない）
地震・津波の記事（noPhoto）は写真を付けない決まりなので数えない。まとめ・重複・取り下げも数えない。

  python3 scripts/image_coverage.py                 # 一覧を表示
  python3 scripts/image_coverage.py --issue         # 公開から1時間を過ぎて画像の無い記事があれば issue（ラベル missing-image）に書く／無ければ閉じる
scripts/images.py は回の終わりに summary_line の1行をログに出す。毎時の見張り .github/workflows/broken_images.yml が --issue で呼ぶ。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
LABEL = "missing-image"
NOT_PHOTO_KINDS = ("logo", "generic")
FILLER_PROMPT = re.compile(r"empty exhibition hall|no exhibits", re.I)
SITE = "https://ai-tech-express.jp"


def _when(article: dict) -> datetime | None:
    raw = article.get("publishedAt") or article.get("generatedAt")
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def borrowed(url: str, slug: str) -> bool:
    m = re.search(r"/img/([^/?#]+)$", str(url or "").split("?")[0])
    return bool(m and slug) and not m.group(1).startswith(slug[:120])


def image_state(article: dict) -> str:
    """photo（写真・AI のイメージ）/ figure（図の表紙だけ）/ none（何も無い）/ exempt（地震・津波など数えない）"""
    if article.get("noPhoto") or article.get("type") == "roundup" or article.get("duplicateOf") or article.get("retired") \
            or article.get("draft") or article.get("hidden"):
        return "exempt"
    slug = str(article.get("slug") or "")
    cover = str(article.get("coverImage") or "").strip()
    if cover and (article.get("coverCredit") or {}).get("kind") == "ai":
        return "photo"
    thumb = str(article.get("thumbnail") or "").strip()
    credit = article.get("imageCredit") or {}
    kind = credit.get("kind")
    if not thumb or kind == "card":
        return "none"
    if kind == "official" and credit.get("imageKind") in NOT_PHOTO_KINDS:
        return "none"
    if kind == "ai" and FILLER_PROMPT.search(str(credit.get("prompt") or "")):
        return "none"
    if borrowed(thumb, slug):
        return "none"
    if kind == "figure" and credit.get("imageKind") == "cover":
        return "figure"
    return "photo"


def life_money(article: dict) -> bool:
    """暮らしとお金の記事か（scripts/muse_images.py の優先の段 1・2・3。判定できないときは True）"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import muse_images  # noqa: PLC0415

        return muse_images.priority(article, set()) <= muse_images.TIER_CORE
    except Exception:  # noqa: BLE001
        return True


def scan(articles: Iterable[dict], hours: float = 24, grace_minutes: float = 60, now: datetime | None = None) -> dict:
    """直近 hours 時間の記事の画像の状態。missing は公開から grace_minutes を過ぎて画像の無い記事（新しい順）"""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)
    total = 0
    figure: list[str] = []
    waiting: list[str] = []
    missing: list[dict] = []
    for article in articles:
        when = _when(article)
        if not when or when < since or when > now:
            continue
        state = image_state(article)
        if state == "exempt":
            continue
        total += 1
        if state == "figure":
            figure.append(str(article.get("slug")))
        elif state == "none":
            age = (now - when).total_seconds() / 60
            if age < grace_minutes:
                waiting.append(str(article.get("slug")))
            else:
                missing.append({"slug": str(article.get("slug")), "title": str(article.get("title") or "")[:60],
                                "minutes": round(age), "lifeMoney": life_money(article)})
    missing.sort(key=lambda row: row["minutes"])
    return {"hours": hours, "total": total, "missing": missing, "waiting": waiting, "figure": figure}


def load_articles() -> list[dict]:
    out = []
    for path in ARTICLES.glob("*.json"):
        try:
            out.append(json.loads(path.read_text("utf-8")))
        except (OSError, ValueError):
            continue
    return out


def summary_line(articles: Iterable[dict], now: datetime | None = None, hours: float = 24, grace_minutes: float = 60) -> str:
    found = scan(articles, hours=hours, grace_minutes=grace_minutes, now=now)
    lm = sum(1 for row in found["missing"] if row["lifeMoney"])
    head = (f"[img-cover] 直近{found['hours']:.0f}時間の記事 {found['total']} 本: 画像の無い記事 {len(found['missing'])} 本"
            f"（公開から1時間を過ぎたもの。うち暮らしとお金 {lm} 本）・1時間以内で待ち {len(found['waiting'])} 本・図の表紙 {len(found['figure'])} 本")
    if found["missing"]:
        head += ": " + ", ".join(row["slug"] for row in found["missing"][:12])
    return head


def render_issue(found: dict) -> str:
    lines = [f"直近{found['hours']:.0f}時間に公開した記事のうち、公開から1時間を過ぎても画像（写真・AI のイメージ）が無い記事が "
             f"{len(found['missing'])} 本あります（台帳 I9）。", "",
             "| 記事 | 公開から | 暮らしとお金 |", "|---|---|---|"]
    for row in found["missing"][:60]:
        lines.append(f"| [{row['title'] or row['slug']}]({SITE}/articles/{row['slug']}) | {row['minutes'] // 60}時間{row['minutes'] % 60}分 | "
                     f"{'はい' if row['lifeMoney'] else ''} |")
    lines += ["", "直し方: Auto Article Pipeline の「Article images」（scripts/images.py）が回ごとに暮らしとお金の記事から探し直す。"
              "AI の1日の枚数（IMAGE_AI_DAILY_MAX）が尽きた夜は Muse への依頼（state/muse_images.json）か、Google ドライブの "
              "サイソク連絡/images/<slug>.jpg に置いた写真が入る。見張り: scripts/image_coverage.py（毎時。0本になればこの issue は閉じます）"]
    return "\n".join(lines)


def _gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def write_issue(found: dict) -> None:
    listed = _gh("issue", "list", "--label", LABEL, "--state", "open", "--json", "number", "--limit", "5")
    existing = json.loads(listed.stdout or "[]") if listed.returncode == 0 else []
    if not found["missing"]:
        for item in existing:
            _gh("issue", "close", str(item["number"]), "--comment", "画像の無い記事は無くなりました（scripts/image_coverage.py）。")
        return
    body = render_issue(found)
    if existing:
        _gh("issue", "edit", str(existing[0]["number"]), "--title", f"画像の無い記事があります（{len(found['missing'])}本）", "--body", body)
        return
    _gh("label", "create", LABEL, "--color", "D93F0B", "--description", "公開から1時間を過ぎて画像の無い記事（scripts/image_coverage.py）", "--force")
    _gh("issue", "create", "--title", f"画像の無い記事があります（{len(found['missing'])}本）", "--label", LABEL, "--body", body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--grace-minutes", type=float, default=60)
    parser.add_argument("--issue", action="store_true")
    parser.add_argument("--json", help="結果を書くファイル")
    args = parser.parse_args(argv)
    found = scan(load_articles(), hours=args.hours, grace_minutes=args.grace_minutes)
    print(summary_line(load_articles(), hours=args.hours, grace_minutes=args.grace_minutes))
    for row in found["missing"]:
        print(f"  - {row['slug']}（公開から{row['minutes']}分{'・暮らしとお金' if row['lifeMoney'] else ''}）")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.issue:
        write_issue(found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
