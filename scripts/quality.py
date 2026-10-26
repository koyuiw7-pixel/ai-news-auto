#!/usr/bin/env python3
"""生成した記事を書き出す前の品質ゲート。

  (a) 形のチェック（API 不要）: 本文の長さ・かんたん版・タイトル長・英語の残骸・元記事の丸写し
  (b) 事実確認（LLM・bulk）: 記事と元記事を突き合わせ {grounded, score, problems} を返させる
      grounded が false か score < 70 なら不合格

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

# 確認する記事
<<<
{article}
>>>

# 確認のしかた
- 記事にある数値・日付・価格・固有名詞・発言・対象者・提供状況が、元記事に書かれているか、元記事と矛盾しないかを確かめる。
- 次は問題にしない: 元記事の内容の言い換え・要約、「（編集部注）」と明記した一般的な背景説明（具体的な数値を含まないもの）、
  「元記事では言及なし」「発表されていない」といった記述、読者への一般的な助言（公式情報を確認しよう等）。
- 次は必ず問題にする: 元記事に無い具体的な数値・日付・価格・機能・発言の創作、元記事との矛盾、
  予定や研究段階のものを提供開始済み・実用化済みのように書くこと、効能・効果の断定、特定個人への憶測。

# 出力
- grounded: 創作・矛盾が1つも無ければ true。1つでもあれば false。
- score: 記事全体が元記事に裏付けられている度合い（0〜100）。軽微な言い過ぎは減点、創作・矛盾は大きく減点。
- problems: 見つけた問題を最大8個。各項目は「記事の該当箇所（短く引用）→ 何が問題か」を1文で。問題が無ければ空配列。"""


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
    if not easy.startswith("## ひとことで言うと"):
        problems.append("easy_markdown が「## ひとことで言うと」から始まっていない")
    if not TITLE_RANGE[0] <= len(title) <= TITLE_RANGE[1]:
        problems.append(f"title の長さが不適切（{len(title)}字 / {TITLE_RANGE[0]}〜{TITLE_RANGE[1]}字）")
    if re.search(r"[！!]", f"{title}{record.get('seoTitle') or ''}"):
        problems.append("title / seo_title に感嘆符がある")
    if kind == "broad":
        for heading in ("## ひとことで言うと", "## 自分に関係ある？"):
            if heading not in body:
                problems.append(f"body_markdown に「{heading}」の章がない（構成どおりの見出しを使う）")

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


def fact_check(record: dict, source_text: str) -> dict:
    """{grounded, score, problems, model}。LLM が使えないときは例外"""
    prompt = FACT_PROMPT.format(source=source_text[:SOURCE_CAP], article=_article_for_check(record))
    data, model = llm.generate_json(FACT_SYSTEM, prompt, FACT_SCHEMA, temperature=0.1, max_output_tokens=4096, tier="bulk")
    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    problems = [str(p).strip() for p in (data.get("problems") or []) if str(p).strip()][:8]
    return {"grounded": bool(data.get("grounded")), "score": max(0, min(100, score)), "problems": problems, "model": model}


def evaluate(record: dict, source_text: str, kind: str) -> dict:
    """{ok, score, problems, structural, fact}。形で落ちたときは事実確認を省く（API の節約）"""
    structural = structural_problems(record, kind, source_text)
    if structural:
        return {"ok": False, "score": None, "problems": structural, "structural": structural, "fact": None}
    try:
        fact = fact_check(record, source_text)
    except Exception as error:  # noqa: BLE001 - 確認できない記事は出さない
        problem = f"事実確認を実行できなかった（{str(error)[:80]}）"
        return {"ok": False, "score": None, "problems": [problem], "structural": [], "fact": None, "unavailable": True}
    ok = fact["grounded"] and fact["score"] >= PASS_SCORE
    problems = fact["problems"] if not ok else []
    if not ok and not problems:
        problems = [f"元記事との整合性が低い（score {fact['score']}）"]
    return {"ok": ok, "score": fact["score"], "problems": problems, "structural": [], "fact": fact}


def feedback_block(problems: list[str]) -> str:
    """作り直しのときにプロンプト末尾へ足す指示"""
    lines = "\n".join(f"- {p}" for p in problems[:10])
    return (
        "\n\n# 前回の原稿で見つかった問題（必ず直すこと）\n"
        f"{lines}\n"
        "- 元記事に無い数値・日付・価格・発言は削る。足りない分は元記事の事実の説明を厚くして補い、推測で埋めない。"
    )
