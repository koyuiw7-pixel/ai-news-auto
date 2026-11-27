import { coverPath, getArticleSummary, sourceHref, sourceLabel, type ArticleSummary, type FullArticle } from "@/lib/articles";
import { cleanSections, dropOverviewSections, retitleHtml, stripSummaryOpener, titleSlugLinks } from "@/lib/article-sections";
import { insertBodyImages } from "@/lib/body-images";
import { renderMarkdown } from "@/lib/markdown";
import { isLiveArticleSlug } from "@/lib/retired";
import { isAffiliateUrl } from "@/lib/affiliate";
import { pickPartnerArticles } from "@/lib/partner-feed";
import { siteConfig } from "@/site.config";

/**
 * ニュースアプリ（スマートニュース・グノシーなど）向けフィードの共通部品。
 * フィードはビルド時に静的化する（force-static）ので、Workers の実行時には本文を読まない。
 * 載せる記事は暮らしとお金の記事だけ（lib/partner-feed.ts。2026-11-28）。
 * 本文に広告・紹介リンク・PR の囲み・計測の画像・登録への誘導を入れない（Yahoo!ニュース・スマートニュース・グノシーの決まり）。
 */

/** 各記事の最後に付ける AI 利用の開示（記事ページ・構造化データの backstory と同じ内容） */
export const AI_DISCLOSURE = "この記事は生成AIで下書きを作成し、元の発表と自動で照合してから公開しています。";

/**
 * 配信用の本文に残ってはいけないもの（広告・紹介リンク・計測の画像・PR の札・スクリプト）。
 * 見つかった記事はフィードに載せない（feedProblems が空でない記事は buildItems が外す）
 */
