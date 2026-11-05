#!/usr/bin/env python3
"""発表時刻が決まった速報（統計・決算）の記事の書き方と合格の基準（2026-11-05 オーナー承認・台帳 W35）。

オーナーの決まり: 速さで質を落とさない。正確さと自然でプロの日本語が先、速さは二の次。数字はすべて公式の発表そのものから。
予想で埋めない・空欄の型で先に出さない。

- prompt_note(release): 記事を書く段に渡す注意（数字の優先順・題名とリードの決め方・比べる基準・速報値・予想の言い方）。
  予定表（scripts/release_calendar.json の article）から作る。文面の見本は渡さない（記事は毎回、資料から新しく書く）。
- release_problems(record, source_text): 公開前の門（quality.structural_problems から。速報レーン・作り直しのどの段でも同じ）。
  1. 題名・リード・要点・SNS の投稿文の数字（金額・割合・連続の月数など）が、公式の資料の文字にあるか。表の単位（百万円・千円・円 銭）は
     記事の単位（兆・億・万・円）に直して照合し、記事の表示の桁での切り捨て・四捨五入まで同じとみなす（2,191,124百万円 → 2兆1,911億円。
     2026-11-05 決算の速報が正しい数字でも止まった件）。17.50 と 17.5円・17円50銭、△12.1 と「12.1%減」も同じ
  2. 単位（%と円・前期比の年率など）を取り違えていないか（資料の同じ値と単位で照合）
  3. 増減の向き（増・減・上昇・低下・プラス・マイナス・▲）が資料と逆になっていないか
  4. 比べる基準（前年同月比など）をリードに書いているか（言いかえ・「1兆円から1.3兆円に」の書き方も可。basis_written）・速報値なら「速報」と書いているか
  5. 予想・見通しの言い方を、資料に無いのに事実のように書いていないか（市場予想・他社の報道の数字を使わない）
  6. 空欄の印（○○・XX など）が残っていないか・出典が予定表の公式の発表か
"""

from __future__ import annotations

import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calc_facts  # noqa: E402  表の数字（百万円・千円・△）と記事の数字（兆・億・万）の照合（display_match・table_numbers）

NUM = r"\d+(?:,\d{3})*(?:\.\d+)?"
# 「2兆1,911億」「242億1,400万」「1兆2,345億6,700万」のような組み合わせの数
JP_NUM = rf"{NUM}(?:\s?[兆億万](?:\s?{NUM})?)*"
# 題名・リード・要点で確かめる数字（単位つき）。「17円50銭」の銭も読む
QTY_RE = re.compile(rf"(?P<neg>[▲△-]|マイナス)?\s?(?P<num>{JP_NUM})\s?(?P<unit>円|%|ポイント|pt|か月|カ月|ヵ月|ヶ月|ケ月|四半期|倍)(?:\s?(?P<sen>\d{{1,2}})\s?銭)?")
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
        value = calc_facts.parse_jp(m.group("num"))
        unit = m.group("unit")
        if m.group("sen") and unit == "円":
            value += float(m.group("sen")) / 100
        unit = {"pt": "ポイント", "カ月": "か月", "ヵ月": "か月", "ヶ月": "か月", "ケ月": "か月"}.get(unit, unit)
        start, end = m.start(), m.end()
        before = text[max(0, start - 14):start]
        after = text[end:end + 10]
        out.append({
            "value": value, "unit": unit, "text": m.group(0).strip(), "neg": bool(m.group("neg")),
            "approx": bool(re.search(r"(?:約|およそ|ほぼ)\s?$", before) or re.match(r"\s?(?:程度|前後|強|弱|超|余り)", after)),
            "before": before, "after": after,
            # 表示の最後の桁の1つ分（「約43万円」なら1万円、「2兆1,911億円」なら1億円、「29万7,145円」なら1円）
            "step": calc_facts.display_step(m.group(0)),
        })
    return out


