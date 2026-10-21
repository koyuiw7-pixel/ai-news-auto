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

/** まとめ記事が統合した元記事 */
export type RoundupSource = {
  slug: string;
  title: string;
  publishedAt: string;
  channel: string;
};

export type Article = {
  slug: string;
  /** "roundup" は複数記事を統合した横断まとめ。省略時は通常記事 */
  type?: "roundup";
  /** まとめ記事が統合した元記事（type === "roundup" のとき） */
  sources?: RoundupSource[];
  /** 通常記事から、自分を含むまとめ記事への逆リンク */
  roundupSlug?: string;
  roundupTitle?: string;
  title: string;
  /** 検索結果用の短い題名（<title>）。無ければ title を使う */
  seoTitle?: string;
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
  /** ジャンル（AI・テクノロジー / 不動産 …） */
  genre: string;
  genreSlug: string;
  /** ジャンルごとの免責文（不動産は投資勧誘でない旨を含む） */
  disclaimer: string;
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
        sources: parsed.sources ?? [],
        lede: parsed.lede ?? "",
        genre: parsed.genre ?? "AI・テクノロジー",
        genreSlug: parsed.genreSlug ?? "ai",
        disclaimer: parsed.disclaimer ?? "",
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

/** 横断まとめ記事だけを新しい順に返す（トップのハブ枠用） */
export function getRoundups(): Article[] {
  return getAllArticles().filter((a) => a.type === "roundup");
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
        (a.channelSlug === article.channelSlug ? 1 : 0) +
        // 別ジャンルの記事が関連記事に混ざらないよう強めに重み付けする
        (a.genreSlug === article.genreSlug ? 5 : 0),
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

/**
 * タグの識別子。**URLエンコードしない**のが重要。
 * generateStaticParams に渡す値は「デコード済み」でなければならず、
 * ここでエンコードすると Next.js が再度エンコードして二重エンコードになり、
 * 日本語タグのページが 404 になる。
 */
export function tagSlug(tag: string): string {
  return tag.trim().toLowerCase().replace(/\s+/g, "-");
}

/** リンクの href には（ブラウザ互換のため）エンコードした値を使う */
export function tagHref(tag: string): string {
  return `/tags/${encodeURIComponent(tagSlug(tag))}`;
}

export function getAllTags(): Facet[] {
  const map = new Map<string, Facet>();
  for (const article of getAllArticles()) {
    for (const tag of article.tags) {
      const slug = tagSlug(tag);
      if (!slug) continue;
      const found = map.get(slug);
      if (found) found.count += 1;
      else map.set(slug, { slug, label: tag, count: 1 });
    }
  }
  return [...map.values()].sort((a, b) => b.count - a.count);
}

export function getArticlesByTag(slug: string): Article[] {
  // Next.js が渡す params はデコード済みだが、念のため両方で照合する
  const decoded = safeDecode(slug);
  return getAllArticles().filter((a) =>
    a.tags.some((t) => {
      const s = tagSlug(t);
      return s === slug || s === decoded;
    }),
  );
}

/**
 * 表示用のタグ名。params は環境によって %XX のまま渡ることがあるため、
 * 必ずデコードしてから照合する（しないと見出しに %E4%B8%8D... が出る）。
 */
export function getTagLabel(slug: string): string {
  const decoded = safeDecode(slug);
  const found = getAllTags().find(
    (t) => t.slug === slug || t.slug === decoded,
  );
  return found?.label ?? decoded;
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** ジャンル一覧（記事が1本でもあるものだけ） */
export function getAllGenres(): Facet[] {
  const map = new Map<string, Facet>();
  for (const article of getAllArticles()) {
    if (!article.genreSlug) continue;
    const found = map.get(article.genreSlug);
    if (found) found.count += 1;
    else
      map.set(article.genreSlug, {
        slug: article.genreSlug,
        label: article.genre,
        count: 1,
      });
  }
  return [...map.values()].sort((a, b) => b.count - a.count);
}

export function getArticlesByGenre(genreSlug: string): Article[] {
  return getAllArticles().filter((a) => a.genreSlug === genreSlug);
}

/** そのジャンルに属するチャンネル一覧 */
export function getChannelsByGenre(genreSlug: string): Facet[] {
  const map = new Map<string, Facet>();
  for (const article of getArticlesByGenre(genreSlug)) {
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
