import Link from "next/link";
import Image from "next/image";
import Thumb from "@/components/Thumb";
import { coverPath } from "@/lib/articles";
import { thumbSource } from "@/lib/companies";
import { displayHeadline } from "@/lib/headline";
import type { FunnelCard as FunnelCardData } from "@/lib/comparison";

/**
 * ニュース記事から比較記事へ案内する「次に読む」のカード（lib/comparison.ts）。
 * 自分たちの編集記事への案内なので PR の札は付けない（広告の枠にも数えない）。
 * 置き場所: ①判断ガイドの直後（無ければ「すぐにできること」の直後）②記事の終わり。pos で分けて数えられるよう data-compare-funnel-pos を付ける。
 */
export default function FunnelCard({ card, pos, className = "my-8" }: { card: FunnelCardData; pos: "mid" | "end"; className?: string }) {
  const a = card.target;
  const cover = a.thumbnail ? null : coverPath(a);
  return (
    <aside data-compare-funnel={card.topic} data-compare-funnel-pos={pos} aria-label="次に読む記事" className={`max-w-[46em] ${className}`}>
      <Link
        href={`/articles/${a.slug}`}
        className="group grid overflow-hidden rounded-2xl border-2 border-ink bg-paper transition-shadow hover:shadow-[0_10px_30px_-18px_rgb(0_0_0/0.5)] sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"
      >
        <span className="relative block aspect-[40/21] overflow-hidden bg-surface-2 sm:aspect-auto sm:min-h-[180px]">
          {cover ? (
            <Image src={cover} alt="" fill sizes="(max-width: 640px) 100vw, 360px" className="object-cover" />
          ) : (
            <Thumb
              src={a.thumbnail}
              source={thumbSource(a)}
              cover={coverPath(a)}
              aiGenerated={a.imageCredit?.kind === "ai"}
              alt=""
              fill
              sizes="(max-width: 640px) 100vw, 360px"
              className="object-cover"
            />
          )}
        </span>
        <span className="flex flex-col gap-2 p-5">
          <span className="flex items-center gap-2">
            <span className="rounded-sm bg-live px-2 py-[2px] text-badge font-bold text-live-ink">選び方・比較</span>
            <span className="text-meta font-bold text-muted">当サイトの比較記事</span>
          </span>
          <span className="text-[17px] font-bold leading-[1.55] text-ink text-balance group-hover:underline">
            {`次に読む：${displayHeadline(a.title)}`}
          </span>
          <span className="text-note leading-[1.75] text-ink-soft">{card.reason}</span>
          <span className="mt-auto inline-flex items-center gap-1 pt-1 text-note font-bold text-live">
            比較を読む <span aria-hidden>→</span>
          </span>
        </span>
      </Link>
    </aside>
  );
}
