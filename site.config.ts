/**
 * サイト全体の設定。ここだけ書き換えればブランディングが一括で変わる。
 * NEXT_PUBLIC_SITE_URL は Vercel の環境変数で本番ドメインに差し替える。
 */
export const siteConfig = {
  name: "サイソク",
  shortName: "サイソク",
  // 「催促」と読み違えられないよう、タグラインとタイトルで必ず「最速」を併記する
  tagline: "最速で、要点だけ。",
  description:
    "AI・テクノロジー、不動産、投資の専門チャンネルをAIが常時監視。公式発表や専門家の解説動画を映像と音声ごと解析し、要点・数字・料金・リスクまで日本語で最速にまとめます。",
  url:
    process.env.NEXT_PUBLIC_SITE_URL ??
    (process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : "http://localhost:3000"),
  locale: "ja_JP",
  lang: "ja",
  author: "サイソク編集部",

  /**
   * 運営者情報。AdSense・ASPの審査では実在の運営者と連絡手段の明示が必須です。
   * ここを実際の情報に差し替えてください（未設定のうちは審査に通りません）。
   */
  operator: {
    name: "サイソク編集部",
    representative: "koyuiw7",
    location: "日本",
    email: "koyuiw7@gmail.com",
    established: "2026年7月",
  },

  // トップに出す記事件数
  topArticles: 24,
} as const;

export type SiteConfig = typeof siteConfig;
