import type { Offer } from "@/lib/offers";
import { Pixels, PrNote, ProductImage, Rating, priceText, rankBadge } from "./parts";

/** 案A「商品ページ型」：1つを大きく見せ、ほかの候補を下に並べる */
export default function RailShop({ offer }: { offer: Offer }) {
  const [main, ...rest] = offer.items;
  const badge = rankBadge(main);
  return (
    <aside aria-label="PR：おすすめ商品" className="relative overflow-hidden rounded-2xl border border-line-strong bg-paper">
      <div className="px-4 pt-4">
        <p className="flex items-center gap-2 text-[11.5px] font-bold text-muted">
          <span className="rounded bg-ink px-1.5 py-[1px] text-[10px] tracking-wider text-paper">PR</span>
          {offer.eyebrow}
        </p>
        <p className="mt-1.5 text-[15px] font-bold leading-snug text-ink text-balance">{offer.headline}</p>
      </div>

      <a href={main.url} target="_blank" rel="sponsored noopener noreferrer" className="group block px-4 pb-4 pt-3">
        <span className="relative block">
          <ProductImage item={main} className="aspect-square rounded-xl border border-line" pad={main.kind === "book" ? "p-8" : "p-4"} />
          {main.label && (
            <span className="absolute left-2.5 top-2.5 rounded-full bg-ink px-2.5 py-1 text-[11px] font-bold text-paper">
              {main.label}
            </span>
          )}
          {badge && (
            <span className="absolute right-2.5 top-2.5 rounded-full bg-live px-2.5 py-1 text-[11px] font-bold text-white">
              {badge}
            </span>
          )}
        </span>
        <span className="mt-3 block line-clamp-2 text-[15px] font-bold leading-[1.5] text-ink group-hover:underline">
          {main.name}
        </span>
        {main.note && <span className="mt-1 block text-[12.5px] leading-[1.65] text-ink-soft">{main.note}</span>}
        <span className="mt-1.5 block">
          <Rating item={main} />
        </span>
        <span className="mt-2 flex items-baseline justify-between">
          <span className="index-num text-[24px] font-bold tracking-tight text-ink">{priceText(main)}</span>
          <span className="text-[11px] text-muted">{main.shop}</span>
        </span>
        <span className="mt-3 flex h-12 items-center justify-center gap-1.5 rounded-xl bg-live text-[14px] font-bold text-white transition-opacity group-hover:opacity-90">
          {main.cta}
          <span aria-hidden>↗</span>
        </span>
      </a>

      {rest.length > 0 && (
        <div className="border-t border-line px-4 py-3">
          <p className="text-[11px] font-bold text-muted">ほかの候補</p>
          <ul className="mt-2 grid gap-2">
            {rest.map((item) => (
              <li key={item.key}>
                <a
                  href={item.url}
                  target="_blank"
                  rel="sponsored noopener noreferrer"
                  className="group grid grid-cols-[56px_minmax(0,1fr)] items-center gap-3 rounded-lg p-1 hover:bg-surface"
                >
                  <ProductImage item={item} className="size-14 rounded-lg border border-line" pad="p-1.5" />
                  <span className="min-w-0">
                    <span className="line-clamp-2 text-[12.5px] font-bold leading-snug text-ink group-hover:underline">{item.name}</span>
                    <span className="mt-0.5 flex items-center gap-2 text-[12px]">
                      <span className="index-num font-bold text-ink">{priceText(item)}</span>
                      <span className="text-muted">{item.shop}</span>
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="border-t border-line bg-surface px-4 py-2.5">
        <PrNote checkedAt={offer.checkedAt} hasBook={offer.items.some((i) => i.kind === "book")} />
      </div>
      <Pixels pixels={offer.pixels} />
    </aside>
  );
}
