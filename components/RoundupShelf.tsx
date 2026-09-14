import Thumb from "@/components/Thumb";
import Link from "next/link";
import { formatDate, type Article } from "@/lib/articles";
import { Highlight } from "@/lib/highlight";

/**
 * 横断まとめ記事の一覧。
 * 「何本を統合したか」はこのサイトにしかない価値なので、写真に載せた黒いバッジで示す。
 * 大きな色付き数字と見出しの強調が競合しないよう、強調は写真側に寄せている。
 */
export default function RoundupShelf({ roundups }: { roundups: Article[] }) {
  if (roundups.length === 0) return null;

  return (
    <section id="roundups" className="scroll-mt-24">
      <div className="mb-2 flex flex-wrap items-end justify-between gap-3 border-b border-line-strong pb-3">
        <div>
          <p className="eyebrow">DEEP DIVE</p>
          <h2 className="display mt-1 text-2xl sm:text-[1.75rem]">話題まるごと解説</h2>
        </div>
        <p className="max-w-md text-[14px] leading-[1.75] text-ink-soft">
          同じ話題の発表を横断して、1本にまとめた記事です。
        </p>
      </div>

      <div className="grid gap-x-10 md:grid-cols-2">
        {roundups.map((roundup) => {
          const sources = roundup.sources?.length ?? 0;
          return (
            <Link
              key={roundup.slug}
              href={`/articles/${roundup.slug}`}
              className="group grid grid-cols-[132px_1fr] items-start gap-4 border-b border-line py-5 sm:grid-cols-[168px_1fr] sm:gap-5"
            >
              <div className="relative aspect-video overflow-hidden rounded-xl bg-surface-2">
                <Thumb
                  src={roundup.thumbnail}
                  alt=""
                  fill
                  sizes="168px"
                  className="object-cover transition-transform duration-500 ease-out group-hover:scale-[1.05]"
                />
                {sources > 0 && (
                  <span className="absolute bottom-1.5 left-1.5 inline-flex items-baseline gap-0.5 rounded-full bg-ink/90 px-2 py-0.5 text-paper">
                    <span className="index-num text-[13px] font-semibold leading-none">{sources}</span>
                    <span className="text-[10px] font-bold">本</span>
                  </span>
                )}
              </div>

              <div className="min-w-0">
                <time dateTime={roundup.generatedAt} className="index-num text-[11px] text-muted">
                  {formatDate(roundup.generatedAt)}
                </time>
                <h3 className="mt-1 text-[15.5px] font-bold leading-[1.6] text-ink decoration-[1.5px] underline-offset-4 group-hover:underline">
                  <Highlight text={roundup.title} />
                </h3>
                <p className="mt-1 line-clamp-1 text-[13.5px] leading-[1.7] text-ink-soft">
                  {roundup.lede || roundup.description}
                </p>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
