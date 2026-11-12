#!/usr/bin/env python3
"""新しい記事に「サイソクの見方」の章を必ず入れ、中身の薄い記事を出さない（2026-11-12 オーナー・AdSense「有用性の低いコンテンツ」の2回目の不承認）。

オーナー: 「ただの公式の書写しじゃなくてこちら側の見解とか、読者のためになる情報に進化させるイメージ」。
公式ページより読む価値のある記事にするため、すべての新しい記事（自動の記事 web_articles・動画 main・Muse・深掘り deep_dive）で:

1. 書く段（プロンプト）: 本文の後半に「## サイソクの見方：<中身の言葉>」の章（2〜4文）を置く。中身は
   なぜ今か（過去の公式の数字・経緯）／誰が得をし誰が損をするか・どのくらいか（計算は「計算済みの数字」だけ）／
   読者の判断の目安（「〜ならA、〜ならB」）。根拠は記事の中の事実だけ。見方は見方として書き、事実のように断定しない。
2. 門: 暮らしとお金のジャンル（LIFE_GENRES）の記事にこの章と判断の目安が無ければ、1回だけ自動で足す（ensure）。
   足したあとも、ふつうの事実確認（quality.evaluate）を通す（嘘だけを落とす門は変えない）。それでも章が残らなければ出さない（hold_reason）。
3. 中身の下限: 本文が EXPAND_BELOW 字未満なら、公式の資料にある事実だけで1回書き足す。それでも HOLD_BELOW 字未満なら出さない。
   速報・大きなニュース・速報レーン・地震や災害・お知らせや注意喚起（public_interest.short_ok）は急ぐので、書き足しも保留もしない。

しきい値は 2026-11-12 に直近7日の記事（532本・暮らしとお金319本）で測って決めた（tests/test_own_view_20261112.py に数字）:
  本文1,000字未満は暮らしとお金の37%（書き足しの対象）。500字未満で速報・注意喚起でないものは7.5%（24本。保留の上限の見込み）。
  600字にすると11.9%（38本）になり、オーナーの許容（約10%）を超えるので500字にした。
"""
from __future__ import annotations

import re
import unicodedata

# 暮らしとお金の「自分ごと」ニュース（台帳 A61）のジャンル。お金・制度・暮らし・ビジネス・投資・不動産
LIFE_GENRES = frozenset({"business", "investment", "real-estate", "public", "lifestyle"})
VIEW_LABEL = "サイソクの見方"
EXPAND_BELOW = 1000  # これ未満は公式の資料の事実で1回書き足す
HOLD_BELOW = 500  # 書き足したあともこれ未満なら出さない（速報・注意喚起は除く）
VIEW_MIN_SENTENCES = 2
VIEW_MAX_SENTENCES = 6  # 決まりは2〜4文。箇条書きの目安（「〜なら」）が並ぶ章は少し長くてもよい

VIEW_HEADING_RE = re.compile(rf"^##[ \t　]+{VIEW_LABEL}(?:[ \t　]*[：:][^\n]*)?[ \t　]*$", re.M)
_NEXT_H2_RE = re.compile(r"^## ", re.M)
UNKNOWN_H2_RE = re.compile(r"^## まだ分からないこと", re.M)
# 読者の判断の目安・すること（「〜なら」「〜場合は」「確かめる」「申し込む」「待つ」「見送る」「選ぶ」）
JUDGE_RE = re.compile(r"なら|場合(?:は|、|に)|かどうか|確かめ|確認し|確認する|見送|待つ|待ち|申し込|申請|選ぶ|選び|選べ|比べ|見直")
_SENT_SPLIT_RE = re.compile(r"(?<=[。！？])")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")

