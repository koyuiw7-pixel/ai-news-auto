import Link from "next/link";
import { displayHeadline } from "@/lib/headline";
import type { NextRead } from "@/lib/articles";

/**
 * 「この話の続き」: 同じ話題の記事を2本、要点と「すぐにできること」のすぐ下に、文字だけで小さく出す（2026-11-10 オーナー承認）。
 * 11/9 は1訪問あたり約1.04ページで、「次に読む記事」が画面16〜24枚目にあり、ほとんどの人が見ないまま帰っていた。
 * 題名と、なぜ続きなのか（同じ話題・同じ企業）だけ。写真は出さない（答えを押し下げないため）。
 * 押した場所は components/ReadingBeacon.tsx が "story" として数える（data-read-zone）。
 */
export default function StoryLinks({ items, heading = "この話の続き" }: { items: NextRead[]; heading?: string }) {
  if (items.length === 0) return null;
  return (
    <nav aria-labelledby="story-links-heading" data-read-zone="story" className="nr-story mb-8 max-w-[40em] border-y border-line py-3">
      {/* 記事の外側の欄の見出しは h2 にしない（SEO A20） */}
      <p id="story-links-heading" className="text-badge font-bold tracking-wide text-accent">
        {heading}
      </p>
      <ul className="mt-1 divide-y divide-line">
        {items.map(({ article, reason }) => (
          <li key={article.slug}>
            <Link href={`/articles/${article.slug}`} className="group block py-2.5">
              <span className="block min-w-0">
                <span className="block text-desc font-bold leading-snug text-ink group-hover:underline">{displayHeadline(article.title)}</span>
                <span className="mt-0.5 block text-meta text-muted">{reason}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
