import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { getAllGenres } from "@/lib/articles";
import { siteConfig } from "@/site.config";

export default function Header() {
  const genres = getAllGenres();

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-paper/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1240px] items-center gap-6 px-5 sm:px-8">
        <Link href="/" className="group flex shrink-0 items-baseline gap-2.5">
          <span className="block h-4 w-1 bg-accent" aria-hidden />
          <span className="font-serif text-[1.15rem] font-bold tracking-tight text-ink">
            {siteConfig.shortName}
          </span>
        </Link>

        <nav className="hidden min-w-0 flex-1 items-center gap-6 md:flex">
          {genres.map((genre) => (
            <Link
              key={genre.slug}
              href={`/genres/${genre.slug}`}
              className="shrink-0 border-b-2 border-transparent pb-0.5 text-sm font-semibold text-muted transition-colors hover:border-accent hover:text-ink"
            >
              {genre.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-2.5">
          <Link
            href="/articles"
            className="hidden text-sm font-semibold text-muted transition-colors hover:text-ink sm:block"
          >
            記事一覧
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
