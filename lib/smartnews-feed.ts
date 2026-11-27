import { articleTitle } from "@/lib/headline";
import { sourceHref, sourceLabel, type ArticleSummary, type FullArticle } from "@/lib/articles";
import { isPartnerArticle, pickPartnerArticles } from "@/lib/partner-feed";
import { AI_DISCLOSURE, adLinkFilter, articleBodyHtml, buildItems, articleUrl, cdata, coverUrl, escapeXml, publishedOf, rfc822 } from "@/lib/feeds";
import { feedPhoto, photoFigure, smartnewsBody } from "@/lib/smartformat";
import { siteConfig } from "@/site.config";

/**
 * スマートニュース（SmartFormat / RSS 2.0）のフィードの中身（/feeds/smartnews.xml）。
 * 仕様: publishers.smartnews.com/hc/ja の「SmartFormat仕様書（RSS2.0準拠）」と「SmartFormat申請前のチェックリスト」。
 *
 * - 載せる記事: 暮らしとお金の記事だけ（lib/partner-feed.ts。2026-11-28 の新しい方向）。検索に出している記事で、従来の外部配信の基準も満たすもの。
 *   まとめ（他の記事へのリンクの一覧）・重複・比較ページ・未来の日時の記事は載せない。2週間より古い記事は取り込まれないので載せない。
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

/** スマートニュースに載せてよい記事か（暮らしとお金の記事・検索対象・まとめでない・重複でない） */
export function smartnewsEligible(a: ArticleSummary): boolean {
  return isPartnerArticle(a);
}

export function pickSmartnewsArticles(now = Date.now()): FullArticle[] {
  return pickPartnerArticles({ limit: SMARTNEWS_MAX_ITEMS, maxAgeDays: SMARTNEWS_MAX_AGE_DAYS, minItems: SMARTNEWS_MIN_ITEMS, now });
}

/** 記事の全文 HTML（SmartFormat 向け） */
export async function smartnewsHtml(article: FullArticle): Promise<string> {
  const isAd = adLinkFilter(article);
  const withImages = await articleBodyHtml(article);

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
    `<p>${AI_DISCLOSURE}制作方法と事実確認の手順は<a href="${siteConfig.url}/editorial-policy">${escapeXml(siteConfig.siteName)}の編集方針</a>をご覧ください。</p>`,
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
      <media:thumbnail url="${escapeXml(smartnewsThumbnail(a))}">${escapeXml(smartnewsThumbnail(a))}</media:thumbnail>
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
    <description>${escapeXml(siteConfig.feedShortDescription)}</description>
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
