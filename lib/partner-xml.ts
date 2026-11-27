import { buildItems, articleUrl, cdata, coverUrl, escapeXml, feedHtml, pickFeedArticles, publishedOf, rfc822 } from "@/lib/feeds";
import { lastModifiedOf } from "@/lib/articles";
import { siteConfig } from "@/site.config";

/**
 * 配信先向けの汎用フィード（RSS 2.0・全文入り。/feeds/partner.xml と、前からある /feeds/news.xml は同じ中身）。
 * グノシーの「RSS の URL」欄や、仕様が非公開の配信先（Yahoo!ニュース・LINE NEWS・MSN・NewsPicks）の申し込みに書く用。
 * 暮らしとお金の記事だけ・直近14日・最大50本（lib/partner-feed.ts）。広告・紹介リンク・PR・計測の画像は入れない。
 */
export const PARTNER_MAX_ITEMS = 50;
export const PARTNER_MAX_AGE_DAYS = 14;

export async function partnerFeedXml(selfPath: string, now = Date.now()): Promise<{ xml: string; count: number }> {
  const articles = pickFeedArticles({ limit: PARTNER_MAX_ITEMS, maxAgeDays: PARTNER_MAX_AGE_DAYS });
  const items = await buildItems(articles, 1_900_000, async (a) => `    <item>
      <title>${escapeXml(a.title)}</title>
      <link>${articleUrl(a)}</link>
      <guid isPermaLink="true">${articleUrl(a)}</guid>
      <description>${escapeXml(a.description)}</description>
      <pubDate>${rfc822(publishedOf(a))}</pubDate>
      <atom:updated>${new Date(lastModifiedOf(a)).toISOString()}</atom:updated>
      <category>${escapeXml(a.genre)}</category>
      <dc:creator>${escapeXml(siteConfig.author)}</dc:creator>
      <enclosure url="${coverUrl(a)}" type="image/jpeg" length="0" />
      <media:content url="${coverUrl(a)}" medium="image" type="image/jpeg" width="1200" height="630" />
      <media:thumbnail url="${coverUrl(a)}" width="1200" height="630" />
      <content:encoded>${cdata(await feedHtml(a, { links: true, tables: true }))}</content:encoded>
    </item>`);

  const built = rfc822(new Date(now).toISOString());
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(siteConfig.siteName)}</title>
    <link>${siteConfig.url}</link>
    <description>${escapeXml(siteConfig.feedDescription)}</description>
    <language>ja</language>
    <copyright>© ${escapeXml(siteConfig.siteName)}</copyright>
    <managingEditor>${escapeXml(siteConfig.operator.email)} (${escapeXml(siteConfig.author)})</managingEditor>
    <lastBuildDate>${built}</lastBuildDate>
    <ttl>15</ttl>
    <atom:link href="${siteConfig.url}${selfPath}" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
    <image>
      <url>${siteConfig.url}/icon</url>
      <title>${escapeXml(siteConfig.siteName)}</title>
      <link>${siteConfig.url}</link>
    </image>
${items.join("\n")}
  </channel>
</rss>
`;
  return { xml, count: items.length };
}
