import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import AdSlot from "@/components/AdSlot";
import AffiliateBox from "@/components/AffiliateBox";
import ArticleCard from "@/components/ArticleCard";
import CtaBanner from "@/components/CtaBanner";
import Morph from "@/components/Morph";
import RoundupSources from "@/components/RoundupSources";
import Sidebar from "@/components/Sidebar";
import {
  formatDate,
  getAllArticles,
  getArticle,
  getRelatedArticles,
  tagHref,
} from "@/lib/articles";
import { Highlight } from "@/lib/highlight";
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
    // AI以外は専門性を薄めるため検索対象から外す（ページ自体は残す）
    ...(article.genreSlug === "ai"
      ? {}
      : { robots: { index: false, follow: true } }),
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

  const isRoundup = article.type === "roundup";
  const affiliates = article.affiliates ?? [];
  const html = await renderMarkdown(
    article.body,
    affiliates.map((a) => a.url),
  );
  // 第3章の前に広告、さらに後半の前に収益導線を挟む
  const [bodyTop, afterAd] = splitBeforeHeading(html, 3);
  const [bodyMid, bodyTail] = splitBeforeHeading(afterAd, 4);
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
    <div className="mx-auto max-w-[1240px] px-5 py-8 sm:px-8 sm:py-10">
      <script
        type="application/ld+json"
        suppressHydrationWarning
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <nav aria-label="パンくず" className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
            <Link href="/" className="hover:text-accent">
              ホーム
            </Link>
            <span aria-hidden>/</span>
            <Link href={`/genres/${article.genreSlug}`} className="hover:text-accent">
              {article.genre}
            </Link>
            <span aria-hidden>/</span>
            <Link href={`/channels/${article.channelSlug}`} className="hover:text-accent">
              {article.channel}
            </Link>
          </nav>

          <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] font-bold">
            <span className={`inline-flex items-center gap-1.5 ${isRoundup ? "text-roundup" : "text-official"}`}>
              <i className={`dot ${isRoundup ? "dot-roundup" : "dot-official"}`} aria-hidden />
              {isRoundup ? "まとめ記事" : "公式発表"}
            </span>
            <span className="text-muted">{article.channel}</span>
            <time dateTime={article.publishedAt} className="index-num font-normal text-muted">
              {formatDate(article.publishedAt)}
            </time>
          </div>

          <Morph name={`title-${article.slug}`}>
            <h1 className="display mt-3 font-bold text-[1.85rem] text-ink sm:text-[2.5rem]">
              <Highlight text={article.title} />
            </h1>
          </Morph>

          {article.lede && (
            <p className="mt-5 max-w-[62ch] text-[15.5px] leading-[1.95] text-ink-soft sm:text-base">
              {article.lede}
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-[11.5px] text-muted">
            <span>AI解析: {article.model}</span>
            {affiliates.length > 0 && (
              <span className="rounded-full bg-surface px-2 py-0.5 text-[10.5px] font-bold">
                PR含む
              </span>
            )}
          </div>

          {/* 個別記事 → 同じ話題のまとめ記事へ */}
          {article.roundupSlug && (
            <Link
              href={`/articles/${article.roundupSlug}`}
              className="group mt-6 flex items-start gap-3 rounded-2xl bg-surface px-5 py-4 transition-colors hover:bg-surface-2"
            >
              <span className="mt-0.5 shrink-0 rounded-full bg-ink px-2.5 py-0.5 text-[10.5px] font-bold text-paper">
                まとめ
              </span>
              <span className="min-w-0">
                <span className="block text-[12.5px] text-muted">この話題の全体像はこちら</span>
                <span className="mt-0.5 block text-[15px] font-bold leading-snug text-ink group-hover:text-accent">
                  {article.roundupTitle}
                </span>
              </span>
            </Link>
          )}

          {/* ① 記事トップの広告枠 */}
          <AdSlot position="article-top" className="mt-6" />

          {/* まとめ記事: 統合本数を主役に */}
          {isRoundup && (
            <div className="mt-7 flex flex-wrap items-end gap-x-4 gap-y-1 rounded-3xl bg-surface px-6 py-5">
              <span className="index-num text-[3.5rem] font-semibold leading-[0.85] tracking-tighter text-roundup">
                {article.sources?.length ?? 0}
              </span>
              <span className="pb-1 text-[13.5px] font-bold leading-snug text-muted">
                本の発表を1本に統合した記事です
              </span>
            </div>
          )}

          {/* 個別記事: 動画（クリックで初めて YouTube を開く軽量表示） */}
          {!isRoundup && (
            <div className="mt-7 overflow-hidden rounded-3xl bg-black">
              <Morph name={`cover-${article.slug}`}>
                <a
                  href={article.videoUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group relative block aspect-video"
                  aria-label={`元動画「${article.videoTitle}」をYouTubeで見る`}
                >
                  <Image
                    src={article.thumbnail}
                    alt=""
                    fill
                    priority
                    sizes="(max-width: 1024px) 100vw, 860px"
                    className="object-cover opacity-90 transition-opacity group-hover:opacity-100"
                  />
                  <span className="absolute inset-0 grid place-items-center">
                    <span className="grid h-14 w-20 place-items-center rounded-2xl bg-red-600/95 text-white shadow-lg transition-transform group-hover:scale-110">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    </span>
                  </span>
                </a>
              </Morph>
              <p className="truncate px-5 py-3 text-xs text-white/60">
                元動画: {article.videoTitle}
              </p>
            </div>
          )}

          {/* 3秒でわかる要点 */}
          {article.highlights.length > 0 && (
            <section aria-labelledby="points-heading" className="mt-8 rounded-3xl bg-surface p-6 sm:p-7">
              <h2 id="points-heading" className="text-[13px] font-bold">
                3秒でわかる要点
              </h2>
              <ol className="mt-4 grid gap-3.5">
                {article.highlights.map((highlight, index) => (
                  <li key={index} className="grid grid-cols-[24px_1fr] gap-3 text-[15px] font-medium leading-[1.7] text-ink">
                    <span className="index-num mt-0.5 grid size-6 place-items-center rounded-full bg-ink text-[11.5px] font-semibold text-paper">
                      {index + 1}
                    </span>
                    {highlight}
                  </li>
                ))}
              </ol>
            </section>
          )}

          {/* 章立て */}
          {headings.length > 1 && (
            <nav aria-labelledby="toc-heading" className="mt-6 rounded-3xl border border-line p-6">
              <h2 id="toc-heading" className="text-[13px] font-bold text-muted">
                この記事の章立て
              </h2>
              <ol className="mt-3 grid list-decimal gap-2 pl-5 marker:font-mono marker:text-[11px] marker:text-muted">
                {headings.map((heading) => (
                  <li key={heading.id}>
                    <a href={`#${heading.id}`} className="text-[14px] font-medium text-ink-soft hover:text-accent">
                      {heading.text}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
          )}

          {/* 本文（前半） */}
          <article className="prose mt-10 max-w-[42em]" dangerouslySetInnerHTML={{ __html: bodyTop }} />

          {/* ② 記事中盤の広告枠 */}
          {bodyMid && <AdSlot position="article-middle" className="my-10" />}

          {bodyMid && (
            <article className="prose max-w-[42em]" dangerouslySetInnerHTML={{ __html: bodyMid }} />
          )}

          {/* 本文に馴染ませる収益導線 */}
          {bodyTail && <CtaBanner genreSlug={article.genreSlug} slot="inline" className="my-10" />}

          {bodyTail && (
            <article className="prose max-w-[42em]" dangerouslySetInnerHTML={{ __html: bodyTail }} />
          )}

          {/* まとめ記事が統合した元記事 */}
          {isRoundup && <RoundupSources sources={article.sources ?? []} />}

          {/* 動画のタイムテーブル */}
          {article.timetable.length > 0 && (
            <section aria-labelledby="timetable-heading" className="mt-12">
              <h2 id="timetable-heading" className="text-lg font-bold text-ink">
                動画のタイムテーブル
              </h2>
              <ul className="mt-4 divide-y divide-line overflow-hidden rounded-3xl bg-surface">
                {article.timetable.map((item, index) => (
                  <li key={index} className="grid grid-cols-[4.5rem_1fr] gap-4 px-5 py-3.5">
                    <a
                      href={`${article.videoUrl}&t=${toSeconds(item.time)}s`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="index-num text-[13px] font-semibold text-official hover:underline"
                    >
                      {item.time}
                    </a>
                    <span className="text-[14px] leading-relaxed text-ink-soft">{item.label}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 記事末の主導線 */}
          <CtaBanner genreSlug={article.genreSlug} slot="primary" className="mt-12" />

          {affiliates.length > 0 && (
            <div className="mt-12">
              <AffiliateBox links={affiliates} />
            </div>
          )}

          {article.tags.length > 0 && (
            <div className="mt-12 flex flex-wrap gap-2">
              {article.tags.map((tag) => (
                <Link
                  key={tag}
                  href={tagHref(tag)}
                  className="rounded-full bg-surface px-3.5 py-1.5 text-xs font-medium text-ink-soft hover:bg-surface-2 hover:text-accent"
                >
                  #{tag}
                </Link>
              ))}
            </div>
          )}

          <p className="mt-10 rounded-2xl bg-surface px-5 py-4 text-xs leading-relaxed text-muted">
            {article.disclaimer ||
              "本記事は元動画の映像・音声をAIが解析して自動生成したものです。誤りが含まれる可能性があるため、正確な情報は公式発表をご確認ください。"}
            <a href={article.videoUrl} target="_blank" rel="noopener noreferrer" className="mx-1 text-accent underline">
              元動画を見る
            </a>
            （解析モデル: {article.model}）
          </p>

          {related.length > 0 && (
            <section aria-labelledby="related-heading" className="mt-16">
              <h2 id="related-heading" className="display mb-5 border-b border-line-strong pb-3 text-xl">
                関連記事
              </h2>
              <div className="grid gap-3.5 sm:grid-cols-2">
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
