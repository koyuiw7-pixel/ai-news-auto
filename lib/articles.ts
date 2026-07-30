import fs from "node:fs";
import path from "node:path";

export type TimetableItem = {
  time: string;
  label: string;
};

/** affiliate_links.json との照合でパイプラインが自動挿入する */
export type AffiliateLink = {
  name: string;
  label: string;
  url: string;
  note?: string;
};

export type Article = {
  slug: string;
  title: string;
  /** 記事冒頭のリード文 */
  lede: string;
  description: string;
  keywords: string[];
  tags: string[];
  highlights: string[];
  timetable: TimetableItem[];
  affiliates: AffiliateLink[];
  body: string;
  channel: string;
  channelId: string;
  channelSlug: string;
  videoId: string;
  videoUrl: string;
  videoTitle: string;
  publishedAt: string;
  generatedAt: string;
  thumbnail: string;
  model: string;
};

const ARTICLES_DIR = path.join(process.cwd(), "content", "articles");

function isArticle(value: unknown): value is Article {
  if (typeof value !== "object" || value === null) return false;
  const a = value as Record<string, unknown>;
  return (
    typeof a.slug === "string" &&
    typeof a.title === "string" &&
    typeof a.body === "string" &&
    typeof a.videoId === "string"
  );
}

/** 壊れた JSON が 1 本混ざってもビルドを落とさないよう、個別に握り潰す */
function readAll(): Article[] {
  if (!fs.existsSync(ARTICLES_DIR)) return [];

  const articles: Article[] = [];
  for (const file of fs.readdirSync(ARTICLES_DIR)) {
    if (!file.endsWith(".json")) continue;
    try {
      const raw = fs.readFileSync(path.join(ARTICLES_DIR, file), "utf8");
      const parsed: unknown = JSON.parse(raw);
      if (!isArticle(parsed)) {
        console.warn(`[articles] skip (schema mismatch): ${file}`);
        continue;
      }
      articles.push({
        ...parsed,
        keywords: parsed.keywords ?? [],
        tags: parsed.tags ?? [],
        highlights: parsed.highlights ?? [],
        timetable: parsed.timetable ?? [],
        affiliates: parsed.affiliates ?? [],
        lede: parsed.lede ?? "",
      });
    } catch (error) {
      console.warn(`[articles] skip (invalid JSON): ${file}`, error);
    }
  }

  return articles.sort(
    (a, b) =>
      new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime(),
  );
}

// モジュールスコープでキャッシュ（ビルド中に何百回も呼ばれるため）
let cache: Article[] | null = null;

export function getAllArticles(): Article[] {
  if (cache === null) cache = readAll();
  return cache;
}

export function getArticle(slug: string): Article | undefined {
  return getAllArticles().find((a) => a.slug === slug);
}

export function getRelatedArticles(article: Article, limit = 4): Article[] {
  const tags = new Set(article.tags);
  return getAllArticles()
    .filter((a) => a.slug !== article.slug)
    .map((a) => ({
      article: a,
      score:
        a.tags.filter((t) => tags.has(t)).length +
        (a.channelSlug === article.channelSlug ? 1 : 0),
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((x) => x.article);
}

/* ------------------------------------------------------------------ */
/* pSEO 用の集約（タグ別 / チャンネル別ページを自動生成するための材料）   */
/* ------------------------------------------------------------------ */

export type Facet = {
  slug: string;
  label: string;
  count: number;
};

export function encodeTag(tag: string): string {
  return encodeURIComponent(tag.trim().toLowerCase().replace(/\s+/g, "-"));
}

export function getAllTags(): Facet[] {
  const map = new Map<string, Facet>();
  for (const article of getAllArticles()) {
    for (const tag of article.tags) {
      const slug = encodeTag(tag);
      if (!slug) continue;
      const found = map.get(slug);
      if (found) found.count += 1;
      else map.set(slug, { slug, label: tag, count: 1 });
    }
  }
  return [...map.values()].sort((a, b) => b.count - a.count);
}

export function getArticlesByTag(tagSlug: string): Article[] {
  return getAllArticles().filter((a) =>
    a.tags.some((t) => encodeTag(t) === tagSlug),
  );
}

export function getAllChannels(): Facet[] {
  const map = new Map<string, Facet>();
  for (const article of getAllArticles()) {
    if (!article.channelSlug) continue;
    const found = map.get(article.channelSlug);
    if (found) found.count += 1;
    else
      map.set(article.channelSlug, {
        slug: article.channelSlug,
        label: article.channel,
        count: 1,
      });
  }
  return [...map.values()].sort((a, b) => b.count - a.count);
}

export function getArticlesByChannel(channelSlug: string): Article[] {
  return getAllArticles().filter((a) => a.channelSlug === channelSlug);
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Tokyo",
  }).format(date);
}
