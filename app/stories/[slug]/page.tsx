import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ActionAd from "@/components/ActionAd";
import FlagshipStoryView from "@/components/flagship/FlagshipStoryView";
import { actionAdWithBenefits } from "@/lib/ad-benefits";
import { FLAGSHIP_AD_POS, FLAGSHIP_STORIES, flagshipHref, getFlagship } from "@/lib/flagship";
import { toolAd } from "@/lib/guide-ads";
import { itemShareImage } from "@/lib/page-share-items";
import { flagshipJsonLd } from "@/lib/flagship-jsonld";
import type { ToolKind } from "@/lib/tool-ad";
import { siteConfig } from "@/site.config";

/**
 * 特集（計算つきの記事）。中身は content/flagship/<slug>.json と計算の lib（lib/flagship.ts）。
 * すべてビルド時に作る（台帳 W29: サイトマップに載るページは初回アクセスで描かない）
 */
export const dynamicParams = false;

export function generateStaticParams() {
  return FLAGSHIP_STORIES.map((story) => ({ slug: story.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const story = getFlagship(slug);
  if (!story) return {};
  const url = flagshipHref(story.slug);
  const image = itemShareImage("story", story.slug, story.title);
  return {
    title: story.title,
    description: story.description,
    keywords: story.keywords,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      siteName: siteConfig.siteName,
      locale: siteConfig.locale,
      url,
      title: story.title,
      description: story.description,
      publishedTime: story.publishedAt,
      modifiedTime: story.updatedAt,
      images: [image],
    },
    twitter: { card: "summary_large_image", title: story.title, description: story.description, images: [image.url] },
  };
}

export default async function FlagshipPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const story = getFlagship(slug);
  if (!story) notFound();
  // 広告の枠は1ページに1つ（台帳 W10）。結果のすぐ下の「次に確かめること」の中。見た目 A/B は計算ツールと同じ（components/ToolAdSlot.tsx）
  const ad = actionAdWithBenefits(toolAd(story.ad.rule), "");
  return (
    <div className="mx-auto w-full max-w-[1120px] px-4 py-6 sm:px-8 sm:py-10">
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(flagshipJsonLd(story)) }} />
      <FlagshipStoryView story={story} adSlot={ad ? <ActionAd ad={ad} pos={FLAGSHIP_AD_POS} tool={story.ad.tool as ToolKind} className="mt-0" /> : undefined} />
    </div>
  );
}
