import { flagshipHref, orderedSources, type FlagshipStory } from "@/lib/flagship";
import { itemShareImage } from "@/lib/page-share-items";
import { authorJsonLd, publisherJsonLd } from "@/lib/publisher";
import { faqPageJsonLd } from "@/lib/structured-data";
import { siteConfig } from "@/site.config";

/** 特集のページの構造化データ（NewsArticle・パンくず・FAQPage）。記事のページ（app/articles/[slug]/page.tsx）と同じ形。FAQ はページに見えている問いだけ */
export function flagshipJsonLd(story: FlagshipStory) {
  const url = `${siteConfig.url}${flagshipHref(story.slug)}`;
  return [
    {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      headline: story.title.slice(0, 110),
      description: story.description,
      image: [`${siteConfig.url}${itemShareImage("story", story.slug, story.title).url}`],
      datePublished: story.publishedAt,
      dateModified: story.updatedAt,
      inLanguage: "ja",
      keywords: story.keywords.join(", "),
      mainEntityOfPage: url,
      author: authorJsonLd,
      publisher: publisherJsonLd,
      publishingPrinciples: `${siteConfig.url}/editorial-policy`,
      correctionsPolicy: `${siteConfig.url}/corrections`,
      backstory: `生成AIを使って作成し、数字と事実は出典の公式ページと報道で確かめてから公開しています。計算はこども家庭庁の案内どおりの式です。制作方法と事実確認の手順: ${siteConfig.url}/editorial-policy`,
      isAccessibleForFree: true,
      articleSection: story.genre.label,
      speakable: { "@type": "SpeakableSpecification", cssSelector: [".fs-answer", ".fs-answer-sub"] },
      citation: orderedSources(story).map((s) => ({ "@type": "CreativeWork", name: s.title, url: s.url, publisher: { "@type": "Organization", name: s.org } })),
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { name: "ホーム", item: siteConfig.url },
        { name: story.genre.label, item: `${siteConfig.url}${story.genre.href}` },
        { name: story.title },
      ].map((entry, i) => ({ "@type": "ListItem", position: i + 1, ...entry })),
    },
    ...[faqPageJsonLd(story.faq)].filter((entry) => entry !== null),
  ];
}

