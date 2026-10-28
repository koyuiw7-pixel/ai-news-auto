import type { MetadataRoute } from "next";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

/**
 * Web アプリの情報（/manifest.webmanifest）。iPhone は「ホーム画面に追加」したサイトだけが
 * プッシュ通知を受け取れるので、そのために置く（display: standalone が必要）。アイコンは app/icon.tsx・apple-icon.tsx
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
      { src: "/icon", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png", purpose: "any" },
    ],
  };
}
