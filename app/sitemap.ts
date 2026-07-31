import type { MetadataRoute } from "next";
import {
  getAllArticles,
  getAllChannels,
  getAllGenres,
  getAllTags,
} from "@/lib/articles";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = siteConfig.url;
  const articles = getAllArticles();
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
    ...articles.map((article) => ({
      url: `${base}/articles/${article.slug}`,
      lastModified: new Date(article.generatedAt || article.publishedAt),
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...getAllGenres().map((genre) => ({
      url: `${base}/genres/${genre.slug}`,
      lastModified,
      changeFrequency: "hourly" as const,
      priority: 0.9,
    })),
    ...getAllChannels().map((channel) => ({
      url: `${base}/channels/${channel.slug}`,
      lastModified,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
    ...getAllTags().map((tag) => ({
      url: `${base}/tags/${tag.slug}`,
      lastModified,
      changeFrequency: "daily" as const,
      priority: 0.6,
    })),
  ];
}
