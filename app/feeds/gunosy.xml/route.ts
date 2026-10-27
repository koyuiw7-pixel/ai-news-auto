import { buildItems, articleUrl, cdata, coverUrl, escapeXml, feedHtml, feedResponse, pickFeedArticles, publishedOf, rfc822 } from "@/lib/feeds";
import { lastModifiedOf } from "@/lib/articles";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

/**
 * グノシー用のフィード（GunosyFeed ver 3.2.x / RSS 2.0）。
 * - 全文必須。table 非対応なので表は段落に開く
 * - 本文のリンクは原則置けない（出典は例外）ので、本文中のリンクは文字だけ残す
 * - guid は URL 形式不可 → slug。10日より古い記事は取り込まれない
 */
export async function GET() {
  const articles = pickFeedArticles({ limit: 50, maxAgeDays: 10 });
  const items = await buildItems(articles, 1_900_000, async (a) => `    <item>
      <title>${escapeXml(a.title)}</title>
      <link>${articleUrl(a)}</link>
      <guid isPermaLink="false">saisoku-${a.slug}</guid>
      <pubDate>${rfc822(publishedOf(a))}</pubDate>
      <gnf:modified>${rfc822(lastModifiedOf(a))}</gnf:modified>
      <dc:creator>${escapeXml(siteConfig.author)}</dc:creator>
      <media:status state="active" />
      <enclosure url="${coverUrl(a)}" type="image/jpeg" length="0" />
      <content:encoded>${cdata(await feedHtml(a, { links: false, tables: false }))}</content:encoded>
    </item>`);

  const latest = articles[0] ? rfc822(publishedOf(articles[0])) : new Date().toUTCString();
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:gnf="http://assets.gunosy.com/media/gnf" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>${escapeXml(siteConfig.siteName)}</title>
    <link>${siteConfig.url}</link>
    <description>海外AIの新発表を最速で日本語に。今すぐ使えるかまで解説</description>
    <language>ja</language>
    <copyright>© ${escapeXml(siteConfig.siteName)}</copyright>
    <ttl>15</ttl>
    <lastBuildDate>${latest}</lastBuildDate>
    <image>
      <url>${siteConfig.url}/icon</url>
      <title>${escapeXml(siteConfig.siteName)}</title>
      <link>${siteConfig.url}</link>
    </image>
    <gnf:wide_image_link>${siteConfig.url}/feeds/logo-44.png</gnf:wide_image_link>
${items.join("\n")}
  </channel>
</rss>
`;
  return feedResponse(xml);
}
