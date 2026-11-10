import { siteConfig } from "@/site.config";

/** 全ページで同じ媒体を指す。検索結果の favicon とは別の、発行元のロゴ情報。 */
export const publisherJsonLd = {
  "@type": "NewsMediaOrganization",
  "@id": `${siteConfig.url}/#publisher`,
  name: siteConfig.siteName,
  // 別名は略称「サイソク」を先頭に。旧名「サイソクAIニュース」は残す（改名後も Google に同じ媒体だと伝えるため。消さない）。
  // 使っていない別の呼び名は入れない（2026-11-10 LLMO-A13）
  alternateName: [siteConfig.nickname, siteConfig.formerName],
  url: siteConfig.url,
  // Organization のロゴは縦横とも 112px 以上。既存のブランド画像を使う。
  logo: { "@type": "ImageObject", url: `${siteConfig.url}/icons/icon-512.png`, width: 512, height: 512 },
  email: siteConfig.operator.email,
  contactPoint: { "@type": "ContactPoint", email: siteConfig.operator.email, contactType: "editorial" },
  publishingPrinciples: `${siteConfig.url}/editorial-policy`,
  correctionsPolicy: `${siteConfig.url}/corrections`,
  sameAs: siteConfig.social.map((social) => social.url),
  // 運営責任者の名前は全ページ共通のデータには載せない（オーナーの決まり W6。記事は下の editorInCharge だけ）
  address: { "@type": "PostalAddress", addressRegion: siteConfig.operator.location, addressCountry: "JP" },
} as const;

/** 記事・ガイドの著者。全ページで同じ編集部を指し、発行元とつなぐ */
export const authorJsonLd = {
  "@type": "Organization",
  "@id": `${siteConfig.url}/#editorial`,
  name: siteConfig.author,
  url: `${siteConfig.url}/about`,
  parentOrganization: { "@id": `${siteConfig.url}/#publisher` },
} as const;

/**
 * 編集責任者の名前を出す記事（2026-11-10 オーナー承認。docs/owner_rules.md W6）。
 * お金と暮らしの記事（年金・税・手当・値上げなど）だけ。出すのは名前だけで、経歴は出さない。
 * 見張り scripts/owner_rules_audit.py の EDITOR_NAME_GENRES と同じ一覧にする。
 */
export const EDITOR_NAME_GENRES: ReadonlySet<string> = new Set(["public", "lifestyle", "investment", "real-estate"]);

/** 記事に出す編集責任者（対象外のジャンルは null）。名前は /about に載せているものと同じ */
export function editorInCharge(genreSlug: string | undefined) {
  if (!genreSlug || !EDITOR_NAME_GENRES.has(genreSlug)) return null;
  const name = siteConfig.operator.representative;
  return {
    name,
    jsonLd: { "@type": "Person", name, url: `${siteConfig.url}/about` },
  } as const;
}