const FORBIDDEN: [string, RegExp][] = [
  ["a8", /a8\.net/i],
  ["affiliate-host", /(?:afl\.rakuten|hb\.afl|moshimo\.com|valuecommerce|accesstrade|felmat|afi-b\.com|linksynergy|amzn\.to)/i],
  ["amazon-tag", /amazon\.co\.jp[^"'\s<]*[?&](?:amp;)?tag=/i],
  ["aff-redirect", /\/api\/aff\//i],
  ["sponsored", /rel="[^"]*\b(?:sponsored|nofollow)\b/i],
  ["pr-badge", /【PR】|［PR］|\[PR\]|>\s*PR\s*<|広告\s*[:：]|スポンサーリンク/],
  ["script", /<(?:script|iframe|object|embed|form|button|input|noscript|style)\b/i],
  ["pixel", /<img[^>]*(?:width="1"|height="1")/i],
];

export function feedProblems(html: string): string[] {
  return FORBIDDEN.filter(([, re]) => re.test(html)).map(([name]) => name);
}

/**
 * 記事ページと同じ下ごしらえをした本文の HTML（app/articles/[slug]/page.tsx）: 要約の書き出し・概要の章を除き、空の章を隠し、本文の写真を入れる。
 * 紹介リンクの URL を渡して描画するので、紹介リンクには印が付く（あとで文字だけにする）
 */
export async function articleBodyHtml(article: FullArticle): Promise<string> {
  const affiliateUrls = (article.affiliates ?? []).map((a) => a.url);
  const opened = stripSummaryOpener(titleSlugLinks(article.body, (s) => getArticleSummary(s)?.title), article.lede ?? "");
  const body = cleanSections(article.lede && article.highlights.length > 0 ? dropOverviewSections(opened) : opened, article.sectionTitles?.body).markdown;
  const rendered = await renderMarkdown(body, affiliateUrls, isLiveArticleSlug);
  return retitleHtml(insertBodyImages(rendered, article.bodyImages ?? [], article.title), "body", article.sectionTitles);
}

/** 広告・紹介リンクか（文字だけ残す） */
export function adLinkFilter(article: FullArticle): (href: string) => boolean {
  const affiliateUrls = new Set((article.affiliates ?? []).map((a) => a.url));
  return (href: string) => {
    const plain = href.replace(/&amp;/g, "&");
    return affiliateUrls.has(plain) || affiliateUrls.has(href) || isAffiliateUrl(plain, affiliateUrls) || /\/api\/aff\//.test(plain) || feedProblems(`<a href="${plain}">`).length > 0;
  };
}

export const escapeXml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");

/** CDATA で包む（中に "]]>" があっても壊れないように分割） */
export const cdata = (value: string) => `<![CDATA[${value.replace(/]]>/g, "]]]]><![CDATA[>")}]]>`;

/** RFC822 の日時（例: Tue, 27 Oct 2026 09:30:00 +0000） */
export const rfc822 = (iso: string) => new Date(iso).toUTCString().replace(/GMT$/, "+0000");

/** サイソクに載せた日時（ニュースサイトマップ・構造化データと同じ基準） */
export const publishedOf = (a: ArticleSummary) => a.generatedAt || a.publishedAt;

export const articleUrl = (a: ArticleSummary) => `${siteConfig.url}/articles/${a.slug}`;
export const coverUrl = (a: ArticleSummary) => `${siteConfig.url}${coverPath(a)}`;

/** <a> を外して中の文字だけ残す */
const unwrap = (html: string, keep: (href: string) => boolean) =>
  html.replace(/<a\s[^>]*?href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, (whole, href: string, text: string) => (keep(href) ? whole : text));

/** 表を「見出し：値」の段落に開く（表に対応しないアプリ向け） */
function flattenTables(html: string): string {
  return html.replace(/<table[\s\S]*?<\/table>/gi, (table) => {
    const rows = [...table.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)].map((row) =>
      [...row[1].matchAll(/<t[hd][^>]*>([\s\S]*?)<\/t[hd]>/gi)].map((cell) => cell[1].trim()),
    );
    if (rows.length === 0) return "";
    const [head, ...body] = rows;
    if (body.length === 0) return `<p>${head.join("／")}</p>`;
    return body
      .map((cells) => `<p>${cells.map((cell, i) => (head[i] && i > 0 ? `${head[i]}：${cell}` : `<strong>${cell}</strong>`)).join("<br />")}</p>`)
      .join("\n");
  });
}

export type FeedHtmlOptions = {
  /** 本文中のリンクを残すか（グノシーは出典以外のリンクを原則置けない） */
  links: boolean;
  /** 表を残すか（グノシーは table 非対応） */
  tables: boolean;
};

/** 記事の全文 HTML（リード・要点・本文・出典・AI利用の開示）。JS・CSS・広告は含めない */
export async function feedHtml(article: FullArticle, options: FeedHtmlOptions): Promise<string> {
  const isAd = adLinkFilter(article);
  let body = (await articleBodyHtml(article))
    // サイト内リンクは絶対URLに
    .replace(/(href|src)="\/(?!\/)/g, `$1="${siteConfig.url}/`)
    // スクリプト・フォーム・ボタン類（記事には無いはずだが、念のため）
    .replace(/<(script|style|noscript|form|button|iframe|object|embed)\b[\s\S]*?<\/\1>/gi, "")
    .replace(/<(input|button|iframe|embed)\b[^>]*\/?>/gi, "")
    // 配信先では不要な属性
    .replace(/\s(?:id|class|style|target|align|rel|loading|decoding|data-[\w-]+)="[^"]*"/g, "")
    .replace(/<h1(\s[^>]*)?>/gi, "<h2>")
    .replace(/<\/h1>/gi, "</h2>");
  // 本文のリンク: 広告・紹介・自サイトへのリンクは文字だけ。外部の出典リンクは links のときだけ残す
  body = unwrap(body, (href) => options.links && /^https?:\/\//.test(href) && !href.startsWith(siteConfig.url) && !isAd(href));
  if (!options.tables) body = flattenTables(body);

  const parts: string[] = [];
  if (article.lede) parts.push(`<p>${escapeXml(article.lede)}</p>`);
  if (article.highlights.length > 0) {
    parts.push(`<h2>この記事のポイント</h2>`, `<ol>${article.highlights.map((h) => `<li>${escapeXml(h)}</li>`).join("")}</ol>`);
  }
  parts.push(body.trim());

  const src = sourceHref(article);
  if (src && /^https?:\/\//.test(src)) parts.push(`<p>出典：<a href="${escapeXml(src)}">${escapeXml(sourceLabel(article))}</a></p>`);
  const policy = `${siteConfig.url}/editorial-policy`;
  parts.push(
    options.links
      ? `<p>${AI_DISCLOSURE}制作方法と事実確認の手順は<a href="${policy}">${escapeXml(siteConfig.siteName)}の編集方針</a>をご覧ください。</p>`
      : `<p>${AI_DISCLOSURE}制作方法と事実確認の手順は${escapeXml(siteConfig.siteName)}の編集方針（${policy}）をご覧ください。</p>`,
  );
  return parts.join("\n");
}

/**
 * フィードに載せる記事（新しい順・本文つき）。暮らしとお金の記事だけ（lib/partner-feed.ts）。
 * maxAgeDays より古い記事は配信先が取り込まないので載せない
 */
export function pickFeedArticles({ limit, maxAgeDays }: { limit: number; maxAgeDays: number }): FullArticle[] {
  return pickPartnerArticles({ limit, maxAgeDays });
}

/** item の XML を作り、合計サイズが上限を超えたところで打ち切る（最低5件は残す） */
const encoder = new TextEncoder();

export async function buildItems(
  articles: FullArticle[],
  maxBytes: number,
  render: (article: FullArticle) => Promise<string>,
): Promise<string[]> {
  const items: string[] = [];
  let total = 0;
  for (const article of articles) {
    const item = await render(article);
    // 広告・紹介リンク・計測の画像などが残った記事は送らない（配信先の決まりに反するため）
    const problems = feedProblems(item);
    if (problems.length > 0) {
      console.warn(`[feeds] skip ${article.slug}: ${problems.join(",")}`);
      continue;
    }
    total += encoder.encode(item).length;
    if (total > maxBytes && items.length >= 5) break;
    items.push(item);
  }
  return items;
}

/** フィードのレスポンス。中身はデプロイごとに固定（エッジに置かれ、デプロイで入れ替わる） */
export function feedResponse(xml: string): Response {
  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=600, s-maxage=600",
    },
  });
}
