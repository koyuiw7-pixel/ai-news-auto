import { getAllArticles } from "@/lib/articles";
import { getAllWeeks, weekPublishedAt } from "@/lib/weekly";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function GET() {
  const articles = getAllArticles().slice(0, 50);

  const articleItems = articles.map((article) => ({
    at: Date.parse(article.publishedAt),
    xml: `    <item>
      <title>${escapeXml(article.title)}</title>
      <link>${siteConfig.url}/articles/${article.slug}</link>
      <guid isPermaLink="true">${siteConfig.url}/articles/${article.slug}</guid>
      <description>${escapeXml(article.description)}</description>
      <category>${escapeXml(article.genre)}</category>
      <category>${escapeXml(article.channel)}</category>
      <pubDate>${new Date(article.publishedAt).toUTCString()}</pubDate>
    </item>`,
  }));
  // 週まとめ（直近4週）も同じフィードに流す
  const weekItems = getAllWeeks()
    .slice(0, 4)
    .map((week) => ({
      at: Date.parse(weekPublishedAt(week)),
      xml: `    <item>
      <title>${escapeXml(week.title)}</title>
      <link>${siteConfig.url}/weekly/${week.id}</link>
      <guid isPermaLink="true">${siteConfig.url}/weekly/${week.id}</guid>
      <description>${escapeXml(week.lede.join(""))}</description>
      <category>今週のAIニュース</category>
      <pubDate>${new Date(weekPublishedAt(week)).toUTCString()}</pubDate>
    </item>`,
    }));
  const items = [...articleItems, ...weekItems]
    .sort((a, b) => b.at - a.at)
    .map((item) => item.xml)
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(siteConfig.name)}</title>
    <link>${siteConfig.url}</link>
    <description>${escapeXml(siteConfig.description)}</description>
    <language>ja</language>
    <atom:link href="${siteConfig.url}/feed.xml" rel="self" type="application/rss+xml" />
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
}
