import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ArticleCard from "@/components/ArticleCard";
import {
  getAllTags,
  getArticlesByTag,
  getTagLabel,
  tagSlug,
} from "@/lib/articles";

type Props = { params: Promise<{ tag: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  // ここに渡すのは「デコード済み」の値。エンコードすると二重エンコードで404になる。
  return getAllTags().map((tag) => ({ tag: tag.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { tag } = await params;
  const label = getTagLabel(tag);
  const articles = getArticlesByTag(tag);
  const genres = [...new Set(articles.map((a) => a.genre))].join("・");

  return {
    title: `${label} の最新ニュース・解説記事`,
    description: `${label} に関する${genres}の解説記事を ${articles.length} 本掲載。公式発表や専門家の動画をAIが解析し、要点・数字・注意点まで日本語でまとめています。`,
    alternates: { canonical: `/tags/${encodeURIComponent(tagSlug(label))}` },
  };
}

export default async function TagPage({ params }: Props) {
  const { tag } = await params;
  const articles = getArticlesByTag(tag);
  if (articles.length === 0) notFound();

  const label = getTagLabel(tag);
  const genres = [...new Set(articles.map((a) => a.genre))].join("・");

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-12 sm:px-8">
      <p className="eyebrow">TOPIC</p>
      <h1 className="display mt-2 text-[1.75rem] sm:text-[2.25rem]">
        {label} の最新ニュース・解説
      </h1>
      <p className="mt-4 max-w-3xl text-[15px] leading-[1.9] text-muted">
        {label} に関連する{genres}
        の動画をAIが映像・音声ごと解析し、要点・数字・注意点まで日本語でまとめた記事が
        {articles.length} 本あります。
      </p>

      <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
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
