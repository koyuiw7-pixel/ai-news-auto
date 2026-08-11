import Link from "next/link";
import { formatDate, type Article } from "@/lib/articles";

/**
 * 横断まとめ記事の専用枠。
 * まとめ記事は複数動画を統合した唯一の独自コンテンツなので、
 * 通常記事と同列に時系列で埋もれさせず、ハブとして目立たせる。
 */
export default function RoundupShelf({ roundups }: { roundups: Article[] }) {
  if (roundups.length === 0) return null;

  return (
    <section className="mt-16 border-y-2 border-ink py-10">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">DEEP DIVE</p>
          <h2 className="display mt-1 text-xl sm:text-2xl">
            話題まるごと解説
          </h2>
          <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-muted">
            同じ話題を扱った複数の動画を横断して統合した記事です。
            個々の発表では見えない全体像と、発表どうしの食い違いまで整理しています。
          </p>
        </div>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {roundups.slice(0, 4).map((roundup) => (
          <Link
            key={roundup.slug}
            href={`/articles/${roundup.slug}`}
            className="group flex flex-col justify-between rounded-2xl border border-line bg-surface p-6 transition-colors hover:border-accent"
          >
            <div>
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="bg-ink px-2 py-0.5 font-bold tracking-widest text-paper">
                  まとめ
                </span>
                <span className="font-semibold text-accent">{roundup.genre}</span>
                <span className="index-num text-muted">
                  {formatDate(roundup.generatedAt)}
                </span>
              </div>

              <h3 className="mt-3 font-serif text-[1.0625rem] font-bold leading-[1.6] text-ink transition-colors group-hover:text-accent">
                {roundup.title}
              </h3>

              <p className="mt-2.5 line-clamp-3 text-[13px] leading-relaxed text-muted">
                {roundup.lede || roundup.description}
              </p>
            </div>

            <p className="mt-4 flex items-center gap-2 text-[12px] font-semibold text-accent">
              <span className="index-num">
                {roundup.sources?.length ?? 0}本の記事を統合
              </span>
              <span aria-hidden>→</span>
            </p>
          </Link>
        ))}
      </div>
    </section>
  );
}