PROMPT_RULE = f"""
# {VIEW_LABEL}（必ず書く章。2026-11-12 オーナー「公式の書き写しではなく、こちらの見解と読者のためになる情報に」）
公式の発表を言い換えるだけの記事にしない。本文の後半（「## まだ分からないこと」の章があればその前）に、次の章を1つ置く。
- 見出しは「## {VIEW_LABEL}：」に続けて、この記事でしか使えない中身の言葉を書く（例「## {VIEW_LABEL}：急がないなら固定5年、1年以内に使うなら見送り」）。
- 本文は2〜4文（判断の目安を箇条書きにしてもよい）。次の3つのうち、材料のあるものを入れる（材料の無い部分は書かない）。
  1. なぜ今か: 元記事・確認済みの事実の束・サイソクの過去記事にある前回や過去の公式の数字・経緯と比べて、今回の何が違うか（日付は資料どおり）。
  2. 誰が得をし、誰が損をするか・どのくらいか: 対象の人と、資料にある金額・期間。計算した数字は「計算済みの数字」の欄にあるものだけを表記どおりに使い、
     「（サイソク編集部の計算）」と添える（自分で計算しない）。
  3. 読者の判断の目安（必ず入れる）: 「〜ならA、〜ならB」の形で、読者が自分の場合に何をするか（確かめる・申し込む・待つ・見送る・比べる）。
     次に起きることは、資料にある日付・予定だけを書く。
- 各文に、記事の中にある具体（数字・日付・制度や商品の名前・対象の人）を1つ以上入れる。この章で新しい事実・数字を足さない（本文の事実から考える章）。
- 見方は事実と書き分ける（「〜とみられます」「〜と考えられます」）。事実のように断定しない。相場や価格の予想、効果の断定、あおり、
  特定の会社・商品をすすめる言い方はしない（どの利用者にも当てはまる中立の言い方にする）。
- 読者がすることの無い発表（面会・式典・人事・表彰など）では、この章を書かない。
"""

REPAIR_SYSTEM = f"""あなたはニュースサイトのデスクです。記事に「{VIEW_LABEL}」の章を足し、薄い記事は元の資料にある事実だけで書き足します。
元の資料・確認済みの文脈に無い事実・数字・日付・固有名詞・発言は1つも足しません。出力は指定の JSON だけ。"""

VIEW_PROMPT = """次の記事に「{label}」の章が無いか、読者の判断の目安が足りません。章を1つだけ書いてください（本文のほかの部分は変えません）。
{rule}
# 出力
- view_markdown: 「## {label}：…」の見出しの行から始まる章の Markdown だけ（ほかの章は書かない）。

# 元の資料（公式の発表）
<<<
{source}
>>>
{context}
# いまの記事
タイトル: {title}
本文:
<<<
{body}
>>>"""

EXPAND_PROMPT = """次の記事は本文が{length}字で、公式ページを読むのと変わらない薄さです。元の資料にある事実だけで、読者の役に立つ記事に書き足した完成稿を返してください。
# 書き足し方
- 目安は{aim}字以上。ただし資料に材料が無ければ無理に延ばさない（同じことのくり返し・一般論・つなぎの文で埋めない）。
- 足すのは資料にある事実の説明だけ: 対象（だれ・どの契約・どの地域）、条件、日付・期限、金額、手順と窓口、前回や過去との違い、資料に書かれた背景や理由。
  資料に無い大事な条件は「〇〇はまだ発表されていません」と1回だけ書く。
- 今の文・数字・見出しの順番は保つ。資料の文をそのまま書き写さない（自分の言葉で説明する）。
- 「{label}」の章が無ければ、下の決まりで1つ足す（あれば根拠の無い部分だけ直す）。
{rule}
# 出力
- body_markdown: 書き足した本文の Markdown 全体（h1 は使わない）。

# 元の資料（公式の発表）
<<<
{source}
>>>
{context}
# いまの記事
タイトル: {title}
本文:
<<<
{body}
>>>"""

VIEW_SCHEMA = {"type": "OBJECT", "properties": {"view_markdown": {"type": "STRING"}}, "required": ["view_markdown"]}
BODY_SCHEMA = {"type": "OBJECT", "properties": {"body_markdown": {"type": "STRING"}}, "required": ["body_markdown"]}


def prompt_block() -> str:
    """記事を書くプロンプトに足す決まり（web_articles・main・Muse・深掘り）"""
    return PROMPT_RULE


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def view_section(body: str) -> str:
    """「## サイソクの見方」の章の本文（見出しの行を除く）。無ければ空"""
    m = VIEW_HEADING_RE.search(body or "")
    if not m:
        return ""
    rest = body[m.end():]
    nxt = _NEXT_H2_RE.search(rest)
    return (rest[:nxt.start()] if nxt else rest).strip()


def _sentences(text: str) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        line = re.sub(r"^\s*(?:[-*+・]|\d+[.)．])\s+", "", line).strip()
        if not line or line.startswith(("#", "|", ">")):
            continue
        out.extend(s.strip() for s in _SENT_SPLIT_RE.split(line) if len(s.strip()) >= 6)
    return out


