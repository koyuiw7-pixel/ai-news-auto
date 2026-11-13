#!/usr/bin/env python3
"""数字の計算部品（決定的。LLM なし）。

無料の LLM は計算を間違えやすいので、記事に使う「計算した数字」はここで作り、式つきで LLM に渡す。
LLM は計算しない（式の結果をそのまま写すだけ）。品質ゲート（quality.number_problems）は、
記事の数字が「元記事・確認済みの事実の束・計算済みの数字」のどれかにあるかをここの部品で確かめる。

計算するもの（どれも元記事・過去記事・料金表の数字から）:
- ペース: 「約7カ月で100万口座増」→ 1カ月あたり約14.3万口座
- 年換算: 「1-10月累計67件」→ このペースなら年約80件
- 前と比べた差・増減率: 「67件（前年同期56件）」→ 11件増・19.6%増
- 割合: 「負債総額20億7,700万円 … 最大の倒産は負債11億円」→ 53.0%
- 進み具合: 「上限2,000億円 … 累計1,048億円」→ 52.4%
- 1つあたり: 「総額272億円 … 総数1億5,700万株」→ 1株あたり約173円
- 料金の段の「使う量あたりの値段」: Max $100（Pro の5倍）→ Pro 1倍分あたり $20（Pro と同じ）
- 円への換算: $200 × 157.90円 = 約31,580円（為替のレートと日付つきの目安）
- 過去記事との比較: 前回の記事の1,400万口座 → 今回1,500万口座

  python3 scripts/calc_facts.py "本文…"     # 文章から数字を取り出して計算結果を表示（試し）
"""

from __future__ import annotations

import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

JST_TZ = timezone(timedelta(hours=9))

# --------------------------------------------------------------------------- #
# 数字の取り出し
# --------------------------------------------------------------------------- #

NUM = r"\d+(?:,\d{3})*(?:\.\d+)?"
# 日本語の数（「20億7,700万」「3万1,580」「1,500万」「14.3万」）
JP_NUM = rf"{NUM}(?:\s?[兆億万千](?:\s?{NUM})?)*"
JP_MULT = {"兆": 1e12, "億": 1e8, "万": 1e4, "千": 1e3}
EN_MULT = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "k": 1e3, "m": 1e6, "b": 1e9, "bn": 1e9}

MONEY_PREFIX = r"(?P<pre>US\$|\$|＄|USD\s?|¥|￥|€)"
COUNTERS = "件|口座|社|人|名|台|株|店舗|世帯|戸|万人"
UNIT = rf"(?P<unit>円|米ドル|ドル|ユーロ|%|％|パーセント|倍|(?<=\d)x\b|{COUNTERS})"
QTY_RE = re.compile(
    rf"(?:{MONEY_PREFIX}\s?)?(?P<num>{JP_NUM})(?:\s?(?P<en>thousand|million|billion|trillion|bn|[kKmMbB](?![A-Za-z])))?\s?{UNIT}?"
)
SEN_RE = re.compile(r"\s?(\d{1,2})\s?銭")
APPROX_BEFORE_RE = re.compile(r"(?:約|およそ|ほぼ|概ね|おおむね|推定|最大|最大で|少なくとも|over|about|approximately|nearly|around|~)\s*$", re.I)
APPROX_AFTER_RE = re.compile(r"^\s*(?:前後|程度|ほど|強|弱|超|余り|あまり|近く|以上|未満|以下|超え|台)")
SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")
WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "twenty": 20, "fifty": 50, "hundred": 100, "twice": 2, "double": 2, "triple": 3, "half": 0.5,
}
WORD_MULT_RE = re.compile(r"\b(a|an|one|two|three|four|five|six|seven|eight|nine|ten|twenty|fifty|hundred)\s+(thousand|million|billion|trillion)\b", re.I)
WORD_NUM_RE = re.compile(r"\b(" + "|".join(WORD_NUMBERS) + r")\b", re.I)


@dataclass
class Qty:
    value: float
    unit: str  # JPY / USD / EUR / % / x / 件・口座など / "" （単位なし）
    text: str
    start: int
    end: int
    approx: bool = False
    has_mult: bool = False  # 万・億・million など
    before: str = ""  # 同じ文の直前（最大30字）
    after: str = ""  # 直後（最大24字）
    sentence: str = ""
    para: int = 0  # 何番目の段落か

    @property
    def is_money(self) -> bool:
        return self.unit in ("JPY", "USD", "EUR")


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def parse_jp(num: str) -> float:
    """「20億7,700万」→ 2077000000.0、「3万1,580」→ 31580.0"""
    total, current = 0.0, None
    for n, mult in re.findall(r"(\d[\d,]*(?:\.\d+)?)|([兆億万千])", num):
        if n:
            current = float(n.replace(",", ""))
        else:
            total += (current if current is not None else 1.0) * JP_MULT[mult]
            current = None
    return total + (current or 0.0)


def _unit_of(pre: str | None, unit: str | None) -> str:
    pre = (pre or "").strip()
    if pre in ("$", "＄", "US$", "USD"):
        return "USD"
    if pre in ("¥", "￥"):
        return "JPY"
    if pre == "€":
        return "EUR"
    unit = unit or ""
    if unit == "円":
        return "JPY"
    if unit in ("ドル", "米ドル"):
        return "USD"
    if unit == "ユーロ":
        return "EUR"
    if unit in ("%", "％", "パーセント"):
        return "%"
    if unit in ("倍", "x"):
        return "x"
    if unit == "万人":
        return "人"
    return unit


def extract(text: str) -> list[Qty]:
    """文章の中の数字（単位つきも単位なしも）。日付・年（「2026年」「11月3日」）は単位なしで返る"""
    text = nfkc(text)
    out: list[Qty] = []
    para_starts = [m.start() for m in re.finditer(r"\n\s*\n", text)]
    consumed = 0  # 「17円50銭」の「50銭」を別の数字として拾わない
    for m in QTY_RE.finditer(text):
        if m.start() < consumed:
            continue
        num = m.group("num")
        value = parse_jp(num)
        en = (m.group("en") or "").lower()
        if en:
            value *= EN_MULT[en]
        unit = _unit_of(m.group("pre"), m.group("unit"))
        if m.group("unit") == "万人":
            value *= 1e4
        # 「2026年」の年・「11月」の月・「3日」の日は単位として扱わない（単位なし＝日付の数字）
        start, end = m.start(), m.end()
        qty_text = m.group(0).strip()
        # 配当などの「17円50銭」＝ 17.5円（資料の表は「17.50」と書く。2026-11-05 決算の速報）
        if unit == "JPY" and (sen := SEN_RE.match(text, end)):
            value += float(sen.group(1)) / 100
            qty_text = (text[m.start():sen.end()]).strip()
            end = consumed = sen.end()
        sent_start = max(text.rfind(c, 0, start) for c in "。！？!?\n") + 1
        sent_end_candidates = [i for i in (text.find(c, end) for c in "。！？!?\n") if i >= 0]
        sent_end = min(sent_end_candidates) + 1 if sent_end_candidates else len(text)
        before = text[max(sent_start, start - 30):start]
        after = text[end:end + 6]
        out.append(Qty(
            value=value, unit=unit, text=qty_text, start=start, end=end,
            approx=bool(APPROX_BEFORE_RE.search(before) or APPROX_AFTER_RE.search(after)),
            has_mult=bool(re.search(r"[兆億万千]", num) or en or m.group("unit") == "万人"),
            before=before, after=text[end:end + 24], sentence=text[sent_start:sent_end].strip(),
            para=sum(1 for p in para_starts if p < start),
        ))
    return out


