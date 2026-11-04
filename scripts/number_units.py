#!/usr/bin/env python3
"""数字を読者に意味の分かる単位で書く（2026-11-05 オーナー承認の記事の質のピボット・台帳 A45）。

決算の表や会社の発表は「百万」の単位で書くことが多いが、日本語の文では「約77百万件」は不自然で読みにくい
（とろいも〔Muse〕の批評 out/muse/saisoku-article-quality-critique.md）。文では「万」「億」で書く:
  約77百万件 → 約7,700万件 / 150百万人 → 1億5,000万人 / 3,500百万円 → 35億円 / 1.5百万台 → 150万台

  - natural_units(text): 文の「N百万＋単位」を「万・億」に直した文
  - unnatural_units(text): 直していない「N百万＋単位」の一覧（公開前の門 article_style.coded_problems が見る）
表の単位の断り書き（「単位：百万円」「（百万円）」）は数字が後ろに無いので変えない。
"""

from __future__ import annotations

import re

# 数字のすぐ後ろの「百万」＋単位（件・人・通・台・円 など）。「数百万人」のような数字の無いものは自然なので見ない
UNIT_WORDS = "件|人|名|通|台|回|個|本|社|口座|世帯|戸|株|枚|部|冊|店舗|ユーザー|アカウント|アドレス|円|ドル|米ドル|ユーロ|トークン|ダウンロード|再生|票"
MILLION_RE = re.compile(rf"(?<![\d.,])(\d{{1,3}}(?:,\d{{3}})+|\d+)(\.\d+)?\s?百万\s?({UNIT_WORDS})")


def _fmt_man(value_man: float) -> str:
    """万の単位の値（7700.0）を「7,700万」「1億5,000万」「150万」の形にする"""
    if abs(value_man - round(value_man)) < 1e-9:
        n = int(round(value_man))
        oku, man = divmod(n, 10000)
        if oku and man:
            return f"{oku:,}億{man:,}万"
        if oku:
            return f"{oku:,}億"
        return f"{man:,}万"
    # 小数が残る（0.25百万＝25万、1.234百万＝123.4万）
    text = f"{value_man:,.4f}".rstrip("0").rstrip(".")
    return f"{text}万"


def _replace(m: re.Match) -> str:
    whole = m.group(1).replace(",", "")
    frac = m.group(2) or ""
    value = float(whole + frac)  # 百万の単位の値
    return _fmt_man(value * 100) + m.group(3)


def natural_units(text: str) -> str:
    if not text or "百万" not in text:
        return text
    return MILLION_RE.sub(_replace, text)


def unnatural_units(text: str) -> list[str]:
    return [m.group(0) for m in MILLION_RE.finditer(text or "")]
