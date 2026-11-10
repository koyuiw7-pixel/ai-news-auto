import Link from "next/link";
import RelTime from "@/components/RelTime";
import FreshBadge from "@/components/FreshBadge";
import { PushBell } from "@/components/PushOptIn";
import { displayHeadline } from "@/lib/headline";
import type { ArticleSummary } from "@/lib/articles";

/**
 * ノワールの記事の上の1行: 同じジャンルの新着1本（2026-11-10 オーナー承認）。
 * サイト共通の速報の1行（components/LiveLine.tsx。いちばん新しい AI の記事）は、暮らし・お金の記事を読みに来た人には関係が薄いので、
 * ノワールの記事ではそれを隠して（components/noir/noir.css の html:has(.noir) .live-line）、同じ高さのこの1行を出す（画面がずれない）。
 */
export default function GenreLine({ genre, item }: { genre: string; item?: ArticleSummary }) {
  if (!item) return null;
  const postedAt = item.generatedAt || item.publishedAt;
  return (
    <div className="nr-genreline border-b border-line bg-surface" data-genre-strip="" aria-label={`${genre}の新着`} role="region">
      <div className="mx-auto flex h-9 max-w-[1240px] items-center gap-2.5 px-4 text-meta sm:px-8">
        {/* 札は載せてから24時間以内だけ。時刻は載せた時刻（一覧・記事の「公開」と同じ。2026-11-11 読者目線レビュー 11位） */}
        <FreshBadge iso={postedAt} renderedAt={Date.now()} className="shrink-0 rounded-sm bg-accent px-1.5 py-[1px] text-badge font-bold tracking-[0.06em] text-accent-ink" />
        <RelTime iso={postedAt} className="index-num shrink-0 text-muted" />
        <Link href={`/articles/${item.slug}`} className="min-w-0 truncate font-bold text-ink underline-offset-[3px] hover:underline">
          {displayHeadline(item.title)}
        </Link>
        <PushBell />
      </div>
    </div>
  );
}
