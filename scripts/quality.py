#!/usr/bin/env python3
"""生成した記事を書き出す前の品質ゲート。

  (a) 形のチェック（API 不要）: 本文の長さ・かんたん版・タイトル長・英語の残骸・元記事の丸写し・独自の価値（流れ／表／自分に関係ある？）
  (b) 事実確認（LLM・bulk）: 記事と元記事を突き合わせ {grounded, score, problems} を返させる
      grounded が false か score < 70 なら不合格

  (c) 読みやすさ（測るのは API 不要）: 文・段落の長さ。形と事実が合格で読みやすさだけ基準外なら「やわらかい不合格」。
      polish() で本文だけ文を分ける書き直しを1回頼み（数値を添えて）、見出し・数字・長さが保たれ再確認も通れば差し替える。
      だめなら元の原稿のまま受理して数値をログに残す（読みやすさだけで記事を落とさない）

web_articles.py は不合格のとき problems を添えて1回だけ作り直し、それでもだめなら諦める。
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402

MIN_BODY = {"ai": 2500, "broad": 1800, "trend": 1800}
MIN_EASY = 400
TITLE_RANGE = (18, 64)
PASS_SCORE = 70
# 事実確認・文の書き直しに使うモデルの段（速報レーンは待たせないよう quality にする。web_articles.py が切り替える）
CHECK_TIER = "bulk"
SOURCE_CAP = 9000
ARTICLE_CAP = 9000

BOILERPLATE_RE = re.compile(
    r"\b(Read more|Learn more|Subscribe|Sign up|Sign in|Cookie|Privacy Policy|Terms of (Use|Service)|"
    r"All rights reserved|Share this|Click here|Skip to (main )?content|Table of contents|Back to top|"
    r"Related (posts|articles)|Loading\.\.\.)\b",
    re.IGNORECASE,
)
# 英単語が12語以上続く＝訳し忘れ・コピペの残骸（製品名程度なら12語には届かない）
ENGLISH_RUN_RE = re.compile(r"(?:\b[A-Za-z][A-Za-z'’\-]*\b[\s,;:]+){11,}\b[A-Za-z][A-Za-z'’\-]*\b")
# 文章ソースなのに「動画」前提の言い回しが残っている
VIDEO_LEFTOVER_RE = re.compile(r"動画(内|では|の中で|で示|で紹介|で語ら|の冒頭)|映像では|スライドでは|音声では")

FACT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "grounded": {"type": "BOOLEAN"},
        "score": {"type": "INTEGER"},
        "problems": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["grounded", "score", "problems"],
    "propertyOrdering": ["grounded", "score", "problems"],
}

FACT_SYSTEM = """あなたは報道機関の校閲記者です。AIが書いた記事を、元記事（一次情報）と1文ずつ突き合わせて事実確認します。
判定は厳格に、しかし公平に行ってください。出力は指定の JSON だけ。"""

FACT_PROMPT = """# 元記事（一次情報。自動抽出なのでメニュー等の残骸は無視）
<<<
{source}
>>>
{context}

# 確認する記事
<<<
{article}
>>>

# 確認のしかた
- 記事にある数値・日付・価格・固有名詞・発言・対象者・提供状況が、元記事に書かれているか、元記事と矛盾しないかを確かめる。
- 次は問題にしない: 元記事の内容の言い換え・要約、「確認済みの文脈」に書かれた事実（過去の経緯・日付・価格など）、「（編集部注）」と明記した一般的な背景説明（具体的な数値を含まないもの）、
  「元記事では言及なし」「発表されていない」といった記述、読者への一般的な助言（公式情報を確認しよう等）。
- 次は必ず問題にする: 元記事に無い具体的な数値・日付・価格・機能・発言の創作、元記事との矛盾、
  予定や研究段階のものを提供開始済み・実用化済みのように書くこと、効能・効果の断定、特定個人への憶測。

