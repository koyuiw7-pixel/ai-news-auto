#!/usr/bin/env python3
"""検索から人が来ている記事を、掃除（取り下げ・削除）から守る（2026-11-06 オーナー決定・台帳 A46）。

11/3 の掃除（価値の低い記事342本・検索に出していない記事112本・お知らせの転載14本）で、Google 検索のクリックがあった記事まで
取り下げてしまい、検索からの流入の約4分の1を失った。これからは、Search Console で直近28日にクリックがある、または表示が多い記事は
取り下げずに書き直す（今の品質の基準に合わせ、同じ URL のまま）。

守る記事の一覧は content/search_protected.json（slug → 直近28日のクリック数・表示回数）。
取り下げの道具（scripts/retire_articles.py のすべての区分・scripts/audit.py）は、この一覧の記事を取り下げない。

一覧の更新のしかた（Search Console）:
  1. 検索パフォーマンス → 期間「過去28日間」→「ページ」タブを開き、エクスポート（CSV）する
  2. /articles/<slug> のうち、クリックが1以上、または表示回数が20以上の記事を content/search_protected.json の "articles" に足す
     （{"clicks": n, "impressions": n, "title": "…"}。"updatedAt" と "window" も直す）
  3. 足した記事が掃除の対象になっていたら、取り下げずに scripts/rewrite_types.py などで書き直す

  python3 scripts/search_protected.py   # 守る記事の一覧と、記事が今あるかを表示

2026-11-12（案B・オーナー承認）: content/search_impressions90.json（Search Console「ページ」過去3か月で表示が1回以上の記事）も守る。

2026-11-09 オーナー承認（台帳 A68）: 検索に表示が1回でもあったページは取り下げない・転送しない。
  - 守る記事は content/search_protected.json に加えて、content/search_positions.json（Search Console の「ページ」と「検索語」を
    書き写した一覧。scripts/search_refresh.py が毎週の書き直しにも使う）で表示が1以上の記事すべて。
  - 転送（301）するときは、転送先の記事に、元の記事の主な名前（題名の英字の固有名詞・「」の名前・検索語）がすべて入っていること
    （redirect_ok）。入っていなければ転送せず 410 にする（11/3 に「excel クローン」8位の記事を Excel の話が無い記事へ転送していた）。
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "content" / "search_protected.json"
POSITIONS = ROOT / "content" / "search_positions.json"
# Search Console「ページ」過去3か月で表示が1回以上あった記事（2026-11-12 書き出し。案Bの前に作った守りの一覧）
IMPRESSIONS90 = ROOT / "content" / "search_impressions90.json"
# 名前の照合で数えない、どこにでも出てくる語（会社名・一般語）。これだけでは「同じ疑問のページ」とは言えない
COMMON_WORDS = {
    "ai", "the", "and", "for", "with", "new", "api", "app", "pro", "max", "mini", "plus", "beta", "google", "openai",
    "microsoft", "nvidia", "apple", "amazon", "meta", "anthropic", "aws", "gpt", "llm", "ceo", "day", "news", "inc",
}


def load(path: Path = PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_positions(path: Path = POSITIONS) -> dict:
    """Search Console の順位の一覧 {"pages": {slug: {"impressions", "clicks", "position", "query"}}}"""
    return load(path)


def positions_pages(path: Path = POSITIONS) -> dict[str, dict]:
    pages = load_positions(path).get("pages") or {}
    return {str(k): v for k, v in pages.items() if isinstance(v, dict)}


def protected_slugs(path: Path = PATH, positions: Path = POSITIONS, impressions90: Path | None = None) -> set[str]:
    """守る記事の slug（守る一覧 ＋ 検索に表示が1回でもあった記事 ＋ 過去3か月に表示があった記事。台帳 A46・A68）"""
    keep = {str(s) for s in (load(path).get("articles") or {})}
    keep |= {slug for slug, row in positions_pages(positions).items() if int(row.get("impressions") or 0) >= 1}
    # 既定の一覧を見るときだけ、3か月の一覧も足す（テストが別の一覧を渡したときは混ぜない）
    if impressions90 is None and path == PATH:
        impressions90 = IMPRESSIONS90
    if impressions90 is not None:
        keep |= {str(s) for s in (load(impressions90).get("articles") or [])}
    return keep


def query_of(slug: str, path: Path = PATH, positions: Path = POSITIONS) -> str:
    """その記事が表示された主な検索語（分かっていれば）"""
    row = (load(path).get("articles") or {}).get(slug) or {}
    return str(row.get("query") or positions_pages(positions).get(slug, {}).get("query") or "")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text or "")).lower())


def main_names(title: str, query: str = "") -> list[str]:
    """元の記事の主な名前（転送先にも入っているべき語）: 題名の「」の名前・英字の固有名詞（会社名・一般語は除く）・検索語の英字の語"""
    t = unicodedata.normalize("NFKC", str(title or ""))
    names: list[str] = []
    for q in re.findall(r"「([^」]{2,40})」", t):
        # 「レイヤー別埋め込み（PLE）」は「レイヤー別埋め込み」と「PLE」に分ける（言い方の順が違っても同じ名前）
        for part in re.split(r"[()（）・/\s]+", q):
            if len(part) >= 2 and part.lower() not in COMMON_WORDS and part not in names:
                names.append(part)
    for src in (t, unicodedata.normalize("NFKC", query or "")):
        for w in re.findall(r"[A-Za-z][A-Za-z0-9.\-]{2,}", src):
            if w.lower() not in COMMON_WORDS and w not in names:
                names.append(w)
    return names


def redirect_ok(title: str, target: dict, query: str = "") -> tuple[bool, list[str]]:
    """転送先の記事（題名・本文・キーワード・タグ）に、元の記事の主な名前がすべて入っているか。(よいか, 足りない名前)"""
    hay = _norm(" ".join([str(target.get("title") or ""), str(target.get("seoTitle") or ""), str(target.get("body") or ""),
                          " ".join(target.get("keywords") or []), " ".join(target.get("tags") or [])]))
    missing = [n for n in main_names(title, query) if _norm(n) not in hay]
    return (not missing and bool(hay)), missing


def split(slugs, path: Path = PATH) -> tuple[list[str], list[str]]:
    """(取り下げてよい slug, 守るので取り下げない slug)。順番はそのまま"""
    keep = protected_slugs(path)
    allowed = [s for s in slugs if s not in keep]
    refused = [s for s in slugs if s in keep]
    return allowed, refused


def main() -> int:
    data = load()
    articles = data.get("articles") or {}
    print(f"[protected] {len(articles)} 本（{data.get('window', '')}・更新 {data.get('updatedAt', '')}）")
    for slug, row in sorted(articles.items(), key=lambda kv: -int((kv[1] or {}).get("clicks") or 0)):
        live = (ROOT / "content" / "articles" / f"{slug}.json").exists()
        print(f"  {'○' if live else '×'} {slug:55} クリック {row.get('clicks', 0):>3} / 表示 {row.get('impressions', 0):>4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
