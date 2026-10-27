import { buildItems, articleUrl, cdata, coverUrl, escapeXml, feedHtml, feedResponse, pickFeedArticles, publishedOf, rfc822 } from "@/lib/feeds";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

/**
 * スマートニュース用のフィード（SmartFormat / RSS 2.0）。
 * 全文（content:encoded）と記事ごとのカバー画像（media:thumbnail、1200×630）を載せる。
 * 2週間より古い記事は取り込まれないので載せない。1ファイル1MB以内が推奨。
 * snf:relatedLink は Media Prosper Program の参加媒体だけが使えるので出さない。
 */
export async function GET() {
  const articles = pickFeedArticles({ limit: 50, maxAgeDays: 14 });
  const items = await buildItems(articles, 950_000, async (a) => {
    const categories = [a.genre, ...a.tags.slice(0, 3)].filter(Boolean).join(",");
    return `    <item>
      <title>${escapeXml(a.title)}</title>
      <link>${articleUrl(a)}</link>
      <guid isPermaLink="true">${articleUrl(a)}</guid>
      <description>${escapeXml(a.description)}</description>
      <pubDate>${rfc822(publishedOf(a))}</pubDate>
      <category>${escapeXml(categories)}</category>
      <dc:creator>${escapeXml(siteConfig.author)}</dc:creator>
      <dc:language>ja</dc:language>
      <media:thumbnail url="${coverUrl(a)}" />
      <content:encoded>${cdata(await feedHtml(a, { links: true, tables: true }))}</content:encoded>
    </item>`;
  });

  const latest = articles[0] ? rfc822(publishedOf(articles[0])) : new Date().toUTCString();
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:snf="http://www.smartnews.be/snf" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(siteConfig.siteName)}</title>
    <link>${siteConfig.url}</link>
    <description>海外AIの新発表を最速で解説</description>
    <pubDate>${latest}</pubDate>
    <lastBuildDate>${latest}</lastBuildDate>
    <language>ja</language>
    <copyright>© ${escapeXml(siteConfig.siteName)}</copyright>
    <ttl>15</ttl>
    <atom:link href="${siteConfig.url}/feeds/smartnews.xml" rel="self" type="application/rss+xml" />
    <snf:logo><url>${siteConfig.url}/feeds/logo-wide.png</url></snf:logo>
${items.join("\n")}
  </channel>
</rss>
`;
  return feedResponse(xml);
}