# 出力
- grounded: 創作・矛盾が1つも無ければ true。1つでもあれば false。
- score: 記事全体が元記事に裏付けられている度合い（0〜100）。軽微な言い過ぎは減点、創作・矛盾は大きく減点。
- problems: 見つけた問題を最大8個。各項目は「記事の該当箇所（短く引用）→ 何が問題か」を1文で。問題が無ければ空配列。"""


CONTEXT_BLOCK = """
# 確認済みの文脈（サイソクの過去記事・既存記事の事実。ここにある事実は創作として扱わない）
<<<
{context}
>>>
"""
# 独自の価値: 「これまでの流れ」の章 / Markdown の表 / 「自分に関係ある？」の章（150字以上）のどれか
UNIQUE_KINDS = {"ai", "broad", "trend"}
UNIQUE_SECTION_MIN = 150
TABLE_RE = re.compile(r"^\s*\|.+\|\s*\n\s*\|\s*:?-{3,}", re.M)
# 最初の章の見出し（新しい記事は「概要」、古い記事は「ひとことで言うと」）
FIRST_HEADINGS = ("概要", "ひとことで言うと")
# 立場別の「自分に関係ある？」系の章（旧名も含む）
RELEVANCE_HEADINGS = ("自分に関係ある？", "自分にはどう関係する？", "自分にとって何が変わる？", "読者にとって何が変わるのか", "誰にどう効くのか")

# 読みやすさの基準（Terra の書き直し: 平均33字・60字超6%・段落48字）
READ_MAX_AVG_SENTENCE = 45
READ_LONG_SENTENCE = 60
READ_MAX_LONG_SHARE = 0.20
READ_MAX_AVG_PARAGRAPH = 120
READ_MAX_PARAGRAPH = 220
# 段落に数えない行: 見出し・表・箇条書き・引用・コード
_NON_PROSE_RE = re.compile(r"^\s*(#|\||[-*+]\s|\d+[.)]\s|>|```|出典[:：])")
_SENTENCE_END_RE = re.compile(r"(?<=[。！？!?])(?![」』）)\]])")


def _plain_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _norm(text: str) -> str:
    return re.sub(r"[\s　、。，．,.・「」『』()（）\-—:：]", "", unicodedata.normalize("NFKC", text or ""))


def copied_sentences(body: str, source: str, min_len: int = 40) -> list[str]:
    """元記事とほぼ同じ文（記号・空白を無視して40字以上一致）"""
    src = _norm(source)
    if not src:
        return []
    found = []
    for sentence in re.split(r"(?<=[。！？])|\n", body or ""):
        clean = _norm(re.sub(r"[#>*|`]", "", sentence))
        if len(clean) >= min_len and clean in src:
            found.append(sentence.strip()[:50])
    return found


def section_text(body: str, heading: str) -> str:
    """「## 見出し」で始まる章の本文（次の ## まで）。無ければ空文字"""
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)", body or "", re.M | re.S)
    return m.group(1) if m else ""


def has_unique_value(body: str) -> bool:
    if re.search(r"^## これまでの流れ", body or "", re.M) or TABLE_RE.search(body or ""):
        return True
    return any(_plain_len(section_text(body, h)) >= UNIQUE_SECTION_MIN for h in RELEVANCE_HEADINGS)


def _strip_inline(text: str) -> str:
    """リンク・強調・コードの記号を外した地の文"""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"(\*\*|__|\*|<br\s*/?>)", "", text)
    return re.sub(r"\s+", "", text)


def paragraphs(body: str) -> list[str]:
    """地の文の段落（見出し・表・箇条書き・引用・コードを除く）。空行か地の文以外の行で区切る"""
    found: list[str] = []
    current: list[str] = []
    in_code = False
    for line in (body or "").splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        if in_code or not line.strip() or _NON_PROSE_RE.match(line):
            if current:
                found.append("".join(current))
                current = []
            continue
        current.append(_strip_inline(line))
    if current:
        found.append("".join(current))
    return [p for p in found if p]


def readability(body: str) -> dict:
    """文・段落の長さ（決定的。LLM なし）"""
    paras = paragraphs(body)
    sentences = [s for p in paras for s in _SENTENCE_END_RE.split(p) if len(s) >= 2]
    lengths = [len(s) for s in sentences]
    para_lengths = [len(p) for p in paras]
    long_count = sum(1 for n in lengths if n > READ_LONG_SENTENCE)
    return {
        "sentences": len(lengths),
        "avg_sentence": round(sum(lengths) / len(lengths), 1) if lengths else 0.0,
        "long_share": round(long_count / len(lengths), 3) if lengths else 0.0,
        "paragraphs": len(para_lengths),
        "avg_paragraph": round(sum(para_lengths) / len(para_lengths), 1) if para_lengths else 0.0,
        "max_paragraph": max(para_lengths, default=0),
    }


