import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { siteConfig } from "@/site.config";

const NAV = [
  { href: "/", label: "新着" },
  { href: "/companies/openai", label: "OpenAI" },
  { href: "/companies/google", label: "Google" },
  { href: "/companies/anthropic", label: "Anthropic" },
  { href: "/guides", label: "ガイド" },
  { href: "/#roundups", label: "まとめ" },
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
          <span className="hidden text-[11.5px] font-bold text-muted sm:inline">
            {siteConfig.tagline}
          </span>
        </Link>

        <nav
          aria-label="メインメニュー"
          className="ml-auto hidden items-center gap-6 md:flex"
        >
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm font-bold text-ink-soft transition-colors hover:text-accent"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex shrink-0 items-center md:ml-0">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
