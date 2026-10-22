import type { MetadataRoute } from "next";
import {
  getAllArticles,
  getAllChannels,
  getAllGenres,
  getAllTags,
  tagSlug,
} from "@/lib/articles";
import { companyCounts } from "@/lib/companies";
import { getAllGuides, guideArticles } from "@/lib/guides";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = siteConfig.url;
  // 検索対象はAIジャンルのみ。noindex にしたページは sitemap からも外す
  const articles = getAllArticles().filter((a) => a.genreSlug === "ai");
  const liveChannels = new Set(articles.map((a) => a.channelSlug));
  const liveTags = new Set(articles.flatMap((a) => a.tags.map(tagSlug)));
  const lastModified = articles[0]?.generatedAt
    ? new Date(articles[0].generatedAt)
    : new Date();

  return [
    {
      url: base,
      lastModified,
      changeFrequency: "hourly",
      priority: 1,
    },
    {
      url: `${base}/articles`,
      lastModified,
      changeFrequency: "hourly",
      priority: 0.9,
    },
    ...["/about", "/privacy", "/disclaimer", "/contact"].map((path) => ({
      url: `${base}${path}`,
      lastModified,
      changeFrequency: "yearly" as const,
      priority: 0.3,
    })),
    ...articles.map((article) => ({
      url: `${base}/articles/${article.slug}`,
      lastModified: new Date(article.generatedAt || article.publishedAt),
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