def _table_qtys(source: str) -> list[dict]:
    """資料の表の単位の付いていない数字（決算短信の 2,191,124〔百万円〕・△12.1〔%〕・17.50〔円 銭〕）を、記事と同じ単位の候補にする"""
    unit_of = {"JPY": "円", "%": "%"}
    return [{"value": t.value, "unit": unit_of[t.unit], "text": t.raw, "neg": t.neg, "approx": False, "before": "", "after": "",
             "step": 0.0, "table": True} for t in calc_facts.table_numbers(source)]


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
    """記事の数字 a と資料の数字 s が同じか。
    - 円: 資料の値を記事の表示の桁で切り捨てか四捨五入したもの（2,191,124百万円 → 2兆1,911億円、24,214百万円 → 242億1,400万円）。
      有効数字1桁の書き方（「2兆円」）は「約」「超」付きのときだけ
    - %・ポイントなど: 同じ値（17.50 と 17.5 は同じ）。「約」付きなら表示の桁での四捨五入まで
    - 符号は向きの確かめ（_direction）で見るので、ここでは絶対値で比べる（△12.1 と「12.1%減」）"""
    if a["unit"] != s["unit"]:
        return False
    if abs(abs(a["value"]) - abs(s["value"])) < 1e-9:
        return True
    if a["unit"] == "円":
        return calc_facts.display_match(a["value"], a["step"], a["approx"], s["value"])
    if a["approx"] and a["step"]:
        return abs(abs(a["value"]) - abs(s["value"])) <= a["step"] / 2 + 1e-9
    return False


# 比べる基準の言いかえ（自然な書き方を認める。2026-11-05 決算の速報が「前年同期より」「1兆円から1.3兆円に」で止まった件）
BASIS_SYNONYMS = {
    "前年同期": ["前年同期", "前年の同じ時期", "前の年の同じ時期", "1年前の同じ時期", "前年同四半期", "前年の同じ期間"],
    "前年同月": ["前年同月", "前年の同じ月", "前の年の同じ月", "1年前の同じ月", "1年前"],
    "前年度": ["前年度", "前の年度", "前期"],
    "前年": ["前年", "前の年", "1年前", "昨年"],
    "前期": ["前期", "前の期", "前四半期", "前の四半期", "直前の四半期"],
    "前月": ["前月", "前の月", "先月"],
    "変更前": ["変更前", "修正前", "前回予想", "前回の予想", "従来予想", "従来の予想", "これまでの予想", "当初予想", "当初の予想", "期初の予想"],
    "前回予想": ["前回予想", "前回の予想", "従来予想", "従来の予想", "これまでの予想", "変更前", "修正前", "当初予想"],
}
# 「1兆円から1.3兆円に」「1兆円→1.3兆円」のように、前の値と新しい値を並べた書き方（比べたものが読者に分かる）
CHANGE_RE = re.compile(rf"{JP_NUM}\s?(?:円|%|ドル)?\s?(?:から|→|⇒|➡)\s?(?:約)?{JP_NUM}\s?(?:円|%|ドル)?")


def basis_written(basis: str, lede_title: str) -> bool:
    """題名・リードに比べる基準が書かれているか。言いかえ（「前年同期より」「前年の同じ時期」）・前の値からの変化の書き方
    （「1兆円から1.3兆円に」）・基準の日付（「8月に公表した予想」）も認める。基準をまったく書かないリードは通さない"""
    basis = _nfkc(basis)
    text = _nfkc(lede_title)
    key = re.split(r"[（(]", basis)[0].strip().removesuffix("比").strip()
    if not key:
        return True
    words = {key}
    for k, synonyms in BASIS_SYNONYMS.items():
        if key == k:
            words.update(synonyms)
    if any(w in text for w in words):
        return True
    if CHANGE_RE.search(text):
        return True
    # 基準に日付が書いてある（「変更前（2026年8月4日の取締役会決議）」）とき、その月の予想・公表を書いていればよい
    if m := re.search(r"(\d{1,2})月(?:\d{1,2}日)?", basis):
        if re.search(rf"(?<!\d){m.group(1)}月[^。]{{0,12}}?(?:予想|公表|発表|決議|計画)", text):
            return True
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
    src_q = _qtys(source) + _table_qtys(source)
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
                # 表の符号の無い数字（増えた向き）は向きが分からないものとして扱う（同じ値の別の行の △ で誤って止めない）
                unsigned_table = any(s.get("table") and not s["neg"] for s in same)
                if mine and theirs and mine not in theirs and not unsigned_table:
                    problems.append(f"{label}の「{q['text']}」の増減の向きが資料と逆（資料は{'増加・上昇' if 1 in theirs else '減少・低下'}）")
    lede_title = _nfkc(f"{record.get('title') or ''}\n{record.get('lede') or ''}")
    basis = _nfkc(str(release.get("basis") or ""))
    if basis and not basis_written(basis, lede_title):
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