def readability_problems(body: str, stats: dict | None = None) -> list[str]:
    """読みやすさの基準外。作り直しの指示に使えるよう、数字と直し方を書く"""
    r = stats or readability(body)
    if not r["sentences"]:
        return []
    problems = []
    if r["avg_sentence"] > READ_MAX_AVG_SENTENCE or r["long_share"] > READ_MAX_LONG_SHARE:
        problems.append(
            f"文が長い（1文の平均 {r['avg_sentence']}字・{READ_LONG_SENTENCE}字超の文が {r['long_share']:.0%} / "
            f"基準 平均{READ_MAX_AVG_SENTENCE}字以下・{READ_LONG_SENTENCE}字超{READ_MAX_LONG_SHARE:.0%}以下）。"
            "1文は50字以内を目安に2文に分け、1文に言いたいことは1つにする（内容と文字数は減らさない）"
        )
    if r["avg_paragraph"] > READ_MAX_AVG_PARAGRAPH or r["max_paragraph"] > READ_MAX_PARAGRAPH:
        problems.append(
            f"段落が長い（平均 {r['avg_paragraph']}字・最長 {r['max_paragraph']}字 / "
            f"基準 平均{READ_MAX_AVG_PARAGRAPH}字以下・最長{READ_MAX_PARAGRAPH}字以下）。"
            "1段落は1〜3文にし、数字が3つ以上並ぶところは箇条書きにする（内容と文字数は減らさない）"
        )
    return problems


def structural_problems(record: dict, kind: str, source_text: str = "") -> list[str]:
    """形のチェック。問題のリスト（空なら合格）"""
    problems: list[str] = []
    body = record.get("body") or ""
    easy = (record.get("easy") or "").strip()
    title = record.get("title") or ""

    min_body = MIN_BODY.get(kind, 1800)
    if _plain_len(body) < min_body:
        problems.append(f"本文が短い（{_plain_len(body)}字 / 基準 {min_body}字以上）。元記事の事実を使って各章を具体的に書き足す（推測で水増ししない）")
    if _plain_len(easy) < MIN_EASY:
        problems.append(f"easy_markdown が短い（{_plain_len(easy)}字 / 基準 {MIN_EASY}字以上）")
    if not easy.startswith(("## ひとことで言うと", "## 概要")):
        problems.append("easy_markdown が「## ひとことで言うと」から始まっていない")
    if not TITLE_RANGE[0] <= len(title) <= TITLE_RANGE[1]:
        problems.append(f"title の長さが不適切（{len(title)}字 / {TITLE_RANGE[0]}〜{TITLE_RANGE[1]}字）")
    if re.search(r"[！!]", f"{title}{record.get('seoTitle') or ''}"):
        problems.append("title / seo_title に感嘆符がある")
    if kind == "broad":
        if not any(f"## {h}" in body for h in FIRST_HEADINGS):
            problems.append("body_markdown に「## 概要」の章がない（構成どおりの見出しを使う）")
        if "## 自分に関係ある？" not in body:
            problems.append("body_markdown に「## 自分に関係ある？」の章がない（構成どおりの見出しを使う）")

    if record.get("sourceType") == "web" and kind in UNIQUE_KINDS and not has_unique_value(body):
        problems.append(
            "独自の価値が無い。「## これまでの流れ」（過去記事の文脈がある場合）・元記事の数値の Markdown 比較表（比べるものがある場合）・"
            "「## 自分に関係ある？」（150字以上で立場別に具体的に）のどれかを入れる"
        )

    text = f"{body}\n{easy}"
    if m := BOILERPLATE_RE.search(text):
        problems.append(f"Webページの英語の残骸が残っている（「{m.group(0)}」）")
    if m := ENGLISH_RUN_RE.search(re.sub(r"`[^`]*`|\[[^\]]*\]\([^)]*\)", " ", text)):
        problems.append(f"訳されていない英文が残っている（「{m.group(0)[:40]}…」）")
    if record.get("sourceType") == "web" and (m := VIDEO_LEFTOVER_RE.search(text)):
        problems.append(f"文章が元なのに動画前提の表現がある（「{m.group(0)}」）。「元記事」と書く")
    if source_text:
        copied = copied_sentences(body, source_text)
        if len(copied) >= 2:
            problems.append(f"元記事の文をそのまま書き写している（{len(copied)}文。例「{copied[0]}」）。自分の言葉で要約する")
    return problems


