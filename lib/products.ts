import fs from "@/lib/content-fs";
import path from "node:path";
import { getArticleSummary, type ArticleSummary } from "@/lib/articles";

/**
 * 製品ごとのまとめページ（content/products/*.json、scripts/products.py が作る）。
 *
 * ニュースは数日で読まれなくなるが、「〇〇とは」「料金」「日本で使える？」は長く検索される。
 * 中身はすべて自サイトの記事から取った事実で、項目ごとに出典の記事 slug を持つ。
 */
export type Sourced = { text: string; sources: string[] };

export type Product = {
  slug: string;
  name: string;
  aliases: string[];
  /** lib/companies.ts の slug（色・企業ページがない企業は "other"） */
  company: string;
  companyName: string;
  category: string;
  overview: Sourced;
  facts: { label: string; value: string; sources: string[] }[];
  capabilities: Sourced[];
  pricing: Sourced[];
  japan: Sourced[];
  howto: Sourced[];
  differences: Sourced[];
  faq: { q: string; a: string; sources: string[] }[];
  timeline: { date: string; slug: string; event: string }[];
  /** 関連する製品の slug */
  related: string[];
  /** 関係する記事（新しい順） */
  articles: string[];
  /** この製品のまとめページへ案内する記事 */
  linkFrom: string[];
  createdAt: string;
  updatedAt: string;
};

// 文字列で組み立てて、content/ 全体をサーバー関数に同梱させない（lib/articles.ts と同じ理由）
const PRODUCTS_DIR = [process.cwd(), "content", "products"].join(path.sep);

let cache: Product[] | null = null;

/** 関係する記事の多い順 */
export function getAllProducts(): Product[] {
  if (cache) return cache;
  if (!fs.existsSync(PRODUCTS_DIR)) return (cache = []);
  cache = fs
    .readdirSync(PRODUCTS_DIR)
    .filter((file) => file.endsWith(".json"))
    .flatMap((file) => {
      try {
        const data = JSON.parse(fs.readFileSync(/* turbopackIgnore: true */ `${PRODUCTS_DIR}${path.sep}${file}`, "utf8")) as Product;
        return data.slug && data.overview?.text ? [data] : [];
      } catch {
        return [];
      }
    })
    .sort((a, b) => b.articles.length - a.articles.length || a.name.localeCompare(b.name));
  return cache;
}

export function getProduct(slug: string): Product | undefined {
  return getAllProducts().find((p) => p.slug === slug);
}

let byArticle: Map<string, Product> | null = null;

/** 記事から案内するまとめページ（題名でいちばん手前に出てくる製品。1記事に1つ） */
export function productForArticle(articleSlug: string): Product | undefined {
  if (!byArticle) {
    byArticle = new Map();
    for (const product of getAllProducts()) {
      for (const slug of product.linkFrom ?? []) if (!byArticle.has(slug)) byArticle.set(slug, product);
    }
  }
  return byArticle.get(articleSlug);
}

/** 企業ページに出す製品（関係する記事の多い順） */
export function productsByCompany(company: string): Product[] {
  return getAllProducts().filter((p) => p.company === company);
}

/** 関係する記事（索引にある記事だけ。新しい順） */
export function productArticles(product: Product): ArticleSummary[] {
  return product.articles.map((slug) => getArticleSummary(slug)).filter((a): a is ArticleSummary => Boolean(a));
}

/** 料金・日本での提供がわかる製品か（題名の言い方を変える） */
export function hasBuyingInfo(product: Product): boolean {
  // 「未発表」だけの料金は、料金がわかる製品として扱わない（研究段階の製品など）
  return product.pricing.length > 0 || product.facts.some((f) => f.label === "料金" && !/未発表|未定|不明|なし/.test(f.value));
}

/** 検索結果の題名 */
export function productSeoTitle(product: Product): string {
  return hasBuyingInfo(product)
    ? `${product.name}とは？料金・使い方・日本で使えるか【最新】`
    : `${product.name}とは？できること・これまでの流れ【最新】`;
}

/** ページの見出し（【最新】は検索結果用なので付けない） */
export function productHeading(product: Product): string {
  return hasBuyingInfo(product)
    ? `${product.name}とは？料金・使い方・日本で使えるか`
    : `${product.name}とは？できること・これまでの流れ`;
}

/** 同じ製品の古い製品ガイド（/guides/<slug>）は、まとめページへ転送する */
export function supersededGuideSlugs(guideSlugs: string[]): string[] {
  const slugs = new Set(getAllProducts().map((p) => p.slug));
  return guideSlugs.filter((slug) => slugs.has(slug));
}
