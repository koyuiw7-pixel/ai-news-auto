import type { ArticleSummary, NextRead } from "@/lib/articles";

/**
 * 記事ページの「この話の続き」を1つにまとめる（2026-11-11 読者目線レビュー 4位）。
 * 以前は「この話の続き」「あわせて読みたい」「次にやること」「次に読む記事」「関連記事」「この話題のページ」「よく読まれている記事」の7つの枠に、
 * ほぼ同じ題名の記事が何度も出ていた。枠は「この話の続き」（要点の下・最大3本）と「よく読まれている記事」（本文の直後・5本）の2つだけにする。
 * 候補は先に渡したものから順に（次にやること → 同じ話題 → 同じ話題で別の疑問に答える記事）。同じ記事・ほぼ同じ題名は1回だけ
 */

/** 題名の2文字ずつの組（空白・記号を除く） */
function bigrams(title: string): Set<string> {
  const text = title.normalize("NFKC").replace(/[\s\p{P}\p{S}]/gu, "");
  const out = new Set<string>();
  for (let i = 0; i < text.length - 1; i++) out.add(text.slice(i, i + 2));
  return out;
}

/** ほぼ同じ題名か（2文字ずつの組の重なりが6割以上） */
export function nearSameTitle(a: string, b: string): boolean {
  const x = bigrams(a);
  const y = bigrams(b);
  if (x.size === 0 || y.size === 0) return false;
  let both = 0;
  for (const g of x) if (y.has(g)) both += 1;
  return both / Math.min(x.size, y.size) >= 0.6;
}

export function mergeStoryReads(current: Pick<ArticleSummary, "slug" | "title">, groups: NextRead[][], limit = 3): NextRead[] {
  const out: NextRead[] = [];
  for (const group of groups) {
    for (const item of group) {
      if (out.length >= limit) return out;
      const a = item.article;
      if (!a || a.slug === current.slug) continue;
      if (nearSameTitle(a.title, current.title)) continue;
      if (out.some((o) => o.article.slug === a.slug || nearSameTitle(o.article.title, a.title))) continue;
      out.push(item);
    }
  }
  return out;
}
