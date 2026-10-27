import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Vercel の画像最適化は無料プランの月間上限があり、超えると画像が出なくなる（2026-10 に発生）。
    // YouTube のサムネイルも独自カバーも配信時点で十分軽いので、最適化を使わずそのまま配信する
    unoptimized: true,
    remotePatterns: [
      { protocol: "https", hostname: "i.ytimg.com" },
      { protocol: "https", hostname: "img.youtube.com" },
      { protocol: "https", hostname: "yt3.ggpht.com" },
    ],
  },
  // 独自ドメインへの引っ越し。旧URLとwwwは恒久的（301相当）に新ドメインへ転送し、
  // 検索エンジンの評価と外部リンクを引き継ぐ。プレビュー用の *.vercel.app は対象外
  async redirects() {
    return ["ai-news-auto.vercel.app", "www.ai-tech-express.jp"].map((host) => ({
      source: "/:path*",
      has: [{ type: "host" as const, value: host }],
      destination: "https://ai-tech-express.jp/:path*",
      permanent: true,
    }));
  },
  // 新しい記事・カバーだけビルド時に静的化し、残りは初回アクセス時に生成する（ISR）。
  // そのとき JSON・フォント・設定ファイルをサーバー関数から読むので、必ず同梱させる
  // （同梱されないと本番で古い記事が 404 になる）。
  // 記事の本文（content/articles、記事数に比例して増える）は1本ずつ読むページにだけ同梱し、
  // 一覧・タグ・サイトマップなどには軽い索引（content/index.json、npm run build の最初に作る）だけを渡す。
  // 全ページに本文を同梱すると、デプロイのたびに容量（Deployment Storage）が膨らむため。
  // キーは picomatch のパターンなので、[slug] の角かっこはエスケープする
  outputFileTracingIncludes: {
    "/**": [
      "./content/index.json",
      "./content/guides/**/*.json",
      "./content/buying-guides/**/*.json",
      "./content/offers.json",
      "./content/products.json",
      "./content/state.json",
      "./affiliate_links.json",
      "./monetization.json",
    ],
    "/articles/\\[slug\\]": ["./content/articles/**/*.json"],
    "/cover/**": ["./content/articles/**/*.json", "./assets/fonts/**/*"],
    "/api/v1/articles": ["./content/articles/**/*.json"],
  },
  experimental: {
    optimizePackageImports: ["marked"],
    // 記事カードから記事ページへの画面遷移（React の ViewTransition）。
    // 非対応ブラウザでは何も起きず、通常の遷移になる。
    viewTransition: true,
  },
};

export default nextConfig;
