import type { ComponentType, ReactNode } from "react";
import Link from "next/link";
import AdSlot from "@/components/AdSlot";
import MobilePrBar from "@/components/rail/MobilePrBarLazy";
import RailRanking from "@/components/rail/RailRanking";
import CtaBanner from "@/components/CtaBanner";
import NextRead from "@/components/NextRead";
import NewsletterSignup from "@/components/NewsletterSignup";
import PushOptIn from "@/components/PushOptIn";
import InlineRead from "@/components/InlineRead";
import ReadingMode from "@/components/ReadingMode";
import VerdictCard from "@/components/VerdictCard";
import WorkMoneyCard from "@/components/WorkMoneyCard";
import AssetLinks from "@/components/assets/AssetLinks";
import SourceRecord from "@/components/SourceRecord";
import ArticleFaq from "@/components/ArticleFaq";
import TodayActions from "@/components/TodayActions";
import ShareButtons from "@/components/ShareButtons";
import ThreadsFollow from "@/components/ThreadsFollow";
import ReadNextBox from "@/components/ReadNextBox";
import ShopLinks from "@/components/ShopLinks";
import Sidebar from "@/components/Sidebar";
import CalculatorBox from "@/components/calc/CalculatorBox";
import NoirArticle from "@/components/noir/NoirArticle";
import { articleTitle } from "@/lib/headline";
import { isFastNews } from "@/lib/cover-path";
import { OTHER, sourceBadge, type Company } from "@/lib/companies";
import { guideHref } from "@/lib/guides";
import { guideShortName } from "@/lib/buying-guides";
import { getCta } from "@/lib/monetization";
import { workMoneyHeading } from "@/lib/work-money";
import { splitBeforeHeading } from "@/lib/markdown";
import { headingTexts, noirBodyHtml, noirCover } from "@/lib/noir";
import { tagHref, type ArticleSummary, type FullArticle } from "@/lib/articles";
import { siteConfig } from "@/site.config";
import type { ChooseGuide } from "@/lib/choose-data";

/* eslint-disable @typescript-eslint/no-explicit-any -- 記事ページ（app/articles/[slug]/page.tsx）で作った値をそのまま受け取る */
type Any = any;

/**
 * ノワールの記事ページ（2026-11-07 以降の新しい記事。台帳 W36）。
 * 中身（広告の枠・提携の枠・判定・FAQ・出典・次の1本・構造化データ）は今までの記事ページが作った値をそのまま使い、並べ方と見た目だけを変える。
 * 同じ枠はページに1つだけ（台帳 W10）。PC も1列なので、右側の商品枠・サイドバーは記事の終わりに置く（スマホの今までの並びと同じ）。
 */
export type NoirPageContext = {
  article: FullArticle;
  jsonLd: Record<string, unknown>[];
  bodyHtml: string;
  easyHtml: string;
  easyMinutes: number;
  readMinutes: number;
  company: Company;
  sourceUrl: string;
  sourceName: string;
  showAds: boolean;
  inlineOffer: Any;
  shopLink: Any;
  buyingGuide: Any;
  chooseGuide: ChooseGuide | undefined | null;
  readNextInline: Any;
  readNextRail: Any;
  offer: Any;
  inlineRead: Any;
  mainArticle: ArticleSummary | undefined;
  guideLinks: { href: string; kind: string; label: string }[];
  calc: Any;
  calcInline: boolean;
  calcBox: ReactNode;
  priceBox: ReactNode;
  workMoney: Any;
  verdict: Any;
  cardKind: Any;
  todayActions: string[];
  articleFaq: { q: string; a: string }[];
  howto: Any;
  guide: Any;
  product: Any;
  nextReads: Any;
  related: ArticleSummary[];
  crumbs: { href: string; label: string }[];
  reviewedLabel: string | null | undefined;
  ChooseGuideNote: ComponentType<{ guide: ChooseGuide; className?: string }>;
  CompareLink: ComponentType<{ slug: string; name: string; className?: string }>;
};

