import { articleTitle } from "@/lib/headline";
import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import HomeHero from "@/components/HomeHero";
import HomeHeadlines from "@/components/HomeHeadlines";
import HomeTrendingStrip from "@/components/HomeTrendingStrip";
import HomeAssets from "@/components/HomeAssets";
import CompanyChips from "@/components/CompanyChips";
import NewsHub from "@/components/NewsHub";
import Thumb from "@/components/Thumb";
import { smallThumb } from "@/lib/thumb-url";
import Timeline from "@/components/Timeline";
import RailRanking from "@/components/rail/RailRanking";
import StoryRail from "@/components/story/SwipeDeck";
import { getStoryRailBundles } from "@/lib/stories";
import { fallbackOfferForArticle, homeSectionOffer, offerForArticle } from "@/lib/offers";
import { getAllArticles, getAllGenres, tagSlug, type ArticleSummary } from "@/lib/articles";
import { companyCounts, thumbSource } from "@/lib/companies";
import { broadGenresWithArticles, getBroadArticles, isBroadGenre } from "@/lib/sections";
import type { Metadata } from "next";
import { siteConfig } from "@/site.config";
import { pageShareImage } from "@/lib/page-share";
import { coverPath } from "@/lib/cover-path";
import { containPhoto } from "@/lib/photo-fit";
import { isLifeMoneyStory, pickHomeHeadlines, pickHomeLead, pickLifeMoney, pickTrendingStrip, STRIP_VISIBLE, viewsOf } from "@/lib/home-lead";
import { alsoCoveredSentence } from "@/lib/coverage";
import { guideShortName, lifeCompareGuide, type LifeCompareSlug } from "@/lib/buying-guides";

export const revalidate = false;

// トップだけ og:url を自分（＝サイトのURL）にする。下層ページに引き継がせないため layout には置かない
export const metadata: Metadata = {
  openGraph: {
    type: "website",
    siteName: siteConfig.siteName,
    locale: siteConfig.locale,
    url: siteConfig.url,
    title: `${siteConfig.siteName} 暮らしとお金の新しい動きが最速でわかる`,
    description: siteConfig.description,
    // トップのシェア画像（SEO A15。lib/page-share.ts）
    images: [{ url: pageShareImage("home"), width: 1200, height: 630, alt: siteConfig.siteName }],
  },
  twitter: { card: "summary_large_image", images: [pageShareImage("home")] },
};

// AI・テクノロジーは脇役なので5本だけ（残りは「もっと見る」。2026-11-11 読者目線レビュー 1位）
const TIMELINE_SIZE = 5;

/**
 * トップの「お金の計算と比較」の入口（2026-11-10 M6）。10〜12月（日本時間）は、その年の12月31日までの寄附が対象になるふるさと納税の
 * 上限額の計算とサイトの比較を先にする。それ以外の月は電気・ガスの比較を先にする。光回線の比較はいつも出す。
 * 行き先は実在するページだけ（比較ページは lib/buying-guides.ts の LIFE_COMPARE_SLUGS）
 */
function homeMoneyLinks(now = new Date()): { main: { href: string; label: string }; compare: { href: string; label: string }[] } {
  const month = new Date(now.getTime() + 9 * 60 * 60 * 1000).getUTCMonth() + 1;
  const furusatoSeason = month >= 10;
  const compare = (slug: LifeCompareSlug) => {
    const found = lifeCompareGuide(slug);
    return found ? [{ href: found.href, label: `${guideShortName(found.guide)}の比較` }] : [];
  };
  if (furusatoSeason) {
    return { main: { href: "/tools/furusato-limit", label: "ふるさと納税はいくらまで？上限額を計算する" }, compare: [...compare("furusato-sites"), ...compare("hikari")] };
  }
  const [first, ...rest] = [...compare("denki-gas"), ...compare("hikari"), ...compare("kakuyasu-sim")];
  return { main: first ?? { href: "/tools/furusato-limit", label: "ふるさと納税の上限額を計算する" }, compare: rest };
}
const NEWS_SIZE = 8;

/**
 * トップ＝サイトの玄関（2026-11-10 オーナー「ホームは玄関だから魅力感じてもらわないと」）。
 * 上から、主役（暮らしとお金の、読まれている・新しい・写真のある記事）→ 暮らしとお金の主な見出し（文字だけ）→ ストーリーの丸（暮らしとお金が先）→
 * PR 枠（home-top）→ 暮らしとお金のニュース（写真のある記事だけ）→ 使い方・調べられること → PR 枠（home-mid）→ AI・テクノロジーの新着（企業の絞り込みつき）。
 * PR はトップに2つまで。最初の画面・主役より上には置かない。2つが1つの画面に同時に見えないよう、間に1画面分以上の記事を挟む
 * （2026-11-10 オーナー承認・チーム（Claude・Muse・Grok）の合意）。
 * AI の速報はヘッダー下の帯と AI の新着で見える。写真の無い記事は大きな写真の枠に置かない
 */
