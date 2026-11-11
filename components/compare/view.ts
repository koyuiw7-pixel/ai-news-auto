import type { ArticleSummary } from "@/lib/articles";
import { checkedDate } from "@/components/rail/parts";
import {
  guideRelatedArticles,
  resolveProducts,
  type BuyingGuide,
  type ResolvedProduct,
} from "@/lib/buying-guides";
import { siteConfig } from "@/site.config";
import { authorJsonLd, publisherJsonLd } from "@/lib/publisher";

/**
 * 比較ガイド（新形式）の表示用データ。A/B/C どのデザインも同じこのデータだけを描く。
 */
export type GuideView = {
  guide: BuyingGuide;
  products: ResolvedProduct[];
  byKey: Map<string, ResolvedProduct>;
  personas: { who: string; why: string; products: ResolvedProduct[] }[];
  rows: { key: string; label: string }[];
  /** 本題とは別の囲み（guide.sideSections）。ここの商品は products に入れない */
  sideSections: { id: string; label: string; title: string; body: string; products: ResolvedProduct[] }[];
  related: ArticleSummary[];
  pixels: string[];
  /** 例: 10月27日時点・公式サイトより */
  checkedLabel: string;
  hasSponsored: boolean;
  jsonLd: object[];
};

export function buildGuideView(guide: BuyingGuide): GuideView {
  const all = resolveProducts(guide);
  const sideKeys = new Set((guide.sideSections ?? []).flatMap((section) => section.products));
  const products = all.filter((p) => !sideKeys.has(p.key));
  const byKey = new Map(products.map((p) => [p.key, p]));
  const allByKey = new Map(all.map((p) => [p.key, p]));
  const sideSections = (guide.sideSections ?? []).flatMap((section) => {
    const picks = section.products.flatMap((key) => allByKey.get(key) ?? []);
    return picks.length > 0 ? [{ ...section, products: picks }] : [];
  });
  const personas = (guide.personas ?? []).flatMap((persona) => {
    const picks = persona.picks.flatMap((key) => byKey.get(key) ?? []);
    return picks.length > 0 ? [{ who: persona.who, why: persona.why, products: picks }] : [];
  });
  const url = `${siteConfig.url}/compare/${guide.slug}`;
  return {
    guide,
    products,
    byKey,
    personas,
    rows: guide.rows ?? [],
    sideSections,
    related: guideRelatedArticles(guide),
    pixels: [...new Set(all.flatMap((p) => (p.pixel ? [p.pixel] : [])))],
    checkedLabel: guide.checkedLabel ?? `${checkedDate(guide.priceCheckedAt)}時点・公式サイトより`,
    hasSponsored: all.some((p) => p.sponsored),
    jsonLd: [
      {
        // 2026-11-11（台帳 W42・検索に出す準備）: 型は schema.org の Article（以前は型の名前の置き換えで "ArticleSummary" という無い型になっていた）。
        // 発行元・著者は記事ページと同じ @id（lib/publisher.ts）
        "@context": "https://schema.org",
        "@type": "Article",
        headline: guide.title,
        description: guide.description,
        inLanguage: "ja",
        datePublished: guide.publishedAt,
        dateModified: guide.updatedAt,
        mainEntityOfPage: url,
        author: authorJsonLd,
        publisher: publisherJsonLd,
        publishingPrinciples: `${siteConfig.url}/editorial-policy`,
        keywords: guide.targetQueries.join(", "),
      },
      {
        // 比べている商品・サービスの一覧（並びはページの表と同じ）。提携のリンク（a8.net など）は載せず、名前だけ
        "@context": "https://schema.org",
        "@type": "ItemList",
        name: guide.title,
        numberOfItems: products.length,
        itemListElement: products.map((p, i) => ({ "@type": "ListItem", position: i + 1, name: p.item.name })),
      },
      {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "ホーム", item: siteConfig.url },
          { "@type": "ListItem", position: 2, name: "比較ガイド", item: `${siteConfig.url}/compare` },
          { "@type": "ListItem", position: 3, name: guide.title, item: url },
        ],
      },
      {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: guide.faq.map((item) => ({
          "@type": "Question",
          name: item.q,
          acceptedAnswer: { "@type": "Answer", text: item.a },
        })),
      },
    ],
  };
}
