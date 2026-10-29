import type { MetadataRoute } from "next";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

/**
 * Web アプリの情報（/manifest.webmanifest）。iPhone は「ホーム画面に追加」したサイトだけが
 * プッシュ通知を受け取れるので、そのために置く（display: standalone が必要）。アイコンは public/icons/（赤地に白「速」のブランドアイコン）
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: siteConfig.siteName,
    short_name: siteConfig.shortName,
    description: siteConfig.description,
    lang: "ja",
    start_url: "/?utm_source=homescreen",
    scope: "/",
    display: "standalone",
    background_color: "#f3f5f8",
    theme_color: "#0b1f45",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // Android の丸・角丸マスク用。中身を中央 76% に収め、背景のグラデーションは端まで敷いている
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