export default function HomePage() {
  const all = getAllArticles();
  if (all.length === 0) return <EmptyState />;
  const ai = all.filter((a) => a.genreSlug === "ai");

  // 主役は暮らしとお金の記事から、読まれている・新しい・写真のあるものを選ぶ（2026-11-10 オーナー「ホームは玄関」。lib/home-lead.ts）。
  // 公式の発表から選ぶ（報道をもとにした記事を主役にしない。台帳 W17）・写真の無い記事は主役にしない
  const lead = pickHomeLead(all) ?? all[0];
  // 主役のすぐ下は暮らしとお金の列（写真のある記事だけ）。AI の新着はその下（AI は脇役。台帳 A61）
  // スマホの最初の画面に、暮らしとお金の見出しを文字だけで並べる（2026-11-11 読者目線レビュー 2位。Yahoo!ニュースは最初の画面に6本）
  const headlines = pickHomeHeadlines(all, new Set([lead.slug]), 6);
  // 「いま話題」の欄（話題の記事を1記事1行で全部。上の主役・見出しに出た記事は二重に並べない。lib/home-lead.ts の pickTrendingStrip）
  const trendingStrip = pickTrendingStrip(all, new Set([lead.slug, ...headlines.map((a) => a.slug)]));
  // 写真の列には、「いま話題」の最初から見えている記事を重ねて出さない（トップからたどれる記事を増やす）
  const lifeMoney = pickLifeMoney(all, new Set([lead.slug, ...headlines.map((a) => a.slug), ...trendingStrip.slice(0, STRIP_VISIBLE).map((a) => a.slug)]), NEWS_SIZE);
  const timeline = ai.filter((a) => a.slug !== lead.slug).slice(0, TIMELINE_SIZE);
  const roundups = ai.filter((a) => a.type === "roundup" && a.slug !== lead.slug).slice(0, 5);

  // トップにもPR枠。いちばん新しい話題に合う商品を出す。主役の話題に合う商品が無いときは、最初の画面に並ぶ見出し・暮らしとお金の列の
  // 記事の順で、話題が合う最初の記事の商品を出す（2026-11-12: 主役が日産とキリンの共創の記事の日に上の枠が消え、トップの PR が1つになった）。
  // どれにも合わなければ汎用の枠（lib/offers.ts の fallbackOfferForArticle）
  const matched = [lead, ...headlines, ...lifeMoney].reduce<ReturnType<typeof offerForArticle>>(
    (got, article) => got ?? offerForArticle(article, 9),
    undefined,
  );
  const fallback = matched ? undefined : fallbackOfferForArticle(lead, 9);
  const offer = matched ? { ...matched, eyebrow: "今日の話題に合わせて" } : fallback;
  // 暮らしとお金の列の下の PR 枠。列に並ぶ記事の話題（流出ならセキュリティ、電気・暖房なら電気の見直し）で選び、上の枠の商品は出さない（lib/offers.ts の homeSectionOffer）
  // 上の枠と同じ話題（主役も列も流出のときのセキュリティなど）は後回しにして、列で次に多い話題を出す
  const midOffer = homeSectionOffer(
    lifeMoney,
    offer?.items.map((item) => item.key) ?? [],
    offer ? [...new Set(offer.items.map((item) => item.topic ?? offer.topic))] : [],
  );

  const companies = companyCounts(ai);
  const tags = topTags(ai, 14);
  // 暮らしとお金の列の下の話題の絞り込み（/genres/<slug>）
  const broadGenres = broadGenresWithArticles(getBroadArticles());
  // 以前扱っていた分野（不動産・投資など）。幅広い話題は「ニュース」側に出すので除く
  const otherGenres = getAllGenres().filter((g) => g.slug !== "ai" && !isBroadGenre(g.slug));

  const bundles = getStoryRailBundles();
  const homeMoney = homeMoneyLinks();

  return (
    <>
      {/* ページの主見出し（検索エンジンと読み上げ用。見た目はロゴと主役の記事が担う） */}
      <h1 className="sr-only">{siteConfig.siteName} 暮らしとお金の新しい動きが最速でわかる</h1>
      <div className="mx-auto max-w-[1240px] px-5 pb-8 pt-4 sm:px-8 sm:pt-10">
        <HomeHero lead={lead} popular={viewsOf(lead.slug) > 0} />
        {/* 話題の記事（分野を問わない。lib/home-lead.ts の pickTrending）が後ろに並ぶ日は、見出しの名前も合わせる */}
        <HomeHeadlines articles={headlines} label={headlines.some((a) => !isLifeMoneyStory(a)) ? "暮らしとお金・いま話題のニュース" : undefined} />
        <HomeTrendingStrip articles={trendingStrip} />

        {/* ストーリーの丸は見出しの下（暮らしとお金の丸が先。lib/stories.ts。2026-11-11 読者目線レビュー 1位・2位） */}
        {bundles.length > 0 && (
          <div className="-mx-5 mt-4 sm:-mx-8 sm:mt-8">
            <StoryRail bundles={bundles} />
          </div>
        )}

        {offer && (
          // PC の最初の画面に入らないよう、主役との間を少し広く取る（1440×900 で枠の上端が画面の下端より下）
          <div className="mt-12 lg:mt-16">
            <RailRanking offer={offer} wide title={offer.headline} pos="home-top" />
          </div>
        )}

        <NewsHub articles={lifeMoney} genres={broadGenres} />

        {/* お金のページへの入口（計算・比較。サイト内リンクで広告ではない。2026-11-10 M6）。AI の使い方ガイドはその下の行 */}
        <nav aria-label="お金の計算と比較、AIの使い方" data-funnel-pos="home-guides" className="mt-10 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-y border-line py-4">
          <Link href={homeMoney.main.href} data-money-link="" className="text-[16px] font-bold leading-relaxed text-ink underline-offset-4 hover:text-accent hover:underline">
            {homeMoney.main.label} →
          </Link>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {homeMoney.compare.map((link) => (
              <Link key={link.href} href={link.href} data-money-link="" className="text-note font-semibold text-accent underline underline-offset-4">
                {link.label}
              </Link>
            ))}
          </div>
          <div className="mt-2 flex w-full flex-wrap gap-x-6 gap-y-2">
            <Link href="/guides" className="text-note font-semibold text-ink-soft underline decoration-line-strong underline-offset-4 hover:text-accent">
              AIの使い方ガイド一覧
            </Link>
            <Link href="/guides/dify-free-api-cost" className="text-note font-semibold text-ink-soft underline decoration-line-strong underline-offset-4 hover:text-accent">
              Difyは無料？200クレジットとAPI料金を確認
            </Link>
            <Link href="/guides/dify-1-18-startup-check" className="text-note font-semibold text-ink-soft underline decoration-line-strong underline-offset-4 hover:text-accent">
              Dify 1.18.0が起動しないときの確認手順
            </Link>
          </div>
        </nav>

        <HomeAssets />

        {/* 2つ目の PR 枠（home-mid）。上の枠とは暮らしとお金の列・使い方の欄を挟み、同じ画面に2つ並ばない */}
        {midOffer && (
          <div className="mt-12">
            <RailRanking offer={midOffer} wide title={midOffer.headline} pos="home-mid" />
          </div>
        )}

        {/* AI・テクノロジーは暮らしとお金の下（AI は脇役。台帳 A61）。企業での絞り込みもここに置く */}
        <div className="-mx-5 mt-14 border-t border-line sm:-mx-8">
          <CompanyChips companies={companies.slice(0, 8)} />
        </div>
        <div className="mt-8 grid gap-14 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-12">
          <section aria-labelledby="latest-heading" className="min-w-0">
            <div className="mb-2 flex items-end justify-between gap-4">
              <h2 id="latest-heading" className="t-h2">
                AI・テクノロジーの新着
              </h2>
              <Link href="/articles" className="pb-1 text-meta font-bold text-muted hover:text-ink">
                すべての記事 →
              </Link>
            </div>
            <Timeline articles={timeline} />
            <Link
              href="/articles"
              className="mt-8 flex items-center justify-center rounded-full border border-line-strong py-3 text-note font-bold text-ink transition-colors hover:border-ink"
            >
              もっと見る
            </Link>
          </section>

          {/* スマホでは出さない（AI の企業・トピックの一覧が画面何枚分も続き、暮らしとお金のサイトに見えなかった。2026-11-11 読者目線レビュー 1位） */}
          <aside className="hidden content-start gap-12 lg:sticky lg:top-24 lg:grid">
            {roundups.length > 0 && (
              <section aria-labelledby="roundups-heading" id="roundups">
                <RailHead id="roundups-heading" title="話題まるごと解説" note="同じ話題の発表を1本に" />
                <ol className="grid gap-4">
                  {roundups.map((roundup) => (
                    <RailRoundup key={roundup.slug} article={roundup} />
                  ))}
                </ol>
              </section>
            )}

            <section aria-labelledby="companies-heading">
              <RailHead id="companies-heading" title="企業から探す" />
              <ul className="grid grid-cols-2 gap-2">
                {companies.map(({ company, count }) => (
                  <li key={company.slug}>
                    <Link
                      href={`/companies/${company.slug}`}
                      className="flex h-full items-center gap-1.5 rounded-xl border border-line px-2.5 py-2.5 text-meta font-bold text-ink transition-colors hover:border-ink"
                    >
                      <CompanyMark company={company} size={18} />
                      {/* 狭い右の列で「Huggin…」「Anthro…」と切れていたので、切らずに2行まで折り返す（2026-11-03 の画面の点検） */}
                      <span className="line-clamp-2 min-w-0 leading-tight [overflow-wrap:anywhere]">{company.name}</span>
                      <span className="index-num ml-auto pl-0.5 text-meta font-normal text-muted">{count}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>

            {tags.length > 0 && (
              <section aria-labelledby="topics-heading">
                <RailHead id="topics-heading" title="トピック" />
                <div className="flex flex-wrap gap-1.5">
                  {tags.map(([slug, tag]) => (
                    <Link
                      key={slug}
                      href={`/tags/${encodeURIComponent(slug)}`}
                      className="rounded-md bg-surface px-3 py-1.5 text-meta font-medium text-ink-soft transition-colors hover:bg-surface-2 hover:text-ink"
                    >
                      {tag.label}
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </aside>
        </div>

        <footer className="mt-20 grid gap-3 border-t border-line pt-8">
          <p className="max-w-[70ch] text-desc leading-relaxed text-ink-soft">
            <strong>{siteConfig.siteName}（{siteConfig.nickname}）</strong>は、暮らしとお金の「自分ごと」ニュースを公式発表から最速で伝えるニュースメディアです。要点を3行で整理し、自分は対象か、いくらか、何をすればいいかまで書きます。AIは、暮らしと仕事での使い方の目線で扱います。{alsoCoveredSentence()}
          </p>
          <p className="flex flex-wrap gap-x-6 gap-y-2 text-note leading-relaxed text-ink-soft">
            <Link href="/about" className="underline decoration-line-strong underline-offset-4 hover:text-accent">サイソクについて・運営者情報</Link>
            <Link href="/editorial-policy" className="underline decoration-line-strong underline-offset-4 hover:text-accent">編集方針・AI利用と事実確認</Link>
            <Link href="/corrections" className="underline decoration-line-strong underline-offset-4 hover:text-accent">訂正履歴</Link>
          </p>
          {otherGenres.length > 0 && (
            <p className="text-meta text-muted">
              そのほかの分野：
              {otherGenres.map((genre, index) => (
                <span key={genre.slug}>
                  {index > 0 && "、"}
                  <Link href={`/genres/${genre.slug}`} className="underline underline-offset-4 hover:text-ink">
                    {genre.label}
                  </Link>
                </span>
              ))}
            </p>
          )}
        </footer>
      </div>
    </>
  );
}

function topTags(articles: ArticleSummary[], limit: number) {
  const counts = new Map<string, { label: string; count: number }>();
  for (const article of articles) {
    for (const tag of article.tags) {
      const slug = tagSlug(tag);
      const entry = counts.get(slug);
      if (entry) entry.count += 1;
      else counts.set(slug, { label: tag, count: 1 });
    }
  }
  return [...counts.entries()].sort((a, b) => b[1].count - a[1].count).slice(0, limit);
}

function RailHead({ id, title, note }: { id: string; title: string; note?: string }) {
  return (
    <div className="mb-4 border-b border-ink pb-2">
      <h2 id={id} className="t-h3">
        {title}
      </h2>
      {note && <p className="mt-0.5 text-meta text-muted">{note}</p>}
    </div>
  );
}

function RailRoundup({ article }: { article: ArticleSummary }) {
  return (
    <li>
      <Link href={`/articles/${article.slug}`} className="group grid grid-cols-[88px_minmax(0,1fr)] gap-3">
        <span className="relative aspect-video overflow-hidden rounded-lg bg-surface-2">
          <Thumb src={smallThumb(article.photo?.src ?? article.thumbnail, "mqdefault")} source={thumbSource(article)} cover={coverPath(article)} aiGenerated={article.photo ? Boolean(article.photo.ai) : article.imageCredit?.kind === "ai"} pos={article.photo?.pos} contain={containPhoto(article.photo)} alt="" fill sizes="88px" className="object-cover" />
          <span className="index-num absolute bottom-1 left-1 rounded bg-ink/85 px-1.5 py-[1px] text-badge font-semibold text-paper">
            {article.sourceCount}本
          </span>
        </span>
        <span className="line-clamp-3 text-[15px] font-bold leading-[1.55] text-ink group-hover:underline">
          {articleTitle(article)}
        </span>
      </Link>
    </li>
  );
}

function EmptyState() {
  return (
    <div className="mx-auto max-w-2xl px-5 py-32 text-center">
      <p className="eyebrow">NO ARTICLES YET</p>
      <p className="display mt-3 text-2xl">記事はまだありません</p>
      <p className="mt-4 text-desc leading-relaxed text-ink-soft">
        GitHub Actions が6時間ごとに新着動画を解析して、自動で記事を追加します。
      </p>
    </div>
  );
}
