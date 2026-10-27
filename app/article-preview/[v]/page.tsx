import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { VariantA, VariantB, VariantC } from "@/components/article-preview/Variants";
import { buildArticleView, type Variant } from "@/components/article-preview/view";
import { getArticle } from "@/lib/articles";
import { PREVIEW_DEFAULT_SLUG, PREVIEW_VARIANTS } from "../variants";

/**
 * 記事ページのデザイン案（A/B/C）の確認用ページ。?slug= で任意の記事を描ける（既定は GPT-6.1 Terra）。
 * 検索には出さない（noindex）。採用案が決まったら、このルートごと消してよい。
 */

const COMPONENTS = { a: VariantA, b: VariantB, c: VariantC } as const;

type Props = { params: Promise<{ v: string }>; searchParams: Promise<{ slug?: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return Object.keys(COMPONENTS).map((v) => ({ v }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { v } = await params;
  return {
    title: `記事デザイン案 ${PREVIEW_VARIANTS[v as Variant]?.name ?? ""}（確認用）`,
    robots: { index: false, follow: false, nocache: true },
  };
}

export default async function ArticlePreviewPage({ params, searchParams }: Props) {
  const { v } = await params;
  const { slug = PREVIEW_DEFAULT_SLUG } = await searchParams;
  const Component = COMPONENTS[v as Variant];
  const article = getArticle(slug);
  if (!Component || !article) notFound();
  const view = await buildArticleView(article, v as Variant);
  const query = slug === PREVIEW_DEFAULT_SLUG ? "" : `?slug=${encodeURIComponent(slug)}`;

  return (
    <>
      <nav aria-label="デザイン案の切り替え" className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-2 px-4 py-2 text-meta sm:px-8">
          <Link href="/article-preview" className="font-bold text-muted hover:text-ink">
            確認用（検索には出ません）
          </Link>
          {(Object.keys(COMPONENTS) as Variant[]).map((key) => (
            <Link
              key={key}
              href={`/article-preview/${key}${query}`}
              aria-current={key === v ? "page" : undefined}
              className={`rounded-md border px-2.5 py-1 font-bold ${
                key === v ? "border-ink bg-ink text-paper" : "border-line-strong text-ink hover:border-ink"
              }`}
            >
              {PREVIEW_VARIANTS[key].name}
            </Link>
          ))}
        </div>
      </nav>
      <Component view={view} />
    </>
  );
}
