"""出典の資料の日付・会議の回と、記事が書く出来事が合っているかの門（Muse の記事。2026-11-10）。

きっかけ: 2026-11-10 の Muse の記事（取り下げ kokuho-genkagaku-limit-proposal）が、第205回 医療保険部会（令和7年11月27日）の
資料（001599957.pdf）にあった「令和8年度に医療分を92万円→93万円」の案を、資料がまだ出ていない第220回（令和8年11月11日）の
部会の議題であるかのように書いた。

見ること（文字の照合だけ。LLM もネットも使わない）:
1. 出典ごとに、その資料自身の日付・会議の回を取り出す（題名・Muse が付けた名前・本文の冒頭。例「令和7年11月27日 第205回…資料3」）。
2. 記事が「今の案」「N日の部会」のように今の出来事として書いていて（_CURRENT_RE / 会議の日付）、案の数字が
   古い資料（記事の日付より60日より前、または記事の会議と違う第N回）にしか無いときは止める。
   記事が「前年の資料では」「第205回の資料では」のように、古い資料だと分かるように書いていればよい。
3. これから開かれる会議（今日・あす以降）について「〜の案」「案が示されている」と中身を書いているのに、その会議の資料が
   出典に無いとき（資料の公表前）は止める。
決まったルールの解説（2024年の法律など）は「今の案・会議の日付」を書かないので、この門には当たらない。
止めたときは理由を日本語で返し、書き直しの段（scripts/muse_articles.py の試行）で直させる。
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

STALE_DAYS = 60
HEAD_CHARS = 1200

_BODIES = r"(?:社会保障審議会|審議会|部会|分科会|委員会|検討会|会議|会合|懇談会)"
_ERA = {"令和": 2018, "平成": 1988}
_DATE_RES = [
    re.compile(r"(令和|平成)(\d{1,2}|元)年(\d{1,2})月(\d{1,2})日"),
    re.compile(r"(20\d\d)年(\d{1,2})月(\d{1,2})日"),
    re.compile(r"(20\d\d)[/.](\d{1,2})[/.](\d{1,2})"),
]
_MEETING_RE = re.compile(r"第(\d{1,4})回")
_FY_RE = re.compile(r"(?:令和(\d{1,2}|元)|(20\d\d))年度")
# 今の出来事・今の案として書いている印
_CURRENT_RE = re.compile(r"案(?:が|を)?(?:示|提示)|提案(?:です|して|され|した|する)|案です|議論へ|審議へ|議論される(?:予定|見通し)|議論する(?:予定|見通し)|で議論")
# 案・見直しの中身を書いている文（数字を比べる文）
_PROPOSAL_SENT_RE = re.compile(r"案|提案|引き?上げ|引上げ|上げる|下げる|見直|据え?置")
# 古い資料だと分かるように書いている印（その文は数字を比べない）
_EARLIER_RE = re.compile(r"前年|昨年|去年|前回|前年度|過去|以前|かつて|当時|これまで|一昨年")
_FIGURE_RE = re.compile(r"(?<![\d.])(\d[\d,]*(?:\.\d+)?)(万円|億円|兆円|円|%|倍|万人|世帯)")
_DAY_BODY_RE = re.compile(r"(?:(\d{1,2})月)?(\d{1,2})日(?:\([^)]{1,3}\))?(?:に開(?:かれる|く|催される|催)|開催)?の?" + _BODIES)
_BODY_DAY_RE = re.compile(_BODIES + r"(?:は|が|を)(?:(\d{1,2})月)?(\d{1,2})日")
_NOT_MATERIAL_RE = re.compile(r"開催案内|開催について|開催のお知らせ")


def _n(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or ""))


def _era_year(era: str, num: str) -> int:
    return _ERA[era] + (1 if num == "元" else int(num))


def dates_in(text: str) -> list[date]:
    out = []
    text = _n(text)
    for i, rx in enumerate(_DATE_RES):
        for m in rx.finditer(text):
            try:
                year = _era_year(m.group(1), m.group(2)) if i == 0 else int(m.group(1))
                month, day = (int(m.group(3)), int(m.group(4))) if i == 0 else (int(m.group(2)), int(m.group(3)))
                out.append(date(year, month, day))
            except (ValueError, KeyError):
                continue
    return out


def identify(source: dict, today: date) -> dict:
    """出典自身の日付（冒頭で見つかったいちばん新しい日付）・会議の回（冒頭に1つだけあるとき）・年度の表記・資料かどうか"""
    label = _n(" ".join(str(source.get(k) or "") for k in ("title", "name")))
    head = label + "\n" + _n(str(source.get("text") or source.get("full_text") or "")[:HEAD_CHARS])
    found = [d for d in dates_in(head) if d <= today + timedelta(days=400)]
    meetings = {int(x) for x in _MEETING_RE.findall(head)}
    fy = sorted({(_era_year("令和", a) if a else int(b)) for a, b in _FY_RE.findall(head)})
    return {
        "date": max(found) if found else None,
        # 一覧のページ（回がいくつも並ぶ）は、どの会議の資料とも言えない
        "meeting": next(iter(meetings)) if len(meetings) == 1 else None,
        "fy": fy,
        "material": "資料" in head[:300] and len(meetings) <= 1 and not _NOT_MATERIAL_RE.search(label),
        "name": str(source.get("name") or source.get("title") or source.get("url") or "")[:80],
        "body": _n(str(source.get("full_text") or source.get("text") or "")).replace(",", "").replace(" ", ""),
    }


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[。!?])|\n+", _n(text)) if s.strip()]


def _figures(sentence: str) -> set[str]:
    return {f"{m.group(1).replace(',', '')}{m.group(2)}" for m in _FIGURE_RE.finditer(sentence)}


def _figures_in_order(sentence: str) -> list[str]:
    return [f"{m.group(1).replace(',', '')}{m.group(2)}" for m in _FIGURE_RE.finditer(sentence)]


def _has_figure(body: str, figure: str) -> bool:
    return re.search(r"(?<![\d.])" + re.escape(figure), body) is not None


def _meeting_dates(sentence: str, today: date) -> list[date]:
    out = []
    for m in list(_DAY_BODY_RE.finditer(sentence)) + list(_BODY_DAY_RE.finditer(sentence)):
        month, day = m.group(1), m.group(2)
        year = re.search(r"(?:(令和|平成)(\d{1,2}|元)|(20\d\d))年$", sentence[max(0, m.start() - 8):m.start()]) if month else None
        try:
            y = (_era_year(year.group(1), year.group(2)) if year.group(1) else int(year.group(3))) if year else today.year
            when = date(y, int(month) if month else today.month, int(day))
        except ValueError:
            continue
        if month and not year and when < today - timedelta(days=180):
            when = when.replace(year=today.year + 1)
        out.append(when)
    return out


def _fmt(d: date | None) -> str:
    return f"{d.year}年{d.month}月{d.day}日" if d else "日付不明"


def _mentions(article: str, ident: dict) -> bool:
    """記事が、その資料の回・日付をはっきり書いている（「第205回の資料では」「令和7年11月27日の部会で」）"""
    if ident["meeting"] is not None and f"第{ident['meeting']}回" in article:
        return True
    d = ident["date"]
    return bool(d) and any(x == d for x in dates_in(article))


def check(article_texts, sources: list[dict], today: date) -> list[str]:
    """問題（日本語の理由）の一覧。空なら通す。article_texts は記事の文（題名・本文など）の列か1つの文字列"""
    article = _n("\n".join(article_texts) if isinstance(article_texts, (list, tuple)) else article_texts)
    sentences = _sentences(article)
    meeting_refs = [(s, d) for s in sentences for d in _meeting_dates(s, today)]
    named = {int(x) for x in _MEETING_RE.findall(article)}
    if not (meeting_refs or named or _CURRENT_RE.search(article)):
        return []  # 今の出来事・今の案として書いていない（決まったルールの解説など）
    idents = [identify(s, today) for s in sources if s]
    if not idents:
        return []
    target = set(named)
    if not target and idents[0]["meeting"] is not None:
        target = {idents[0]["meeting"]}
    target_dates = sorted({d for _, d in meeting_refs})

    def stale(ident: dict) -> bool:
        if ident["date"] and ident["date"] < today - timedelta(days=STALE_DAYS):
            return True
        return bool(target) and ident["meeting"] is not None and ident["meeting"] not in target

    problems: list[str] = []
    old = [i for i in idents if stale(i) and not _mentions(article, i)]
    others = [i for i in idents if not stale(i)]
    if old:
        claims = [s for s in sentences if _PROPOSAL_SENT_RE.search(s) and not _EARLIER_RE.search(s)]
        for ident in old:
            only_old = list(dict.fromkeys(f for s in claims for f in _figures_in_order(s)
                                          if _has_figure(ident["body"], f) and not any(_has_figure(o["body"], f) for o in others)))
            if not only_old:
                continue
            what = "・".join(x for x in [f"第{ident['meeting']}回の会議" if ident["meeting"] else "", _fmt(ident["date"])] if x)
            event = "・".join(x for x in ["・".join(f"第{n}回" for n in sorted(target)), "・".join(_fmt(d) for d in target_dates)] if x)
            fy = f"（資料の年度の表記: {'・'.join(f'{y}年度' for y in ident['fy'][:3])}）" if ident["fy"] else ""
            problems.append(
                f"出典の日付が記事の出来事と合いません: 「{ident['name']}」は{what}の資料{fy}で、"
                f"記事が書く出来事{f'（{event}）' if event else '（今の案）'}の資料ではありません。"
                f"記事の「{'」「'.join(only_old[:3])}」はこの古い資料にしか無い数字です。今の案として書かず、"
                f"「前年（{_fmt(ident['date'])}）の資料では」のように古い資料だと分かるように書くか、新しい資料を出典にしてください")
    # これから開かれる会議の「案」の中身を、その会議の資料なしに書いている
    for sentence, when in meeting_refs:
        if when < today or not re.search(r"案|提案", sentence):
            continue
        if not (_figures(sentence) or re.search(r"示|提示|資料", sentence)):
            continue
        has_material = any(i["material"] and not stale(i) and (
            (i["meeting"] is not None and i["meeting"] in target) or (i["date"] and abs((i["date"] - when).days) <= 2))
            for i in idents)
        if not has_material:
            problems.append(
                f"まだ資料が公表されていない会議の案の中身を書いています: 「{sentence[:60]}」。{_fmt(when)}の会議の資料は出典にありません。"
                "「案が示されている」と書かず、「この日の会議で〜が議題になる予定（資料は未公表）」とだけ書いてください")
            break
    return problems


def record_texts(record: dict) -> list[str]:
    """記事の JSON から、読者が読む文（題名・リード・本文・SNS の文など）"""
    out = [str(record.get(k) or "") for k in ("title", "seoTitle", "lede", "description", "summaryLine", "body", "easy", "threadsPost")]
    out += [str(h) for h in record.get("highlights") or []]
    return [t for t in out if t]
