import type { ComponentType, ReactNode } from "react";
import Link from "next/link";
import AdSlot from "@/components/AdSlot";
import MobilePrBar from "@/components/rail/MobilePrBarLazy";
import { inAdReview } from "@/lib/ad-review";
import RailRanking from "@/components/rail/RailRanking";
import CtaBanner from "@/components/CtaBanner";
import NewsletterSignup from "@/components/NewsletterSignup";
import PushOptIn from "@/components/PushOptIn";
import ReadingMode from "@/components/ReadingMode";
import VerdictCard from "@/components/VerdictCard";
import WorkMoneyCard from "@/components/WorkMoneyCard";
import AssetLinks from "@/components/assets/AssetLinks";
import SourceRecord from "@/components/SourceRecord";
import ArticleFaq from "@/components/ArticleFaq";
import { ActionSteps, CauseBox, DecisionGuide, Fold, InsightBox, OfficialDesk, WorriesBlock } from "@/components/DepthBoxes";
import StoryLinks from "@/components/noir/StoryLinks";
import FoldOpener from "@/components/noir/FoldOpener";
import GenreLine from "@/components/noir/GenreLine";
import { TargetCheck } from "@/components/noir/NextSteps";
import PopularReads from "@/components/PopularReads";
import { mergeStoryReads } from "@/lib/story-reads";
import { ANSWER_TABLE_ID, extractAnswerTable } from "@/lib/answer-table";
import { topicPages } from "@/lib/related";
import { noReaderAction } from "@/lib/reader-urgency";
import { nextStepsFor } from "@/lib/next-steps";
import { depthOf } from "@/lib/depth";
import ActionAd from "@/components/ActionAd";
import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import type { FunnelCard as FunnelCardData } from "@/lib/comparison";
import FunnelCard from "@/components/FunnelCard";
import ShareButtons from "@/components/ShareButtons";
import MoneyCheckLink from "@/components/MoneyCheckLink";
import TopicListMembership from "@/components/TopicListMembership";
import type { MoneyTarget } from "@/lib/money-pages";
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
import { getAllArticles, tagHref, type ArticleSummary, type FullArticle } from "@/lib/articles";
import { siteConfig } from "@/site.config";
import { editorInCharge } from "@/lib/publisher";
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
  /** 同じ話題の比較記事への「次に読む」（lib/comparison.ts。自分たちの記事への案内なので広告の枠に数えない） */
  funnel?: FunnelCardData;
  /** 比較記事の提携先の一覧（比較表の直後・記事の終わり。広告の枠に数える） */
  compareInline?: ReactNode;
  compareEnd?: ReactNode;
  shopLink: Any;
  buyingGuide: Any;
  chooseGuide: ChooseGuide | undefined | null;
  readNextInline: Any;
  readNextRail: Any;
  offer: Any;
  inlineRead: Any;
  mainArticle: ArticleSummary | undefined;
  guideLinks: { href: string; kind: string; label: string }[];
  /** 要点のすぐ下の「自分は対象か確かめる」（lib/money-pages.ts） */
  moneyLink?: MoneyTarget;
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
  /** 同じ話題の記事（多め。上の2本を「この話の続き」、残りを本文直後の「次に読む記事」に。2026-11-10） */
  storyReads?: { article: ArticleSummary; reason: string }[];
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