export function noirArticlePage(ctx: NoirPageContext) {
  const {
    article, jsonLd, bodyHtml, easyHtml, easyMinutes, readMinutes, company, sourceUrl, sourceName, showAds,
    inlineOffer, shopLink, buyingGuide, chooseGuide, readNextInline, readNextRail, offer, inlineRead, mainArticle,
    guideLinks, calc, calcInline, calcBox, priceBox, workMoney, verdict, cardKind, todayActions, articleFaq,
    howto, guide, product, nextReads, related, crumbs, reviewedLabel, ChooseGuideNote, CompareLink,
  } = ctx;
  const noirHtml = noirBodyHtml(bodyHtml, article);
  const [noirTop, noirAfterAd] = splitBeforeHeading(noirHtml, 3);
  const [noirMid, noirTail] = splitBeforeHeading(noirAfterAd, 4);
  const noirInlineCta = noirTail && !inlineOffer && !shopLink && getCta(article.genreSlug, "inline") ? "inline" : undefined;
  const noirPrimaryCta = !inlineOffer && !shopLink && !noirInlineCta && getCta(article.genreSlug, "primary") ? "primary" : undefined;
  const noirHasInlinePr = Boolean(inlineOffer || shopLink || noirInlineCta || noirPrimaryCta);
  const badge = sourceBadge(article);
  // 発表元の名前（写真の注記の団体名 → 企業名 → 発信元の名前）
  const org =
    article.imageCredit?.org ||
    (company.slug !== OTHER.slug ? company.name : "") ||
    // 「KDDI ニュースリリース」「NVIDIA公式ブログ」の発信元の名前から、ページの種類の言葉を外して団体の名前にする
    sourceName.replace(/\s*(?:公式)?(?:ニュースリリース|プレスリリース|ニュースルーム|お知らせ|ブログ|Newsroom|News|Blog)\s*$/i, "").trim() ||
    sourceName;
  const noirJsonLd = jsonLd.map((entry, i) =>
    i === 0 ? { ...entry, speakable: { "@type": "SpeakableSpecification", cssSelector: [".nr-sum"] } } : entry,
  );
  const inlinePrBlock = inlineOffer ? (
    <div className="nr-slot">
      <RailRanking offer={inlineOffer} wide id="offer-inline" title={inlineOffer.headline} />
      {shopLink && <ShopLinks link={shopLink} className="mt-3" />}
      {buyingGuide && <CompareLink slug={buyingGuide.slug} name={guideShortName(buyingGuide)} className="flex" />}
    </div>
  ) : null;
  return (
    <NoirArticle
      article={article}
      title={articleTitle(article)}
      jsonLd={noirJsonLd}
      cover={noirCover(article)}
      kicker={[company.slug !== OTHER.slug ? company.name : "", article.genre].filter(Boolean).join(" ・ ")}
      breaking={isFastNews(article)}
      origin={`${org} ${badge}`}
      readMinutes={readMinutes}
      // 報道機関の記事は「公式発表」と呼ばない（台帳 W17）
      sourceCta={sourceUrl ? (badge === "報道" ? `${sourceName}の記事を読む` : `${org}の発表を読む`) : null}
      sourceUrl={sourceUrl}
      body={{ top: noirTop, mid: noirMid, tail: noirTail }}
      headingsHtml={headingTexts(noirHtml).join("")}
      calcSlot={calcInline ? calcBox : undefined}
      priceSlot={priceBox}
      crumbs={crumbs}
      related={related}
      slots={{
        afterSummary: (
          <>
            {mainArticle && (
              <p className="mb-6 border-l-2 border-line-strong pl-3 text-note text-ink-soft">
                同じ話題をまとめた記事があります：
                <Link href={`/articles/${mainArticle.slug}`} className="ml-1 font-bold text-ink underline underline-offset-4">
                  {mainArticle.title}
                </Link>
              </p>
            )}
            {article.roundupSlug && (
              <p className="mb-6 text-note text-ink-soft">
                この話題の全体像：
                <Link href={`/articles/${article.roundupSlug}`} className="ml-1 font-bold text-ink underline underline-offset-4">
                  {article.roundupTitle}
                </Link>
              </p>
            )}
            {guideLinks.length > 0 && (
              <nav aria-label="この製品のガイド" className="mb-6 flex flex-wrap gap-x-5 gap-y-1.5 text-note">
                {guideLinks.map((link) => (
                  <Link key={link.href} href={link.href} className="font-bold text-ink-soft underline decoration-line-strong underline-offset-4 hover:text-ink">
                    {link.kind === "pricing" ? "料金ガイド：" : link.kind === "howto" ? "使い方ガイド：" : "ガイド："}
                    {link.label} →
                  </Link>
                ))}
              </nav>
            )}
          </>
        ),
        adTop: showAds ? <AdSlot position="article-top" className="my-6" /> : null,
        readingMode: easyHtml ? <ReadingMode easyMinutes={easyMinutes} expertMinutes={readMinutes} /> : null,
        easy: easyHtml ? (
          <div className="read-easy">
            <p className="mt-8 text-note font-bold text-ink-soft">要約版：専門用語を控えて説明しています</p>
            <article className="prose nr-prose mt-5" dangerouslySetInnerHTML={{ __html: noirBodyHtml(easyHtml, {}) }} />
          </div>
        ) : null,
        inlineRead: inlineRead ? <InlineRead item={{ article: inlineRead, reason: "同じ話題の記事" }} /> : null,
        adMid: showAds ? <AdSlot position="article-middle" className="my-10" /> : null,
        beforeTail: chooseGuide ? <ChooseGuideNote guide={chooseGuide} className="my-10" /> : null,
        betweenTail: (
          <>
            {inlinePrBlock}
            {readNextInline && <ReadNextBox link={readNextInline} className="my-10" />}
            {!inlineOffer && shopLink && <ShopLinks link={shopLink} className="my-10" />}
          </>
        ),
        tailCta: noirInlineCta ? <CtaBanner genreSlug={article.genreSlug} slot="inline" className="my-10" /> : null,
        afterBody: (
          <>
            {calc && !calcInline && <CalculatorBox calc={calc} className="mt-12" />}
            {workMoney && (
              <WorkMoneyCard
                workMoney={workMoney}
                heading={workMoneyHeading(article.newsType, article.genreSlug, article.title, article.tags)}
                money={article.genreSlug === "investment" || article.genreSlug === "real-estate" || article.newsType === "earnings"}
              />
            )}
            {verdict && (
              <VerdictCard verdict={verdict} cardKind={cardKind} judgedAt={verdict.judgedAt || article.generatedAt || article.publishedAt} />
            )}
            <AssetLinks article={article} />
            {todayActions.length >= 2 && <TodayActions actions={todayActions} />}
            {articleFaq.length >= 1 && <ArticleFaq items={articleFaq} />}
          </>
        ),
        afterSource: (
          <>
            <div className="mt-12 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-y border-line py-4">
              <p className="text-note font-bold text-ink">この記事をシェアする</p>
              <ShareButtons url={`${siteConfig.url}/articles/${article.slug}`} title={articleTitle(article)} />
            </div>
            <ThreadsFollow />
            <SourceRecord
              article={article}
              sourceUrl={sourceUrl}
              sourceName={sourceName}
              guide={
                howto
                  ? { href: `/guides/${howto.slug}`, label: howto.title }
                  : guide
                    ? { href: guideHref(guide.slug), label: `${guide.name}とは？できること・料金・使い方` }
                    : product
                      ? { href: `/products/${product.slug}`, label: `${product.name}のまとめページ` }
                      : undefined
              }
            />
            <NextRead items={nextReads} />
          </>
        ),
        end: (
          <>
            {!noirTail && chooseGuide && <ChooseGuideNote guide={chooseGuide} className="mt-12" />}
            {noirPrimaryCta && <CtaBanner genreSlug={article.genreSlug} slot="primary" className="mt-12" />}
            <NewsletterSignup variant="article" />
            <PushOptIn />
            {!noirTail && inlinePrBlock}
            {!noirTail && readNextInline && <ReadNextBox link={readNextInline} className="mt-12" />}
            {!noirTail && !inlineOffer && shopLink && <ShopLinks link={shopLink} className="mt-12" />}
            {article.tags.length > 0 && (
              <div className="mt-12 flex flex-wrap gap-2">
                {article.tags.map((tag) => (
                  <Link key={tag} href={tagHref(tag)} className="rounded-md bg-surface px-3.5 py-1.5 text-meta font-medium text-ink-soft hover:bg-surface-2 hover:text-ink">
                    #{tag}
                  </Link>
                ))}
              </div>
            )}
            <p className="mt-10 bg-surface px-5 py-4 text-note leading-relaxed text-muted">
              {article.disclaimer ||
                `本記事は${sourceName ? `${sourceName}の発表内容` : "公開されている情報"}をもとにAIが要約・解説して自動生成したものです。誤りが含まれる可能性があるため、正確な情報は元記事をご確認ください。`}
              {sourceUrl && (
                <a href={sourceUrl} target="_blank" rel="noopener" className="mx-1 text-ink underline">
                  元記事を読む
                </a>
              )}
              <span className="mt-1.5 block">
                制作方法と事実確認の手順は
                <Link href="/editorial-policy" className="mx-1 text-ink underline">
                  編集方針
                </Link>
                をご覧ください。誤りのご指摘は
                <Link href="/contact" className="mx-1 text-ink underline">
                  お問い合わせ
                </Link>
                から受け付けています。
              </span>
            </p>
          </>
        ),
        // PC でも1列なので、右側に置いていた物は記事の終わりに置く（スマホの今までの並びと同じ）
        rail: offer ? (
          <>
            <RailRanking offer={offer} />
            {buyingGuide && <CompareLink slug={buyingGuide.slug} name={guideShortName(buyingGuide)} className="flex" />}
          </>
        ) : (
          <>
            {readNextRail && !readNextInline && <ReadNextBox link={readNextRail} className="mb-8" />}
            <Sidebar current={article} showAds={showAds} />
          </>
        ),
        mobileBar: offer && !noirHasInlinePr ? <MobilePrBar item={offer.items[0]} watchId="offer-inline" /> : null,
      }}
      byline={
        <p className="flex flex-wrap gap-x-5 gap-y-1">
          <span>
            制作：<Link href="/about" rel="author">{siteConfig.author}</Link>
          </span>
          <Link href="/editorial-policy">編集方針・AI利用と事実確認</Link>
          {reviewedLabel && <span>✓ 編集部が確認済み（{reviewedLabel}）</span>}
        </p>
      }
    />
  );
}