def values(text: str) -> list[float]:
    """文章に出てくる数の値すべて（単位を問わない。品質ゲートの「使ってよい数字」用）。英語の数の言葉（two・twice）も含む"""
    found = [q.value for q in extract(text)]
    found += [float(WORD_NUMBERS[w.lower()]) for w in WORD_NUM_RE.findall(text or "")]
    # 「one billion」「a million」「two thousand」
    for word, mult in WORD_MULT_RE.findall(text or ""):
        base = 1.0 if word.lower() in ("a", "an") else float(WORD_NUMBERS.get(word.lower(), 1))
        found.append(base * EN_MULT[mult.lower()])
    # 決算の表は「百万ドル単位」「in millions」で書かれる（6,540 → 65億4,000万ドル）。単位の断り書きがある資料だけ、
    # 表の数字を単位どおりに直した値も「使ってよい数字」に入れる（2026-11-03: 決算の記事が製品別・地域別の数字を書けるように）
    plain = [q.value for q in extract(text) if q.value >= 1]
    # 文の「約77百万件」（資料の書き方）は 7,700万件 と同じ値（記事は万・億で書く。scripts/number_units.py・台帳 A45）
    found += [float(n.replace(",", "") + (f or "")) * 1e6 for n, f in MILLION_WORD_RE.findall(nfkc(text or ""))]
    if UNIT_MILLIONS_RE.search(text or ""):
        found += [v * 1e6 for v in plain]
    if UNIT_THOUSANDS_RE.search(text or ""):
        found += [v * 1e3 for v in plain]
    # 日本の決算の表は「（億円）」単位が多い（KDDI 29,160 → 2兆9,160億円。2026-11-06 の速報が門で落ちた）
    if UNIT_OKU_RE.search(text or ""):
        found += [v * 1e8 for v in plain]
    return found


MILLION_WORD_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?百万")
UNIT_MILLIONS_RE = re.compile(r"in millions|\(millions|millions of (?:dollars|U\.S\.)|百万(?:円|ドル|ユーロ)|単位[:：]\s*百万", re.I)
UNIT_OKU_RE = re.compile(r"[（(]\s*億円\s*[)）]|単位[:：]\s*億")
UNIT_THOUSANDS_RE = re.compile(r"in thousands|\(thousands|千(?:円|ドル)|単位[:：]\s*千", re.I)


# 品質ゲートで確かめる数字（お金・割合・倍・大きな件数）。日付・時間・小さな数は確かめない
CHECK_COUNTERS = {"件", "口座", "社", "人", "名", "台", "株", "店舗", "世帯", "戸"}


def checkable(q: Qty) -> bool:
    if q.value == 0:
        return False
    if q.is_money or q.unit == "%":
        return True
    if q.unit == "x":
        return q.value >= 1.1
    if q.unit in CHECK_COUNTERS:
        return q.value >= 10 or q.has_mult
    return False


def sig_round(value: float, digits: int = 3) -> float:
    if value == 0:
        return 0.0
    return round(value, digits - 1 - int(math.floor(math.log10(abs(value)))))


def supported(q: Qty, allowed: list[float]) -> bool:
    """記事の数字 q が、使ってよい数字のどれかと（丸めの範囲で）一致するか。「約」などの付いた数字は6%まで、ほかは1%まで。
    お金は、表示の桁での切り捨て・四捨五入でも一致とみなす（資料の 2,191,124 百万円 → 記事の「2兆円超」など。display_match）"""
    tol = 0.06 if q.approx else 0.01
    step = display_step(q.text) if q.is_money else 0.0
    for a in allowed:
        if abs(q.value - a) <= tol * max(abs(a), 1e-9) or abs(q.value - a) < 1e-9:
            return True
        if step and display_match(q.value, step, q.approx, a):
            return True
    return False


# --------------------------------------------------------------------------- #
# 表の数字と記事の数字の照合（2026-11-05 決算の速報・台帳 W35）
#   決算短信の表は「百万円」「千円」の単位で 2,191,124 と書き、記事は「2兆1,911億円」と書く。
#   表の単位の断り書き（近くの行の「百万円」「千円」「円 銭」「%」）から表の数字を記事の単位に直し、
#   記事の表示の桁での切り捨て・四捨五入で一致すれば同じ数字とみなす。△・▲は減る向き。
#   使う所: scripts/release_quality.py（速報の門）・supported（元記事・事実の束の数字の門 quality.number_problems）
# --------------------------------------------------------------------------- #

_DISPLAY_PART_RE = re.compile(r"(\d[\d,]*)(?:\.(\d+))?\s?([兆億万千]?)")


def display_step(num_text: str) -> float:
    """記事の数字の「表示の最後の桁の1つ分」。「2兆1,911億円」→ 1億、「2.2兆円」→ 1,000億、「242億1,400万円」→ 1万、
    「17.5円」→ 0.1、「17円50銭」→ 0.01、「29万7,145円」→ 1"""
    text = nfkc(num_text)
    if re.search(r"\d\s?銭", text):
        return 0.01
    parts = _DISPLAY_PART_RE.findall(text)
    if not parts:
        return 0.0
    _, decimals, mult = parts[-1]
    return JP_MULT.get(mult, 1.0) / 10 ** len(decimals)


