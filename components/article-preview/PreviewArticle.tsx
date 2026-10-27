import type { ReactNode } from "react";
import Link from "next/link";
import Thumb from "@/components/Thumb";
import AdSlot from "@/components/AdSlot";
import AffiliateBox from "@/components/AffiliateBox";
import MobilePrBar from "@/components/rail/MobilePrBar";
import RailRanking from "@/components/rail/RailRanking";
import ArticleCard from "@/components/ArticleCard";
import CompanyMark from "@/components/CompanyMark";
import CtaBanner from "@/components/CtaBanner";
import RelTime from "@/components/RelTime";
import NextRead from "@/components/NextRead";
import InlineRead from "@/components/InlineRead";
import ReadingMode from "@/components/ReadingMode";
import Sidebar from "@/components/Sidebar";
import { companyOf, thumbSource } from "@/lib/companies";
import { offerForArticle } from "@/lib/offers";
import {
  formatDate,
  formatDateTime,
  getNextReads,
  getRelatedArticles,
  isWeb,
  sourceHref,
  sourceLabel,
  tagHref,
} from "@/lib/articles";
import { Highlight } from "@/lib/highlight";
import { splitBeforeHeading } from "@/lib/markdown";
import type { ArticleView } from "./view";
import "./preview.css";

type Slots = {
  /** ap-a / ap-b / ap-c（本文の組版を切り替える） */
  className: string;
  /** 要点・判定のまとまり（タイトルの直下） */
  summary: ReactNode;
  /** 本文の直前に置く目次 */
  topToc?: ReactNode;
  /** PC（xl 以上）で本文の左に置く目次 */
  railToc?: ReactNode;
  /** 画面に浮かせる部品（読了バー・目次ボタンなど） */
  floating?: ReactNode;
};

/**
 * 記事ページの骨格（本番 app/articles/[slug]/page.tsx と同じ並び）。案ごとに差し替えるのは Slots だけ。
 * 構造化データは確認用なので出さない。
 */
