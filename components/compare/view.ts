import type { Article } from "@/lib/articles";
import { checkedDate } from "@/components/rail/parts";
import {
  guideRelatedArticles,
  resolveProducts,
  type BuyingGuide,
  type ResolvedProduct,
} from "@/lib/buying-guides";
import { siteConfig } from "@/site.config";

/**
 * 比較ガイド（新形式）の表示用データ。A/B/C どのデザインも同じこのデータだけを描く。
 */
export type GuideView = {
  guide: BuyingGuide;
  products: ResolvedProduct[];
  byKey: Map<string, ResolvedProduct>;
  personas: { who: string; why: string; products: ResolvedProduct[] }[];
  rows: { key: string; label: string }[];
  related: Article[];
  pixels: string[];
  /** 例: 10月27日時点・公式サイトより */
  checkedLabel: string;
  hasSponsored: boolean;
  jsonLd: object[];
};

export function buildGuideView(guide: BuyingGuide): GuideView {
  const products = resolveProducts(guide);
  const byKey = new Map(products.map((p) => [p.key, p]));
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
    related: guideRelatedArticles(guide),
    pixels: [...new Set(products.flatMap((p) => (p.pixel ? [p.pixel] : [])))],
    checkedLabel: guide.checkedLabel ?? `${checkedDate(guide.priceCheckedAt)}時点・公式サイトより`,
    hasSponsored: products.some((p) => p.sponsored),
    jsonLd: [
      {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: guide.title,
        description: guide.description,
        inLanguage: "ja",
        datePublished: guide.publishedAt,
        dateModified: guide.updatedAt,
        mainEntityOfPage: url,
        author: { "@type": "Organization", name: siteConfig.author, url: `${siteConfig.url}/about` },
        publisher: {
          "@type": "Organization",
          name: siteConfig.name,
          url: siteConfig.url,
          logo: { "@type": "ImageObject", url: `${siteConfig.url}/logo.png`, width: 600, height: 60 },
        },
        publishingPrinciples: `${siteConfig.url}/editorial-policy`,
        keywords: guide.targetQueries.join(", "),
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
