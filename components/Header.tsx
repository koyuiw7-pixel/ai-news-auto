import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { siteConfig } from "@/site.config";

// 上のメニューは5つまでに絞る（企業別はトップの企業チップから、まとめは記事一覧から辿れる）
const NAV: { href: string; label: string; wide?: boolean }[] = [
  { href: "/", label: "AI速報" },
  { href: "/usable", label: "使えるAI" },
  { href: "/news", label: "ニュース" },
  { href: "/products", label: "製品まとめ" },
  { href: "/articles", label: "記事一覧" },
];

export default function Header() {
  return (
    <header className="site-header sticky top-0 z-50 border-b border-line">
      <div className="mx-auto flex h-16 max-w-[1240px] items-center gap-6 px-5 sm:px-8">
        <Link href="/" className="flex shrink-0 items-baseline gap-3">
          <span className="font-display text-[1.4rem] leading-none text-ink">
            {siteConfig.shortName}
          </span>
          <span className="hidden text-[11.5px] font-bold text-muted sm:inline md:hidden lg:inline">
            {siteConfig.tagline}
          </span>
        </Link>

        <nav
          aria-label="メインメニュー"
          className="ml-auto hidden items-center gap-4 md:flex lg:gap-6"
        >
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`whitespace-nowrap text-sm font-bold text-ink-soft transition-colors hover:text-accent ${item.wide ? "hidden lg:inline" : ""}`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-1 md:ml-0">
          {/* スマホではメニューを畳んでいるので、AI以外の話題への入口だけ出す */}
          <Link
            href="/news"
            className="rounded-full border border-line px-3 py-1 text-[12.5px] font-bold text-ink-soft transition-colors hover:border-ink hover:text-ink md:hidden"
          >
            ニュース
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