def _article_for_check(record: dict) -> str:
    parts = [
        f"タイトル: {record.get('title', '')}",
        f"リード: {record.get('lede', '')}",
        "要点: " + " / ".join(record.get("highlights") or []),
        f"本文:\n{record.get('body', '')}",
        f"かんたん版:\n{record.get('easy', '')}",
    ]
    verdict = record.get("verdict")
    if verdict:
        parts.append(f"判定: 提供状況={verdict.get('status')} 価格={verdict.get('price')} ひとこと={verdict.get('take')}")
    return "\n\n".join(parts)[:ARTICLE_CAP]


def fact_check(record: dict, source_text: str, context: str = "") -> dict:
    """{grounded, score, problems, model}。context は確認済みの事実（過去記事など）。LLM が使えないときは例外"""
    prompt = FACT_PROMPT.format(
        source=source_text[:SOURCE_CAP],
        context=CONTEXT_BLOCK.format(context=context[:3000]) if context.strip() else "",
        article=_article_for_check(record),
    )
    data, model = llm.generate_json(FACT_SYSTEM, prompt, FACT_SCHEMA, temperature=0.1, max_output_tokens=4096, tier=CHECK_TIER)
    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    problems = [str(p).strip() for p in (data.get("problems") or []) if str(p).strip()][:8]
    return {"grounded": bool(data.get("grounded")), "score": max(0, min(100, score)), "problems": problems, "model": model}


def evaluate(record: dict, source_text: str, kind: str, context: str = "", check_facts: bool = True) -> dict:
    """{ok, soft, score, problems, structural, fact, readability, readability_problems}。形で落ちたときは事実確認を省く（API の節約）。
    soft=True は「形と事実は合格、読みやすさだけが基準外」。polish() で文を分け、だめでも受理してよい。
    形・事実の不合格のときの problems には読みやすさを混ぜない（作り直しで本文が縮み、長さで落ちるのを防ぐ）"""
    read = readability(record.get("body") or "")
    read_problems = readability_problems("", read)
    base = {"structural": [], "fact": None, "readability": read, "readability_problems": read_problems}
    structural = structural_problems(record, kind, source_text)
    if structural:
        return {**base, "ok": False, "soft": False, "score": None, "problems": structural, "structural": structural}
    if not check_facts:
        return {**base, "ok": not read_problems, "soft": bool(read_problems), "score": None, "problems": read_problems}
    try:
        fact = fact_check(record, source_text, context)
    except Exception as error:  # noqa: BLE001 - 確認できない記事は出さない
        problem = f"事実確認を実行できなかった（{str(error)[:80]}）"
        return {**base, "ok": False, "soft": False, "score": None, "problems": [problem], "unavailable": True}
    fact_ok = fact["grounded"] and fact["score"] >= PASS_SCORE
    problems = fact["problems"] if not fact_ok else read_problems
    if not fact_ok and not problems:
        problems = [f"元記事との整合性が低い（score {fact['score']}）"]
    return {**base, "ok": fact_ok and not read_problems, "soft": fact_ok and bool(read_problems), "score": fact["score"],
            "problems": problems, "fact": fact}


POLISH_SCHEMA = {
    "type": "OBJECT",
    "properties": {"body_markdown": {"type": "STRING"}},
    "required": ["body_markdown"],
}

POLISH_SYSTEM = """あなたはニュースサイトの編集者です。記者の原稿を、中身を変えずにスマホで読みやすい文に整えます。
出力は指定の JSON だけ。"""

POLISH_PROMPT = """次の記事本文（Markdown）を、中身を変えずに読みやすく整えてください。

# 今の原稿の数値
{problems}

# 直し方
- 1文は50字以内を目安にする。長い文は2〜3文に分ける。1文に言いたいことは1つ。読点（、）で文をつながない。
  例:「AはBを発表し、Cができるようになったことで、Dの手間が減ると期待されています。」
  →「AはBを発表しました。これでCができるようになります。Dの手間が減りそうです。」
- 1段落は1〜3文。段落の間には空行を入れる。
- 文中に数字が3つ以上並ぶところは箇条書きにする。
- 飾りの誇張語（圧倒的・極限・劇的・強烈 など）は普通の言葉にする。

# 変えてはいけないもの
- 見出し（## と ###）の文言・数・順番。表・リンク・既存の箇条書き。
- 事実・数字・日付・価格・固有名詞・引用。情報を削らない。足さない。
- 文字数はほぼ同じに保つ（{length}字前後。短くしない）。

# 原稿
<<<
{body}
>>>"""

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
_HEADING_RE = re.compile(r"^#{2,3} .+$", re.M)
_PROTECTED_HEADING_RE = re.compile(r"^## (概要|ひとことで言うと|自分に関係ある？|まとめ|これまでの流れ|続報)")