def display_match(value: float, step: float, approx: bool, source: float) -> bool:
    """記事の値 value（表示の桁 step）が、資料の値 source を表示の桁で切り捨てか四捨五入したものか。
    有効数字が1桁だけの書き方（「2兆円」）は「約」「超」などが付くときだけ丸めを認める（粗い数字で何にでも合わないように）"""
    a, s = abs(value), abs(source)
    if abs(a - s) <= 1e-9 * max(1.0, s):
        return True
    if step <= 0 or a <= 0 or s < step / 2:
        return False
    digits = int(math.floor(math.log10(a / step) + 1e-9)) + 1
    if digits < 2 and not approx:
        return False
    q = s / step
    eps = step * 1e-6
    return abs(a - math.floor(q + 1e-9) * step) <= eps or abs(a - math.floor(q + 0.5) * step) <= eps


TABLE_NUM_RE = re.compile(
    r"(?<![\d.,])(?P<sign>[△▲]\s?|-(?=\d))?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?![\d.]|,\d)(?!\s?(?:年|月|日|兆|億|万|千|百|円|銭|%|社|件|人|名|株|倍|ポイント|期|四半期|時|分|秒|か月|カ月|ヵ月|ヶ月|ページ|頁|号))"
)
TABLE_CTX = {
    "百万円": re.compile(r"百万円|単位\s?[:：]?\s?百万"),
    "千円": re.compile(r"(?<!百)千円|単位\s?[:：]?\s?千円"),
    "円": re.compile(r"円\s*銭|[(（]円[)）]|単位\s?[:：]?\s?円"),
    "%": re.compile(r"%"),
}
TABLE_SCALE = {"百万円": (1e6, "JPY"), "千円": (1e3, "JPY"), "円": (1.0, "JPY"), "%": (1.0, "%")}


@dataclass
class TableNum:
    value: float  # 記事の単位に直した値（円・%）
    unit: str  # JPY / %
    neg: bool  # △・▲・- が付いている（減る向き・赤字）
    raw: str


def table_numbers(text: str, before: int = 30, after: int = 3) -> list[TableNum]:
    """表の単位の付いていない数字を、近くの行（前 before 行・後 after 行）の単位の断り書きで円・%に直した候補。
    1つの数字に複数の候補ができる（同じ表に「百万円」と「%」の欄があるため）"""
    lines = nfkc(text).splitlines()
    marks = [{k for k, r in TABLE_CTX.items() if r.search(line)} for line in lines]
    out: list[TableNum] = []
    for i, line in enumerate(lines):
        nums = list(TABLE_NUM_RE.finditer(line))
        if not nums:
            continue
        ctx = set().union(*marks[max(0, i - before):i + after + 1])
        for m in nums:
            value = float(m.group("num").replace(",", ""))
            neg = bool(m.group("sign"))
            for key in ctx:
                scale, unit = TABLE_SCALE[key]
                out.append(TableNum(value=value * scale, unit=unit, neg=neg, raw=m.group(0)))
    return out


# --------------------------------------------------------------------------- #
# 表示
# --------------------------------------------------------------------------- #


def _comma(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}"


