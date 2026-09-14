import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import AdSlot from "@/components/AdSlot";
import AffiliateBox from "@/components/AffiliateBox";
import ArticleCard from "@/components/ArticleCard";
import RoundupSources from "@/components/RoundupSources";
import CtaBanner from "@/components/CtaBanner";
import Sidebar from "@/components/Sidebar";
import {
  tagHref,
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
    ...(article.genreSlug === "ai"
      ? {}
      // AI以外は専門性を薄めるため検索対象から外す（ページ自体は残す）
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

  const affiliates = article.affiliates ?? [];
  const html = await renderMarkdown(
    article.body,
    affiliates.map((a) => a.url),
  );
  // 第3章の前に広告、さらに後半（通算6つ目の見出し）の前に収益導線を挟む
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
    <div className="mx-auto max-w-[1240px] px-5 py-10 sm:px-8">
      <script
        type="application/ld+json"
        suppressHydrationWarning
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <nav className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
            <Link href="/" className="hover:text-accent">
              ホーム
            </Link>
            <span className="text-muted">/</span>
            <Link
              href={`/genres/${article.genreSlug}`}
              className="hover:text-accent"
            >
              {article.genre}
            </Link>
            <span className="text-muted">/</span>
            <Link
              href={`/channels/${article.channelSlug}`}
              className="hover:text-accent"
            >
              {article.channel}
            </Link>
          </nav>

          <p className="eyebrow mt-6">{article.genre}</p>
          <h1 className="display mt-2 text-[1.75rem] sm:text-[2.375rem]">
            {article.title}
          </h1>

          {article.lede && (
            <p className="mt-5 border-l-[3px] border-accent pl-4 text-[15px] leading-[1.9] text-ink-soft sm:text-base">
              {article.lede}
            </p>
          )}

          <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted">
            <span className="rounded-full bg-accent-soft px-2.5 py-1 font-medium text-accent">
              {article.channel}
            </span>
            <time dateTime={article.publishedAt}>
              公開 {formatDate(article.publishedAt)}
            </time>
            <span className="text-muted">|</span>
            <span>AI解析: {article.model}</span>
            {affiliates.length > 0 && (
              <>
                <span className="text-muted">|</span>
                <span className="rounded bg-line px-1.5 py-0.5 text-[10px]">
                  PR含む
                </span>
              </>
            )}
          </div>

          {/* ① 記事トップ（タイトル下）の広告枠 */}
          {/* 同じ話題のまとめ記事へ誘導する（個別記事 → ハブ） */}
          {article.roundupSlug && (
            <Link
              href={`/articles/${article.roundupSlug}`}
              className="group mt-6 flex items-start gap-3 rounded-xl border-2 border-accent/40 bg-accent-soft px-5 py-4 transition-colors hover:border-accent"
            >
              <span className="mt-0.5 shrink-0 bg-accent px-2 py-0.5 text-[10px] font-bold tracking-widest text-accent-ink">
                まとめ
              </span>
              <span className="min-w-0">
                <span className="block text-[13px] text-muted">
                  この話題の全体像はこちら
                </span>
                <span className="mt-0.5 block font-serif text-[15px] font-bold leading-snug text-ink group-hover:text-accent">
                  {article.roundupTitle}
                </span>
              </span>
            </Link>
          )}

          <AdSlot position="article-top" className="mt-6" />

          {/* 動画（クリックで初めて YouTube を読み込む軽量ファサード） */}
          {article.type !== "roundup" && (
          <div className="mt-7 overflow-hidden rounded-2xl border border-line bg-black">
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
            <p className="truncate bg-black px-4 py-2.5 text-xs text-white/60">
              元動画: {article.videoTitle}
            </p>
          </div>
          )}

          {/* 3秒でわかる要点3選 */}
          {article.highlights.length > 0 && (
            <section className="mt-9 rounded-2xl border border-accent/20 bg-accent-soft/50 p-6">
              <h2 className="text-sm font-black tracking-wide text-accent">
                ⚡ 3秒でわかる要点
              </h2>
              <ul className="mt-4 space-y-3">
                {article.highlights.map((highlight, index) => (
                  <li key={index} className="flex gap-3">
                    <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-accent text-[11px] font-bold text-accent-ink">
                      {index + 1}
                    </span>
                    <span className="text-sm font-medium leading-relaxed text-ink">
                      {highlight}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 目次 */}
          {headings.length > 1 && (
            <nav className="mt-8 rounded-2xl border border-line bg-surface p-6">
              <p className="text-sm font-bold text-ink">目次</p>
              <ol className="mt-3 space-y-2">
                {headings.map((heading) => (
                  <li key={heading.id}>
                    <a
                      href={`#${heading.id}`}
                      className="text-sm text-muted hover:text-accent"
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
            className="prose mt-10 max-w-none"
            dangerouslySetInnerHTML={{ __html: bodyTop }}
          />

          {/* ② 記事中盤（第3章の前）の広告枠 */}
          {bodyMid && <AdSlot position="article-middle" className="my-10" />}

          {/* 本文（中盤） */}
          {bodyMid && (
            <article
              className="prose max-w-none"
              dangerouslySetInnerHTML={{ __html: bodyMid }}
            />
          )}

          {/* 本文に馴染ませる収益導線 */}
          {bodyTail && (
            <CtaBanner
              genreSlug={article.genreSlug}
              slot="inline"
              className="my-10"
            />
          )}

          {/* 本文（後半） */}
          {bodyTail && (
            <article
              className="prose max-w-none"
              dangerouslySetInnerHTML={{ __html: bodyTail }}
            />
          )}

          {/* まとめ記事が統合した元記事（ハブ → 個別記事） */}
          {article.type === "roundup" && (
            <RoundupSources sources={article.sources ?? []} />
          )}

          {/* タイムテーブル */}
          {article.timetable.length > 0 && (
            <section className="mt-12">
              <h2 className="text-lg font-bold text-ink">
                🕒 発表タイムテーブル
              </h2>
              <ul className="mt-4 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
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
                    <span className="text-sm leading-relaxed text-ink-soft">
                      {item.label}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 記事末の主導線（読了直後がいちばん動く） */}
          <CtaBanner
            genreSlug={article.genreSlug}
            slot="primary"
            className="mt-12"
          />

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
                  href={tagHref(tag)}
                  className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-xs text-ink-soft hover:border-accent hover:text-accent"
                >
                  #{tag}
                </Link>
              ))}
            </div>
          )}

          <p className="mt-10 rounded-xl bg-line/60 px-5 py-4 text-xs leading-relaxed text-muted">
            {article.disclaimer ||
              "本記事は元動画の映像・音声をAIが解析して自動生成したものです。誤りが含まれる可能性があるため、正確な情報は公式発表をご確認ください。"}
            <a
              href={article.videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mx-1 text-accent underline"
            >
              元動画を見る
            </a>
            （解析モデル: {article.model}）
          </p>

          {related.length > 0 && (
            <section className="mt-16">
              <h2 className="mb-5 text-sm font-bold tracking-widest text-muted">
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
