import { buildItems, articleUrl, cdata, coverUrl, escapeXml, feedHtml, feedResponse, pickFeedArticles, publishedOf, rfc822 } from "@/lib/feeds";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

/**
 * 配信先向けの汎用フィード（RSS 2.0・全文入り）。仕様が非公開の配信先（NewsPicks・LINE NEWS など）の
 * 申請フォームに書く用。/feed.xml（要約のみ・全記事）は読者・RSSリーダー向けにそのまま残す。
 */
export async function GET() {
  const articles = pickFeedArticles({ limit: 50, maxAgeDays: 14 });
  const items = await buildItems(articles, 1_900_000, async (a) => `    <item>
      <title>${escapeXml(a.title)}</title>
      <link>${articleUrl(a)}</link>
      <guid isPermaLink="true">${articleUrl(a)}</guid>
      <description>${escapeXml(a.description)}</description>
      <pubDate>${rfc822(publishedOf(a))}</pubDate>
      <category>${escapeXml(a.genre)}</category>
      <dc:creator>${escapeXml(siteConfig.author)}</dc:creator>
      <enclosure url="${coverUrl(a)}" type="image/jpeg" length="0" />
      <media:content url="${coverUrl(a)}" medium="image" type="image/jpeg" width="1200" height="630" />
      <content:encoded>${cdata(await feedHtml(a, { links: true, tables: true }))}</content:encoded>
    </item>`);

  const latest = articles[0] ? rfc822(publishedOf(articles[0])) : new Date().toUTCString();
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(siteConfig.siteName)}</title>
    <link>${siteConfig.url}</link>
    <description>${escapeXml(siteConfig.description)}</description>
    <language>ja</language>
    <copyright>© ${escapeXml(siteConfig.siteName)}</copyright>
    <lastBuildDate>${latest}</lastBuildDate>
    <ttl>15</ttl>
    <atom:link href="${siteConfig.url}/feeds/news.xml" rel="self" type="application/rss+xml" />
    <image>
      <url>${siteConfig.url}/icon</url>
      <title>${escapeXml(siteConfig.siteName)}</title>
      <link>${siteConfig.url}</link>
    </image>
${items.join("\n")}
  </channel>
</rss>
`;
  return feedResponse(xml);
}
