#!/usr/bin/env python3
"""記事の読者が読む欄から、表示されない太字の記号（** と __）を取る（2026-11-27）。

2026-11-27、Muse の原稿から作ったガソリン補助の記事（fuel-subsidy-december-price-threshold）の本文に
「**」だけの段落が残り、本番で生の「**」が読者に見えた（UI check が公開のあとで見つけた）。

サイトが太字として出せる形だけを残し、ほかは記号を消す（文字はそのまま）:
- 本文 body・かんたん版 easy（lib/markdown.ts の marked で出す）: 1行の中で対になった「**…**」は太字として残す。
  対にならない「**」（「**」だけの行・閉じていない「**」）は消す。「__…__」は「**…**」に直す（日本語の中の __ は太字にならない）。
- 要点の1文 summaryLine（components/noir/NoirArticle.tsx の splitEmphasis が最初の1組だけ太字にする）:
  最初の1組だけ残し、ほかの記号は消す。
- ほかの読者の欄（題名・リード・説明・要点・FAQ・今日やること・仕事とお金・ノワールの欄・SNS の文）: 太字にならないので記号を全部消す。

消さないもの: 伏せ字（「C05-*****-******1」。3つ以上並んだ「*」は触らない）、URL・コード（`…`）の中、`__init__` のような英数字の語。
すべての経路の記事は scripts/main.py の write_article で書き出す前にここを通る（Muse の記事も、ふつうの記事も）。続報の書き足しも同じ。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MARKDOWN_FIELDS = ("body", "easy")
EMPHASIS_FIELDS = ("summaryLine",)
PLAIN_FIELDS = ("title", "seoTitle", "searchTitle", "lede", "description", "threadsPost", "threadsHook", "shortTitle")

# ちょうど2つの「*」（前後が「*」でない）。伏せ字の「*****」は数えない
STAR2 = r"(?<!\*)\*\*(?!\*)"
PAIR_RE = re.compile(rf"{STAR2}(?=\S)(.+?)(?<=\S){STAR2}")
LONE_STAR_RE = re.compile(STAR2)
# 日本語を含む「__…__」（英数字の語 __init__ は触らない）
UNDER_PAIR_RE = re.compile(r"(?<![A-Za-z0-9_])__(?!_)(?=\S)([^_\n]*?[^\x00-\x7f][^_\n]*?)(?<=\S)(?<!_)__(?![A-Za-z0-9_])")
# 前後が英数字・「_」でない、ちょうど2つの「_」（対にならない残り）
LONE_UNDER_RE = re.compile(r"(?<![A-Za-z0-9_])__(?![A-Za-z0-9_])")
# 記号だけの行（「**」「__」「** **」）。3つ以上の「*」・「---」の区切り線は残す
MARKER_ONLY_LINE = re.compile(r"^[ \t]*(?:(?:\*\*|__)[ \t]*)+$")
# 触らない所: `…`・URL・Markdown のリンク先
PROTECT_RE = re.compile(r"`[^`\n]*`|https?://[^\s)\]>]+|\]\([^)\n]*\)")


def _protect(text: str) -> tuple[str, list[str]]:
    kept: list[str] = []

    def hold(m: re.Match) -> str:
        kept.append(m.group(0))
        return f"\x00{len(kept) - 1}\x00"

    return PROTECT_RE.sub(hold, text), kept


def _restore(text: str, kept: list[str]) -> str:
    return re.sub(r"\x00(\d+)\x00", lambda m: kept[int(m.group(1))], text)


def _strip_all(line: str) -> str:
    line = UNDER_PAIR_RE.sub(r"\1", line)
    line = LONE_UNDER_RE.sub("", line)
    return LONE_STAR_RE.sub("", line)


def clean_markdown(text: str) -> str:
    """本文・かんたん版: 1行の中で対になった **…** は残し、対にならない記号を消す"""
    out: list[str] = []
    fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
            out.append(line)
            continue
        if fence:
            out.append(line)
            continue
        if MARKER_ONLY_LINE.match(line):
            out.append("")  # 段落の区切りは残す（あとで空行の重なりをまとめる）
            continue
        masked, kept = _protect(line)
        masked = UNDER_PAIR_RE.sub(r"**\1**", masked)
        pairs: list[str] = []

        def hold_pair(m: re.Match) -> str:
            pairs.append(m.group(0))
            return f"\x01{len(pairs) - 1}\x01"

        masked = PAIR_RE.sub(hold_pair, masked)
        masked = LONE_UNDER_RE.sub("", LONE_STAR_RE.sub("", masked))
        masked = re.sub(r"\x01(\d+)\x01", lambda m: pairs[int(m.group(1))], masked)
        out.append(_restore(masked, kept))
    joined = "\n".join(out)
    if joined == text:
        return text
    return re.sub(r"\n{3,}", "\n\n", joined).strip("\n")


def clean_emphasis(text: str) -> str:
    """要点の1文: 最初の1組の **…** だけ残す（サイトの splitEmphasis と同じ）"""
    masked, kept = _protect(text)
    masked = UNDER_PAIR_RE.sub(r"**\1**", masked)
    m = PAIR_RE.search(masked)
    if m:
        masked = _strip_all(masked[: m.start()]) + m.group(0) + _strip_all(masked[m.end():])
    else:
        masked = _strip_all(masked)
    return _restore(masked, kept)


def clean_plain(text: str) -> str:
    """太字にならない欄: 記号を全部消す"""
    masked, kept = _protect(text)
    return _restore(_strip_all(masked), kept)


def _apply_list(record: dict, key: str, sub: str | None, fn, changes: list[str]) -> None:
    items = record.get(key)
    if not isinstance(items, list):
        return
    for i, item in enumerate(items):
        if sub is None and isinstance(item, str):
            if (new := fn(item)) != item:
                items[i] = new
                changes.append(f"{key}[{i}]")
        elif sub and isinstance(item, dict):
            v = item.get(sub)
            if isinstance(v, str) and (new := fn(v)) != v:
                item[sub] = new
                changes.append(f"{key}[{i}].{sub}")


PLAIN_LISTS = (("highlights", None), ("todayActions", None), ("faq", "q"), ("faq", "a"),
               ("changes", "label"), ("changes", "before"), ("changes", "after"), ("changes", "note"),
               ("wrapUp", "name"), ("wrapUp", "text"))


def apply(record: dict) -> list[str]:
    """記事の JSON の読者の欄を直す。直した欄の名前の一覧を返す（何も無ければ空）"""
    changes: list[str] = []
    for fields, fn in ((MARKDOWN_FIELDS, clean_markdown), (EMPHASIS_FIELDS, clean_emphasis), (PLAIN_FIELDS, clean_plain)):
        for key in fields:
            v = record.get(key)
            if isinstance(v, str) and (new := fn(v)) != v:
                record[key] = new
                changes.append(key)
    for key, sub in PLAIN_LISTS:
        _apply_list(record, key, sub, clean_plain, changes)
    wm = record.get("workMoney")
    if isinstance(wm, dict):
        _apply_list(wm, "points", None, clean_plain, changes)
    kf = record.get("keyFigure")
    if isinstance(kf, dict):
        for k in ("value", "unit", "label", "before"):
            if isinstance(kf.get(k), str) and (new := clean_plain(kf[k])) != kf[k]:
                kf[k] = new
                changes.append(f"keyFigure.{k}")
    return [f"太字の記号を直した: {c}" for c in changes]


def main(argv: list[str]) -> int:
    """今ある記事を点検する。--apply で直して書き戻す"""
    import json  # noqa: PLC0415

    write = "--apply" in argv
    root = Path(__file__).resolve().parent.parent / "content" / "articles"
    hits = 0
    for path in sorted(root.glob("*.json")):
        record = json.loads(path.read_text("utf-8"))
        changes = apply(record)
        if changes:
            hits += 1
            print(f"{path.name}: {', '.join(c.split(': ', 1)[1] for c in changes)}")
            if write:
                path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{'直した' if write else '直すべき'}記事: {hits} 本")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
