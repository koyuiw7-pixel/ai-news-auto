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
import { ActionSteps, CauseBox, DecisionGuide, InsightBox, OfficialDesk, WorriesBlock } from "@/components/DepthBoxes";
import { depthOf } from "@/lib/depth";
import ActionAd from "@/components/ActionAd";
import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import ShareButtons from "@/components/ShareButtons";
import ThreadsFollow from "@/components/ThreadsFollow";
import ReadNextBox from "@/components/ReadNextBox";
import ShopLinks from "@/components/ShopLinks";
import CalculatorBox from "@/components/calc/CalculatorBox";
import NoirArticle from "@/components/noir/NoirArticle";
import NoirPopular from "@/components/noir/NoirPopular";
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
 * 同じ枠はページに1つだけ（台帳 W10）。
 * 2026-11-09 オーナー「広告が一番下にしか無い」: 本文の列の PR は最大3つ（fa0bfacd の決まり）を、①要点・すぐにできることの直後 ②本文の途中 ③記事の終わりに置く。
 * PC は右の列に商品の枠（追従）と、よく読まれている記事。スマホは右の列の商品枠の写し（ranking-end。表示の計測は右の列の1回だけ）を本文の列に置く。
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
  /** 「すぐにできること」のすぐ下の PR（lib/action-ad.ts）。ここに出した商品は本文中・記事末の枠に重ねない */
  actionAd?: ActionAdData;
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

/** 要点のすぐ下の「すぐにできること」の短い一覧。手順つきの欄（ActionSteps）が下にあれば、そこへ飛べる */
function QuickActions({ actions, detailed }: { actions: string[]; detailed: boolean }) {
  return (
    <section className="nr-quick" aria-labelledby="nr-quick-heading">
      <h2 id="nr-quick-heading">すぐにできること</h2>
      <ol>
        {actions.map((action, i) => (
          <li key={i}>
            <b aria-hidden>{i + 1}</b>
            <span>{action}</span>
          </li>
        ))}
      </ol>
      {detailed && (
        <a href="#steps" className="nr-quick-more">
          手順と公式の窓口を見る <span aria-hidden>↓</span>
        </a>
      )}
    </section>
  );
}

