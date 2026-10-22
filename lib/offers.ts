import fs from "node:fs";
import path from "node:path";
import type { Article } from "@/lib/articles";

/**
 * 記事の途中に出す「試すなら」枠。
 * 話題の定義は content/offers.json、本の候補は content/products.json（scripts/rakuten_books.py が更新）。
 * 全記事に出すため、話題が当たらない記事も「向いている人」や既定の話題で必ず1つ選ぶ。
 */

type Topic = {
  key: string;
  match: string;
  eyebrow: string;
  headline: string;
  lead: string;
  partners: string[];
  search?: string | string[];
  /** 商品が足りないときに補う話題 */
  fill?: string[];
};

type Partner = {
  program: string;
  name: string;
  label: string;
  note?: string;
  price: number | null;
  priceText?: string;
  image: string | null;
  page: string | null;
  shop: string;
};

type Book = {
  rbId: string;
  title: string;
  author: string;
  price: number;
  rating: number | null;
  reviews: number;
  image: string;
  url: string;
  /** 楽天ブックスの売れ筋順（検索語ごと）での順位 */
  rank?: number;
  keyword?: string;
};

type OffersFile = {
  topics: Topic[];
  audience: Record<string, string>;
  fallback: string;
  partners: Record<string, Partner>;
};

type ProductsFile = {
  fetchedAt: string;
  pixel?: string;
  books: Record<string, Book[]>;
  partnerPrices?: Record<string, number>;
};

type AffiliateEntry = { url?: string; pixel?: string };

export type OfferItem = {
  key: string;
  kind: "partner" | "book";
  name: string;
  label?: string;
  note?: string;
  author?: string;
  price?: number | null;
  priceText?: string;
  image?: string | null;
  url: string;
  shop: string;
  cta: string;
  rating?: number | null;
  reviews?: number;
  /** 楽天ブックス売れ筋の順位（10位以内のときだけ表示に使う） */
  rank?: number;
  keyword?: string;
};

export type Offer = {
  topic: string;
  eyebrow: string;
  headline: string;
  lead: string;
  items: OfferItem[];
  /** 価格・評価の取得日（ISO） */
  checkedAt: string;
  /** ASPの表示計測用ピクセル */
  pixels: string[];
};

const MAX_ITEMS = 3;

function readJson<T>(file: string): T | null {
  const full = path.join(process.cwd(), file);
  if (!fs.existsSync(full)) return null;
  try {
    return JSON.parse(fs.readFileSync(full, "utf8")) as T;
  } catch {
    return null;
  }
}

let loaded: { offers: OffersFile; products: ProductsFile | null; affiliates: Record<string, AffiliateEntry> } | null = null;

function load() {
  if (loaded) return loaded;
  const offers = readJson<OffersFile>("content/offers.json") ?? {
    topics: [],
    audience: {},
    fallback: "",
    partners: {},
  };
  const products = readJson<ProductsFile>("content/products.json");
  const affiliates = readJson<Record<string, AffiliateEntry>>("affiliate_links.json") ?? {};
  loaded = { offers, products, affiliates };
  return loaded;
}

/** A8 の提携リンクに飛び先（商品ページ）を付ける。提携先が許可している商品リンクの形式 */
function partnerUrl(base: string, page: string | null): string {
  return page ? `${base}&a8ejpredirect=${encodeURIComponent(page)}` : base;
}

function pickTopic(article: Article, offers: OffersFile): Topic | undefined {
  const byKey = new Map(offers.topics.map((topic) => [topic.key, topic]));

  // 本文の言及で提携商品が自動挿入されている記事は、その商品の話題を優先する
  const linked = new Set(article.affiliates.map((a) => a.name));
  const partnerTopic = offers.topics.find((topic) =>
    topic.partners.some((key) => linked.has(offers.partners[key]?.program)),
  );
  if (partnerTopic) return partnerTopic;

  const text = [article.title, article.seoTitle ?? "", ...article.tags, ...article.keywords].join(" ");
  const matched = offers.topics.find((topic) => new RegExp(topic.match, "i").test(text));
  if (matched) return matched;

  const audience = article.verdict?.audience;
  if (audience && offers.audience[audience]) return byKey.get(offers.audience[audience]);
  return byKey.get(offers.fallback);
}

export function offerForArticle(article: Article, maxItems = MAX_ITEMS): Offer | undefined {
  if (article.genreSlug !== "ai") return undefined;
  const { offers, products, affiliates } = load();
  const topic = pickTopic(article, offers);
  if (!topic) return undefined;

  const items: OfferItem[] = [];
  const pixels = new Set<string>();

  for (const key of topic.partners) {
    const partner = offers.partners[key];
    const program = partner ? affiliates[partner.program] : undefined;
    if (!partner || !program?.url) continue;
    items.push({
      key,
      kind: "partner",
      name: partner.name,
      label: partner.label,
      note: partner.note,
      price: products?.partnerPrices?.[key] ?? partner.price,
      priceText: partner.priceText,
      image: partner.image,
      url: partnerUrl(program.url, partner.page),
      shop: partner.shop,
      cta: "公式サイトで見る",
    });
    if (program.pixel) pixels.add(program.pixel);
  }

  // 話題の本 → 補充用の話題の本 → 既定の話題の本、の順に、必ず maxItems 個そろえる
  const seen = new Set<string>();
  const sources = [topic.key, ...(topic.fill ?? []), offers.fallback];
  let usedBooks = false;
  for (const source of sources) {
    for (const book of products?.books?.[source] ?? []) {
      if (items.length >= maxItems) break;
      if (seen.has(book.rbId)) continue;
      seen.add(book.rbId);
      usedBooks = true;
      items.push({
        key: book.rbId,
        kind: "book",
        name: book.title,
        author: book.author,
        price: book.price,
        image: book.image,
        url: book.url,
        shop: "楽天ブックス",
        cta: "楽天で見る",
        rating: book.rating,
        reviews: book.reviews,
        rank: book.rank,
        keyword: book.keyword,
      });
    }
  }
  if (usedBooks && products?.pixel) pixels.add(products.pixel);

  if (items.length === 0) return undefined;
  return {
    topic: topic.key,
    eyebrow: topic.eyebrow,
    headline: topic.headline,
    lead: topic.lead,
    items,
    checkedAt: products?.fetchedAt ?? new Date().toISOString(),
    pixels: [...pixels],
  };
}
