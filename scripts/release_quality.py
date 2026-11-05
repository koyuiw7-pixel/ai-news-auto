#!/usr/bin/env python3
"""発表時刻が決まった速報（統計・決算）の記事の書き方と合格の基準（2026-11-05 オーナー承認・台帳 W35）。

オーナーの決まり: 速さで質を落とさない。正確さと自然でプロの日本語が先、速さは二の次。数字はすべて公式の発表そのものから。
予想で埋めない・空欄の型で先に出さない。

- prompt_note(release): 記事を書く段に渡す注意（数字の優先順・題名とリードの決め方・比べる基準・速報値・予想の言い方）。
  予定表（scripts/release_calendar.json の article）から作る。文面の見本は渡さない（記事は毎回、資料から新しく書く）。
- release_problems(record, source_text): 公開前の門（quality.structural_problems から。速報レーン・作り直しのどの段でも同じ）。
  1. 題名・リード・要点・SNS の投稿文の数字（金額・割合・連続の月数など）が、公式の資料の文字にそのままあるか（丸めは「約」付きで資料の値の丸めだけ）
  2. 単位（%と円・前期比の年率など）を取り違えていないか（資料の同じ値と単位で照合）
  3. 増減の向き（増・減・上昇・低下・プラス・マイナス・▲）が資料と逆になっていないか
  4. 比べる基準（前年同月比など）をリードに書いているか・速報値なら「速報」と書いているか
  5. 予想・見通しの言い方を、資料に無いのに事実のように書いていないか（市場予想・他社の報道の数字を使わない）
  6. 空欄の印（○○・XX など）が残っていないか・出典が予定表の公式の発表か
"""

from __future__ import annotations

import re
import unicodedata
import urllib.parse

NUM = r"\d+(?:,\d{3})*(?:\.\d+)?"
# 題名・リード・要点で確かめる数字（単位つき）
QTY_RE = re.compile(rf"(?P<neg>[▲△-]|マイナス)?\s?(?P<num>{NUM})\s?(?P<mult>兆|億|万)?(?:(?P<num2>{NUM})\s?(?P<mult2>億|万)?)?\s?(?P<unit>円|%|ポイント|pt|か月|カ月|ヵ月|ヶ月|ケ月|四半期|倍)")
UP_RE = re.compile(r"増|上昇|プラス|伸び|上回|拡大|黒字")
DOWN_RE = re.compile(r"減|低下|下落|マイナス|落ち込|下回|縮小|赤字|▲|△")
PLACEHOLDER_RE = re.compile(r"[○〇◯●]{2,}|[XxＸｘ]{2,}|××|＿＿|__|\{[a-z_]+\}|【数字】|（数字）|\?\?")
FORECAST_RE = re.compile(r"見込み|見込まれ|予想|予測|見通し|とみられ|と見られ|になりそう|しそうだ|可能性が高い|公算")
PRELIM_RE = re.compile(r"速報")


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def prompt_note(release: dict) -> str:
    """記事を書く段に渡す注意（予定表の article から。見本の文は渡さない）"""
    if not release:
        return ""
    figures = "\n".join(f"  {i}. {f}" for i, f in enumerate(release.get("figures") or [], 1))
    prelim = "これは速報値。題名かリードのどこかに「速報」と書き、確報で改訂されうることを本文で一言触れる。" if release.get("preliminary") else ""
    return f"""

## 発表時刻が決まった公式発表の速報です（正確さが最優先。台帳 W35）
発表元: {release.get('publisher', '')}（{release.get('name', '')}）。材料は発表元の公式の資料の文字だけ。
- 数字はすべて上の資料の文字にあるものを、そのまま（桁・小数点・単位・増減の向きを変えずに）使う。資料に無い数字・自分で計算した数字・
  市場の予想・他の報道の数字は書かない。資料に無い項目は書かない（空欄や「〇〇」を残さない）。
- 拾う数字の優先順:
{figures}
- {release.get('leadRule', '')}
- 比べる基準（{release.get('basis', '')}）を、リードの数字のそばに必ず書く（何と比べた増減かを取り違えない）。{prelim}
- 予想・見通しは、資料が発表元の予想として書いているときだけ「〇〇の予想では」と分かるように書き、事実として書かない。
- {release.get('notes', '')}
- 読者順の型のまま書く（題名＝結論と一番の数字、リード3文＝結論・数字・読者の家計や仕事への意味）。読者への意味は資料の事実から言える範囲だけにし、
  煽らない。統計の数字を書き写すだけで終わらせない。
"""