def _no_reader_action(record: dict) -> bool:
    try:
        import persona  # noqa: PLC0415

        return persona.no_reader_action(record.get("title"))
    except Exception:  # noqa: BLE001 - 判定できなくても章は求める
        return False


def required(record: dict) -> bool:
    """「サイソクの見方」の章を門で求める記事か（暮らしとお金のジャンル。読者がすることの無い発表は除く）"""
    return (record.get("genreSlug") or "") in LIFE_GENRES and not _no_reader_action(record)


def short_alert(record: dict) -> bool:
    """短くてよい速報・お知らせ・注意喚起・地震や災害（public_interest.short_ok。今までの決まりで800字の下限の記事）"""
    if record.get("disaster") or record.get("breaking") is True or (record.get("newsType") or "") == "breaking":
        return True
    try:
        import public_interest  # noqa: PLC0415

        return public_interest.short_ok(record)
    except Exception:  # noqa: BLE001
        return False


def view_problems(record: dict) -> list[str]:
    """章が無い・短すぎる・判断の目安が無い（LLM を使わない）"""
    body = record.get("body") or ""
    if not VIEW_HEADING_RE.search(body):
        return [f"「## {VIEW_LABEL}：…」の章が無い（公式の発表の言い換えだけになっている）。本文の事実を根拠に、なぜ今か・誰にどのくらい影響するか・"
                "読者の判断の目安（〜ならA、〜ならB）を2〜4文で書く"]
    sec = view_section(body)
    sentences = _sentences(sec)
    out = []
    if len(sentences) < VIEW_MIN_SENTENCES:
        out.append(f"「{VIEW_LABEL}」の章が{len(sentences)}文しかない（2〜4文にする）")
    if not JUDGE_RE.search(_nfkc(sec)):
        out.append(f"「{VIEW_LABEL}」の章に読者の判断の目安が無い（「〜ならA、〜ならB」の形で、確かめる・申し込む・待つ・見送るを書く）")
    return out


def thin(record: dict) -> bool:
    return len(record.get("body") or "") < EXPAND_BELOW


def needs(record: dict, urgent: bool = False) -> dict:
    """{"view": bool, "expand": bool}。急ぐ記事（速報・大きなニュース・速報レーン）は何もしない。
    お知らせ・注意喚起は書き足さない（急ぐ）が、章は1回だけ足す（暮らしの注意喚起こそ判断の目安が要る）"""
    if urgent or record.get("disaster") or record.get("breaking") is True or (record.get("newsType") or "") == "breaking":
        return {"view": False, "expand": False}
    alert = short_alert(record)
    return {"view": required(record) and bool(view_problems(record)), "expand": not alert and thin(record)}


def insert_view(body: str, view_md: str) -> str:
    """章を本文に入れる（今の章は置き換え。「## まだ分からないこと」があればその前、無ければ最後）"""
    view_md = view_md.strip()
    m = VIEW_HEADING_RE.search(body)
    if m:
        rest = body[m.end():]
        nxt = _NEXT_H2_RE.search(rest)
        end = m.end() + (nxt.start() if nxt else len(rest))
        return (body[:m.start()].rstrip() + "\n\n" + view_md + "\n\n" + body[end:].lstrip()).strip() + "\n"
    u = UNKNOWN_H2_RE.search(body)
    if u:
        return (body[:u.start()].rstrip() + "\n\n" + view_md + "\n\n" + body[u.start():]).strip() + "\n"
    return body.rstrip() + "\n\n" + view_md + "\n"


def _clean_view(text: str) -> str:
    text = (text or "").strip().replace("\uff5c", "\u3000")
    text = re.sub(r"^#{1,6}[ \t　]*", "## ", text, count=1) if text.startswith("#") else text
    if not VIEW_HEADING_RE.search(text):
        return ""
    # 見出しの行から始まる最初の章だけ（ほかの章が混ざったら外す）
    m = VIEW_HEADING_RE.search(text)
    rest = text[m.end():]
    nxt = _NEXT_H2_RE.search(rest)
    return (text[m.start():m.end()] + (rest[:nxt.start()] if nxt else rest)).strip()


def _new_numbers(new: str, *known: str) -> set[str]:
    seen: set[str] = set()
    for text in known:
        seen |= set(_NUM_RE.findall(_nfkc(text)))
    return {n for n in set(_NUM_RE.findall(_nfkc(new))) - seen if len(n) > 1}