def _numbers(text: str) -> set[str]:
    """本文中の数字（リンク先と番号付きリストの番号は除く）"""
    text = re.sub(r"\]\([^)]*\)", "]", text or "")
    text = re.sub(r"^\s*\d+[.)]\s", "", text, flags=re.M)
    return set(_NUM_RE.findall(unicodedata.normalize("NFKC", text)))


def polish(record: dict, source_text: str, kind: str, context: str = "", check_facts: bool = True):
    """読みやすさだけ基準外の記事の本文を、文を分けるだけの書き直しにかける。
    (record, verdict) を返す。見出し・数字・長さが崩れたり、事実確認に落ちたりしたら None"""
    body = record.get("body") or ""
    length = _plain_len(body)
    problems = readability_problems(body)
    prompt = POLISH_PROMPT.format(problems="\n".join(f"- {p}" for p in problems), length=length, body=body)
    data, model = llm.generate_json(POLISH_SYSTEM, prompt, POLISH_SCHEMA, temperature=0.3, max_output_tokens=16384, tier=CHECK_TIER)
    new_body = re.sub(r"^(#{1,6}) +(?:#{1,6} +)+", r"\1 ", str(data.get("body_markdown") or "").strip(), flags=re.M)
    # 見出しは数と階層を保つ。言い回しの手直し（誇張語を外す等）は許すが、決まった章名は変えさせない
    heads_old, heads_new = _HEADING_RE.findall(body), _HEADING_RE.findall(new_body)
    if [h.split(" ")[0] for h in heads_old] != [h.split(" ")[0] for h in heads_new]:
        return None, f"見出しの数・階層が変わった（{len(heads_old)}→{len(heads_new)}個）"
    for a, b in zip(heads_old, heads_new):
        if _PROTECTED_HEADING_RE.match(a) and _norm(a) != _norm(b):
            return None, f"決まった章名が変わった（{a}→{b}）"[:80]
    if _plain_len(new_body) < max(length * 0.9, MIN_BODY.get(kind, 1800)):
        return None, f"本文が縮んだ（{length}→{_plain_len(new_body)}字）"
    # 「3つあります」のような1桁の数は箇条書きにするときに増えるので見逃す（事実確認は後で通す）
    added = {n for n in _numbers(new_body) - _numbers(body) if len(n) > 1}
    if added:
        return None, f"元に無い数字が増えた（{', '.join(sorted(added)[:5])}）"
    if len(_numbers(body) - _numbers(new_body)) > 2:
        return None, "数字が抜けた"
    polished = {**record, "body": new_body}
    verdict = evaluate(polished, source_text, kind, context, check_facts=check_facts)
    if not (verdict["ok"] or verdict.get("soft")):
        return None, "書き直し後の確認に不合格: " + "; ".join(verdict["problems"][:2])
    before, after = readability(body), verdict["readability"]
    improved = (
        len(verdict["readability_problems"]) < len(problems)
        or after["avg_sentence"] <= before["avg_sentence"] - 3
        or after["avg_paragraph"] <= before["avg_paragraph"] * 0.85
    )
    if not improved:
        return None, f"読みやすさが改善しなかった（{before['avg_sentence']}→{after['avg_sentence']}字）"
    verdict["polished_by"] = model
    return polished, verdict


def feedback_block(problems: list[str]) -> str:
    """作り直しのときにプロンプト末尾へ足す指示"""
    lines = "\n".join(f"- {p}" for p in problems[:10])
    return (
        "\n\n# 前回の原稿で見つかった問題（必ず直すこと）\n"
        f"{lines}\n"
        "- 元記事に無い数値・日付・価格・発言は削る。足りない分は元記事の事実の説明を厚くして補い、推測で埋めない。"
    )
