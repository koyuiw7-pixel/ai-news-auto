import Link from "next/link";
import GenreTabs from "@/components/HeaderNav";
import LiveLine from "@/components/LiveLine";
import ThemeToggle from "@/components/ThemeToggle";
import { getAllArticles, type ArticleSummary } from "@/lib/articles";
import { isLifeMoneyStory, pickHomeLead } from "@/lib/home-lead";
import { isFastNews } from "@/lib/cover-path";
import { displayHeadline } from "@/lib/headline";
import { genreNav, MONEY_NAV, UTILITY_NAV } from "@/lib/nav";
import { siteConfig } from "@/site.config";

/** 虫めがねの線画（検索の入口） */
function SearchIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.5 15.5 5 5" />
    </svg>
  );
}

/**
 * 濃紺の帯（ロゴ・検索・定番ページ）と、その下のジャンルのタブ、速報の1行。
 * 帯だけ画面上に残し、タブと速報の1行はスクロールで流す（スマホで本文を押し下げすぎないため）。
 * 検索窓はただのフォーム（/search?q=…）なので、JS を読まなくても動く。
 */
export default function Header() {
  // いちばん新しく載せた暮らしとお金の記事（2026-11-11 読者目線レビュー 11位: 帯が AI の記事で、日付も下の一覧と食い違っていた）。
  // 面会・式典などの発表は出さない（lib/home-lead.ts の isLifeMoneyStory）。並びと時刻は載せた時刻（下の一覧・記事の「公開」と同じ）
  const all = getAllArticles();
  const postedAt = (a: ArticleSummary) => a.generatedAt || a.publishedAt;
  const [latest, second, third] = all
    .filter((a) => isLifeMoneyStory(a) && a.type !== "roundup" && !a.duplicate)
    .sort((x, y) => Date.parse(postedAt(y)) - Date.parse(postedAt(x)))
    .slice(0, 3);
  // トップでは主役の記事と重ならないものを出す（LiveLine が切り替える）
  const lead = pickHomeLead(all)?.slug;
  // 描いた時刻（静的ページの「速報／最新」の札の初期値。表示後に閲覧時刻で当て直す。components/LiveLine.tsx）
  const renderedAt = Date.now();

  return (
    <>
      <header className="site-header sticky top-0 z-50">
        <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-6 px-4 sm:px-8">
          <Link href="/" className="flex shrink-0 items-baseline gap-3">
            <span className="font-display text-[1.35rem] leading-none text-mast-ink">{siteConfig.shortName}</span>
            <span className="hidden text-meta font-bold text-mast-muted sm:inline md:hidden xl:inline">{siteConfig.tagline}</span>
          </Link>

          <nav aria-label="暮らしとお金の入口" className="ml-auto hidden items-center gap-4 lg:flex xl:gap-5">
            {UTILITY_NAV.map((item) => (
              <Link key={item.href} href={item.href} className="whitespace-nowrap text-meta font-bold text-mast-muted transition-colors hover:text-mast-ink">
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex shrink-0 items-center gap-1.5 lg:ml-0">
            <form action="/search" method="get" role="search" className="hidden md:block">
              <label className="flex h-9 w-56 items-center gap-2 rounded-md border border-white/25 bg-white/10 px-2.5 text-mast-muted focus-within:border-white focus-within:text-mast-ink">
                <SearchIcon className="size-4 shrink-0" />
                <span className="sr-only">記事を検索</span>
                <input
                  type="search"
                  name="q"
                  placeholder="記事を検索（例：NISA）"
                  enterKeyHint="search"
                  className="min-w-0 flex-1 bg-transparent text-note text-mast-ink outline-none placeholder:text-mast-muted"
                />
              </label>
            </form>
            <Link
              href="/search"
              aria-label="記事を検索"
              className="grid size-10 place-items-center rounded-md text-mast-ink transition-colors hover:bg-white/10 md:hidden"
            >
              <SearchIcon className="size-[22px]" />
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <GenreTabs items={genreNav()} lead={MONEY_NAV} />

      {latest && (
        <LiveLine
          renderedAt={renderedAt}
          skipOnHome={lead}
          items={[latest, second, third].filter((a): a is ArticleSummary => Boolean(a)).map((a) => ({
            slug: a.slug,
            title: displayHeadline(a.title),
            publishedAt: postedAt(a),
            // 赤い「速報」は本当の速報だけ（画像の札と同じ判定。台帳 A9・W23）
            fast: isFastNews(a),
          }))}
        />
      )}
    </>
  );
}