def _context_block(context: str) -> str:
    return f"\n# 確認済みの文脈（事実の束・計算済みの数字・過去記事。ここにある事実も使ってよい）\n<<<\n{context[:8000]}\n>>>\n" if (context or "").strip() else ""


def ensure(record: dict, source_text: str, context: str = "", *, urgent: bool = False, log=print, generate=None) -> list[str]:
    """足りなければ、1回だけ書き足す・章を足す（record をその場で書き換える）。したことの説明を返す。
    このあとふつうの事実確認（quality.evaluate）を通す。generate は llm.generate_json と同じ形（テスト用に差し替える）"""
    need = needs(record, urgent)
    if not (need["view"] or need["expand"]):
        return []
    if generate is None:
        import llm  # noqa: PLC0415

        generate = llm.generate_json
    body = record.get("body") or ""
    source = (source_text or "")[:12000]
    notes: list[str] = []
    rule = PROMPT_RULE if required(record) else ""
    try:
        if need["expand"]:
            prompt = EXPAND_PROMPT.format(length=len(body), aim=EXPAND_BELOW + 300, label=VIEW_LABEL, rule=rule, source=source,
                                          context=_context_block(context), title=record.get("title", ""), body=body)
            data, model = generate(REPAIR_SYSTEM, prompt, BODY_SCHEMA, temperature=0.3, max_output_tokens=8192, tier="bulk", purpose="helper")
            new_body = re.sub(r"^#(?!#)\s*", "## ", str(data.get("body_markdown") or "").strip(), flags=re.M).replace("\uff5c", "\u3000")
            added = _new_numbers(new_body, body, source_text, context)
            if len(new_body) <= len(body):
                notes.append(f"書き足せなかった（{len(body)}→{len(new_body)}字・{model}）")
            elif added:
                notes.append(f"書き足しに資料に無い数字が出たので使わない（{', '.join(sorted(added)[:4])}・{model}）")
            else:
                notes.append(f"公式の資料の事実で書き足した（{len(body)}→{len(new_body)}字・{model}）")
                record["body"] = body = new_body
                record["ownViewExpanded"] = True
        if required(record) and view_problems(record):
            prompt = VIEW_PROMPT.format(label=VIEW_LABEL, rule=PROMPT_RULE, source=source, context=_context_block(context),
                                        title=record.get("title", ""), body=body)
            data, model = generate(REPAIR_SYSTEM, prompt, VIEW_SCHEMA, temperature=0.3, max_output_tokens=2048, tier="bulk", purpose="helper")
            view = _clean_view(str(data.get("view_markdown") or ""))
            added = _new_numbers(view, body, source_text, context)
            if not view:
                notes.append(f"「{VIEW_LABEL}」の章を書けなかった（{model}）")
            elif added:
                notes.append(f"「{VIEW_LABEL}」の章に資料に無い数字が出たので使わない（{', '.join(sorted(added)[:4])}・{model}）")
            else:
                record["body"] = insert_view(body, view)
                record["ownViewAdded"] = True
                notes.append(f"「{VIEW_LABEL}」の章を足した（{model}）")
    except Exception as error:  # noqa: BLE001 - 足せなくても、このあとの門（hold_reason）で決める
        notes.append(f"書き足し・章の追加に失敗（{str(error)[:100]}）")
    for note in notes:
        log(f"   [view] {note}")
    return notes


def hold_reason(record: dict, *, urgent: bool = False) -> str | None:
    """事実確認に合格したあとの最後の確かめ。出さない理由（出してよいなら None）。
    急ぐ記事・速報・お知らせ・注意喚起・災害は止めない（今までの決まりどおり短くてよい）"""
    if urgent or short_alert(record):
        return None
    body = record.get("body") or ""
    if len(body) < HOLD_BELOW:
        return (f"中身が足りない: 本文が{len(body)}字（{HOLD_BELOW}字未満）で、公式の資料で書き足しても公式ページを読むのと変わらない"
                "（2026-11-12 オーナー「公式の書き写しにしない」）")
    if required(record) and (problems := view_problems(record)):
        return f"「{VIEW_LABEL}」の章が無い・足りない（自動で足しても事実確認で残らなかった）: {problems[0][:120]}"
    return None