export default async function PreviewArticle({ view, slots }: { view: ArticleView; slots: Slots }) {
  const { article, html, easyHtml } = view;
  const isRoundup = article.type === "roundup";
  const web = isWeb(article);
  const sourceUrl = sourceHref(article);
  const sourceName = sourceLabel(article);
  const affiliates = article.affiliates ?? [];
  const company = companyOf(article);
  const offerAll = offerForArticle(article, 12);
  const pool = offerAll?.items ?? [];
  const offer = offerAll && { ...offerAll, items: [...pool.slice(0, 3), ...pool.slice(6, 9)] };
  const inlineItems = [...pool.slice(3, 6), ...pool.slice(9, 12)];
  const inlineOffer =
    offerAll && inlineItems.length >= 2 ? { ...offerAll, eyebrow: "あわせてチェック", items: inlineItems } : undefined;
  const [bodyTop, afterAd] = splitBeforeHeading(html, 3);
  const [bodyMid, bodyTail] = splitBeforeHeading(afterAd, 4);
  const nextReads = getNextReads(article, (a) => companyOf(a).slug);
  const nextSlugs = new Set(nextReads.map((n) => n.article.slug));
  const related = getRelatedArticles(article, 8).filter((a) => !nextSlugs.has(a.slug)).slice(0, 4);
  const prose = `prose ap-prose max-w-none`;

  return (
    <div className={`ap ${slots.className} mx-auto max-w-[1240px] px-4 py-8 sm:px-8 sm:py-10`}>
      {slots.floating}
      <div className={`grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px] ${slots.railToc ? "xl:grid-cols-[200px_minmax(0,1fr)_300px]" : ""}`}>
        {slots.railToc && <div className="hidden xl:block">{slots.railToc}</div>}
        <div className="min-w-0">
          <nav aria-label="パンくず" className="flex flex-wrap items-center gap-1.5 text-meta text-muted">
            <Link href="/" className="hover:text-accent">ホーム</Link>
            <span aria-hidden>/</span>
            <Link href={`/companies/${company.slug}`} className="hover:text-accent">{company.name}</Link>
            <span aria-hidden>/</span>
            <Link href={`/channels/${article.channelSlug}`} className="hover:text-accent">{article.channel}</Link>
          </nav>

          <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-meta">
            <CompanyMark company={company} size={20} withName />
            <span className="rounded-full border border-line-strong px-2 py-[1px] text-badge font-bold text-ink-soft">
              {isRoundup ? `まとめ ${article.sources?.length ?? 0}本` : "公式発表"}
            </span>
            <span className="text-muted">
              <RelTime iso={article.publishedAt} className="index-num font-semibold text-ink" />
              <span className="index-num ml-1.5">（{formatDate(article.publishedAt)}）</span>
            </span>
            <span className="index-num text-muted">読了 {view.readMinutes}分</span>
            {article.updatedAt && formatDateTime(article.updatedAt) && (
              <span className="index-num font-semibold text-ink-soft">最終更新: {formatDateTime(article.updatedAt)}</span>
            )}
          </div>

          <h1 className="display headline mt-3 text-[1.75rem] font-bold text-ink sm:text-[2.4rem]">
            <Highlight text={article.title} />
          </h1>

          {slots.summary}

          {easyHtml && <ReadingMode easyMinutes={view.easyMinutes} expertMinutes={view.readMinutes} />}

          {article.lede && <p className="ap-lede mt-6">{article.lede}</p>}

          <p className="mt-4">
            <span className="rounded-full bg-surface px-2 py-0.5 text-badge font-bold text-muted">本ページはプロモーションを含みます</span>
          </p>

          <AdSlot position="article-top" className="mt-6" />

          {!isRoundup && web && article.thumbnail && (
            <figure className="mt-7 overflow-hidden rounded-3xl border border-line">
              <a href={sourceUrl || undefined} target="_blank" rel="noopener" className="relative block aspect-video bg-surface-2">
                <Thumb src={article.thumbnail} source={thumbSource(article)} alt="" fill priority sizes="(max-width: 1024px) 100vw, 860px" className="object-cover" />
              </a>
              <figcaption className="bg-surface px-5 py-3 text-meta text-muted">出典: {sourceName}「{article.videoTitle}」</figcaption>
            </figure>
          )}
          {!isRoundup && web && !article.thumbnail && sourceUrl && (
            <p className="mt-6 flex items-center gap-3 rounded-2xl bg-surface px-5 py-3.5 text-meta">
              <CompanyMark company={company} size={28} />
              <span className="min-w-0 flex-1">
                <span className="block text-meta font-bold text-muted">出典: {sourceName}</span>
                <a href={sourceUrl} target="_blank" rel="noopener" className="font-bold text-ink hover:text-accent hover:underline">
                  「{article.videoTitle}」
                </a>
              </span>
            </p>
          )}
          {!isRoundup && !web && article.thumbnail && (
            <a href={article.videoUrl} target="_blank" rel="noopener noreferrer" className="relative mt-7 block aspect-video overflow-hidden rounded-3xl bg-black">
              <Thumb src={article.thumbnail} alt="" fill priority sizes="(max-width: 1024px) 100vw, 860px" className="object-cover opacity-90" />
            </a>
          )}

          <div id="article-flow" data-read-mode="expert">
            {easyHtml && (
              <div className="read-easy">
                <p className="mt-8 inline-flex items-center gap-2 rounded-full bg-go-soft px-3 py-1 text-badge font-bold text-go">
                  かんたん版：専門用語を使わずに説明しています
                </p>
                <article className={`${prose} mt-5`} dangerouslySetInnerHTML={{ __html: easyHtml }} />
              </div>
            )}
            <div className="read-expert">
              {slots.topToc}
              <article className={`${prose} mt-10`} dangerouslySetInnerHTML={{ __html: bodyTop }} />
              {bodyMid && <InlineRead item={nextReads[2] ?? nextReads[1]} />}
              {bodyMid && <AdSlot position="article-middle" className="my-10" />}
              {bodyMid && <article className={prose} dangerouslySetInnerHTML={{ __html: bodyMid }} />}
              {bodyTail && inlineOffer && (
                <div className="my-10 max-w-[46em]">
                  <RailRanking offer={inlineOffer} wide id="offer-inline" title="もっと深く知るための3選" countImpression={false} />
                </div>
              )}
              {bodyTail && !offer && affiliates.length > 0 && (
                <div className="my-10">
                  <AffiliateBox links={affiliates} />
                </div>
              )}
              {bodyTail && <CtaBanner genreSlug={article.genreSlug} slot="inline" className="my-10" />}
              {bodyTail && <article className={prose} dangerouslySetInnerHTML={{ __html: bodyTail }} />}
            </div>
          </div>

          <NextRead items={nextReads} />
          <CtaBanner genreSlug={article.genreSlug} slot="primary" className="mt-12" />

          {article.tags.length > 0 && (
            <div className="mt-12 flex flex-wrap gap-2">
              {article.tags.map((tag) => (
                <Link key={tag} href={tagHref(tag)} className="rounded-full bg-surface px-3.5 py-1.5 text-meta font-medium text-ink-soft hover:bg-surface-2 hover:text-accent">
                  #{tag}
                </Link>
              ))}
            </div>
          )}

          <p className="mt-10 rounded-2xl bg-surface px-5 py-4 text-meta leading-relaxed text-muted">
            {article.disclaimer || "本記事はAIが解析して自動生成したものです。正確な情報は公式発表をご確認ください。"}（解析モデル: {article.model}）
          </p>

          {related.length > 0 && (
            <section aria-labelledby="related-heading" className="mt-16">
              <h2 id="related-heading" className="display mb-5 border-b border-line-strong pb-3 text-xl">関連記事</h2>
              <div className="grid gap-3.5 sm:grid-cols-2">
                {related.map((item) => (
                  <ArticleCard key={item.slug} article={item} />
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="min-w-0">
          {offer ? (
            <div className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:[scrollbar-width:thin]">
              <RailRanking offer={offer} countImpression={false} />
            </div>
          ) : (
            <Sidebar current={article} affiliates={affiliates} />
          )}
        </aside>
      </div>
      {offer && <MobilePrBar item={offer.items[0]} watchId="offer-inline" />}
    </div>
  );
}