def fmt_num(value: float) -> str:
    """数を日本語の読みやすい形に（3桁の有効数字）。1,234 / 14.3万 / 2,370億 / 1.5兆"""
    v = abs(value)
    sign = "-" if value < 0 else ""
    if v >= 1e12:
        return f"{sign}{sig_round(v / 1e12):g}兆"
    if 1e8 <= v < 1e10 and round((v % 1e8) / 1e4, -2):
        oku, man = int(v // 1e8), round((v % 1e8) / 1e4, -2)
        if man >= 1e4:
            oku, man = oku + 1, 0
        return f"{sign}{oku}億" + (f"{_comma(man)}万" if man else "")
    if v >= 1e8:
        n = sig_round(v / 1e8)
        return f"{sign}{_comma(n, 0) if n >= 100 else f'{n:g}'}億"
    if v >= 1e4:
        n = sig_round(v / 1e4)
        return f"{sign}{_comma(n, 0) if n >= 100 else f'{n:g}'}万"
    if v >= 100:
        return f"{sign}{_comma(round(v))}"
    return f"{sign}{sig_round(v):g}"


def fmt_qty(value: float, unit: str) -> str:
    if unit == "JPY":
        if abs(value) < 1e6:
            return f"{_comma(round(value, -1) if abs(value) >= 1000 else round(value))}円"
        return f"{fmt_num(value)}円"
    if unit == "USD":
        return f"${_comma(value, 2).rstrip('0').rstrip('.')}" if abs(value) < 1e6 else f"{fmt_num(value)}ドル"
    if unit == "EUR":
        return f"{fmt_num(value)}ユーロ"
    if unit == "%":
        return f"{value:.1f}%"
    if unit == "x":
        return f"{sig_round(value):g}倍"
    return f"{fmt_num(value)}{unit}"


def fmt_pct(value: float) -> str:
    return f"{value:+.1f}%".replace("+", "＋").replace("-", "−")


# --------------------------------------------------------------------------- #
# 計算
# --------------------------------------------------------------------------- #


@dataclass
class Computed:
    kind: str  # pace / annual / change / share / progress / per_unit / ladder / yen / past
    text: str  # LLM に渡す1行（結果と式）
    values: list[float] = field(default_factory=list)  # 結果の数（品質ゲートで「使ってよい数字」になる）


PERIOD_RE = re.compile(r"(約)?\s?(\d+(?:\.\d+)?)\s?(カ月|か月|ヶ月|ケ月|ヵ月|カ年|年|週間|日)(?:間)?(?:で|の間に|をかけて)")
MONTHS_PER = {"カ月": 1, "か月": 1, "ヶ月": 1, "ケ月": 1, "ヵ月": 1, "年": 12, "カ年": 12, "週間": 7 / 30.44, "日": 1 / 30.44}
CUMULATIVE_RE = re.compile(r"(?<![\d年])(1)\s?[-－〜~～ー]\s?(\d{1,2})\s?月(?:の)?(?:累計|合計)?")
PREV_RE = re.compile(r"(前年同期|前年同月|前年同時期|前年度|前年|前月|前回|前期|前四半期|昨年|去年)(?:比)?(?:（[^）]{0,12}）|\([^)]{0,12}\))?(?:は|の|が|：|:|、)?\s?$")
TOTAL_LABEL_RE = re.compile(r"(総額|合計|総数|全体|累計額)(?:は|が|：|:)?\s?(?:約)?\s?$")
PART_RE = re.compile(r"最大|うち|そのうち")
GOAL_RE = re.compile(r"(上限|目標|計画|予定総額|取得枠|枠)")
DONE_RE = re.compile(r"(累計|取得済み|これまでに|これまで|達成|到達|突破|取得した|実績)")


def _same_unit(a: Qty, b: Qty) -> bool:
    return a.unit == b.unit and a.unit != ""


def _ctx(q: Qty, n: int = 14) -> str:
    """数字の前の言葉（何の数か）。読点などで区切った最後のまとまり"""
    tail = re.split(r"[、，,（()）]", q.before)[-1].strip()
    return tail[-n:]


def pace(qs: list[Qty]) -> list[Computed]:
    """「約7カ月で100万口座増」→ 1カ月あたり"""
    out = []
    for q in qs:
        if not (q.unit in CHECK_COUNTERS or q.is_money) or q.value <= 0:
            continue
        m = None
        for m in PERIOD_RE.finditer(q.before):
            pass
        if not m or len(q.before) - m.end() > 6:
            continue
        months = float(m.group(2)) * MONTHS_PER[m.group(3)]
        if months <= 0 or months > 240:
            continue
        per = q.value / months
        approx = "約" if m.group(1) else ""
        period = f"{approx}{m.group(2)}{m.group(3)}"
        out.append(Computed(
            "pace",
            f"{period}で{q.text} → 1カ月あたり約{fmt_qty(per, q.unit)}（{q.text} ÷ {sig_round(months):g}カ月）",
            [per],
        ))
    return out


def annual(qs: list[Qty]) -> list[Computed]:
    """「1-10月累計67件」→ このペースなら年約80件"""
    out = []
    for q in qs:
        if not (q.unit in CHECK_COUNTERS or q.is_money):
            continue
        m = None
        for m in CUMULATIVE_RE.finditer(q.before):
            pass
        if not m or len(q.before) - m.end() > 8:
            continue
        last = int(m.group(2))
        if not 1 <= last < 12:
            continue
        year = q.value / last * 12
        out.append(Computed(
            "annual",
            f"1〜{last}月で{q.text} → このペースが続くと1年で約{fmt_qty(year, q.unit)}（{q.text} ÷ {last}カ月 × 12カ月。残りは{12 - last}カ月）",
            [year, float(12 - last)],
        ))
    return out


def changes(qs: list[Qty]) -> list[Computed]:
    """同じ文の「今の数」と「前年・前回の数」→ 差と増減率"""
    out = []
    for i, ref in enumerate(qs):
        if not PREV_RE.search(ref.before):
            continue
        label = PREV_RE.search(ref.before).group(1)
        cur = next((q for q in reversed(qs[:i]) if q.sentence == ref.sentence and _same_unit(q, ref) and q.value != ref.value
                    and not PREV_RE.search(q.before)), None)
        if not cur or ref.value == 0:
            continue
        diff = cur.value - ref.value
        pct = diff / ref.value * 100
        word = "増" if diff > 0 else "減"
        out.append(Computed(
            "change",
            f"{_ctx(cur) or '今回'}{cur.text}と{label}の{ref.text} → {fmt_qty(abs(diff), cur.unit)}{word}、{fmt_pct(pct)}"
            f"（({cur.text} − {ref.text}) ÷ {ref.text}）",
            [abs(diff), abs(pct)],
        ))
    return out


IMPLIED_RE = re.compile(r"^\s?[（(]?\s?(前年同月|前年同期|前年度|前年|前月|前期)比\s?[+＋]?(\d+(?:\.\d+)?)\s?[％%]\s?(増|減)")


def implied_previous(qs: list[Qty]) -> list[Computed]:
    """「20億7,700万円（前年同月比47.0％増）」→ 前年同月は約14億1,300万円（増減率から逆算）"""
    out = []
    for q in qs:
        m = IMPLIED_RE.match(q.after)
        if not m or not (q.is_money or q.unit in CHECK_COUNTERS) or q.value <= 0:
            continue
        rate = float(m.group(2)) / 100 * (1 if m.group(3) == "増" else -1)
        if rate <= -1:
            continue
        prev = q.value / (1 + rate)
        diff = q.value - prev
        out.append(Computed(
            "implied",
            f"{q.text}（{m.group(1)}比{m.group(2)}％{m.group(3)}）→ {m.group(1)}は約{fmt_qty(prev, q.unit)}、差は約{fmt_qty(abs(diff), q.unit)}"
            f"（{q.text} ÷ {1 + rate:g}。増減率からの逆算）",
            [prev, abs(diff)],
        ))
    return out


def shares(qs: list[Qty]) -> list[Computed]:
    """「総額 T … 最大・うち P」（同じ段落・同じ単位）→ 割合"""
    out = []
    for t in qs:
        if not TOTAL_LABEL_RE.search(t.before) or t.value <= 0:
            continue
        for p in qs:
            if p is t or p.para != t.para or not _same_unit(p, t) or not (0 < p.value < t.value):
                continue
            if not PART_RE.search(p.sentence) or p.sentence == t.sentence and not PART_RE.search(p.before):
                continue
            share = p.value / t.value * 100
            out.append(Computed(
                "share",
                f"{TOTAL_LABEL_RE.search(t.before).group(1)}{t.text}のうち{p.text}（{_ctx(p, 10) or '一部'}）→ {share:.1f}%（{p.text} ÷ {t.text}）",
                [share],
            ))
            break
    return out


def progress(qs: list[Qty]) -> list[Computed]:
    """「上限・目標 G … 累計・取得済み D」（同じ単位・同じ段落）→ 進み具合と残り"""
    out = []
    for g in qs:
        if not GOAL_RE.search(g.before[-12:]) or g.value <= 0:
            continue
        for d in qs:
            if d is g or not _same_unit(d, g) or d.para != g.para or not (0 < d.value < g.value):
                continue
            if not DONE_RE.search(d.before[-14:]):
                continue
            pct = d.value / g.value * 100
            out.append(Computed(
                "progress",
                f"{GOAL_RE.search(g.before[-12:]).group(1)}{g.text}に対して{DONE_RE.search(d.before[-14:]).group(1)}{d.text} → {pct:.1f}%、残り{fmt_qty(g.value - d.value, g.unit)}"
                f"（{d.text} ÷ {g.text}）",
                [pct, g.value - d.value],
            ))
            break
    return out


def per_unit(qs: list[Qty]) -> list[Computed]:
    """同じ文（または隣の文）の「総額 M（お金）」と「総数 C（株・口座など）」→ 1つあたり"""
    out = []
    for m_ in qs:
        if not m_.is_money or not re.search(r"総額|金額", m_.before):
            continue
        for c in qs:
            if c.unit not in CHECK_COUNTERS or c.para != m_.para or abs(c.start - m_.start) > 120 or c.value <= 0:
                continue
            if not re.search(r"総数|数", c.before[-10:]):
                continue
            per = m_.value / c.value
            out.append(Computed(
                "per_unit",
                f"{m_.text}で{c.text} → 1{c.unit}あたり約{fmt_qty(per, m_.unit)}（{m_.text} ÷ {c.text}）",
                [per],
            ))
            break
    return out


def yen(usd_amounts: list[tuple[float, str]], fx: dict | None, monthly: set[float] | None = None) -> list[Computed]:
    """ドルの金額 → 円の目安（為替のレート・日付つき）。monthly にある金額（個人向けの月額）は税込み（10%）の目安も出す"""
    if not fx or not isinstance(fx.get("rate"), (int, float)) or not 50 < fx["rate"] < 400:
        return []
    rate, date = float(fx["rate"]), str(fx.get("date") or "")
    src = str(fx.get("source") or "")
    out, seen = [], set()
    for amount, label in usd_amounts:
        if amount <= 0 or amount in seen:
            continue
        seen.add(amount)
        jpy = amount * rate
        line = f"{label or fmt_qty(amount, 'USD')}：{fmt_qty(amount, 'USD')} × {rate:.2f}円 = 約{fmt_qty(jpy, 'JPY')}（税別の目安）"
        vals = [jpy]
        if monthly and amount in monthly:
            line += f"、消費税10%込みで約{fmt_qty(jpy * 1.1, 'JPY')}"
            vals.append(jpy * 1.1)
        out.append(Computed("yen", f"{line}　※1ドル={rate:.2f}円（{date}、{src}）で計算", vals))
        if len(out) >= 6:
            break
    return out


LADDER_REF_RE = re.compile(r"([A-Za-z][A-Za-z0-9 ]*?|[^\s、,（(。.$\d]{2,12}?)\s?の\s?(\d+(?:\.\d+)?)\s?倍")


def ladder(rows: list[dict]) -> list[Computed]:
    """料金の段（[{plan, usd_month, limits}]）で「Xの N 倍」とあるプラン → 1倍分あたりの値段。基準のプランと同じかを比べる"""
    by_name = {}
    for r in rows:
        if isinstance(r.get("usd_month"), (int, float)) and r["usd_month"] > 0:
            by_name[r["plan"]] = r
    out, same = [], []
    for r in rows:
        price = r.get("usd_month")
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        for limit in r.get("limits") or []:
            m = LADDER_REF_RE.search(nfkc(limit))
            if not m:
                continue
            ref_name, times = m.group(1).strip(), float(m.group(2))
            base = by_name.get(ref_name) or next((b for n, b in by_name.items() if ref_name and (ref_name in n or n in ref_name)), None)
            if not base or base is r or times <= 0:
                continue
            per = price / times
            base_price = base["usd_month"]
            if abs(per - base_price) < 0.01 * base_price:
                verdict = f"{base['plan']}（{fmt_qty(base_price, 'USD')}/月）と同じ。使える量あたりの値段は変わらない"
                same.append((r["plan"], base["plan"], per))
            elif per < base_price:
                verdict = f"{base['plan']}（{fmt_qty(base_price, 'USD')}/月）より{(1 - per / base_price) * 100:.0f}%安い"
            else:
                verdict = f"{base['plan']}（{fmt_qty(base_price, 'USD')}/月）より{(per / base_price - 1) * 100:.0f}%高い"
            out.append(Computed(
                "ladder",
                f"{r['plan']}：{fmt_qty(price, 'USD')}/月で{base['plan']}の{times:g}倍の使用量 → {base['plan']} 1倍分あたり{fmt_qty(per, 'USD')}"
                f"（{fmt_qty(price, 'USD')} ÷ {times:g}）。{verdict}",
                [per, times],
            ))
            break
    bases = {b for _, b, _ in same}
    if len(same) >= 2 and len(bases) == 1:
        base = bases.pop()
        names = "・".join([base] + [p for p, _, _ in same])
        out.insert(0, Computed(
            "ladder",
            f"{names}は、{base} 1倍分の使用量あたりの値段がどれも{fmt_qty(same[0][2], 'USD')}で同じ（料金 ÷ 使用量の倍率）。"
            "上のプランは「量あたりの割引」ではなく、同じ単価で量を増やすもの",
            [same[0][2]],
        ))
    return out


def _bigrams(text: str) -> set[str]:
    t = re.sub(r"[\d\s,.%、。「」『』（）()・\-—:：]", "", text or "")
    return {t[i:i + 2] for i in range(len(t) - 1)}


def past(current: list[Qty], past_rows: list[dict], now: datetime | None = None) -> list[Computed]:
    """過去記事（[{slug, title, at, text}]）の同じ種類の数字と、今回の数字を比べる（件・口座・人などの数だけ）。
    何の数かの言葉（直前の言葉）が似ているものだけ"""
    out, used = [], set()
    for q in current:
        if q.unit not in CHECK_COUNTERS or not q.has_mult and q.value < 1000:
            continue
        label = _bigrams(_ctx(q, 12))
        for row in past_rows:
            for p in extract(row.get("text") or ""):
                if p.unit != q.unit or p.value == q.value or p.value <= 0:
                    continue
                if len(label & _bigrams(_ctx(p, 12))) < 1 or (row["slug"], p.value) in used:
                    continue
                used.add((row["slug"], p.value))
                diff = q.value - p.value
                line = (f"サイソクの過去記事（{row['at']:%Y-%m-%d}「{row['title'][:30]}」）の{p.text} → 今回{q.text}："
                        f"{fmt_qty(abs(diff), q.unit)}{'増' if diff > 0 else '減'}、{fmt_pct(diff / p.value * 100)}")
                vals = [abs(diff), abs(diff / p.value * 100)]
                if now and isinstance(row.get("at"), datetime):
                    months = (now - row["at"]).days / 30.44
                    if months >= 0.5:
                        line += f"。1カ月あたり約{fmt_qty(abs(diff) / months, q.unit)}（{fmt_qty(abs(diff), q.unit)} ÷ {months:.1f}カ月。記事の日付どうしの目安）"
                        vals.append(abs(diff) / months)
                out.append(Computed("past", line, vals))
                break
            if len(out) >= 2:
                return out
    return out


RELATIVE_DATE_RE = re.compile(r"(来月|今月|翌月|先月)\s?(\d{1,2})日|(来年|今年|翌年|昨年)\s?(\d{1,2})月(?:\s?(\d{1,2})日)?|(来年度|今年度)")


ABS_DATE_RE = re.compile(r"(?:(令和|平成)\s?(\d{1,2}|元)年\s?|(20\d\d)年\s?)?(\d{1,2})月\s?(\d{1,2})日")


def _shift_month(y: int, mo: int, shift: int) -> tuple[int, int]:
    mo += shift
    return y + (mo - 1) // 12, (mo - 1) % 12 + 1


def dated_mentions(text: str, published: datetime | None) -> list[tuple["date", int, int]]:
    """文章の中の「日付」を実際の日付にする（2026-11-03）。[(日付, 始まり, 終わり)]（位置は nfkc した文章の中）。
    「令和8年11月9日」「2026年11月9日」「11月9日」（年が無ければ元記事の日付の年。半年以上前になるなら翌年）と、
    「来月1日」「来年4月1日」などの言い方（relative_dates と同じ。元記事の日付から数える。今日から数えない）"""
    from datetime import date  # noqa: PLC0415

    if not isinstance(published, datetime):
        return []
    base = published.astimezone(JST_TZ).date()
    t = nfkc(text)
    out = []
    for m in ABS_DATE_RE.finditer(t):
        month, day = int(m.group(4)), int(m.group(5))
        if m.group(1):
            n = 1 if m.group(2) == "元" else int(m.group(2))
            year = (2018 if m.group(1) == "令和" else 1988) + n
        elif m.group(3):
            year = int(m.group(3))
        else:
            year = base.year
        try:
            when = date(year, month, day)
        except ValueError:
            continue
        if not (m.group(1) or m.group(3)) and (base - when).days > 183:
            when = date(year + 1, month, day)
        out.append((when, m.start(), m.end()))
    for m in RELATIVE_DATE_RE.finditer(t):
        try:
            if m.group(1):
                y, mo = _shift_month(base.year, base.month, {"来月": 1, "翌月": 1, "今月": 0, "先月": -1}[m.group(1)])
                out.append((date(y, mo, int(m.group(2))), m.start(), m.end()))
            elif m.group(3) and m.group(5):
                y = base.year + {"来年": 1, "翌年": 1, "今年": 0, "昨年": -1}[m.group(3)]
                out.append((date(y, int(m.group(4)), int(m.group(5))), m.start(), m.end()))
        except ValueError:
            continue
    return sorted(out, key=lambda x: x[1])


def relative_dates(text: str, published: datetime | None) -> list[Computed]:
    """「来月1日」「来年4月」などを、元記事の日付から実際の日付にする（LLM が今日の日付で読み違えないように）"""
    if not isinstance(published, datetime):
        return []
    base = published.astimezone(JST_TZ)
    out, seen = [], set()
    for m in RELATIVE_DATE_RE.finditer(nfkc(text)):
        word = m.group(0)
        if word in seen:
            continue
        seen.add(word)
        y, mo = base.year, base.month
        if m.group(1):
            shift = {"来月": 1, "翌月": 1, "今月": 0, "先月": -1}[m.group(1)]
            mo += shift
            y += (mo - 1) // 12
            mo = (mo - 1) % 12 + 1
            day = int(m.group(2))
            if not 1 <= day <= 31:
                continue
            when = f"{y}年{mo}月{day}日"
        elif m.group(3):
            y += {"来年": 1, "翌年": 1, "今年": 0, "昨年": -1}[m.group(3)]
            month = int(m.group(4))
            if not 1 <= month <= 12:
                continue
            when = f"{y}年{month}月" + (f"{int(m.group(5))}日" if m.group(5) else "")
        else:
            fy = base.year if base.month >= 4 else base.year - 1
            fy += 1 if m.group(6) == "来年度" else 0
            when = f"{fy}年度（{fy}年4月〜{fy + 1}年3月）"
        out.append(Computed("date", f"元記事の「{word}」＝{when}（元記事の日付 {base:%Y年%m月%d日} から数えた日付。今日の日付から数えない）", []))
        if len(out) >= 4:
            break
    return out


def spec_difference(a_label: str, a: float, b_label: str, b: float, unit: str) -> Computed:
    """2つの製品の同じ項目の差（製品の比較表 scripts/rivals.py）。「Aの105Nm − Bの100Nm = 5Nm」。
    差は絶対値（どちらが大きいかは呼び出し側が文で書く）。単位はそろえてから渡す"""
    diff = abs(a - b)
    decimals = max(_decimals(a), _decimals(b))
    diff = round(diff, decimals)
    big, small = ((a_label, a), (b_label, b)) if a >= b else ((b_label, b), (a_label, a))
    show = lambda v: f"{v:,.{decimals}f}{unit}"  # noqa: E731
    return Computed("spec_diff", f"{big[0]}の{show(big[1])} − {small[0]}の{show(small[1])} = {show(diff)}", [diff])


def _decimals(value: float) -> int:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return len(text.split(".")[1]) if "." in text else 0


TAIL_RE = re.compile(r"\n\s*(?:あわせて読みたい|関連記事|関連ニュース|人気記事|この記事に関する|おすすめ記事|Related (?:articles|posts|stories)|More from)")


def compute(text: str, *, fx: dict | None = None, ladder_rows: list[dict] | None = None, past_rows: list[dict] | None = None,
            now: datetime | None = None, published: datetime | None = None, limit: int = 10) -> list[Computed]:
    """元記事の文章（と料金の段・過去記事・為替）から、計算済みの数字の一覧を作る（同じ結果は1つにまとめる）"""
    # ページの後ろの「あわせて読みたい」「人気記事」などの囲み（別の記事の数字）は計算に使わない
    text = TAIL_RE.split(text or "", maxsplit=1)[0]
    qs = extract(text)
    found: list[Computed] = relative_dates(text, published)
    found += ladder(ladder_rows or [])
    found += pace(qs) + annual(qs) + changes(qs) + implied_previous(qs) + shares(qs) + progress(qs) + per_unit(qs)
    found += past(qs[:40], past_rows or [], now)
    usd = [(q.value, "") for q in qs if q.unit == "USD" and q.value >= 1]
    monthly = {q.value for q in qs if q.unit == "USD" and re.search(r"月|month|/mo", q.sentence, re.I)}
    for r in ladder_rows or []:
        if isinstance(r.get("usd_month"), (int, float)) and r["usd_month"] > 0:
            usd.append((float(r["usd_month"]), f"{r['plan']}の月額"))
            monthly.add(float(r["usd_month"]))
    # 料金の段にある金額は段の名前つきで先に出す
    usd.sort(key=lambda x: x[1] == "")
    found += yen(usd, fx, monthly)
    out, seen = [], set()
    for c in found:
        key = c.text
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out[:limit]


def block(computed: list[Computed]) -> str:
    """プロンプト・事実確認に渡す「計算済みの数字」の行"""
    return "\n".join(f"- [C{i}] {c.text}" for i, c in enumerate(computed, 1))


# --------------------------------------------------------------------------- #
# 記事が自分で書いた簡単な計算（2026-11-08 オーナー決定・台帳 A64）
#   「1人50万円×2人＝100万円（サイソク編集部の計算）」のように、確かめた数字どうしの簡単な計算で、
#   「計算」「試算」と分かる書き方をしたものは、結果が合っていれば使ってよい数字とみなす。合わない式は門で直させる。
# --------------------------------------------------------------------------- #

CALC_LABEL_RE = re.compile(r"計算|試算")
_OP_NUM = r"\d[\d,]*(?:\.\d+)?[兆億万千]?(?:\d[\d,]*[億万千]?)*"
# 数字のあとの単位。「円/kWh」のような「〜あたり」の書き方も単位に含める（「/」を割り算と読まない）
_OP_UNIT = (r"(?:円|ドル|人|か月|ヶ月|カ月|ヵ月|か所|カ所|月|年|回|件|本|枚|台|日|時間|分|%|倍|口|社|個|世帯|歳"
            r"|kWh|m3|リットル|杯|品|点|食|泊|名|株|通|週)?(?:/[A-Za-z][A-Za-z0-9]{0,3})?")
_OPERAND = rf"\(*(?:{_OP_NUM}){_OP_UNIT}\)*"
# 「A×B＝C」「A÷12≒月C」「A＋(B−C)×1%＝約C」。答えの前の「約・月・年・合計」などは読み飛ばす（2026-11-13）
EXPR_RE = re.compile(
    rf"(?P<left>{_OPERAND}(?:\s*[×x*÷/+\-−]\s*{_OPERAND})+)\s*(?P<eq>=|≒)\s*(?P<pre>(?:約|およそ|月額|年額|合計|月|年|計){{0,2}})\s*"
    rf"(?P<right>{_OP_NUM})(?P<runit>{_OP_UNIT})"
)
SMALL_COUNT_MAX = 1000  # 「2人」「12か月」のような数（お金・割合でないもの）は、文にあれば計算の材料にしてよい
_OP_TOKEN_RE = re.compile(rf"({_OP_NUM})({_OP_UNIT})|([×x*÷/+\-−])|([()])")
_OPS = {"×": "*", "x": "*", "÷": "/", "−": "-"}


def _expr_eval(left: str, percent_as_fraction: bool = False) -> float | None:
    """式の左辺の値。percent_as_fraction: 「5%」を 0.05 として計算する（46万円×5% ＝ 23,000円）"""
    expr = []
    for num, unit, op, par in _OP_TOKEN_RE.findall(left):
        if num:
            value = repr(parse_jp(num))
            expr.append(f"({value}/100)" if percent_as_fraction and unit.startswith("%") else value)
        elif op:
            expr.append(_OPS.get(op, op))
        elif par:
            expr.append(par)
    try:
        return float(eval("".join(expr), {"__builtins__": {}}, {}))  # noqa: S307 - 数字と + - * / ( ) だけ
    except Exception:  # noqa: BLE001
        return None


def _expr_value(left: str) -> float | None:
    return _expr_eval(left)


def _percent_multiplied(left: str) -> bool:
    """割合（%）が、かけ算・割り算の相手になっているか（「46万円×5%」「5%×46万円」）。足し算・引き算だけ（「10%＋5%」）は False"""
    tokens = [(num, unit, op) for num, unit, op, par in _OP_TOKEN_RE.findall(left) if num or op]
    for i, (num, unit, _) in enumerate(tokens):
        if not num or not unit.startswith("%"):
            continue
        near = [tokens[j][2] for j in (i - 1, i + 1) if 0 <= j < len(tokens)]
        if any(op in ("×", "x", "*", "÷", "/") for op in near):
            return True
    return False


def _expr_candidates(m: re.Match) -> list[float]:
    """式の左辺の値の候補（答えと同じ表し方にそろえたもの）。
    - 割合がかけ算・割り算の相手のときは、割合として計算した値だけ（「46万円×5%＝23,000円」は合う。「＝2,300円」は合わない）
    - 答えが割合のとき（「2,500円÷50万円＝0.5%」）は 100 倍して比べる
    - 割合どうしの足し算・引き算（「10%＋5%＝15%」）と、割合の無い式は、数字のままの値も候補にする"""
    left = m.group("left")
    as_fraction = _expr_eval(left, percent_as_fraction=True)
    if as_fraction is None:
        return []
    out = [as_fraction * 100 if m.group("runit").startswith("%") else as_fraction]
    if not _percent_multiplied(left):
        plain = _expr_eval(left)
        if plain is not None:
            out.append(plain)
    return out


def expressions(text: str):
    """文章の中の式（EXPR_RE の一致）を順に返す。「A＝B＋C＝D」のように続く式は、B から始まる式としても読む"""
    pos = 0
    while m := EXPR_RE.search(text, pos):
        yield m
        pos = m.start("right") if _TAIL_RE.match(text, m.end()) else m.end()


_TAIL_RE = re.compile(rf"(?:[ \t]*[×x*÷/+\-−][ \t]*{_OPERAND})+")


def _middle_step(text: str, m: re.Match) -> tuple[str, float] | None:
    """「A＋(B−C)×1%＝85,800円＋7,140円＝92,940円」の真ん中のように、「＝」の右がまた式になっているとき（右の式の文字列, その値）。
    このときの「＝」の右の最初の数字（85,800円）は答えとは限らないので、左辺は右の式の値とも比べる
    （「1,000円＋200円＝1,200円＋300円＝1,500円」のように、答えに続けて足していく書き方もあるので、どちらかに合えばよい）"""
    tail = _TAIL_RE.match(text, m.end())
    if not tail:
        return None
    right = text[m.start("right"):tail.end()]
    value = _expr_eval(right, percent_as_fraction=True)
    return (right, value) if value is not None else None


def bad_expressions(text: str) -> list[str]:
    """「A×B＝C」のように書いた式で、計算が合わないもの（式の文字列）"""
    out = []
    t = nfkc(text or "")
    for m in expressions(t):
        got = _expr_candidates(m)
        want = parse_jp(m.group("right"))
        if not got or want == 0:
            continue
        wants = [want] + ([middle[1]] if (middle := _middle_step(t, m)) else [])
        if all(abs(g - w) > 0.011 * max(abs(w), 1e-9) for g in got for w in wants):
            out.append(m.group(0))
    return out


def _answer_matches(m: re.Match, got: float, want: float) -> bool:
    """式の値 got が、書かれた答え want と合うか。
    端数は1円（1単位）か0.1%まで。小数の答え（0.5%）はその桁の中、「21万円」のような書き方は表示の桁での切り捨て・四捨五入、
    「約」「≒」の付いた答えは1%まで。それ以上ずれる式は答えとして認めない"""
    diff = abs(got - want)
    step = display_step(m.group("right"))
    if diff <= max(1.0 if step >= 1 else step * 0.999, 0.001 * abs(want)):
        return True
    approx = m.group("eq") == "≒" or bool(re.search(r"約|およそ", m.group("pre") or ""))
    if approx and diff <= 0.011 * abs(want):
        return True
    return step > 1 and display_match(want, step, approx, got)


def _is_known(value: float, known: list[float]) -> bool:
    return any(abs(value - k) <= 1e-9 * max(1.0, abs(k)) for k in known)


def _operands_known(left: str, known: list[float]) -> bool:
    """式の材料が全部、確かめた数字か、文にある小さな数（お金・割合・1単位あたりの金額でないもの）か"""
    for num, unit, _op, _par in _OP_TOKEN_RE.findall(left):
        if not num:
            continue
        v = parse_jp(num)
        if _is_known(v, known):
            continue
        if not unit.startswith(("円", "ドル", "%")) and 0 < v <= SMALL_COUNT_MAX:
            continue
        return False
    return True


def _expression_ok(q: "Qty", verified: list[float], text: str) -> bool:
    """「A＋B×2＝C」「C＋D＝E」のように式を書いた計算で、q がその答えになっていて、
    式の数字がすべて確かめた数字・文にある小さな数（お金・割合でないもの）・前の式の答えのどれかで、
    式の答えが合っているか（2026-11-12 障害基礎年金の正しい2段の計算が落ちていたため。台帳 A64 の続き）。
    2026-11-13: 割合（3,000万円×0.7%＝21万円）・かっこ・「≒」「＝月」「＝約」の書き方も読む。合わない式は今までどおり認めない"""
    t = nfkc(text or "")
    if not t:
        return False
    known = list(verified)
    for m in expressions(t):
        got = _expr_candidates(m)
        want = parse_jp(m.group("right"))
        if not got or not want:
            continue
        if (middle := _middle_step(t, m)) and not any(_answer_matches(m, g, want) for g in got):
            # 「左辺＝P＋Q＝答え」の真ん中: 左辺が確かめた数字だけの式で、P＋Q（か P−Q）と合い、片方が分かっている数字なら、
            # もう片方は計算で決まる数字（途中の答え）として次の式の材料にしてよい
            parts = [(parse_jp(n), u) for n, u, _o, _p in _OP_TOKEN_RE.findall(middle[0]) if n]
            ops = [o for _n, _u, o, _p in _OP_TOKEN_RE.findall(middle[0]) if o]
            if (len(parts) == 2 and ops in (["+"], ["-"], ["−"]) and _operands_known(m.group("left"), known)
                    and any(abs(g - middle[1]) <= max(1.0, 0.001 * abs(middle[1])) for g in got)
                    and sum(1 for v, _u in parts if _is_known(v, known)) == 1):
                known += [v for v, _u in parts]
                if m.start() <= q.start and any(abs(v - q.value) <= 1e-9 * max(1.0, abs(q.value)) for v, _u in parts):
                    return True
            continue
        if not any(_answer_matches(m, g, want) for g in got):
            continue
        if not _operands_known(m.group("left"), known):
            continue
        known.append(want)
        # 式の答えそのもの、またはそのあとの文で同じ答えを使ったところ
        if abs(want - q.value) <= 1e-9 * max(1.0, abs(q.value)) and m.start() <= q.start:
            return True
    return False


PARAGRAPH_CAP = 1500


def _labelled_block(q: "Qty", text: str) -> bool:
    """q のある段落（空行で区切ったまとまり。表・箇条書きはすぐ次の段落まで）に「計算」「試算」と書いてあるか。
    式を何行も並べて、最後に1回だけ「（サイソク編集部の計算）」と添える書き方のため"""
    t = nfkc(text or "")
    if not t or q.start > len(t):
        return False
    start = t.rfind("\n\n", 0, q.start)
    start = 0 if start < 0 else start + 2
    end = t.find("\n\n", q.end)
    end = len(t) if end < 0 else end
    line_start = t.rfind("\n", 0, q.start) + 1
    if t[line_start:line_start + 2].lstrip()[:1] in ("|", "-", "*", "・"):
        nxt = t.find("\n\n", end + 2)
        end = len(t) if nxt < 0 else nxt
    block = t[max(start, q.start - PARAGRAPH_CAP):min(end, q.end + PARAGRAPH_CAP)]
    return bool(CALC_LABEL_RE.search(block))


def derived(q: "Qty", verified: list[float], text: str = "") -> bool:
    """記事の数字 q が、「計算」「試算」と分かる書き方の文で、確かめた数字（verified）どうし（か、文にある小さな数）の
    1回の足し算・引き算・かけ算・割り算、または同じ単位の数字の合計で出せるか。
    式を書いた計算なら、2段の計算（A＋B×2）や前の式の答えを使う計算も、答えが合っていれば認める"""
    if not CALC_LABEL_RE.search(q.sentence or ""):
        # 式を書いた計算だけは、同じ段落に「計算」とあればよい（式が合い、材料が確かめた数字のときだけ。2026-11-13）
        return bool(text) and _labelled_block(q, text) and _expression_ok(q, verified, text)
    if text and _expression_ok(q, verified, text):
        return True
    # 同じ文と、その直前（2文くらい）の数字を材料にする
    window = q.sentence
    if text:
        t = nfkc(text)
        window = t[max(0, q.start - 160):q.end + 40]
    ops, verified_ops = [], []
    for x in extract(window):
        if abs(x.value - q.value) < 1e-9 and x.unit == q.unit:
            continue
        if supported(x, verified):
            ops.append(x.value)
            verified_ops.append(x.value)
        elif not x.is_money and x.unit != "%" and 0 < x.value <= SMALL_COUNT_MAX:
            ops.append(x.value)
    if not verified_ops:
        return False
    ops = list(dict.fromkeys(ops))[:30]
    results = []
    for a in verified_ops:
        for b in ops:
            results += [a * b, a + b, abs(a - b)]
            if b:
                results.append(a / b)
            if a:
                results.append(b / a)
    results.append(sum(dict.fromkeys(verified_ops)))
    return supported(q, [r for r in results if r])


def main() -> int:
    text = " ".join(sys.argv[1:]) or sys.stdin.read()
    for c in compute(text):
        print(f"[{c.kind}] {c.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
