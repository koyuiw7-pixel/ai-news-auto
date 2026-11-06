#!/usr/bin/env python3
"""新しい記事の見た目「ノワール」（黒い表紙の写真＋白い紙面）の印と、要点の欄の中身を作る（2026-11-07 オーナー承認・台帳 W36）。

オーナー「デザインはOK。今ある記事はそのまま、新しい記事から新しいデザインに」。
- 新しく書き出す記事だけに `layout: "noir"` を付ける（scripts/main.py の write_article。今ある記事のファイルには触らない）。
  サイトは layout が "noir" の記事だけ components/noir/NoirArticle.tsx で出し、それ以外は今までの見た目のまま。
- 欄の中身は LLM に書かせない。品質ゲート（事実確認・数字の照合 calc_facts）を通った本文・要点の文字から、決まった手順で抜き出すだけ。
  抜き出した欄の数字は、記事の本文・要点・リードにそのまま書いてある数字だけ（無い数字が1つでもあれば欄ごと出さない）。
  計算で作る数字（差・合計・四捨五入）は使わない。値は記事に書いてある文字のまま。

作る欄（すべて任意。作れなければ付けない。サイトは欄が無ければその部品を出さない）:
  summaryLine  何が起きたかの1文（要点の1つ目）。大事な数字を **…** で囲む
  keyFigure    {value, unit, label, before?} 黒いカードの大きな数字（前と今の表の1行目、または要点の「売上高3兆528億円」）
  changes      [{label, before, after, note?}] 本文の「前／今回」の表の行（サイトはその表の場所に「前 → 今」の行で出す）
  wrapUp       [{name, text}] 本文の最後の章の、名前と説明の2列の表（サイトはその表の場所に一覧で出す）
"""

from __future__ import annotations

import re

import article_charts

LAYOUT = "noir"

# 数字（記事に書いてある形のまま）。「3兆528億」「479万7,100」「4.7」「$20」
NUMBER = r"(?:約)?[¥$￥]?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:[兆億万千](?:\d{1,3}(?:,\d{3})*|\d+)?)*"
UNIT = r"(?:億円|万円|円|ドル|ユーロ|%|％|ポイント|万人|人|万件|件|万台|台|社|倍|店舗|拠点|口座|GB|TB)"
FIGURE_RE = re.compile(rf"(?P<value>{NUMBER})(?P<unit>{UNIT})")
# 表のセル全体が「数字＋単位」だけのとき
CELL_FIGURE_RE = re.compile(rf"^(?P<value>{NUMBER})(?P<unit>{UNIT})$")
# 要点の「売上高3兆528億円」「国費920万円」「累計ダウンロード数が100万件」の、数字の前の名前
LABELED_RE = re.compile(rf"(?P<label>[一-龥ァ-ヶーA-Za-z]{{2,12}})(?:は|が|を|で|に)?(?P<value>{NUMBER})(?P<unit>{UNIT})")
LABEL_STOP = re.compile(r"^(約|総額|合計|およそ|前年|今回|昨年|累計で|税込|税抜|税別|米国|日本|国内|海外|世界|全国|計|同|最大|最低|最大で|上限|月額|年額)$")
DIGITS_RE = re.compile(r"\d[\d,.]*")
MAX_CELL = 24
MAX_ROWS = 6


def _strip(cell: str) -> str:
    return re.sub(r"\*\*|__|`", "", article_charts._clean(cell)).strip()


def _is_blank(text: str) -> bool:
    return not text or text in ("—", "-", "–", "ー", "なし", "記載なし", "不明", "未定", "非公表")


def changes_from_body(body: str) -> tuple[list[dict], str | None]:
    """本文の最初の「前／今回」の表（2列目と3列目の見出しが前と今・2つの時期）の行。戻り値は (行, 表の章の見出し)"""
    for heading, header, rows in article_charts._tables(body or ""):
        if len(header) < 3:
            continue
        h1, h2 = _strip(header[1]), _strip(header[2])
        periods = article_charts.PERIOD_RE.match(h1) and article_charts.PERIOD_RE.match(h2)
        if not periods and not (article_charts.BEFORE_HEAD.match(h1) and article_charts.AFTER_HEAD.match(h2)):
            continue
        out = []
        for row in rows:
            if len(row) < 3:
                continue
            label, before, after = _strip(row[0]), _strip(row[1]), _strip(row[2])
            if not label or _is_blank(before) or _is_blank(after) or before == after:
                continue
            if max(len(before), len(after)) > MAX_CELL or len(label) > 40:
                continue  # 1行に収まらない値は「前 → 今」の行にしない（表のまま）
            change = {"label": label, "before": before, "after": after}
            if len(row) >= 4 and (note := _strip(row[3])) and not _is_blank(note) and len(note) <= 16:
                change["note"] = note
            out.append(change)
        if out:
            return out[:MAX_ROWS], heading
    return [], None


