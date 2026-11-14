import Link from "next/link";
import type { ArticleSummary } from "@/lib/articles";
import { displayHeadline } from "@/lib/headline";
import { STRIP_VISIBLE } from "@/lib/home-lead";

const clock = new Intl.DateTimeFormat("ja-JP", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Tokyo" });
const monthDay = new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", timeZone: "Asia/Tokyo" });
const jstDay = (time: number) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo" }).format(time);

/**
 * トップの「いま話題」の欄（2026-11-13 オーナー「Googleからの流入対策をもっと」）。
 * 話題の記事（話題のレーン・Muse に頼んだ記事。載せて24時間以内）を、時刻つきの見出しで新しい順に1記事1行で並べる。
 * 見た目は上の見出しの欄（components/HomeHeadlines.tsx）と同じ細い線・太字。時刻はサイソクに載った時刻（components/Timeline.tsx と同じ）。
 * 最初の STRIP_VISIBLE 本はそのまま、残りは「ほか◯本を見る」の中（details。リンクは最初から HTML にあり、画面の動きも無い）。
 * 記事は lib/home-lead.ts の pickTrendingStrip
 */
export default function HomeTrendingStrip({ articles }: { articles: ArticleSummary[] }) {
  if (articles.length === 0) return null;
  const postedAt = (a: ArticleSummary) => Date.parse(a.generatedAt || a.publishedAt);
  const newestDay = jstDay(postedAt(articles[0]));
  const head = articles.slice(0, STRIP_VISIBLE);
  const rest = articles.slice(STRIP_VISIBLE);
  const rows = (items: ArticleSummary[]) => (
    <ul className="sm:grid sm:grid-cols-2 sm:gap-x-8">
      {items.map((article) => {
        const at = postedAt(article);
        return (
          <li key={article.slug} className="border-b border-line">
            <Link href={`/articles/${article.slug}`} className="group grid grid-cols-[3.25em_minmax(0,1fr)] items-baseline gap-2 py-2.5 sm:py-3">
              <time dateTime={new Date(at).toISOString()} className="index-num whitespace-nowrap text-meta text-muted">
                {jstDay(at) === newestDay ? clock.format(at) : monthDay.format(at)}
              </time>
              <span className="line-clamp-2 text-[15px] font-bold leading-[1.5] text-ink underline-offset-4 group-hover:underline">
                {displayHeadline(article.title)}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
  return (
    <section aria-labelledby="trending-strip-heading" data-home-zone="trending" className="mt-6 sm:mt-10">
      <h2 id="trending-strip-heading" className="flex items-center gap-2 text-[1.25rem] font-bold leading-[1.4] text-ink">
        <span aria-hidden className="h-5 w-[3px] rounded-full bg-live" />
        いま話題
        <span className="index-num text-meta font-normal text-muted">この24時間の{articles.length}本</span>
      </h2>
      <div className="mt-1 sm:mt-3">{rows(head)}</div>
      {rest.length > 0 && (
        <details>
          <summary className="cursor-pointer list-none py-3 text-note font-bold text-accent underline-offset-4 hover:underline [&::-webkit-details-marker]:hidden">
            ほか{rest.length}本を見る
          </summary>
          {rows(rest)}
        </details>
      )}
    </section>
  );
}
