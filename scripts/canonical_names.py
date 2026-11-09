#!/usr/bin/env python3
"""新しい製品・機能・制度・イベントの名前ごとに「〜とは」の記事を1本だけにし、ほかの記事から結ぶ（2026-11-09 オーナー承認・台帳 A68）。

Search Console（2026-10-20〜11-07）で3位以内に入った検索語は、ほぼすべてが新しい名前そのもの（「ワークiq」「jev type」など）で、
1位の記事は題名の先頭近くにその名前があり、最初の1文で「何か」に答えていた。そこで:

  1. 「〜とは」の記事（scripts/story.py の page_role が about）を、名前ごとに1本だけ「代表」にする（いちばん先に載せた記事）。
     同じ名前の「とは」の記事が後から出たら、新しく増やさずに代表へまとめる（duplicateOf を付ける。サイトは noindex・canonical を代表へ）。
     新しいニュースは、ふつうのニュースの記事として出してよい（役割が違うので重複にしない）。代表へは本文のリンクで結ぶ。
  2. 「とは」の記事の決まり: 名前を題名の最初の20字以内と、本文の最初の1文に入れる（about_problems。記事を書く指示は
     scripts/headline_normalize.py の TITLE_STYLE_PROMPT）。
  3. ほかの記事の本文で、その名前が最初に出てくる1か所を、代表の記事へのリンクにする（link_first_mention。見出し・表・すでにある
     リンクの中・URL は避ける。1本の記事に足すのは1回に3つまで）。Google はサイトの中の大事なページへの本文のリンクを勧めている。

名前は記事の canonicalName（手で決めた名前）か、題名の「とは」の前の言葉（かっこの中は別名。「AのB」は B）から取る。
短すぎる名前（英字2字以下・日本語2字以下）は、別の語の一部に当たりやすいので使わない。
英字4字以下の短い名前（PLE・Jev など）は、別の物の略称と重なりやすいので、リンクする記事に代表の題名のほかの名前
（Gemma・TypeSafe など）も出てくるときだけ結ぶ（context_ok）。

  python3 scripts/canonical_names.py list                 # 名前と代表の記事の一覧
  python3 scripts/canonical_names.py link --days 7        # 直近7日に載せた記事にリンクを足す（0=全記事）
  python3 scripts/canonical_names.py link --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
TITLE_HEAD = 20  # 名前は題名の最初の20字以内に
LINKS_PER_RUN = 3
NAME_BEFORE_TOWA = re.compile(r"^(.{1,40}?)とは")
PAREN = re.compile(r"[（(]([^）)]{2,30})[）)]")


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or ""))


def usable(name: str) -> bool:
    name = name.strip()
    if name.isascii():
        return len(re.sub(r"[^A-Za-z0-9]", "", name)) >= 3
    return len(name) >= 3


def names_of(article: dict) -> list[str]:
    """「とは」の記事が答える名前（先頭が主な名前。あとは別名）。とはの記事でなければ空"""
    title = _nfkc(article.get("title"))
    if story.page_role(title) != "about":
        return []
    out: list[str] = []
    if article.get("canonicalName"):
        out.append(_nfkc(article["canonicalName"]).strip())
    m = NAME_BEFORE_TOWA.search(title)
    if m:
        head = m.group(1).strip("「」 　")
        aliases = [a.strip() for a in PAREN.findall(head)]
        bare = PAREN.sub("", head).strip("「」 　")
        main = bare.rsplit("の", 1)[-1].strip("「」 　") if "の" in bare else bare
        for n in [main, *aliases]:
            if n and n not in out:
                out.append(n)
    return [n for n in out if usable(n)]


def first_sentence(body: str) -> str:
    """本文の最初の1文（見出し・空行・引用を飛ばした最初の段落の、最初の「。」まで）"""
    for line in str(body or "").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", ">", "|", "-", "*", "!", "<")):
            continue
        return s.split("。", 1)[0] + ("。" if "。" in s else "")
    return ""


def _has(text: str, name: str) -> bool:
    return _pattern(name).search(_nfkc(text)) is not None


def about_problems(article: dict) -> list[str]:
    """「とは」の記事の決まり（名前が題名の最初の20字以内・本文の最初の1文にある）に合わないところ"""
    names = names_of(article)
    if not names:
        return []
    name = names[0]
    out = []
    if not _has(_nfkc(article.get("title"))[:TITLE_HEAD], name):
        out.append(f"名前「{name}」が題名の最初の{TITLE_HEAD}字に無い")
    if not any(_has(first_sentence(article.get("body") or ""), n) for n in names):
        out.append(f"名前「{name}」が本文の最初の1文に無い")
    return out


def _time(a: dict) -> str:
    return str(a.get("publishedAt") or a.get("generatedAt") or "")


def index(articles: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """({名前: 代表の slug}, {同じ名前の後の「とは」の記事: 代表の slug})。重複の印の記事・まとめ記事は代表にしない"""
    canon: dict[str, str] = {}
    later: dict[str, str] = {}
    for a in sorted(articles, key=_time):
        if a.get("duplicateOf") or a.get("type") == "roundup":
            continue
        names = names_of(a)
        if not names:
            continue
        key = names[0].lower()
        if key in canon and canon[key] != a["slug"]:
            later[a["slug"]] = canon[key]
            continue
        for n in names:
            canon.setdefault(n.lower(), a["slug"])
    return canon, later


def _pattern(name: str) -> re.Pattern:
    esc = re.escape(_nfkc(name)).replace(r"\ ", r"\s?")
    if name.isascii():
        return re.compile(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])", re.I)
    return re.compile(esc)


# リンクを足さない部分: 見出し・表・引用・コード・すでにあるリンク・URL・太字の中
SKIP_LINE = re.compile(r"^\s*(?:#|\||>|```|<)")
PROTECTED_SPAN = re.compile(r"\[[^\]]*\]\([^)]*\)|`[^`]*`|https?://\S+|\*\*[^*]+\*\*|<[^>]+>")


def link_first_mention(body: str, name: str, slug: str) -> str | None:
    """本文で名前が最初に出てくる1か所を [名前](/articles/slug) にした本文。すでに代表へリンクがある・名前が無ければ None"""
    if f"/articles/{slug}" in body:
        return None
    pattern = _pattern(name)
    lines = body.split("\n")
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or SKIP_LINE.match(line):
            continue
        norm = _nfkc(line)
        if len(norm) != len(line):
            continue  # 全角の英字などで位置がずれる行は触らない（次の行で探す）
        blocked = [m.span() for m in PROTECTED_SPAN.finditer(line)]
        for m in pattern.finditer(line):
            if any(a <= m.start() < b for a, b in blocked):
                continue
            lines[i] = f"{line[:m.start()]}[{line[m.start():m.end()]}](/articles/{slug}){line[m.end():]}"
            return "\n".join(lines)
    return None


def load_all() -> list[tuple[Path, dict]]:
    rows = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("slug"):
            rows.append((path, data))
    return rows


def context_words(article: dict, name: str) -> list[str]:
    """代表の題名にある、名前のほかの英字の固有名詞（短い名前が同じ物を指しているかの手がかり）"""
    import search_protected  # noqa: PLC0415

    return [w for w in search_protected.main_names(article.get("title", "")) if w.isascii() and w.lower() != name.lower()]


def context_ok(text: str, name: str, canonical: dict) -> bool:
    if not name.isascii() or len(re.sub(r"[^A-Za-z0-9]", "", name)) > 4:
        return True
    words = context_words(canonical, name)
    hay = _nfkc(text).lower()
    return bool(words) and any(w.lower() in hay for w in words)


def link_all(rows: list[tuple[Path, dict]], since: datetime | None = None, dry_run: bool = False) -> dict[str, list[str]]:
    """代表の記事へのリンクを足す {記事: [足した名前]}。同じ名前の後の「とは」の記事には重複の印を付ける"""
    articles = [d for _, d in rows]
    canon, later = index(articles)
    by_slug = {d["slug"]: d for d in articles}
    added: dict[str, list[str]] = {}
    for path, data in rows:
        changed = False
        if data["slug"] in later and not data.get("duplicateOf"):
            print(f"[canonical] 同じ名前の「とは」の記事は代表へまとめる: {data['slug']} → {later[data['slug']]}")
            data["duplicateOf"] = later[data["slug"]]
            data["duplicateReason"] = "同じ名前の「とは」の記事（代表は1本だけ。台帳 A68）"
            changed = True
        made = story._time(data.get("generatedAt")) or story._time(data.get("publishedAt"))  # noqa: SLF001
        if since is None or (made and made >= since):
            body = str(data.get("body") or "")
            done_targets: set[str] = set()
            for name, target in sorted(canon.items(), key=lambda kv: -len(kv[0])):
                if target == data["slug"] or target in done_targets or len(added.get(data["slug"], [])) >= LINKS_PER_RUN:
                    continue
                if data.get("duplicateOf") == target:
                    continue
                if not context_ok(f"{data.get('title', '')} {body}", name, by_slug.get(target, {})):
                    continue
                new = link_first_mention(body, name, target)
                if new is None:
                    continue
                body = new
                done_targets.add(target)
                added.setdefault(data["slug"], []).append(name)
            if data["slug"] in added:
                data["body"] = body
                changed = True
                print(f"[canonical] {data['slug']}: {'・'.join(added[data['slug']])} → 「とは」の記事へリンク")
        if changed and not dry_run:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    lk = sub.add_parser("link")
    lk.add_argument("--days", type=int, default=7)
    lk.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rows = load_all()
    if args.cmd == "list":
        canon, later = index([d for _, d in rows])
        by_slug = {d["slug"]: d for _, d in rows}
        for name, slug in sorted(canon.items()):
            probs = about_problems(by_slug[slug])
            print(f"{name:30} → {slug}{'  ⚠ ' + ' / '.join(probs) if probs else ''}")
        for slug, keep in later.items():
            print(f"（後の「とは」）{slug} → {keep}")
        return 0
    since = datetime.now(timezone.utc) - timedelta(days=args.days) if args.days else None
    added = link_all(rows, since, args.dry_run)
    print(f"[canonical] リンクを足した記事 {len(added)} 本{'（dry-run）' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