def key_figure(changes: list[dict], highlights: list[str]) -> dict | None:
    """黒いカードの大きな数字。①要点の1つ目に出てくる「前と今」の表の数字 ②要点の「名前＋数字」（売上高3兆528億円）
    ③前と今の表の、数字だけの行（いちばん上）の順"""
    head = (highlights or [""])[0] or ""

    def from_change(change: dict) -> dict | None:
        m = CELL_FIGURE_RE.match(change["after"].replace(" ", ""))
        if not m:
            return None
        fig = {"value": m.group("value"), "unit": m.group("unit"), "label": change["label"]}
        if CELL_FIGURE_RE.match(change["before"].replace(" ", "")):
            fig["before"] = change["before"]
        return fig

    for change in changes:
        if change["after"] in head and (fig := from_change(change)):
            return fig
    for m in LABELED_RE.finditer(head):
        label = re.sub(r"^(の|と|、)", "", m.group("label"))
        if LABEL_STOP.match(label) or len(label) < 2:
            continue
        return {"value": m.group("value"), "unit": m.group("unit"), "label": label}
    for change in changes:
        if fig := from_change(change):
            return fig
    return None


def summary_line(highlights: list[str], fig: dict | None) -> str | None:
    """何が起きたかの1文（要点の1つ目）。大事な数字（黒いカードの数字、無ければ文の最初の数字）を **…** で囲む"""
    text = re.sub(r"^\s*(?:\d+[.)．、]|[・•\-*])\s*", "", (highlights or [""])[0] or "").strip()
    text = text.replace("**", "")
    if not text or len(text) > 90:
        return None
    target = f"{fig['value']}{fig['unit']}" if fig else None
    if target and target in text:
        return text.replace(target, f"**{target}**", 1)
    m = FIGURE_RE.search(text)
    if m:
        return text[: m.start()] + f"**{m.group(0)}**" + text[m.end():]
    return text


def wrap_up(body: str) -> tuple[list[dict], str | None]:
    """本文の最後の章にある、名前と説明の2列の表（2〜5行）。グレード・品目・対象ごとのまとめ"""
    tables = list(article_charts._tables(body or ""))
    if not tables:
        return [], None
    last_heading = None
    for line in (body or "").split("\n"):
        if h := re.match(r"^##\s+(.+?)\s*$", line):
            last_heading = h.group(1).strip()
    heading, header, rows = tables[-1]
    if heading != last_heading or len(header) != 2 or not 2 <= len(rows) <= 5:
        return [], None
    out = []
    for row in rows:
        if len(row) != 2:
            return [], None
        name, text = _strip(row[0]), _strip(row[1])
        # 説明の列は文（数字だけのセルは料金表なので、まとめの一覧にしない）
        if not name or len(name) > 16 or _is_blank(text) or len(text) < 6 or CELL_FIGURE_RE.match(text.replace(" ", "")):
            return [], None
        out.append({"name": name, "text": text})
    return out, heading


def _grounded(value: object, record_text: str) -> bool:
    """欄の中の数字が、すべて記事の本文・要点・リードにそのまま書いてあるか（作った数字を出さない）"""
    texts: list[str] = []

    def walk(v: object) -> None:
        if isinstance(v, str):
            texts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(value)
    flat = record_text.replace("**", "")
    return all(num in flat for t in texts for num in DIGITS_RE.findall(t.replace("**", "")))


def derive(record: dict) -> dict:
    """記事から、ノワールの要点の欄を作る（記事は書き換えない）"""
    body = str(record.get("body") or "")
    highlights = [str(h) for h in record.get("highlights") or [] if str(h).strip()]
    record_text = "\n".join([body, str(record.get("lede") or ""), *highlights])
    changes, _ = changes_from_body(body)
    fig = key_figure(changes, highlights)
    fields: dict = {}
    if line := summary_line(highlights, fig):
        fields["summaryLine"] = line
    if fig:
        fields["keyFigure"] = fig
    if changes:
        fields["changes"] = changes
    wrap, _ = wrap_up(body)
    if wrap:
        fields["wrapUp"] = wrap
    # 記事に書いていない数字が混ざった欄は出さない
    return {k: v for k, v in fields.items() if _grounded(v, record_text)}


def eligible(record: dict) -> bool:
    """ノワールで出す記事か。公式発表・報道から書いた通常の記事（動画の紹介・まとめ記事・地震の速報は今までの見た目）"""
    return record.get("sourceType") == "web" and record.get("type") != "roundup" and not record.get("quake")


def attach(record: dict) -> list[str]:
    """新しい記事に layout と欄を付ける（scripts/main.py の write_article が、まだ無い記事のファイルを書く前に呼ぶ）"""
    if not eligible(record) or record.get("layout"):
        return []
    record["layout"] = LAYOUT
    for key in ("summaryLine", "keyFigure", "changes", "wrapUp"):
        record.pop(key, None)
    fields = derive(record)
    record.update(fields)
    return [f"layout=noir（{'・'.join(fields) or '欄なし'}）"]
