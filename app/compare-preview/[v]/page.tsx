import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import VariantA from "@/components/compare/VariantA";
import VariantB from "@/components/compare/VariantB";
import VariantC from "@/components/compare/VariantC";
import { buildGuideView } from "@/components/compare/view";
import { getBuyingGuide } from "@/lib/buying-guides";

/**
 * 比較ガイドのデザイン案（A/B/C）の確認用ページ。3案とも同じ content/buying-guides/ai-voice-recorder.json を描く。
 * 検索には出さない（noindex）。採用案が決まったら、このルートごと消してよい。
 */

const SLUG = "ai-voice-recorder";
const VARIANTS = {
  a: { name: "A 報道テロップ型", Component: VariantA },
  b: { name: "B 店頭POP・雑誌型", Component: VariantB },
  c: { name: "C 診断チャート型", Component: VariantC },
} as const;

type Key = keyof typeof VARIANTS;
type Props = { params: Promise<{ v: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return Object.keys(VARIANTS).map((v) => ({ v }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { v } = await params;
  const variant = VARIANTS[v as Key];
  return {
    title: `デザイン案 ${variant?.name ?? ""}（確認用）`,
    robots: { index: false, follow: false, nocache: true },
    alternates: { canonical: `/compare/${SLUG}` },
  };
}

export default async function ComparePreviewPage({ params }: Props) {
  const { v } = await params;
  const variant = VARIANTS[v as Key];
  const guide = getBuyingGuide(SLUG);
  if (!variant || !guide) notFound();
  const { Component } = variant;

  return (
    <>
      <nav aria-label="デザイン案の切り替え" className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1160px] flex-wrap items-center gap-2 px-4 py-2 text-[12px] sm:px-8">
          <span className="font-bold text-muted">確認用（検索には出ません）</span>
          {(Object.keys(VARIANTS) as Key[]).map((key) => (
            <Link
              key={key}
              href={`/compare-preview/${key}`}
              aria-current={key === v ? "page" : undefined}
              className={`rounded-md border px-2.5 py-1 font-bold ${
                key === v ? "border-ink bg-ink text-paper" : "border-line-strong text-ink hover:border-ink"
              }`}
            >
              {VARIANTS[key].name}
            </Link>
          ))}
        </div>
      </nav>
      <Component view={buildGuideView(guide)} />
    </>
  );
}
