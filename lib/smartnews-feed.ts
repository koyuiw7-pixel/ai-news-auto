import { articleTitle } from "@/lib/headline";
import { getAllArticles, getArticle, getArticleSummary, sourceHref, sourceLabel, type ArticleSummary, type FullArticle } from "@/lib/articles";
import { cleanSections, dropOverviewSections, retitleHtml, stripSummaryOpener, titleSlugLinks } from "@/lib/article-sections";
import { insertBodyImages } from "@/lib/body-images";
import { isAffiliateUrl } from "@/lib/affiliate";
import { isDistributionEligible, isIndexable } from "@/lib/indexing";
import { renderMarkdown } from "@/lib/markdown";
import { buildItems, articleUrl, cdata, coverUrl, escapeXml, publishedOf, rfc822 } from "@/lib/feeds";
import { feedPhoto, photoFigure, smartnewsBody } from "@/lib/smartformat";
import { siteConfig } from "@/site.config";

/**
 * スマートニュース（SmartFormat / RSS 2.0）のフィードの中身（/feeds/smartnews.xml）。
 * 仕様: publishers.smartnews.com/hc/ja の「SmartFormat仕様書（RSS2.0準拠）」と「SmartFormat申請前のチェックリスト」。
 *
 * - 載せる記事: 検索に出している記事（lib/indexing.ts の isIndexable）で、従来の外部配信の基準も満たすもの。
 *   まとめ（他の記事へのリンクの一覧）・重複・未来の日時の記事は載せない。2週間より古い記事は取り込まれないので載せない。
 *   新しい順に最大50本・1MB以内。2週間で5本に届かないときだけ、古い記事で5本まで埋める（チェックリスト「常に5本以上」）
 * - 本文（content:encoded）: 記事ページと同じ全文（リード・要点・本文・本文の公式の写真・出典・AI利用の開示）。
 *   広告・PR・アフィリエイト・自サイトへの誘導リンク・ボタン・スクリプトは入れない（lib/smartformat.ts）
 * - サムネイル（media:thumbnail）: 共有カードと同じ写真の順。無ければ見出しのカバー（1200×630）
 * - snf:analytics は付けない（サイトは Google アナリティクスを使っていない。スマートニュースの数字は SmartNews Insights で見る）
 * - snf:relatedLink は Media Prosper Program の参加媒体だけが使えるので出さない
 */

export const SMARTNEWS_MAX_ITEMS = 50;
export const SMARTNEWS_MIN_ITEMS = 5;
export const SMARTNEWS_MAX_AGE_DAYS = 14;
export const SMARTNEWS_MAX_BYTES = 950_000;

/** スマートニュースに載せてよい記事か（検索対象・まとめでない・重複でない） */
export function smartnewsEligible(a: ArticleSummary): boolean {
  if (a.type === "roundup") return false;
  if (a.duplicate || (a.duplicateOf && a.duplicateOf !== a.slug)) return false;
  return isIndexable(a) && isDistributionEligible(a);
}

export function pickSmartnewsArticles(now = Date.now()): FullArticle[] {
  const published = getAllArticles()
    .filter(smartnewsEligible)
    .filter((a) => {
      const at = Date.parse(publishedOf(a));
      return Number.isFinite(at) && at <= now;
    });
  const fresh = published.filter((a) => now - Date.parse(publishedOf(a)) < SMARTNEWS_MAX_AGE_DAYS * 86_400_000);
  const chosen = (fresh.length >= SMARTNEWS_MIN_ITEMS ? fresh : published.slice(0, SMARTNEWS_MIN_ITEMS)).slice(0, SMARTNEWS_MAX_ITEMS);
  return chosen.map((a) => getArticle(a.slug)).filter((a): a is FullArticle => Boolean(a));
}

