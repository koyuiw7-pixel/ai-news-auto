import type { Offer } from "@/lib/offers";
import { Pixels, PrNote, ProductImage, Rating, priceText, rankBadge } from "./parts";

/** 案B「ランキング型」：番号つきで3つを比べられる。1位だけ大きく */
export default function RailRanking({ offer }: { offer: Offer }) {
  const [first, ...rest] = offer.items;
  return (
    <aside aria-label="PR：おすすめ商品" className="relative overflow-hidden rounded-2xl border border-line-strong bg-paper">
      <div className="bg-ink px-4 py-3.5 text-paper">
        <p className="flex items-center gap-2 text-[11px] font-bold opacity-75">
          <span className="rounded border border-current px-1.5 text-[10px] tracking-wider">PR</span>
          {offer.eyebrow}
        </p>
        <p className="font-display mt-1.5 text-[18px] leading-snug">サイソクのおすすめ{offer.items.length}選</p>
        <p className="mt-1 text-[12px] leading-snug opacity-80">{offer.headline}</p>
      </div>

      <ol>
        <li className="border-b border-line">
          <a href={first.url} target="_blank" rel="sponsored noopener noreferrer" className="group block p-4">
            <span className="flex items-center gap-2">
              <span className="font-display text-[30px] leading-none text-live">1</span>
              {first.label && <span className="rounded-full bg-live/10 px-2 py-0.5 text-[11px] font-bold text-live">{first.label}</span>}
              {rankBadge(first) && <span className="text-[11px] font-bold text-muted">{rankBadge(first)}</span>}
            </span>
            <ProductImage item={first} className="mt-2.5 aspect-[4/3] rounded-xl border border-line" pad={first.kind === "book" ? "p-5" : "p-3"} />
            <span className="mt-2.5 block line-clamp-2 text-[14.5px] font-bold leading-[1.5] text-ink group-hover:underline">{first.name}</span>
            <span className="mt-1 block">
              <Rating item={first} />
            </span>
            <span className="mt-1.5 flex items-baseline justify-between">
              <span className="index-num text-[21px] font-bold text-ink">{priceText(first)}</span>
              <span className="text-[11px] text-muted">{first.shop}</span>
            </span>
            <span className="mt-2.5 flex h-11 items-center justify-center gap-1.5 rounded-xl bg-live text-[13.5px] font-bold text-white group-hover:opacity-90">
              {first.cta}
              <span aria-hidden>↗</span>
            </span>
          </a>
        </li>
        {rest.map((item, index) => (
          <li key={item.key} className="border-b border-line last:border-b-0">
            <a
              href={item.url}
              target="_blank"
              rel="sponsored noopener noreferrer"
              className="group grid grid-cols-[22px_64px_minmax(0,1fr)] items-center gap-3 px-4 py-3 hover:bg-surface"
            >
              <span className="font-display text-[22px] leading-none text-ink">{index + 2}</span>
              <ProductImage item={item} className="size-16 rounded-lg border border-line" pad="p-1.5" />
              <span className="min-w-0">
                <span className="line-clamp-2 text-[13px] font-bold leading-snug text-ink group-hover:underline">{item.name}</span>
                <span className="mt-0.5 block">
                  <Rating item={item} size={11} />
                </span>
                <span className="mt-0.5 flex items-center justify-between gap-2">
                  <span className="index-num text-[13.5px] font-bold text-ink">{priceText(item)}</span>
                  <span className="rounded-full border border-line-strong px-2 py-0.5 text-[11px] font-bold text-ink-soft group-hover:border-ink">見る ↗</span>
                </span>
              </span>
            </a>
          </li>
        ))}
      </ol>

      <div className="border-t border-line bg-surface px-4 py-2.5">
        <PrNote checkedAt={offer.checkedAt} hasBook={offer.items.some((i) => i.kind === "book")} />
      </div>
      <Pixels pixels={offer.pixels} />
    </aside>
  );
}
