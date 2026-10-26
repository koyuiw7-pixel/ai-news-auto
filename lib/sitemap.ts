import { isIndexable } from "@/lib/indexing";
import {
  getAllArticles,
  getAllChannels,
  getAllGenres,
  getAllTags,
  lastModifiedOf,
  tagSlug,
} from "@/lib/articles";
import { companyCounts } from "@/lib/companies";
import { getAllGuides, guideArticles } from "@/lib/guides";
import { siteConfig } from "@/site.config";

export type SitemapEntry = {
  url: string;
  lastModified: Date;
  changeFrequency: "always" | "hourly" | "daily" | "weekly" | "monthly" | "yearly" | "never";
  priority: number;
};

/** 1ファイルに載せる URL の上限（仕様上は5万。余裕を持たせる） */
export const SITEMAP_CHUNK = 40000;

/** サイトマップに載せる全 URL（記事は全件） */
export function sitemapEntries(): SitemapEntry[] {
  const base = siteConfig.url;
  // 全ジャンルが対象。ただし薄くなりやすい記事は検索に出さないので載せない（lib/indexing.ts）
  const articles = getAllArticles().filter(isIndexable);
  const liveChannels = new Set(articles.map((a) => a.channelSlug));
  const liveTags = new Set(articles.flatMap((a) => a.tags.map(tagSlug)));
  const lastModified = articles[0]?.generatedAt
    ? new Date(articles[0].generatedAt)
    : new Date();

  return [
    {
      url: base,
      lastModified,
      changeFrequency: "hourly" as const,
      priority: 1,
    },
    {
      url: `${base}/articles`,
      lastModified,
      changeFrequency: "hourly" as const,
      priority: 0.9,
    },
    ...["/about", "/editorial-policy", "/privacy", "/disclaimer", "/contact"].map((path) => ({
      url: `${base}${path}`,
      lastModified,
      changeFrequency: "yearly" as const,
      priority: 0.3,
    })),
    ...articles.map((article) => ({
      url: `${base}/articles/${article.slug}`,
      // 続報を足した記事は最終更新日時
      lastModified: new Date(lastModifiedOf(article)),
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...getAllGenres()
      .filter((genre) => genre.slug === "ai")
      .map((genre) => ({
      url: `${base}/genres/${genre.slug}`,
      lastModified,
      changeFrequency: "hourly" as const,
      priority: 0.9,
    })),
    ...getAllChannels()
      .filter((channel) => liveChannels.has(channel.slug))
      .map((channel) => ({
      url: `${base}/channels/${channel.slug}`,
      lastModified,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
    { url: `${base}/usable`, lastModified, changeFrequency: "daily" as const, priority: 0.9 },
    { url: `${base}/guides`, lastModified, changeFrequency: "daily" as const, priority: 0.8 },
    ...getAllGuides().map((guide) => ({
      url: `${base}/guides/${guide.slug}`,
      lastModified: new Date(guideArticles(guide)[0]?.publishedAt ?? lastModified),
      changeFrequency: "daily" as const,
      priority: 0.9,
    })),
    ...companyCounts(articles).map(({ company }) => ({
      url: `${base}/companies/${company.slug}`,
      lastModified,
      changeFrequency: "hourly" as const,
      priority: 0.8,
    })),
    ...getAllTags()
      .filter((tag) => liveTags.has(tag.slug))
      .map((tag) => ({
      url: `${base}/tags/${encodeURIComponent(tag.slug)}`,
      lastModified,
      changeFrequency: "daily" as const,
      priority: 0.6,
    })),
  ];
}

/** URL 数が上限を超えたら分割する。分割後のファイル数 */
export function sitemapChunkCount(): number {
  return Math.max(1, Math.ceil(sitemapEntries().length / SITEMAP_CHUNK));
}

const escapeXml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");

export function renderUrlset(entries: SitemapEntry[]): string {
  const urls = entries
    .map(
      (e) =>
        `<url>\n<loc>${escapeXml(e.url)}</loc>\n${Number.isNaN(e.lastModified.getTime()) ? "" : `<lastmod>${e.lastModified.toISOString()}</lastmod>\n`}<changefreq>${e.changeFrequency}</changefreq>\n<priority>${e.priority}</priority>\n</url>`,
    )
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

export function renderIndex(count: number): string {
  const now = new Date().toISOString();
  const items = Array.from(
    { length: count },
    (_, i) => `<sitemap>\n<loc>${siteConfig.url}/sitemaps/${i}.xml</loc>\n<lastmod>${now}</lastmod>\n</sitemap>`,
  ).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${items}\n</sitemapindex>\n`;
}

export const XML_HEADERS = { "Content-Type": "application/xml; charset=utf-8" };
