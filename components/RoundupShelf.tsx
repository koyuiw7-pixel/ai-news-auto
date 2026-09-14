import Link from "next/link";
import { formatDate, type Article } from "@/lib/articles";
import { Highlight } from "@/lib/highlight";

/**
 * 横断まとめ記事の専用枠。
 * 複数の動画を統合した、このサイト唯一の独自コンテンツなので、
 * 何本を統合したかという数字を主役にして並べる。
 */
export default function RoundupShelf({ roundups }: { roundups: Article[] }) {
  if (roundups.length === 0) return null;

  return (
    <section id="roundups" className="scroll-mt-24">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b-2 border-ink pb-3">
        <div>
          <p className="eyebrow">DEEP DIVE</p>
          <h2 className="display mt-1 text-2xl sm:text-[1.75rem]">話題まるごと解説</h2>
        </div>
        <p className="max-w-md text-[13px] leading-relaxed text-muted">
          同じ話題の発表を横断して1本にまとめた記事です。個々の動画では見えない全体像と、発表どうしの食い違いまで整理しています。
        </p>
      </div>

      <div className="grid gap-3.5 md:grid-cols-2">
        {roundups.map((roundup) => (
          <Link
            key={roundup.slug}
            href={`/articles/${roundup.slug}`}
            className="group grid grid-cols-[auto_1fr] gap-5 rounded-2xl bg-surface p-5 transition duration-300 ease-out hover:-translate-y-0.5 hover:bg-surface-2 sm:p-6"
          >
            <div className="flex flex-col items-start">
              <span className="index-num text-[2.6rem] font-semibold leading-none tracking-tight text-roundup">
                {roundup.sources?.length ?? 0}
              </span>
              <span className="mt-1 text-[10.5px] font-bold text-muted">本を統合</span>
            </div>

            <div className="min-w-0">
              <p className="index-num text-[11px] text-muted">
                {formatDate(roundup.generatedAt)}
              </p>
              <h3 className="mt-1 text-[16px] font-bold leading-[1.6] text-ink [text-wrap:pretty]">
                <Highlight text={roundup.title} />
              </h3>
              <p className="mt-2 line-clamp-2 text-[13px] leading-relaxed text-muted">
                {roundup.lede || roundup.description}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
