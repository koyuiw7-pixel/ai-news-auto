import { siteConfig } from "@/site.config";

/** 全ページで同じ媒体を指す。検索結果の favicon とは別の、発行元のロゴ情報。 */
export const publisherJsonLd = {
  "@type": "NewsMediaOrganization",
  "@id": `${siteConfig.url}/#publisher`,
  name: siteConfig.siteName,
  alternateName: [siteConfig.name, "AI速報サイソク"],
  url: siteConfig.url,
  // Organization のロゴは縦横とも 112px 以上。既存のブランド画像を使う。
  logo: { "@type": "ImageObject", url: `${siteConfig.url}/icons/icon-512.png`, width: 512, height: 512 },
  email: siteConfig.operator.email,
  contactPoint: { "@type": "ContactPoint", email: siteConfig.operator.email, contactType: "editorial" },
  publishingPrinciples: `${siteConfig.url}/editorial-policy`,
  correctionsPolicy: `${siteConfig.url}/editorial-policy`,
  sameAs: siteConfig.social.map((social) => social.url),
} as const;
