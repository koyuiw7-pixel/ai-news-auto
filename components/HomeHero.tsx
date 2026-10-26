import Thumb from "@/components/Thumb";
import Link from "next/link";
import Morph from "@/components/Morph";
import CompanyMark from "@/components/CompanyMark";
import RelTime from "@/components/RelTime";
import type { Article } from "@/lib/articles";
import { companyOf, thumbSource } from "@/lib/companies";
import { Highlight } from "@/lib/highlight";

/**
 * トップの主役。
 * 人は文字より画像を強く記憶する（画像優位性効果）ので、左に大きな写真、右に見出しを置く。
 * 強調は「何本を統合したか」の黒いバッジと、見出しの蛍光ペンの2か所だけに絞る。
 */
export default function HomeHero({ lead }: { lead: Article }) {
  const isRoundup = lead.type === "roundup";
  const sources = lead.sources?.length ?? 0;
  const href = `/articles/${lead.slug}`;

  return (
    <section
      aria-label="注目の記事"
      className="grid items-center gap-6 lg:grid-cols-[1.12fr_1fr] lg:gap-12"
    >
      <Link
        href={href}
        tabIndex={-1}
        aria-hidden
        className="group relative block overflow-hidden rounded-3xl bg-surface-2"
      >
        <Morph name={`cover-${lead.slug}`}>
          <div className="relative aspect-video">
            <Thumb
              src={lead.thumbnail}
              source={thumbSource(lead)}
              alt=""
              fill
              priority
              sizes="(max-width: 1024px) 100vw, 640px"
              className="object-cover transition-transform duration-700 ease-out group-hover:scale-[1.03]"
            />
          </div>
        </Morph>
        {isRoundup && sources > 0 && (
          <span className="absolute bottom-4 left-4 inline-flex items-baseline gap-1.5 rounded-full bg-ink/90 px-4 py-2 text-paper">
            <span className="index-num text-xl font-semibold leading-none">{sources}</span>
            <span className="text-[12.5px] font-bold">本の発表を統合</span>
          </span>
        )}
      </Link>

      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px]">
          <span className="rounded-full bg-live px-2.5 py-0.5 text-[11px] font-bold tracking-wider text-white">
            {isRoundup ? "まとめ" : "最新"}
          </span>
          <CompanyMark company={companyOf(lead)} size={18} withName />
          <RelTime iso={lead.publishedAt} className="index-num font-semibold text-muted" />
        </div>

        <Link href={href} className="group">
          <Morph name={`title-${lead.slug}`}>
            <h2 className="display font-bold text-[1.65rem] leading-[1.45] text-ink decoration-2 underline-offset-[6px] group-hover:underline sm:text-[2.05rem]">
              <Highlight text={lead.title} />
            </h2>
          </Morph>
        </Link>

        <p className="line-clamp-2 text-[15px] leading-[1.85] text-ink-soft">
          {lead.lede || lead.description}
        </p>

        {lead.highlights.length > 0 && (
          <div className="border-t border-line pt-4">
            <p className="text-[12px] font-bold text-muted">3秒でわかる要点</p>
            <ol className="mt-2.5 grid gap-2.5">
              {lead.highlights.slice(0, 3).map((point, index) => (
                <li key={index} className="grid grid-cols-[22px_1fr] gap-3 text-[14px] leading-[1.7] text-ink">
                  <span className="index-num mt-0.5 grid size-[22px] place-items-center rounded-full bg-ink text-[11px] font-semibold text-paper">
                    {index + 1}
                  </span>
                  {point}
                </li>
              ))}
            </ol>
          </div>
        )}

        <Link
          href={href}
          className="mt-1 inline-flex w-fit items-center gap-2 rounded-full bg-ink px-5 py-2.5 text-[13.5px] font-bold text-paper transition-opacity hover:opacity-85"
        >
          {isRoundup ? "まとめを読む" : "記事を読む"}
          <span aria-hidden>→</span>
        </Link>
      </div>
    </section>
  );
}
