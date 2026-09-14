import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "i.ytimg.com" },
      { protocol: "https", hostname: "img.youtube.com" },
      { protocol: "https", hostname: "yt3.ggpht.com" },
    ],
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
