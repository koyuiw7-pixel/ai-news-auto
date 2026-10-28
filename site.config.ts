/**
 * サイト全体の設定。ここだけ書き換えればブランディングが一括で変わる。
 * NEXT_PUBLIC_SITE_URL は Vercel の環境変数で本番ドメインに差し替える。
 */
export const siteConfig = {
  name: "サイソク",
  shortName: "サイソク",
  // 検索結果でアイコンの横に出るサイト名。何に特化したサイトかが伝わる名前にする
  siteName: "サイソクAIニュース",
  // 「催促」と読み違えられないよう、タグラインとタイトルで必ず「最速」を併記する
  tagline: "最速で、要点だけ。",
  description:
    "OpenAI・Google・Anthropicなど海外AIの新発表を、最速で日本語に。新機能が今すぐ使えるか、日本から使えるか、無料で試せるかまで判定して、誰でもわかる言葉で解説します。",
  url:
    process.env.NEXT_PUBLIC_SITE_URL ??
    (process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : `http://localhost:${process.env.PORT ?? 3000}`),
  locale: "ja_JP",
  lang: "ja",
  author: "サイソク編集部",

  /**
   * 運営者情報。AdSense・ASPの審査では実在の運営者と連絡手段の明示が必須です。
   * ここを実際の情報に差し替えてください（未設定のうちは審査に通りません）。
   */
  operator: {
    name: "サイソク編集部",
    representative: "小室勇世",
    location: "東京都",
    email: "koyuiw7@gmail.com",
    established: "2026年7月",
  },

  // 公式SNS（構造化データの sameAs と足元のリンクに使う。Google にサイトと同じ運営だと伝える）
  social: [
    { label: "X", url: "https://x.com/saisoku_ai" },
    { label: "Threads", url: "https://www.threads.com/@saisoku637" },
  ],

  // トップに出す記事件数
  topArticles: 24,
} as const;

export type SiteConfig = typeof siteConfig;
