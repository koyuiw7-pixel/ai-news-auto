import fs from "node:fs";
import path from "node:path";
import { getArticle, type Article } from "@/lib/articles";
import { partnerItem, type OfferItem } from "@/lib/offers";

/**
 * 比較ガイド（content/buying-guides/*.json）。scripts/buying_guides.py が作る。
 * 商品名・画像・リンクは offers.json と affiliate_links.json から毎回引く（提携が切れた商品は自動で消える）。
 */

export type PriceSource =
  | { type: "official"; url: string; checkedAt: string }
  | { type: "data"; file: string; checkedAt: string }
  | null;

export type BuyingGuideProduct = {
  partner: string;
  price: string;
  priceSource: PriceSource;
  priceNote?: string;
  specs: string[];
  bestFor: string;
  summary: string;
  strengths: string[];
  limits: string[];
  officialUrl?: string;
};

export type BuyingGuide = {
  slug: string;
  title: string;
  /** 「〇〇を選ぶなら」に使う短い名前 */
  shortName?: string;
  description: string;
  targetQueries: string[];
  /** offers.json の話題キー。記事ページから案内するのに使う */
  topics: string[];
  intro: string;
  criteria: string[];
  columns: string[];
  products: BuyingGuideProduct[];
  quickPick: { partner: string; reason: string }[];
  faq: { q: string; a: string }[];
  relatedArticleSlugs: string[];
  publishedAt: string;
  updatedAt: string;
  priceCheckedAt: string;
};

/** 表示用：ガイドの商品に提携リンクを合わせたもの */
export type ResolvedProduct = BuyingGuideProduct & { item: OfferItem; pixel?: string };

const DIR = path.join(/*turbopackIgnore: true*/ process.cwd(), "content", "buying-guides");

let cache: BuyingGuide[] | null = null;

export function getAllBuyingGuides(): BuyingGuide[] {
  // 開発中は生成スクリプトが書き足したガイドをすぐ見られるよう、毎回読み直す
  if (cache && process.env.NODE_ENV === "production") return cache;
  if (!fs.existsSync(DIR)) return (cache = []);
  cache = fs
    .readdirSync(DIR)
    .filter((file) => file.endsWith(".json"))
    .flatMap((file) => {
      try {
        return [JSON.parse(fs.readFileSync(path.join(DIR, file), "utf8")) as BuyingGuide];
      } catch {
        return [];
      }
    })
    .filter((guide) => resolveProducts(guide).length >= 2)
    .sort((a, b) => a.title.localeCompare(b.title, "ja"));
  return cache;
}

export function getBuyingGuide(slug: string): BuyingGuide | undefined {
  return getAllBuyingGuides().find((guide) => guide.slug === slug);
}

/** 提携中の商品だけ（リンク・画像つき） */
export function resolveProducts(guide: BuyingGuide): ResolvedProduct[] {
  return guide.products.flatMap((product) => {
    const found = partnerItem(product.partner);
    if (!found) return [];
    const item = { ...found.item, price: null, priceText: product.price || "公式サイトで確認" };
    return [{ ...product, item, pixel: found.pixel }];
  });
}

export function guideRelatedArticles(guide: BuyingGuide, limit = 6): Article[] {
  return guide.relatedArticleSlugs.flatMap((slug) => getArticle(slug) ?? []).slice(0, limit);
}

/** 記事の商品枠の話題（offers.json のキー）に対応する比較ガイド */
export function buyingGuideForTopic(topic: string | undefined): BuyingGuide | undefined {
  if (!topic) return undefined;
  return getAllBuyingGuides().find((guide) => guide.topics.includes(topic));
}

/** ガイドの見出しから「〇〇を選ぶなら」に使う短い名前（【】や：以降を落とす） */
export function guideShortName(guide: BuyingGuide): string {
  if (guide.shortName) return guide.shortName;
  return guide.title.split(/[【：:]/)[0].replace(/(おすすめ)?比較$/, "").replace(/おすすめ$/, "").trim();
}
