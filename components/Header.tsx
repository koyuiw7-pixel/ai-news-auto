import Link from "next/link";
import { getAllChannels } from "@/lib/articles";
import { siteConfig } from "@/site.config";

export default function Header() {
  const channels = getAllChannels().slice(0, 6);

  return (
    <header className="sticky top-0 z-50 border-b border-ink-100 bg-ink-50/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <span className="grid size-8 place-items-center rounded-lg bg-accent text-sm font-black text-white">
            AI
          </span>
          <span className="text-lg font-bold tracking-tight text-ink-950">
            {siteConfig.shortName}
          </span>
        </Link>

        <nav className="hidden min-w-0 flex-1 items-center gap-1 overflow-x-auto md:flex">
          {channels.map((channel) => (
            <Link
              key={channel.slug}
              href={`/channels/${channel.slug}`}
              className="shrink-0 rounded-full px-3 py-1.5 text-sm font-medium text-ink-700 transition-colors hover:bg-accent-soft hover:text-accent"
            >
              {channel.label}
            </Link>
          ))}
        </nav>

        <Link
          href="/articles"
          className="ml-auto shrink-0 rounded-full bg-ink-950 px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-85"
        >
          記事一覧
        </Link>
      </div>
    </header>
  );
}