def _qtys(text: str) -> list[dict]:
    out = []
    text = _nfkc(text)
    for m in QTY_RE.finditer(text):
        value = float(m.group("num").replace(",", ""))
        mult = {"兆": 1e12, "億": 1e8, "万": 1e4}.get(m.group("mult") or "", 1)
        value *= mult
        if m.group("num2"):
            value += float(m.group("num2").replace(",", "")) * {"億": 1e8, "万": 1e4}.get(m.group("mult2") or "", 1)
        unit = m.group("unit")
        unit = {"pt": "ポイント", "カ月": "か月", "ヵ月": "か月", "ヶ月": "か月", "ケ月": "か月"}.get(unit, unit)
        start, end = m.start(), m.end()
        before = text[max(0, start - 14):start]
        after = text[end:end + 10]
        out.append({
            "value": value, "unit": unit, "text": m.group(0).strip(), "neg": bool(m.group("neg")),
            "approx": bool(re.search(r"(?:約|およそ|ほぼ)\s?$", before) or re.match(r"\s?(?:程度|前後|強|弱)", after)),
            "before": before, "after": after,
            # 丸めの幅（「約43万円」なら1万円、「約42.6万円」なら1,000円）。2つ目の数がある書き方（29万7,145円）は丸めない
            "step": 1.0 if m.group("num2") else mult / 10 ** (len(m.group("num").split(".")[1]) if "." in m.group("num") else 0),
        })
    return out


def _direction(q: dict) -> int:
    """数字のすぐ後ろ（なければ前）の増減の語の向き。+1 / -1 / 0（分からない）"""
    if q["neg"]:
        return -1
    after = re.split(r"[、。,]", q["after"], maxsplit=1)[0]
    if DOWN_RE.search(after[:6]):
        return -1
    if UP_RE.search(after[:6]):
        return 1
    return 0


def _matches(a: dict, s: dict) -> bool:
    if a["unit"] != s["unit"]:
        return False
    if abs(a["value"] - s["value"]) < 1e-9:
        return True
    if a["approx"] and a["unit"] == "円":
        # 「約43万円」= 資料の 426,337 円 を表示の桁で丸めたものだけ許す（丸めの幅の半分まで）
        return abs(a["value"] - s["value"]) <= a["step"] / 2 + 1e-6
    return False


def _fields(record: dict) -> list[tuple[str, str]]:
    return [("題名", record.get("title") or ""), ("リード", record.get("lede") or "")] + \
        [("要点", h) for h in record.get("highlights") or []] + [("SNS の投稿文", record.get("threadsPost") or "")]


def release_problems(record: dict, source_text: str) -> list[str]:
    release = record.get("scheduledRelease")
    if not release:
        return []
    problems: list[str] = []
    source = _nfkc(source_text)
    if not source.strip():
        return ["公式の資料の文字が無いので、数字を確かめられない（速報にしない）"]
    src_q = _qtys(source)
    all_text = "\n".join(str(record.get(k) or "") for k in ("title", "lede", "body", "easy")) + "\n" + "\n".join(record.get("highlights") or [])
    if m := PLACEHOLDER_RE.search(_nfkc(all_text)):
        problems.append(f"空欄の印（「{m.group(0)}」）が残っている。資料の数字を入れるか、その文を削る")
    for label, text in _fields(record):
        for q in _qtys(text):
            same = [s for s in src_q if _matches(q, s)]
            if not same:
                problems.append(f"{label}の数字「{q['text']}」が公式の資料に無い（桁・単位・丸めを資料どおりに。資料に無い数字は書かない）")
                continue
            if q["unit"] in ("%", "ポイント", "円"):
                mine = _direction(q)
                theirs = {_direction(s) for s in same} - {0}
                if mine and theirs and mine not in theirs:
                    problems.append(f"{label}の「{q['text']}」の増減の向きが資料と逆（資料は{'増加・上昇' if 1 in theirs else '減少・低下'}）")
    lede_title = _nfkc(f"{record.get('title') or ''}\n{record.get('lede') or ''}")
    basis = _nfkc(str(release.get("basis") or ""))
    key = re.split(r"[（(]", basis)[0].removesuffix("比")
    if key and key not in lede_title:
        problems.append(f"題名・リードに比べる基準（{basis}）が書かれていない。何と比べた増減かをリードの数字のそばに書く")
    if release.get("preliminary") and not PRELIM_RE.search(lede_title):
        problems.append("速報値なのに、題名・リードに「速報」と書かれていない")
    for label, text in _fields(record):
        for m in FORECAST_RE.finditer(_nfkc(text)):
            if m.group(0) not in source:
                problems.append(f"{label}に予想・見通しの言い方（「{m.group(0)}」）があるが、公式の資料に無い。資料の事実だけを書く")
                break
    hosts = set(release.get("hosts") or [])
    host = (urllib.parse.urlsplit(str(record.get("sourceUrl") or "")).hostname or "").lower()
    if hosts and host not in hosts:
        problems.append(f"出典（{host}）が予定表の公式の発表（{', '.join(sorted(hosts))}）ではない")
    return problems
