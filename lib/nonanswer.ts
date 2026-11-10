import rules from "./index-rules.json";

/**
 * 答えの欄（よくある質問・「こんな不安ありませんか」・ガイドの結論）に「答えになっていない文」を出さない（2026-11-10 SEO A4・LLMO-A4）。
 *
 * 「このページには載っていません」「改定後の金額は記載されていません」だけの答えは、読者にも、検索・AI の答え（FAQPage）にも役に立たない。
 * 式の正本は scripts/nonanswer.py の NOT_STATED_RE（lib/index-rules.json の notStated に書き出す）。生成の門・点検と同じ式を使う。
 *
 * - 最初の文が「書かれていません」などなら、その問いには答えていない → 出さない（null）
 * - 2文目以降のその文は消し、残りの答えを出す（消すだけで、言葉は足さない）
 */
export const NOT_STATED_RE = new RegExp(rules.notStated.source, rules.notStated.flags);

/** 消したあとに残る答えの最短の長さ（scripts/nonanswer.py の MIN_ANSWER と同じ） */
const MIN_ANSWER = 10;

export function sentences(text: string): string[] {
  return (text ?? "").match(/[^。！？!?\n]+(?:[。！？!?]+|\n+|$)/g)?.filter((s) => s.trim()) ?? [];
}

export const isNotStated = (text: string) => NOT_STATED_RE.test(text ?? "");

/** 答えの欄に出してよい答え。答えていなければ null */
export function answerOrNull(text: string): string | null {
  const parts = sentences(text);
  if (!parts.length || isNotStated(parts[0])) return null;
  const kept = parts.filter((s) => !isNotStated(s)).join("").trim();
  return kept.length >= MIN_ANSWER ? kept : null;
}

/** 説明文から、答えになっていない文だけを消す（何も残らなければ ""） */
export function stripNotStated(text: string): string {
  return sentences(text).filter((s) => !isNotStated(s)).join("").trim();
}

/** 問いと答えの一覧から、答えている問いだけを残す（答えは答えになっていない文を外したもの） */
export function answeredOnly<T extends { a: string }>(items: T[]): T[] {
  return items.flatMap((item) => {
    const a = answerOrNull(item.a);
    return a ? [{ ...item, a }] : [];
  });
}
