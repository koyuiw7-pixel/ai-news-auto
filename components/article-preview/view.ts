import type { FullArticle } from "@/lib/articles";
import { extractHeadings, renderMarkdown } from "@/lib/markdown";
import { verdictOf, type Verdict } from "@/lib/verdict";

/**
 * 記事ページのデザイン案（A/B/C）で共有する表示用データ。
 * 数字や比較は記事 JSON の中身（要点・判定・本文の表）からだけ組み立てる。足りない記事では出さない。
 */

export type Variant = "a" | "b" | "c";

export type Stat = { value: string; text: string };

export type ArticleView = {
  article: FullArticle;
  verdict: Verdict | null;
  headings: { id: string; text: string }[];
  /** 見出しに id を付け、表を案ごとに組み替えた本文 HTML */
  html: string;
  easyHtml: string;
  readMinutes: number;
  easyMinutes: number;
  /** 要点ごとの代表的な数字（無い要点は value が空） */
  stats: Stat[];
};

// 単位付きの数字だけを拾う（年号・日付・型番は拾わない）
const FIG =
  /(?:[$＄]\s?\d[\d,.]*(?:\/1?[MK])?|\d[\d,.]*\s?(?:%|％|倍|ドル|円|ポイント|pt|万|億|兆|分の\d+)(?:以上|以下|未満)?(?:削減|低減|向上|改善|短縮|値下げ)?)/g;
const FROM_TO = /(\d[\d,.]*\s?[%％])から(\d[\d,.]*\s?[%％])/;

/** 文中の数字を <strong class="ap-num"> で囲んだ HTML（エスケープ済み） */
export function emphasizeFigures(text: string): string {
  return escapeHtml(text).replace(FIG, (m) => `<strong class="ap-num">${m}</strong>`);
}

/** 要点1文から、大きく見せる数字を1つ取り出す */
export function pickFigure(text: string): string {
  const range = FROM_TO.exec(text);
  if (range) return `${range[1]}→${range[2]}`;
  FIG.lastIndex = 0;
  const m = text.match(FIG);
  return m?.[0] ?? "";
}

export function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function stripTags(html: string): string {
  return html.replace(/<[^>]+>/g, "").replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&").trim();
}

/** 本文の h2 に目次用の id を付ける（marked は id を付けない） */
function addHeadingIds(html: string, headings: { id: string }[]): string {
  let i = 0;
  return html.replace(/<h2>/g, () => {
    const h = headings[i++];
    return h ? `<h2 id="${escapeHtml(h.id)}">` : "<h2>";
  });
}

/** 記事の主役（題名の「」内の製品名など）。表の「注目」列を決めるのに使う */
function focusNames(article: FullArticle): string[] {
  const names = [...article.title.matchAll(/「([^」]{2,30})」/g)].map((m) => m[1]);
  return names.length > 0 ? names : [];
}

const NOTE_COL = /補足|考察|出典|備考|注|メモ/;
const WIN = /優位|圧倒|上回|最優秀|最高|安価|高速|向上|改善|削減|軍配|勝/;
const DIFF = /(\+\d[\d.]*\s?(?:%|pt|ポイント)|\d[\d.]*倍(?:以上)?|約?\d+分の\d+|(?<![\d$])1\/\d+(?![\dMK])|\d+x削減|半額|\d+(?:pt|ポイント)差)/g;

/**
 * 本文の表を案ごとに組み替える。
 * 共通：セルに見出し名（data-label）と「注目」列・注記列の印を付け、スクロール用の枠で包む。
 * B：差分（2倍・1/10 など）を札にする。C：行の中で1つだけ優位を示す語があるセルに色を付ける。
 */
