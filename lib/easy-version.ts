import type { Article } from "@/lib/articles";
import { cleanSections, dropSummarySections, retitleHtml, stripSummaryOpener } from "@/lib/article-sections";
import { renderMarkdown } from "@/lib/markdown";
import { noirBodyHtml } from "@/lib/noir";
import { isLiveArticleSlug } from "@/lib/retired";
import { foldSourceLists } from "@/lib/source-fold";

/**
 * 記事の「要約版」（かんたんに読む版。記事 JSON の easy）。
 *
 * 2026-11-25 AdSense の点検: 記事ページの HTML に詳細版と要約版の両方（とリード）が入り、同じ文が3文以上そのまま重なるページが
 * 30ページ中20ページあった（検索エンジンからは同じ文をくり返す薄いページに見える）。そこで記事ページの HTML には詳細版だけを入れ、
 * 要約版は読者が「要約版で読む」を選んだときに /api/easy/<slug> から読み込む（components/ReadingMode.tsx。/api/ は robots.txt で巡回させない）。
 *
 * 中身なしの章・つなぎの文を除き（lib/article-sections.ts。scripts/section_gate.py と同じ規則）、
 * 決まった型の見出しは記事ごとの見出し（sectionTitles）か普通の見出しに言い換えて出す。
 * 要約版の最初の「ひとことで言うと（要点）」は、上の「この記事のポイント」と同じ役目なので出さない（台帳 A28）。
 * 頭の「要約すると、」はリードの言い直しなので外す（台帳 A19）
 */
type EasySource = Pick<Article, "easy" | "lede" | "highlights" | "sectionTitles" | "affiliates">;

/** 要約版の Markdown（無ければ空） */
export function easyMarkdownOf(article: EasySource): string {
  const raw = article.easy?.trim();
  if (!raw) return "";
  const cleaned = cleanSections(stripSummaryOpener(raw, article.lede ?? ""), article.sectionTitles?.easy).markdown;
  return (article.highlights ?? []).length > 0 ? dropSummarySections(cleaned) : cleaned;
}

/** 要約版の読む時間の目安（分。約500字で1分） */
export function easyMinutesOf(markdown: string): number {
  return Math.max(1, Math.round(markdown.length / 500));
}

/** 要約版の HTML（無ければ空）。noir は 2026-11-07 以降の新しい見た目の記事（lib/noir.ts の noirBodyHtml を通す） */
export async function easyHtmlOf(article: EasySource, noir = false): Promise<string> {
  const easy = easyMarkdownOf(article);
  if (!easy) return "";
  const html = foldSourceLists(
    retitleHtml(await renderMarkdown(easy, (article.affiliates ?? []).map((a) => a.url), isLiveArticleSlug), "easy", article.sectionTitles, "easy"),
  );
  return noir ? noirBodyHtml(html, {}) : html;
}

/** 記事ページに置く、要約版を読み込む場所の印（components/ReadingMode.tsx が中身を入れる） */
export const EASY_BODY_ATTR = "data-easy-body";
