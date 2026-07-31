import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ArticleCard from "@/components/ArticleCard";
import {
  getAllGenres,
  getArticlesByGenre,
  getChannelsByGenre,
} from "@/lib/articles";

type Props = { params: Promise<{ genre: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllGenres().map((genre) => ({ genre: genre.slug }));
}

const GENRE_COPY: Record<string, string> = {
  ai: "OpenAI・Google DeepMind・Anthropic など世界のAI企業の公式発表動画を、AIが映像と音声ごと解析して日本語で速報解説します。新機能・ベンチマーク・料金・日本からの使い方までまとめています。",
  "real-estate":
    "不動産投資・住宅購入・マンション選びの専門YouTubeチャンネルの解説動画を、AIが映像と音声ごと解析して記事化。物件条件・利回り・金利・税制・リスクを数字で整理しています。",
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { genre } = await params;
  const label = getAllGenres().find((g) => g.slug === genre)?.label ?? genre;
  const count = getArticlesByGenre(genre).length;

  return {
    title: `${label}の最新ニュース・解説記事`,
    description: `${label}に関する解説記事を${count}本掲載。専門YouTubeチャンネルの動画をAIが解析し、要点・数字・注意点まで日本語でまとめています。`,
    alternates: { canonical: `/genres/${genre}` },
  };
}

export default async function GenrePage({ params }: Props) {
  const { genre } = await params;
  const articles = getArticlesByGenre(genre);
  if (articles.length === 0) notFound();

  const label = getAllGenres().find((g) => g.slug === genre)?.label ?? genre;
  const channels = getChannelsByGenre(genre);

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-12 sm:px-8">
      <p className="text-xs font-bold tracking-[0.2em] text-accent">GENRE</p>
      <h1 className="mt-3 font-serif text-[1.75rem] font-bold leading-[1.45] tracking-tight text-ink sm:text-[2.25rem]">
        {label}の最新ニュース・解説
      </h1>
      <p className="mt-4 max-w-3xl text-[15px] leading-[1.9] text-muted">
        {GENRE_COPY[genre] ?? `${label}に関する解説記事を${articles.length}本掲載しています。`}
      </p>

      {channels.length > 0 && (
        <div className="mt-6 flex flex-wrap gap-2">
          {channels.map((channel) => (
            <Link
              key={channel.slug}
              href={`/channels/${channel.slug}`}
              className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-xs text-ink-soft transition-colors hover:border-accent hover:text-accent"
            >
              {channel.label}
              <span className="ml-1.5 text-muted">{channel.count}</span>
            </Link>
          ))}
        </div>
      )}

      <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
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
