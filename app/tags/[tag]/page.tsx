import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ArticleCard from "@/components/ArticleCard";
import { getAllTags, getArticlesByTag } from "@/lib/articles";

type Props = { params: Promise<{ tag: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllTags().map((tag) => ({ tag: tag.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { tag } = await params;
  const label = getAllTags().find((t) => t.slug === tag)?.label ?? tag;
  const count = getArticlesByTag(tag).length;

  return {
    title: `${label} の最新ニュース・解説記事`,
    description: `${label} に関するAI公式発表の解説記事を ${count} 本掲載。新機能・料金・日本からの使い方までAIが動画を解析してまとめています。`,
    alternates: { canonical: `/tags/${tag}` },
  };
}

export default async function TagPage({ params }: Props) {
  const { tag } = await params;
  const articles = getArticlesByTag(tag);
  if (articles.length === 0) notFound();

  const label = getAllTags().find((t) => t.slug === tag)?.label ?? tag;

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <p className="text-xs font-bold tracking-widest text-accent">TOPIC</p>
      <h1 className="mt-2 text-2xl font-black tracking-tight text-ink-950 sm:text-3xl">
        #{label} の最新ニュース・解説
      </h1>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-ink-500">
        {label}{" "}
        に関連するAI企業の公式発表動画をAIが解析し、要点・タイムテーブル・料金・日本からの使い方まで日本語でまとめた記事が
        {articles.length} 本あります。
      </p>

      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {articles.map((article, index) => (
          <ArticleCard
            key={article.slug}
            article={article}
            priority={index < 3}
          />
        ))}
      </div>
    </div>
  );
}