/** 発表元の名前を短くする（「」や（）の前まで。短くなりすぎるときはそのまま） */
export function shortOrg(org: string): string {
  const head = org.split(/[「『（(]/)[0].trim();
  return head.length >= 2 ? head : org;
}

export function noirArticlePage(ctx: NoirPageContext) {
  const {
    article, jsonLd, bodyHtml, easyHtml, easyMinutes, readMinutes, company, sourceUrl, sourceName, showAds,
    shopLink, buyingGuide, chooseGuide, readNextInline, readNextRail, inlineRead, mainArticle,
    guideLinks, moneyLink, calc, calcInline, calcBox, priceBox, workMoney, verdict, cardKind, todayActions, articleFaq,
    howto, guide, product, nextReads, crumbs, reviewedLabel, ChooseGuideNote, CompareLink, actionAd,
    funnel, compareInline, compareEnd, storyReads = [],
  } = ctx;
  // 記事に合う PR だけ出す（2026-11-10 オーナー承認）。話題が当たらずジャンルの既定の広告（fallback-*）になった商品枠は、ノワールの記事では出さない
  // （年金生活者支援給付金の記事に証券会社が出ていた）。合う話題は scripts/a8_import.py の ACTION_ADS（life-*）で足す
  const matched = (o: Any) => (o && !String(o.topic ?? "").startsWith("fallback-") ? o : undefined);
  const inlineOffer = matched(ctx.inlineOffer);
  const offer = matched(ctx.offer);
  // お金と暮らしの記事だけ「編集責任者：名前」を出す（出すのは名前のみ。2026-11-10 オーナー承認）
  const editor = editorInCharge(article.genreSlug);
  const noirHtml = noirBodyHtml(bodyHtml, article);
  // 「次の記事」の枠は2つだけ（2026-11-11 読者目線レビュー 4位。以前は7つの枠に同じ記事が何度も出ていた）:
  //  ① 要点の下の「この話の続き」: 同じ話題で別の疑問に答える記事・次にやること（content/next_steps.json）・同じ話題の記事 を1つにまとめて最大3本（lib/story-reads.ts）
  //  ② 本文の直後の「よく読まれている記事」5本（components/PopularReads.tsx。PC は右の列に同じ一覧が付いてくるので本文の列には出さない）
  // 本文途中の「あわせて読みたい」・記事末の「次に読む記事」「関連記事」「この話題のページ」はやめる
  const steps = nextStepsFor(article.slug);
  const reads: { article: ArticleSummary; reason: string }[] = storyReads.length > 0 ? storyReads : nextReads;
  const all = getAllArticles();
  const stepReads = (steps?.next ?? []).flatMap((s) => {
    const a = all.find((x) => x.slug === s.slug);
    return a ? [{ article: a, reason: s.step }] : [];
  });
  const { parent: topicParent, pages: topicSiblings } = topicPages(article, all);
  const topicReads = [...(topicParent ? [{ article: topicParent, reason: "この話題の全体の解説" }] : []), ...topicSiblings.map((a) => ({ article: a, reason: "同じ話題で別の疑問に答える記事" }))];
  // 同じ話題で別の疑問に答える記事（SEO A17。元の記事 ⇄ 角度の記事）を先に2本、次にやることを1本、残りを順に
  const storyTop = mergeStoryReads(
    article,
    [topicReads.slice(0, 2), stepReads.slice(0, 1), topicReads.slice(2), stepReads.slice(1), reads, inlineRead ? [{ article: inlineRead, reason: "同じ話題の記事" }] : []],
    3,
  );
  const depth = depthOf(article);
  // 答えの表（早見表など）を要点のすぐ下へ（比較記事の表は提携先の一覧が直後に付くので動かさない。lib/answer-table.ts）
  const answer = compareInline ? null : extractAnswerTable(noirHtml);
  const [noirTop, noirAfterAd] = splitBeforeHeading(answer ? answer.rest : noirHtml, 3);
  const [noirMid, noirTail] = splitBeforeHeading(noirAfterAd, 4);
  const adReview = inAdReview();
  const noirInlineCta = !adReview && !actionAd && !inlineOffer && !shopLink && getCta(article.genreSlug, "inline") ? "inline" : undefined;
  const noirPrimaryCta = !adReview && !actionAd && !inlineOffer && !shopLink && !noirInlineCta && getCta(article.genreSlug, "primary") ? "primary" : undefined;
  const badge = sourceBadge(article);
  // 発表元の名前（写真の注記の団体名 → 企業名 → 発信元の名前）
  const org =
    article.imageCredit?.org ||
    (company.slug !== OTHER.slug ? company.name : "") ||
    // 「KDDI ニュースリリース」「NVIDIA公式ブログ」の発信元の名前から、ページの種類の言葉を外して団体の名前にする
    sourceName.replace(/\s*(?:公式)?(?:ニュースリリース|プレスリリース|ニュースルーム|お知らせ|ブログ|Newsroom|News|Blog)\s*$/i, "").trim() ||
    sourceName;
  // 題名の下の発表元は短く（「日本年金機構「老齢…の概要」（2026年10月1日更新）」→「日本年金機構」。2026-11-10 オーナー承認: 最初の画面を答えに使う）
  const orgShort = shortOrg(org);
  // 上の1行: 同じジャンルの新着（自分は除く）
  // 面会・式典などの読者がすることの無い発表は出さない。いちばん新しく載せた記事（2026-11-11 読者目線レビュー 11位: 年金の記事の上に財務大臣の面会が出ていた）
  const genreLatest = getAllArticles()
    .filter((a) => a.genreSlug === article.genreSlug && a.slug !== article.slug && !noReaderAction(a.title) && a.type !== "roundup" && !a.duplicate)
    .sort((x, y) => Date.parse(y.generatedAt || y.publishedAt) - Date.parse(x.generatedAt || x.publishedAt))[0];
  const noirJsonLd = jsonLd.map((entry, i) =>
    i === 0 ? { ...entry, speakable: { "@type": "SpeakableSpecification", cssSelector: [".nr-sum"] } } : entry,
  );
  const inlinePrBlock = inlineOffer ? (
    <>
      <RailRanking offer={inlineOffer} wide id="offer-inline" title={inlineOffer.headline} visible={2} />
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
        <RailRanking offer={offer} pos="ranking-end" countImpression={false} visible={2} />
      </div>,
    );
  // 比較記事の提携先の一覧（比較表の直後・記事の終わり）も本文の列の PR に数え、合わせて3つまでにする
  const compareCount = (compareInline ? 1 : 0) + (compareEnd ? 1 : 0);
  if (compareCount > 0) adBlocks.splice(Math.max(0, 3 - compareCount));
  // AdSense の審査の期間は1つだけ・本文の後ろ（lib/ad-review.ts）
  const [adEarly, adMidPr, adEnd] = adReview ? [null, null, adBlocks[0] ?? null] : adBlocks.slice(0, 3);
  // 比較記事への案内: 判断ガイドがあればその直後、無ければ「すぐにできること」の直後（速報の当日・地震津波の速報は記事の終わりだけ）
  const funnelMid = funnel?.placement === "both" ? <FunnelCard card={funnel} pos="mid" /> : null;

  return (
    <NoirArticle
      article={article}
      title={articleTitle(article)}
      jsonLd={noirJsonLd}
      cover={noirCover(article)}
      genre={article.genre}
      kicker={company.slug !== OTHER.slug ? company.name : ""}
      breaking={isFastNews(article)}
      origin={`${orgShort} ${badge}`}
      readMinutes={readMinutes}
      // 報道機関の記事は「公式発表」と呼ばない（台帳 W17）
      sourceCta={sourceUrl ? (badge === "報道" ? `${sourceName}の記事を読む` : `${orgShort}の発表を読む`) : null}
      sourceUrl={sourceUrl}
      body={{ top: noirTop, mid: noirMid, tail: noirTail }}
      compareSlot={compareInline}
      headingsHtml={headingTexts(noirHtml).join("")}
      calcSlot={calcInline ? calcBox : undefined}
      priceSlot={priceBox}
      crumbs={crumbs}
      related={[]}
      slots={{
        genreLine: <GenreLine genre={article.genre} item={genreLatest} />,
        // 要点のすぐ下（「すぐにできること」・1つ目の PR より上）に「自分は対象か確かめる」の1行（2026-11-10 M2。PR の数と位置は変えない）
        quick:
          moneyLink || quickList.length > 0 || (funnelMid && depth.guide.length === 0) ? (
            <>
              <MoneyCheckLink target={moneyLink} className="mb-6" />
              {quickList.length > 0 && <QuickActions actions={quickList} detailed={stepItems.length > 0} />}
              {depth.guide.length === 0 && funnelMid}
            </>
          ) : null,
        answer: answer ? (
          <section id={ANSWER_TABLE_ID} className="nr-answer" aria-labelledby="answer-table-heading">
            {/* 記事の章の見出しではないので h2 にしない（本文の同じ章の見出しは本文に残る） */}
            <p id="answer-table-heading" className="nr-answer-h">{answer.caption}</p>
            <div className="prose nr-prose" dangerouslySetInnerHTML={{ __html: answer.html }} />
          </section>
        ) : null,
        story: (
          <>
            <StoryLinks items={storyTop} />
            <FoldOpener />
          </>
        ),
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
        adMid: showAds ? <AdSlot position="article-middle" className="my-10" /> : null,
        adMidPr,
        // 本文の途中: 読者の迷い・不安に答える欄（判断ガイド・不安Q&A）
        midBoxes: (
          <>
            {/* 判断ガイドは見出しだけ出し、押すと開く（2026-11-10 オーナー承認。画面1〜2枚分あった） */}
            {depth.guide.length > 0 && (
              <Fold kicker="判断ガイド" title={depth.headings.guide || "迷ったときの判断ガイド"} note={`${depth.guide.length}つの迷いに、状況ごとのおすすめと理由`}>
                <DecisionGuide groups={depth.guide} heading={depth.headings.guide} />
              </Fold>
            )}
            {depth.guide.length > 0 && funnelMid}
            {/* 不安Q&A と「よくある質問」は1つの欄にまとめる（同じ問いが2回出ていた） */}
            {depth.worries.length >= 2 && <WorriesBlock items={depth.worries} heading={depth.headings.worries} extra={articleFaq} openCount={1} />}
          </>
        ),
        beforeTail: chooseGuide ? <ChooseGuideNote guide={chooseGuide} className="my-10" /> : null,
        betweenTail: readNextInline ? <ReadNextBox link={readNextInline} className="my-10" /> : null,
        afterBody: (
          <>
            {calc && !calcInline && <CalculatorBox calc={calc} className="mt-12" />}
            {/* 一歩深くする欄（scripts/depth_fields.py。公式ページで確かめた原因・手順・窓口・不安への答え。台帳 A66） */}
            {depth.cause && (
              <Fold kicker="なぜ起きた？" title={depth.headings.cause || "原因と背景"} note="公式ページが書く原因・背景">
                <CauseBox cause={depth.cause} heading={depth.headings.cause} />
              </Fold>
            )}
            {/* 手順つきの「すぐにできること」と公式窓口は、見出しだけ出して押すと開く（2026-11-10 オーナー承認）。
                要点の下の短い一覧と同じ項目が2回並んで見えていたため。一覧の「手順と公式の窓口を見る ↓」で飛ぶと開く（FoldOpener） */}
            {(stepItems.length > 0 || depth.officialDesk.length > 0) && (
              <Fold
                id="steps-fold"
                kicker={stepItems.length > 0 ? "手順と公式窓口" : "公式窓口"}
                title={stepItems.length > 0 ? "上の「すぐにできること」の手順と、困ったときの連絡先" : depth.headings.desk || "困ったときに連絡する先"}
                note={depth.officialDesk.length > 0 ? "SMSやメールの連絡先ではなく、公式の窓口を使ってください" : undefined}
              >
                {stepItems.length > 0 && <ActionSteps items={stepItems} heading={depth.headings.steps} />}
                {depth.officialDesk.length > 0 && <OfficialDesk items={depth.officialDesk} heading={depth.headings.desk} />}
              </Fold>
            )}
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
            {articleFaq.length >= 1 && depth.worries.length < 2 && <ArticleFaq items={articleFaq} />}
            {compareEnd}
          </>
        ),
        adEnd,
        // 本文の直後（出典のボタンの下）に「よく読まれている記事」5本（2026-11-11 読者目線レビュー 4位。以前はページのほぼ一番下）。
        // PC は右の列に同じ一覧が付いてくるので、本文の列はスマホ・タブレットだけ
        next: <PopularReads current={article.slug} className="lg:hidden" />,
        check: steps?.check ? <TargetCheck check={steps.check} /> : null,
        afterSource: (
          <>
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
            {/* 比較記事への案内は1回だけ（本文の途中に出したら、記事の終わりには出さない） */}
            {funnel && !funnelMid && <FunnelCard card={funnel} pos="end" className="mt-12" />}
            <div className="mt-12 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-y border-line py-4">
              <p className="text-note font-bold text-ink">この記事をシェアする</p>
              <ShareButtons url={`${siteConfig.url}/articles/${article.slug}`} title={articleTitle(article)} />
            </div>
            <ThreadsFollow />
          </>
        ),
        end: (
          <>
            {!noirTail && chooseGuide && <ChooseGuideNote guide={chooseGuide} className="mt-12" />}
            <NewsletterSignup variant="article" />
            <PushOptIn />
            {!noirTail && readNextInline && <ReadNextBox link={readNextInline} className="mt-12" />}
            {/* 同じ話題で別の疑問に答えるページ（SEO A17）は、要点の下の「この話の続き」にまとめた（2026-11-11） */}
            {/* 「この記事は「値上げ情報」に載っています」（今までの見た目と同じ。載っていなければ何も出さない。SEO A12） */}
            <TopicListMembership slug={article.slug} className="mt-12" />
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
            {/* よく読まれている記事は PC の右の列だけ（スマホは本文の直後に出す） */}
            <div className="hidden lg:block">
              <NoirPopular current={article.slug} />
            </div>
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
            {editor && (
              <span data-editor-in-charge>
                編集責任者：<Link href="/about">{editor.name}</Link>
              </span>
            )}
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