export function noirArticlePage(ctx: NoirPageContext) {
  const {
    article, jsonLd, bodyHtml, easyHtml, easyMinutes, readMinutes, company, sourceUrl, sourceName, showAds,
    inlineOffer, shopLink, buyingGuide, chooseGuide, readNextInline, readNextRail, offer, inlineRead, mainArticle,
    guideLinks, calc, calcInline, calcBox, priceBox, workMoney, verdict, cardKind, todayActions, articleFaq,
    howto, guide, product, nextReads, related, crumbs, reviewedLabel, ChooseGuideNote, CompareLink, actionAd,
  } = ctx;
  const noirHtml = noirBodyHtml(bodyHtml, article);
  const depth = depthOf(article);
  const [noirTop, noirAfterAd] = splitBeforeHeading(noirHtml, 3);
  const [noirMid, noirTail] = splitBeforeHeading(noirAfterAd, 4);
  const noirInlineCta = !actionAd && !inlineOffer && !shopLink && getCta(article.genreSlug, "inline") ? "inline" : undefined;
  const noirPrimaryCta = !actionAd && !inlineOffer && !shopLink && !noirInlineCta && getCta(article.genreSlug, "primary") ? "primary" : undefined;
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
    <>
      <RailRanking offer={inlineOffer} wide id="offer-inline" title={inlineOffer.headline} />
      {shopLink && <ShopLinks link={shopLink} className="mt-3" />}
      {buyingGuide && <CompareLink slug={buyingGuide.slug} name={guideShortName(buyingGuide)} className="flex" />}
    </>
  ) : null;

  // すぐにできること: 要点の下に短い一覧。手順つき（depth.todaySteps）があれば、手順は本文の後ろ（公式窓口のそば）に置き、一覧から飛べるようにする
  const stepItems = depth.todaySteps.length >= 2 ? depth.todaySteps : [];
  const quickList = stepItems.length > 0 ? stepItems.map((s) => s.action) : todayActions.length >= 2 ? todayActions : [];

  // 本文の列の PR（最大3つ。fa0bfacd の決まり）。上から順に ①要点・すぐにできることの直後 ②本文の途中 ③記事の終わり
  const adBlocks: ReactNode[] = [];
  if (actionAd) adBlocks.push(<ActionAd key="action" ad={actionAd} className="mt-0" />);
  if (inlinePrBlock) adBlocks.push(<div key="inline">{inlinePrBlock}</div>);
  else if (shopLink) adBlocks.push(<ShopLinks key="shop" link={shopLink} />);
  if (noirInlineCta) adBlocks.push(<CtaBanner key="cta" genreSlug={article.genreSlug} slot="inline" />);
  else if (noirPrimaryCta) adBlocks.push(<CtaBanner key="cta" genreSlug={article.genreSlug} slot="primary" />);
  // スマホ: 右の列の商品枠の写し（PC は右の列に付いてくるので出さない）。表示の計測は右の列の1回だけ（二重に数えない）
  if (offer)
    adBlocks.push(
      <div key="end" className="lg:hidden">
        <RailRanking offer={offer} pos="ranking-end" countImpression={false} />
      </div>,
    );
  const [adEarly, adMidPr, adEnd] = adBlocks.slice(0, 3);

  return (
    <NoirArticle
      article={article}
      title={articleTitle(article)}
      jsonLd={noirJsonLd}
      cover={noirCover(article)}
      genre={article.genre}
      kicker={company.slug !== OTHER.slug ? company.name : ""}
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
        quick: quickList.length > 0 ? <QuickActions actions={quickList} detailed={stepItems.length > 0} /> : null,
        adEarly,
        afterSummary: (
          <>
            {depth.insight.length > 0 && <InsightBox items={depth.insight} heading={depth.headings.insight} />}
            {mainArticle && (
              <p className="nr-note">
                同じ話題をまとめた記事があります：
                <Link href={`/articles/${mainArticle.slug}`}>{mainArticle.title}</Link>
              </p>
            )}
            {article.roundupSlug && (
              <p className="nr-note">
                この話題の全体像：
                <Link href={`/articles/${article.roundupSlug}`}>{article.roundupTitle}</Link>
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
        adMidPr,
        // 本文の途中: 読者の迷い・不安に答える欄（判断ガイド・不安Q&A）
        midBoxes: (
          <>
            {depth.guide.length > 0 && <DecisionGuide groups={depth.guide} heading={depth.headings.guide} />}
            {depth.worries.length >= 2 && <WorriesBlock items={depth.worries} heading={depth.headings.worries} />}
          </>
        ),
        beforeTail: chooseGuide ? <ChooseGuideNote guide={chooseGuide} className="my-10" /> : null,
        betweenTail: readNextInline ? <ReadNextBox link={readNextInline} className="my-10" /> : null,
        afterBody: (
          <>
            {calc && !calcInline && <CalculatorBox calc={calc} className="mt-12" />}
            {/* 一歩深くする欄（scripts/depth_fields.py。公式ページで確かめた原因・手順・窓口・不安への答え。台帳 A66） */}
            {depth.cause && <CauseBox cause={depth.cause} heading={depth.headings.cause} />}
            {/* 手順つきの「すぐにできること」と公式窓口を並べる（要点の下の一覧から飛んでくる） */}
            {stepItems.length > 0 && <ActionSteps items={stepItems} heading={depth.headings.steps} />}
            {depth.officialDesk.length > 0 && <OfficialDesk items={depth.officialDesk} heading={depth.headings.desk} />}
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
            {articleFaq.length >= 1 && <ArticleFaq items={articleFaq} />}
          </>
        ),
        adEnd,
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
            <NewsletterSignup variant="article" />
            <PushOptIn />
            {!noirTail && readNextInline && <ReadNextBox link={readNextInline} className="mt-12" />}
            {article.tags.length > 0 && (
              <div className="mt-12 flex flex-wrap gap-2">
                {article.tags.map((tag) => (
                  <Link key={tag} href={tagHref(tag)} className="nr-tag">
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
        // PC の右の列（追従）: 商品の枠（無ければ次に読む案内・広告枠）と、よく読まれている記事。スマホでは記事の後ろに一覧だけ
        rail: (
          <>
            {offer ? (
              <div className="hidden lg:block">
                <RailRanking offer={offer} />
                {buyingGuide && <CompareLink slug={buyingGuide.slug} name={guideShortName(buyingGuide)} className="flex" />}
              </div>
            ) : (
              <div className="hidden lg:block">
                {readNextRail && !readNextInline && <ReadNextBox link={readNextRail} className="mb-6" />}
                {showAds && <AdSlot position="sidebar" />}
              </div>
            )}
            <NoirPopular current={article.slug} />
          </>
        ),
        mobileBar: offer && adBlocks.length === 0 ? <MobilePrBar item={offer.items[0]} watchId="offer-inline" /> : null,
      }}
      byline={
        <>
          <p className="flex flex-wrap gap-x-5 gap-y-1">
            <span>
              制作：<Link href="/about" rel="author">{siteConfig.author}</Link>
            </span>
            <Link href="/editorial-policy">編集方針・AI利用と事実確認</Link>
            {reviewedLabel && <span>✓ 編集部が確認済み（{reviewedLabel}）</span>}
          </p>
          <nav aria-label="パンくず（下）" className="nr-crumbs">
            <Link href="/">ホーム</Link>
            {crumbs.map((c) => (
              <span key={c.href} className="contents">
                <span aria-hidden>/</span>
                <Link href={c.href}>{c.label}</Link>
              </span>
            ))}
          </nav>
        </>
      }
    />
  );
}
