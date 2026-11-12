#!/usr/bin/env python3
"""AI が書いた文に付いた「（編集部注）」などの札を、その文ごと消す（2026-11-12。AdSense 監査・事実だけの決まり）。

人（編集部）が書いていない文に「編集部注」「編集部の見立て」と付けるのは、うその表示になる。しかもその文は、
元の発表に無い一般の知識や比較（動画の要約の「競合サービスとの比較」の表など）を AI が足したもの。だから札だけを外さず、
札の付いた中身を消す（元の資料に無い事実は書かない）。

消し方（本文 body・かんたん版 easy）:
  1. 見出しが「比較・競合・ライバル・他の選択肢」の章で、札があるもの → 章ごと消す（比べた相手の情報は元の資料に無い）
  2. 表: 見出しの行に札がある列 → 列ごと消す。札がある行 → 行を消す。残りが1列以下・中身の行が無い表 → 表ごと消す
  3. 「（編集部注：…）」のような、札で始まるかっこ → かっこごと消す（前後の文は元の資料の事実なので残す）
  4. 札だけのかっこ「…です（編集部注）。」・札のある文 → 文ごと消す
  5. 中身が無くなった章の見出しを消す

  python3 scripts/editor_notes.py            # 数えるだけ
  python3 scripts/editor_notes.py --apply    # 記事を直す

新しい記事は main.write_article → article_style.autofix がこの strip_record を通すので、札は残らない。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"

# 人（編集部・記者）が書いたように見せる札。サイソクの記事は AI が書いており、取材もしていない
LABEL = (r"編集部注|編集部の(?:知識|見立て|補足|分析)|編集部(?:が|で)(?:補足|独自)|編集部による補足|取材班|記者の(?:知見|見立て)")
LABEL_RE = re.compile(LABEL)
BARE_RE = re.compile(r"[（(]\s*(?:※\s*)?(?:" + LABEL + r")\s*[）)]")
COMPARE_HEAD_RE = re.compile(r"比較|競合|ライバル|他の選択肢|他社")
SENT_RE = re.compile(r"[^。！？]*(?:[。！？]+[」』）)]*|$)")
OPEN, CLOSE = "（(", "）)"
DANGLING_RE = re.compile(r"[^。]*(?:以下|次)の(?:通り|とおり)(?:です|に(?:整理|まとめ)しました)?[。：:]$|[^。]*(?:比較|整理)します[。：:]$")
FIELDS = ("body", "easy")
OTHER_FIELDS = ("workMoney", "decisionGuide", "highlights", "faq", "lede", "description", "verdict", "timetable")


def count(text: str) -> int:
    return len(LABEL_RE.findall(text or ""))


def _paren_span(line: str, at: int) -> tuple[int, int] | None:
    """位置 at を囲む一番内側のかっこ（全角・半角）の (開き, 閉じの次)。無ければ None"""
    depth = 0
    start = -1
    for i in range(at - 1, -1, -1):
        ch = line[i]
        if ch in CLOSE:
            depth += 1
        elif ch in OPEN:
            if depth == 0:
                start = i
                break
            depth -= 1
    if start < 0:
        return None
    depth = 0
    for j in range(start, len(line)):
        ch = line[j]
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth -= 1
            if depth == 0:
                return start, j + 1
    return None


def _drop_sentences(line: str) -> str:
    """札のある文を消す（箇条書きの「- 」などの頭は残す）"""
    m = re.match(r"^(\s*(?:[-*+]|\d+[.)])\s+|\s*>\s*)?", line)
    head = m.group(0) if m else ""
    rest = line[len(head):]
    kept = [s for s in SENT_RE.findall(rest) if s and not LABEL_RE.search(s)]
    out = "".join(kept).strip()
    return (head + out) if out else ""


LEAD_RE = re.compile(r"^\s*(?:[-*+]\s+|>\s*)?[*_]*\s*(?:※\s*)?[（(]?\s*(?:※\s*)?(?:" + LABEL + r")")


def strip_line(line: str, paragraph: bool = True) -> str:
    if not LABEL_RE.search(line):
        return line
    # 段落の頭に札がある（「（編集部注）動画では…」「（編集部注：…）」「取材班の見立てでは…」）→ 段落ごと AI の補足なので消す
    if paragraph and LEAD_RE.match(line):
        return ""
    # 札だけのかっこは、その文が AI の補足だという印 → 文ごと消す
    if BARE_RE.search(line):
        parts = SENT_RE.findall(line)
        line = "".join(p for p in parts if not BARE_RE.search(p))
    # 札を含むかっこ（「（編集部注：…）」「（※…は編集部注に基づきます）」）→ かっこごと消す
    for _ in range(20):
        m = LABEL_RE.search(line)
        if not m:
            break
        span = _paren_span(line, m.start())
        if not span:
            break
        line = line[: span[0]] + line[span[1]:]
    if LABEL_RE.search(line):
        line = _drop_sentences(line)
    # 消したあとに残った飾りだけの行（「**」「*」「※」）
    if re.fullmatch(r"[\s*_※:：、。・\-]*", line or ""):
        return ""
    return re.sub(r"[ 　]{2,}", " ", line).rstrip()


def _strip_table(rows: list[str]) -> list[str]:
    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    if len(rows) < 2 or not re.match(r"^\|?\s*:?-{2,}", rows[1].strip()):
        return [r for r in rows if not LABEL_RE.search(r)]
    head = cells(rows[0])
    drop = {i for i, c in enumerate(head) if LABEL_RE.search(c)}
    body = [r for r in rows[2:] if not LABEL_RE.search(r)]
    keep = [i for i in range(len(head)) if i not in drop]
    if len(keep) <= 1 or not body:
        return []

    def build(row: str) -> str:
        cs = cells(row)
        return "| " + " | ".join(cs[i] if i < len(cs) else "" for i in keep) + " |"

    if not drop:
        return rows[:2] + body
    return [build(rows[0]), "| " + " | ".join("---" for _ in keep) + " |"] + [build(r) for r in body]


def strip_text(text: str) -> str:
    """本文（Markdown）から札の付いた中身を消す。札が無ければ同じ文字列を返す"""
    if not text or not LABEL_RE.search(text):
        return text
    if "\n" not in text.strip() and "  " in text:
        # 改行が空白2つになってしまった本文（1行だけ）。段落に戻してから見る
        text = re.sub(r" {2,}", "\n\n", text)
    lines = text.split("\n")
    # 1. 札のある比較の章は章ごと消す
    sections: list[list[str]] = [[]]
    for line in lines:
        if re.match(r"^#{2,3}\s", line):
            sections.append([line])
        else:
            sections[-1].append(line)
    kept_lines: list[str] = []
    for sec in sections:
        if sec and re.match(r"^#{2,3}\s", sec[0]) and COMPARE_HEAD_RE.search(sec[0]) and any(LABEL_RE.search(x) for x in sec):
            continue
        kept_lines += sec
    # 2〜4. 表・かっこ・文
    out: list[str] = []
    i = 0
    while i < len(kept_lines):
        line = kept_lines[i]
        if line.lstrip().startswith("|"):
            j = i
            while j < len(kept_lines) and kept_lines[j].lstrip().startswith("|"):
                j += 1
            table = kept_lines[i:j]
            out += _strip_table(table) if any(LABEL_RE.search(r) for r in table) else table
            i = j
            continue
        new = strip_line(line)
        if new or not line.strip() or not LABEL_RE.search(line):
            out.append(new if LABEL_RE.search(line) else line)
        i += 1
    # 5. 中身が無くなった見出しを消す（元から中身の無い見出しは触らない）
    had = _section_has_content(kept_lines)
    final: list[str] = []
    for k, line in enumerate(out):
        if re.match(r"^#{2,3}\s", line) and not _has_content_after(out, k) and had.get(line, True):
            continue
        final.append(line)
    # 表や補足を消したあとに残った「以下の通りです。」で終わる段落（次が見出しか終わり）は、その文を消す
    for k in range(len(final)):
        nxt = next((x for x in final[k + 1:] if x.strip()), "")
        if (not nxt or re.match(r"^#{1,6}\s|^---$", nxt)) and DANGLING_RE.search(final[k]):
            final[k] = DANGLING_RE.sub("", final[k]).rstrip()
    result = re.sub(r"(?<=[。）)])---$", "\n\n---", "\n".join(final), flags=re.M)
    result = re.sub(r"\n{3,}", "\n\n", result).strip("\n")
    return result + ("\n" if text.endswith("\n") else "")


def _has_content_after(lines: list[str], k: int) -> bool:
    """見出し k の下に中身があるか（次の同じか上の段の見出しまで。下の段の見出しは、その下に中身があれば数える）"""
    level = len(lines[k]) - len(lines[k].lstrip("#"))
    for n in range(k + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s", lines[n])
        if m:
            return len(m.group(1)) > level and _has_content_after(lines, n)
        if lines[n].strip():
            return True
    return False


def _section_has_content(lines: list[str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for k, line in enumerate(lines):
        if re.match(r"^#{2,3}\s", line):
            out[line] = _has_content_after(lines, k)
    return out


def strip_record(record: dict) -> list[str]:
    """記事 JSON の本文・かんたん版から札の付いた中身を消す。直したことの一覧を返す"""
    changes = []
    for key in FIELDS:
        value = record.get(key)
        if isinstance(value, str) and LABEL_RE.search(value):
            n = count(value)
            record[key] = strip_text(value)
            changes.append(f"{key}: AI の補足に付いた「編集部注」などの札 {n}か所を、その中身ごと消した")
    # ほかの欄（「仕事・お金にどう活かせる？」の点・判断の目安の理由など）は、札のある文だけ消す
    for key in OTHER_FIELDS:
        if key in record and LABEL_RE.search(json.dumps(record[key], ensure_ascii=False)):
            record[key] = _walk(record[key])
            changes.append(f"{key}: 「編集部の見立て」などの札のある文を消した")
    return changes


def _walk(value):
    if isinstance(value, str):
        return strip_line(value, paragraph=False) if LABEL_RE.search(value) else value
    if isinstance(value, list):
        out = [_walk(v) for v in value]
        return [v for v, old in zip(out, value) if not (isinstance(old, str) and LABEL_RE.search(old) and not v)]
    if isinstance(value, dict):
        return {k: _walk(v) for k, v in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    articles = labels = 0
    before_len = after_len = 0
    for path in sorted(ARTICLES.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        if not LABEL_RE.search(raw):
            continue
        data = json.loads(raw)
        n = sum(count(data.get(k) or "") for k in FIELDS) + sum(count(json.dumps(data.get(k), ensure_ascii=False)) for k in OTHER_FIELDS if k in data)
        if not n:
            continue
        before = len(data.get("body") or "")
        trial = dict(data)
        strip_record(trial)
        if len(str(trial.get("body") or "").strip()) < 300:
            print(f"[editor-notes] 消すと本文がほとんど残らないので触らない: {path.stem}", file=sys.stderr)
            continue
        data = trial
        left = sum(count(data.get(k) or "") for k in FIELDS) + sum(count(json.dumps(data.get(k), ensure_ascii=False)) for k in OTHER_FIELDS if k in data)
        if left:
            print(f"[editor-notes] 残った: {path.stem}（{left}か所）", file=sys.stderr)
        articles += 1
        labels += n - left
        before_len += before
        after_len += len(data.get("body") or "")
        if args.apply:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    label = "直した" if args.apply else "直す（確認だけ）"
    print(f"[editor-notes] {label}: 記事 {articles} 本・札 {labels} か所・本文 {before_len:,}字 → {after_len:,}字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
