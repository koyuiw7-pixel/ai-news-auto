import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import AdSlot from "@/components/AdSlot";
import AffiliateBox from "@/components/AffiliateBox";
import ArticleCard from "@/components/ArticleCard";
import Sidebar from "@/components/Sidebar";
import {
  encodeTag,
  formatDate,
  getAllArticles,
  getArticle,
  getRelatedArticles,
} from "@/lib/articles";
import {
  extractHeadings,
  renderMarkdown,
  splitBeforeHeading,
} from "@/lib/markdown";
import { siteConfig } from "@/site.config";

type Props = { params: Promise<{ slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllArticles().map((article) => ({ slug: article.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article) return {};

  const url = `/articles/${article.slug}`;
  return {
    title: article.title,
    description: article.description,
    keywords: article.keywords,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      url,
      title: article.title,
      description: article.description,
      publishedTime: article.publishedAt,
      modifiedTime: article.generatedAt,
      tags: article.tags,
      images: [{ url: article.thumbnail, width: 1280, height: 720 }],
    },
    twitter: {
      card: "summary_large_image",
      title: article.title,
      description: article.description,
      images: [article.thumbnail],
    },
  };
}

export default async function ArticlePage({ params }: Props) {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article) notFound();

  const affiliates = article.affiliates ?? [];
  const html = await renderMarkdown(
    article.body,
    affiliates.map((a) => a.url),
  );
  // 第3章（3つ目の見出し）の直前で本文を割り、広告を挟む
  const [bodyTop, bodyBottom] = splitBeforeHeading(html, 3);
  const headings = extractHeadings(article.body);
  const related = getRelatedArticles(article);

  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      headline: article.title,
      description: article.description,
      image: [article.thumbnail],
      datePublished: article.publishedAt,
      dateModified: article.generatedAt,
      inLanguage: "ja",
      keywords: article.keywords.join(", "),
      mainEntityOfPage: `${siteConfig.url}/articles/${article.slug}`,
      author: { "@type": "Organization", name: siteConfig.author },
      publisher: { "@type": "Organization", name: siteConfig.name },
    },
    {
      "@context": "https://schema.org",
      "@type": "VideoObject",
      name: article.videoTitle,
      description: article.description,
      thumbnailUrl: [article.thumbnail],
      uploadDate: article.publishedAt,
      contentUrl: article.videoUrl,
      embedUrl: `https://www.youtube.com/embed/${article.videoId}`,
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "ホーム", item: siteConfig.url },
        {
          "@type": "ListItem",
          position: 2,
          name: article.channel,
          item: `${siteConfig.url}/channels/${article.channelSlug}`,
        },
        { "@type": "ListItem", position: 3, name: article.title },
      ],
    },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <script
        type="application/ld+json"
        suppressHydrationWarning
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <nav className="flex flex-wrap items-center gap-1.5 text-xs text-ink-500">
            <Link href="/" className="hover:text-accent">
              ホーム
            </Link>
            <span className="text-ink-300">/</span>
            <Link
              href={`/channels/${article.channelSlug}`}
              className="hover:text-accent"
            >
              {article.channel}
            </Link>
          </nav>

          <h1 className="mt-4 font-serif text-[1.75rem] font-bold leading-[1.4] tracking-tight text-ink-950 sm:text-[2.125rem]">
            {article.title}
          </h1>

          {article.lede && (
            <p className="mt-5 border-l-[3px] border-accent pl-4 text-[15px] leading-[1.9] text-ink-700 sm:text-base">
              {article.lede}
            </p>
          )}

          <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-ink-500">
            <span className="rounded-full bg-accent-soft px-2.5 py-1 font-medium text-accent">
              {article.channel}
            </span>
            <time dateTime={article.publishedAt}>
              公開 {formatDate(article.publishedAt)}
            </time>
            <span className="text-ink-300">|</span>
            <span>AI解析: {article.model}</span>
            {affiliates.length > 0 && (
              <>
                <span className="text-ink-300">|</span>
                <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[10px]">
                  PR含む
                </span>
              </>
            )}
          </div>

          {/* ① 記事トップ（タイトル下）の広告枠 */}
          <AdSlot position="article-top" className="mt-6" />

          {/* 動画（クリックで初めて YouTube を読み込む軽量ファサード） */}
          <div className="mt-7 overflow-hidden rounded-2xl border border-ink-100 bg-black">
            <a
              href={article.videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="group relative block aspect-video"
            >
              <Image
                src={article.thumbnail}
                alt={article.videoTitle}
                fill
                priority
                sizes="(max-width: 1024px) 100vw, 700px"
                className="object-cover opacity-90 transition-opacity group-hover:opacity-100"
              />
              <span className="absolute inset-0 grid place-items-center">
                <span className="grid h-14 w-20 place-items-center rounded-xl bg-red-600/95 text-white shadow-lg transition-transform group-hover:scale-110">
                  <svg
                    width="22"
                    height="22"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    aria-hidden
                  >
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </span>
              </span>
            </a>
            <p className="truncate bg-ink-950 px-4 py-2.5 text-xs text-ink-300">
              元動画: {article.videoTitle}
            </p>
          </div>

          {/* 3秒でわかる要点3選 */}
          {article.highlights.length > 0 && (
            <section className="mt-9 rounded-2xl border border-accent/20 bg-accent-soft/50 p-6">
              <h2 className="text-sm font-black tracking-wide text-accent">
                ⚡ 3秒でわかる要点
              </h2>
              <ul className="mt-4 space-y-3">
                {article.highlights.map((highlight, index) => (
                  <li key={index} className="flex gap-3">
                    <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-accent text-[11px] font-bold text-white">
                      {index + 1}
                    </span>
                    <span className="text-sm font-medium leading-relaxed text-ink-900">
                      {highlight}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 目次 */}
          {headings.length > 1 && (
            <nav className="mt-8 rounded-2xl border border-ink-100 bg-white p-6">
              <p className="text-sm font-bold text-ink-950">目次</p>
              <ol className="mt-3 space-y-2">
                {headings.map((heading) => (
                  <li key={heading.id}>
                    <a
                      href={`#${heading.id}`}
                      className="text-sm text-ink-500 hover:text-accent"
                    >
                      {heading.text}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
          )}

          {/* 本文（前半） */}
          <article
            className="prose prose-slate mt-10 max-w-none prose-headings:font-bold prose-headings:tracking-tight prose-a:text-accent prose-strong:text-ink-950 prose-th:bg-ink-50"
            dangerouslySetInnerHTML={{ __html: bodyTop }}
          />

          {/* ② 記事中盤（第3章の前）の広告枠 */}
          {bodyBottom && <AdSlot position="article-middle" className="my-10" />}

          {/* 本文（後半） */}
          {bodyBottom && (
            <article
              className="prose prose-slate max-w-none prose-headings:font-bold prose-headings:tracking-tight prose-a:text-accent prose-strong:text-ink-950 prose-th:bg-ink-50"
              dangerouslySetInnerHTML={{ __html: bodyBottom }}
            />
          )}

          {/* タイムテーブル */}
          {article.timetable.length > 0 && (
            <section className="mt-12">
              <h2 className="text-lg font-bold text-ink-950">
                🕒 発表タイムテーブル
              </h2>
              <ul className="mt-4 divide-y divide-ink-100 overflow-hidden rounded-2xl border border-ink-100 bg-white">
                {article.timetable.map((item, index) => (
                  <li key={index} className="flex gap-4 px-5 py-3.5">
                    <a
                      href={`${article.videoUrl}&t=${toSeconds(item.time)}s`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-16 shrink-0 font-mono text-sm font-semibold text-accent hover:underline"
                    >
                      {item.time}
                    </a>
                    <span className="text-sm leading-relaxed text-ink-700">
                      {item.label}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* アフィリエイト（記事内で言及されたツール） */}
          {affiliates.length > 0 && (
            <div className="mt-12">
              <AffiliateBox links={affiliates} />
            </div>
          )}

          {/* タグ */}
          {article.tags.length > 0 && (
            <div className="mt-12 flex flex-wrap gap-2">
              {article.tags.map((tag) => (
                <Link
                  key={tag}
                  href={`/tags/${encodeTag(tag)}`}
                  className="rounded-full border border-ink-100 bg-white px-3.5 py-1.5 text-xs text-ink-700 hover:border-accent hover:text-accent"
                >
                  #{tag}
                </Link>
              ))}
            </div>
          )}

          <p className="mt-10 rounded-xl bg-ink-100/60 px-5 py-4 text-xs leading-relaxed text-ink-500">
            本記事は {article.model} が元動画の映像・音声を解析して自動生成したものです。
            誤りが含まれる可能性があるため、正確な仕様・料金は
            <a
              href={article.videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mx-1 text-accent underline"
            >
              公式動画
            </a>
            および公式サイトをご確認ください。
          </p>

          {related.length > 0 && (
            <section className="mt-16">
              <h2 className="mb-5 text-sm font-bold tracking-widest text-ink-500">
                関連記事
              </h2>
              <div className="grid gap-6 sm:grid-cols-2">
                {related.map((item) => (
                  <ArticleCard key={item.slug} article={item} />
                ))}
              </div>
            </section>
          )}
        </div>

        {/* ③ サイドバー（最上部に広告枠） */}
        <aside className="min-w-0">
          <Sidebar current={article} affiliates={affiliates} />
        </aside>
      </div>
    </div>
  );
}

/** "12:34" / "1:02:03" → 秒 */
function toSeconds(time: string): number {
  const parts = time.split(":").map((p) => Number.parseInt(p, 10));
  if (parts.some(Number.isNaN)) return 0;
  return parts.reduce((total, part) => total * 60 + part, 0);
}
