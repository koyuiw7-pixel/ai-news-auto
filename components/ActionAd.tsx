import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import type { OfferItem } from "@/lib/offers";
import { AFFILIATE_REL } from "@/lib/affiliate";
import { Pixels } from "@/components/rail/parts";

/**
 * 「すぐにできること」のすぐ下に置く PR の囲み（1記事に1つ。lib/action-ad.ts）。
 * 広告だと一目で分かるよう「PR・広告」を見出しに出し、この記事の読者に関係する理由を1行で添える。
 * 1つ目は広告主のバナー（A8 の素材をそのまま。縦横比 6:5 の場所を先に取り、読み込みで画面がずれない）を大きめに、
 * 2つ目は小さな画像つきの1行にする（スマホで画面を埋めない）。素材の無い商品は文字だけ。
 * クリックは data-aff-pos="action-ad"（components/AffClickTracker.tsx → scripts/aff_stats.py）で、ほかの置き場所と分けて数える。
 */
export default function ActionAd({ ad, className = "mt-4" }: { ad: ActionAdData; className?: string }) {
  if (ad.items.length === 0) return null;
  const [first, ...rest] = ad.items;
  return (
    <aside
      data-aff-pos="action-ad"
      data-action-ad={ad.key}
      aria-label="PR：広告"
      className={`relative max-w-[40em] rounded-2xl border border-line-strong bg-surface p-4 sm:p-5 ${className}`}
    >
      <p className="flex items-center gap-2 text-meta font-bold text-muted">
        <span className="rounded border border-current px-1.5 tracking-wider">PR</span>
        広告・{ad.title}
      </p>
      {ad.reason && <p className="mt-1.5 text-note font-bold leading-relaxed text-ink">{ad.reason}</p>}
      <ul className="mt-3 grid gap-2.5">
        <li>
          <FeaturedCard item={first.item} rank={1} />
        </li>
        {rest.map(({ item }, index) => (
          <li key={item.key}>
            <CompactRow item={item} rank={index + 2} />
          </li>
        ))}
      </ul>
      <p className="mt-2.5 text-meta leading-relaxed text-muted">
        ※ 広告（アフィリエイトリンク）です。申し込みがあると当サイトに紹介料が支払われることがあります。料金・条件は各公式サイトで確認してください。
      </p>
      <Pixels pixels={ad.items.map(({ pixel }) => pixel).filter((p): p is string => Boolean(p))} />
    </aside>
  );
}

/** 広告主のバナー（300×250 の素材。切り抜かず、白地にそのまま） */
function Banner({ item, className }: { item: OfferItem; className: string }) {
  if (!item.image) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={item.image}
      alt={item.name}
      width={300}
      height={250}
      loading="lazy"
      decoding="async"
      className={`block aspect-[6/5] h-auto bg-white object-contain ${className}`}
    />
  );
}

function FeaturedCard({ item, rank }: { item: OfferItem; rank: number }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel={AFFILIATE_REL}
      data-aff-rank={rank}
      className="group grid gap-3 overflow-hidden rounded-xl border border-line bg-paper p-3 transition-colors hover:border-accent sm:grid-cols-[200px_1fr] sm:items-center sm:gap-4"
    >
      <Banner item={item} className="mx-auto w-full max-w-[240px] rounded-lg sm:max-w-[200px]" />
      <span className="min-w-0">
        <span className="block text-desc font-bold text-ink group-hover:text-accent">{item.name}</span>
        {item.note && <span className="mt-1 block text-note leading-relaxed text-ink-soft">{item.note}</span>}
        <span className="mt-3 flex w-full items-center justify-center rounded-lg bg-accent px-4 py-2.5 text-note font-bold text-accent-ink sm:inline-flex sm:w-auto">
          {item.cta} →
        </span>
      </span>
    </a>
  );
}

function CompactRow({ item, rank }: { item: OfferItem; rank: number }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel={AFFILIATE_REL}
      data-aff-rank={rank}
      className="group flex items-center gap-3 rounded-xl border border-line bg-paper p-2.5 pr-4 transition-colors hover:border-accent"
    >
      <Banner item={item} className="w-[84px] shrink-0 rounded-md" />
      <span className="min-w-0 flex-1">
        <span className="block text-note font-bold text-ink group-hover:text-accent">{item.name}</span>
        {item.note && <span className="mt-0.5 block text-meta leading-relaxed text-muted">{item.note}</span>}
        <span className="mt-1 block text-meta font-bold text-accent sm:hidden">{item.cta} →</span>
      </span>
      <span className="hidden shrink-0 text-meta font-bold text-accent sm:block">{item.cta} →</span>
    </a>
  );
}