/** 記事の全文 HTML（SmartFormat 向け） */
export async function smartnewsHtml(article: FullArticle): Promise<string> {
  const affiliateUrls = new Set((article.affiliates ?? []).map((a) => a.url));
  const isAd = (href: string) => affiliateUrls.has(href) || isAffiliateUrl(href, affiliateUrls) || /\/api\/aff\//.test(href);
  // 記事ページと同じ下ごしらえ（app/articles/[slug]/page.tsx）: 要約の書き出し・概要の章を除き、空の章を隠す
  const opened = stripSummaryOpener(titleSlugLinks(article.body, (s) => getArticleSummary(s)?.title), article.lede ?? "");
  const body = cleanSections(article.lede && article.highlights.length > 0 ? dropOverviewSections(opened) : opened, article.sectionTitles?.body).markdown;
  const rendered = await renderMarkdown(body, [...affiliateUrls]);
  const withImages = retitleHtml(insertBodyImages(rendered, article.bodyImages ?? [], article.title), "body", article.sectionTitles);

  const title = articleTitle(article);
  const parts: string[] = [];
  const photo = feedPhoto(article);
  if (photo) parts.push(photoFigure(photo, title));
  if (article.lede) parts.push(`<p>${escapeXml(article.lede)}</p>`);
  if (article.highlights.length > 0) {
    parts.push(`<h2>この記事のポイント</h2>`, `<ol>${article.highlights.map((h) => `<li>${escapeXml(h)}</li>`).join("")}</ol>`);
  }
  parts.push(smartnewsBody(withImages, isAd).trim());

  // 最後の段落の後（ガイドラインの上限は3本）: 出典と編集方針
  const src = sourceHref(article);
  if (src && /^https?:\/\//.test(src)) parts.push(`<p>出典：<a href="${escapeXml(src)}">${escapeXml(sourceLabel(article))}</a></p>`);
  parts.push(
    `<p>この記事は生成AIを使って作成し、元の発表と照合してから公開しています。制作方法と事実確認の手順は<a href="${siteConfig.url}/editorial-policy">${escapeXml(siteConfig.siteName)}の編集方針</a>をご覧ください。</p>`,
  );
  return parts.join("\n");
}

export function smartnewsThumbnail(article: FullArticle): string {
  return feedPhoto(article)?.url ?? coverUrl(article);
}

async function smartnewsItem(a: FullArticle): Promise<string> {
  const categories = [a.genre, ...a.tags.slice(0, 3)].filter(Boolean).map((c) => c.replace(/,/g, " ")).join(",");
  return `    <item>
      <title>${escapeXml(articleTitle(a))}</title>
      <link>${articleUrl(a)}</link>
      <guid isPermaLink="true">${articleUrl(a)}</guid>
      <description>${escapeXml(a.description)}</description>
      <pubDate>${rfc822(publishedOf(a))}</pubDate>
      <category>${escapeXml(categories)}</category>
      <dc:creator>${escapeXml(siteConfig.author)}</dc:creator>
      <media:thumbnail url="${escapeXml(smartnewsThumbnail(a))}" />
      <media:status>active</media:status>
      <content:encoded>${cdata(await smartnewsHtml(a))}</content:encoded>
    </item>`;
}

export async function smartnewsFeedXml(now = Date.now()): Promise<{ xml: string; count: number }> {
  const articles = pickSmartnewsArticles(now);
  const items = await buildItems(articles, SMARTNEWS_MAX_BYTES, smartnewsItem);
  // channel.pubDate は「ファイルを作った日時」（仕様書）
  const built = rfc822(new Date(now).toISOString());
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:snf="http://www.smartnews.be/snf">
  <channel>
    <title>${escapeXml(siteConfig.siteName)}</title>
    <link>${siteConfig.url}</link>
    <description>海外AIの新発表を最速で解説</description>
    <pubDate>${built}</pubDate>
    <language>ja</language>
    <copyright>© ${escapeXml(siteConfig.siteName)}</copyright>
    <ttl>15</ttl>
    <snf:logo><url>${siteConfig.url}/feeds/smartnews-logo.png</url></snf:logo>
    <snf:darkModeLogo><url>${siteConfig.url}/feeds/smartnews-logo-dark.png</url></snf:darkModeLogo>
${items.join("\n")}
  </channel>
</rss>
`;
  return { xml, count: items.length };
}