function transformTables(html: string, variant: Variant, focus: string[]): string {
  return html.replace(/<table>([\s\S]*?)<\/table>/g, (_all, inner: string) => {
    const headRow = /<thead>\s*<tr>([\s\S]*?)<\/tr>\s*<\/thead>/.exec(inner);
    const headers = headRow ? [...headRow[1].matchAll(/<th([^>]*)>([\s\S]*?)<\/th>/g)].map((m) => stripTags(m[2])) : [];
    const focusCol = headers.findIndex((h, i) => i > 0 && focus.some((name) => h.includes(name)));
    const noteCols = new Set(headers.flatMap((h, i) => (i > 0 && NOTE_COL.test(h) ? [i] : [])));
    let wins = 0;

    const cellClass = (i: number) =>
      [i === 0 ? "is-key" : "", i === focusCol ? "is-focus" : "", noteCols.has(i) ? "is-note" : ""].filter(Boolean).join(" ");

    const thead = headRow
      ? `<thead><tr>${[...headRow[1].matchAll(/<th([^>]*)>([\s\S]*?)<\/th>/g)]
          .map(
            (m, i) =>
              `<th${m[1]} class="${cellClass(i)}">${m[2]}${
                i === focusCol && variant !== "c" ? ' <span class="ap-focus-tag">注目</span>' : ""
              }</th>`,
          )
          .join("")}</tr></thead>`
      : "";

    const bodyHtml = /<tbody>([\s\S]*?)<\/tbody>/.exec(inner)?.[1] ?? "";
    const rows = [...bodyHtml.matchAll(/<tr>([\s\S]*?)<\/tr>/g)].map((row) => {
      const cells = [...row[1].matchAll(/<td([^>]*)>([\s\S]*?)<\/td>/g)];
      // C：行の中で1つだけ「優位」を示すセルに印
      const winners = cells.flatMap((c, i) => (i > 0 && !noteCols.has(i) && WIN.test(stripTags(c[2])) ? [i] : []));
      const win = variant === "c" && winners.length === 1 ? winners[0] : -1;
      if (win >= 0) wins++;
      return `<tr>${cells
        .map((c, i) => {
          let content = c[2];
          if (variant === "b" && i > 0 && !noteCols.has(i)) content = content.replace(DIFF, '<span class="ap-diff">$1</span>');
          if (variant === "c" && i > 0) content = content.replace(FIG, '<b class="ap-cellnum">$&</b>');
          const cls = [cellClass(i), i === win ? "is-win" : ""].filter(Boolean).join(" ");
          const label = headers[i] ? ` data-label="${escapeHtml(headers[i])}"` : "";
          return `<td${c[1]}${label}${cls ? ` class="${cls}"` : ""}><span class="ap-cell">${content}</span></td>`;
        })
        .join("")}</tr>`;
    });

    const note =
      variant === "c" && wins > 0
        ? '<p class="ap-tbl-note">色付きのセルは、表の記載から優位と読める項目の目安です</p>'
        : variant === "a" && headers.length > 2
          ? '<p class="ap-tbl-hint">横にスクロールできます →</p>'
          : "";
    return `<div class="ap-tbl ap-cols-${headers.length}"><div class="ap-tbl-scroll"><table>${thead}<tbody>${rows.join(
      "",
    )}</tbody></table></div>${note}</div>`;
  });
}

export async function buildArticleView(article: FullArticle, variant: Variant): Promise<ArticleView> {
  const affiliateUrls = (article.affiliates ?? []).map((a) => a.url);
  const headings = extractHeadings(article.body);
  const raw = await renderMarkdown(article.body, affiliateUrls);
  const html = transformTables(addHeadingIds(raw, headings), variant, focusNames(article));
  const easy = article.easy?.trim() ?? "";
  const easyHtml = easy ? transformTables(await renderMarkdown(easy, affiliateUrls), variant, focusNames(article)) : "";
  return {
    article,
    verdict: verdictOf(article) ?? null,
    headings,
    html,
    easyHtml,
    readMinutes: Math.max(1, Math.round(article.body.length / 600)),
    easyMinutes: Math.max(1, Math.round(easy.length / 500)),
    stats: article.highlights.map((text) => ({ value: pickFigure(text), text })),
  };
}
