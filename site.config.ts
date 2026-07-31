/**
 * サイト全体の設定。ここだけ書き換えればブランディングが一括で変わる。
 * NEXT_PUBLIC_SITE_URL は Vercel の環境変数で本番ドメインに差し替える。
 */
export const siteConfig = {
  name: "AI速報ラボ",
  shortName: "AI速報ラボ",
  description:
    "AI・テクノロジーと不動産の専門YouTubeチャンネルをAIが常時監視。映像と音声を解析して、公式発表の要点・数字・料金・リスクまで日本語で最速まとめます。",
  url:
    process.env.NEXT_PUBLIC_SITE_URL ??
    (process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : "http://localhost:3000"),
  locale: "ja_JP",
  lang: "ja",
  author: "AI速報ラボ編集部",
  // トップに出す記事件数
  topArticles: 24,
} as const;

export type SiteConfig = typeof siteConfig;
