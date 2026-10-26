import type { Metadata } from "next";
import Script from "next/script";
import { Analytics } from "@vercel/analytics/next";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { siteConfig } from "@/site.config";
import { dela, martian, zen } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(siteConfig.url),
  title: {
    // 強み（最速・日本語・使えるかの判定）が伝わる題名。区切りの縦棒は使わない
    default: `${siteConfig.siteName} 海外AIの新機能が今使えるかまで最速でわかる`,
    template: `%s - ${siteConfig.name}`,
  },
  description: siteConfig.description,
  applicationName: siteConfig.siteName,
  // Google Search Console の所有権確認。環境変数に確認コードを入れるだけで有効になる
  verification: process.env.GOOGLE_SITE_VERIFICATION
    ? { google: process.env.GOOGLE_SITE_VERIFICATION }
    : undefined,
  authors: [{ name: siteConfig.author }],
  alternates: {
    canonical: "/",
    types: { "application/rss+xml": "/feed.xml" },
  },
  openGraph: {
    type: "website",
    siteName: siteConfig.siteName,
    locale: siteConfig.locale,
    url: siteConfig.url,
    title: `${siteConfig.siteName} 海外AIの新機能が今使えるかまで最速でわかる`,
    description: siteConfig.description,
  },
  twitter: {
    card: "summary_large_image",
    title: siteConfig.name,
    description: siteConfig.description,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    // Google の検索結果でアイコンの横に出るサイト名
    name: siteConfig.siteName,
    alternateName: ["サイソク", "AI速報サイソク"],
    url: siteConfig.url,
    description: siteConfig.description,
    inLanguage: "ja",
    publisher: {
      "@type": "Organization",
      name: siteConfig.siteName,
      url: siteConfig.url,
      logo: { "@type": "ImageObject", url: `${siteConfig.url}/logo.png`, width: 600, height: 60 },
      email: siteConfig.operator.email,
      contactPoint: { "@type": "ContactPoint", email: siteConfig.operator.email, contactType: "editorial" },
      publishingPrinciples: `${siteConfig.url}/editorial-policy`,
      correctionsPolicy: `${siteConfig.url}/editorial-policy`,
    },
  };

  const adsenseClient = process.env.NEXT_PUBLIC_ADSENSE_CLIENT;

  return (
    <html
      lang={siteConfig.lang}
      className={`${zen.variable} ${dela.variable} ${martian.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* AdSense のサイト所有権確認用（ads.txt と併用が推奨） */}
        {adsenseClient && (
          <meta name="google-adsense-account" content={adsenseClient} />
        )}
        {/* 描画前にテーマを確定させ、リロード時の白フラッシュを防ぐ */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("theme");if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t)}catch(e){}`,
          }}
        />
      </head>
      <body className="flex min-h-dvh flex-col bg-paper text-ink">
        <script
          type="application/ld+json"
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />

        {/* AdSense 本体。NEXT_PUBLIC_ADSENSE_CLIENT を設定すると自動で有効化される */}
        {adsenseClient && (
          <Script
            id="adsbygoogle-init"
            async
            strategy="afterInteractive"
            crossOrigin="anonymous"
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${adsenseClient}`}
          />
        )}
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
        {/* Vercelダッシュボードで Web Analytics を有効にした時点で計測が始まる。
            無効のうちは何も送信されないので、先に仕込んでおいて問題ない。 */}
        <Analytics />
      </body>
    </html>
  );
}
