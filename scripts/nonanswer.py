"""答えの欄（よくある質問・「こんな不安ありませんか」・ガイドの結論）に入った「答えになっていない文」の判定（2026-11-10 SEO A4・LLMO-A4）。

「このページには載っていません」「改定後の金額は記載されていません」だけの答えは、読者にも検索・AI の答えにも役に立たない
（11/10 の点検で、記事の「不安」の答え 216 件・ガイドの質問 80 件にあった）。答えられない問いは出さない（その問いは捨てる）。

1つの式（NOT_STATED_RE）を正本にして、サイト側（lib/nonanswer.ts）にも lib/index-rules.json の notStated で同じ式を渡す
（scripts/indexnow.py --export-rules）。生成の門（quality.FAQ_UNANSWERED_RE・depth_fields・evergreen）と表示の段と点検が同じ式を使う。

答え1つの扱い（answer_or_none。lib/nonanswer.ts の answerOrNull と同じ）:
  - 最初の文が「書かれていません」などなら、その問いには答えていない → 捨てる（None）
  - 2文目以降の「書かれていません」の文は消し、残りの答えを使う（消すだけで、言葉は足さない）
  - 消したあとに答えが短すぎれば捨てる
"""

from __future__ import annotations

import re

NOT_STATED_RE = re.compile(
    r"(?:書かれて|載って|記載されて|示されて|触れられて|明らかにされて|案内されて|発表されて|公表されて|明記されて|言及されて|触れて|述べて)(?:い)?ません"
    r"|(?:記載|言及|案内|明記|説明)(?:は|が)?(?:ありません|なし)"
    r"|説明を控え|分かりません|わかりません|不明です|確認でき(?:ていませ|ませ)ん|判断できません"
)

# 消したあとに残る答えの最短の長さ（これより短ければ答えになっていない）
MIN_ANSWER = 10

_SENTENCE_RE = re.compile(r"[^。！？!?\n]+(?:[。！？!?]+|\n+|$)")


def sentences(text: str) -> list[str]:
    return [m.group(0) for m in _SENTENCE_RE.finditer(text or "") if m.group(0).strip()]


def is_not_stated(text: str) -> bool:
    """文（か短い答え）が「書かれていません」などの答えになっていない文か"""
    return bool(NOT_STATED_RE.search(text or ""))


def answer_or_none(text: str) -> str | None:
    """答えの欄に出してよい答え（答えになっていない文を外したもの）。答えていなければ None"""
    parts = sentences(text)
    if not parts or is_not_stated(parts[0]):
        return None
    kept = "".join(p for p in parts if not is_not_stated(p)).strip()
    return kept if len(kept) >= MIN_ANSWER else None


def strip_not_stated(text: str) -> str:
    """説明文（description など）から、答えになっていない文だけを消す（何も残らなければ ""）"""
    return "".join(p for p in sentences(text) if not is_not_stated(p)).strip()


def has_not_stated(text: str) -> bool:
    """答えの欄に、答えになっていない文が1つでも残っているか（点検・コーパスの確認用）"""
    return any(is_not_stated(p) for p in sentences(text))


# 答えの欄を持つ content/ のフォルダと、その中の問いと答えの欄（記事は「不安」と「よくある質問」、ガイドは「よくある質問」）
SLOT_DIRS = {"articles": ("worries", "faq"), "howto": ("faq",), "guides": ("faq",), "buying-guides": ("faq",)}


def slot_items(kind: str, record: dict):
    """(欄の名前, 問いと答え) を順に返す"""
    for key in SLOT_DIRS.get(kind, ()):
        for item in record.get(key) or []:
            if isinstance(item, dict):
                yield key, item


def corpus_counts(content_dir) -> dict:
    """点検用: 答えの欄に残っている「書かれていません」の数と、答えを待っている質問（openQuestions）の数"""
    import json
    from pathlib import Path

    out = {"articleAnswers": 0, "guideAnswers": 0, "openQuestions": 0}
    for kind in SLOT_DIRS:
        for path in sorted(Path(content_dir, kind).glob("*.json")):
            try:
                record = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(record, dict):
                continue
            bad = sum(1 for _, item in slot_items(kind, record) if has_not_stated(str(item.get("a") or "")))
            out["articleAnswers" if kind == "articles" else "guideAnswers"] += bad
            out["openQuestions"] += len(record.get("openQuestions") or [])
    return out
