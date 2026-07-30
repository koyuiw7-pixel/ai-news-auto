/**
 * サイト全体の設定。ここだけ書き換えればブランディングが一括で変わる。
 * NEXT_PUBLIC_SITE_URL は Vercel の環境変数で本番ドメインに差し替える。
 */
export const siteConfig = {
  name: "AI速報ラボ",
  shortName: "AI速報ラボ",
  description:
    "OpenAI・Google DeepMind・Anthropic など世界のAI企業の公式発表動画を、AIが映像と音声ごと解析して日本語で速報解説。新機能・料金・日本からの使い方まで最速でまとめます。",
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
