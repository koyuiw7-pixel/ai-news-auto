import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
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
  // 記事は全てビルド時に静的化される（pSEO 前提の高速配信）
  experimental: {
    optimizePackageImports: ["marked"],
    // 記事カードから記事ページへの画面遷移（React の ViewTransition）。
    // 非対応ブラウザでは何も起きず、通常の遷移になる。
    viewTransition: true,
  },
};

export default nextConfig;
