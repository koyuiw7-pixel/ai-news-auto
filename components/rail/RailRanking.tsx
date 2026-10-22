import type { Offer, OfferItem } from "@/lib/offers";
import { Pixels, PrNote, ProductImage, Rating, priceText, reasonOf } from "./parts";

/**
 * 「サイソクのおすすめ3選」。記事の文脈に合う商品を番号つきで並べ、1位を大きく推す。
 * wide は本文中（横長）、それ以外は右側の縦長。どちらも中身は同じ。
 */
export default function RailRanking({ offer, wide = false, id }: { offer: Offer; wide?: boolean; id?: string }) {
  const [first, ...rest] = offer.items;
  const hasBook = offer.items.some((i) => i.kind === "book");

  return (
    <aside id={id} aria-label="PR：サイソクのおすすめ" className="relative overflow-hidden rounded-2xl border border-ink bg-paper">
      <Header offer={offer} wide={wide} />

      <div>
        <First item={first} wide={wide} />
        {rest.length > 0 && (
          <ol className={wide ? "grid border-t border-line sm:grid-cols-2 sm:[&>li:nth-child(2)]:border-l sm:[&>li]:border-b-0" : ""} start={2}>
            {rest.map((item, index) => (
              <Row key={item.key} item={item} rank={index + 2} />
            ))}
          </ol>
        )}
      </div>

      <div className="border-t border-line bg-surface px-4 py-2.5">
        <PrNote checkedAt={offer.checkedAt} hasBook={hasBook} />
      </div>
      <Pixels pixels={offer.pixels} />
    </aside>
  );
}

function Header({ offer, wide }: { offer: Offer; wide: boolean }) {
  return (
    <div className={`bg-ink text-paper ${wide ? "px-5 py-4 sm:px-6" : "px-4 py-3.5"}`}>
      <p className="flex items-center gap-2 text-[11px] font-bold opacity-75">
        <span className="rounded border border-current px-1.5 text-[10px] tracking-wider">PR</span>
        {offer.eyebrow}
      </p>
      <p className={`font-display mt-1.5 leading-snug ${wide ? "text-[22px]" : "text-[19px]"}`}>
        サイソクのおすすめ{offer.items.length}選
      </p>
      <p className="mt-1 text-[12.5px] leading-snug opacity-85">{offer.headline}</p>
    </div>
  );
}

function First({ item, wide }: { item: OfferItem; wide: boolean }) {
  const reason = reasonOf(item);
  return (
    <a
      href={item.url}
      target="_blank"
      rel="sponsored noopener noreferrer"
      className={`group block ${wide ? "p-5 sm:p-6" : "border-b border-line p-4"}`}
    >
      <span className="flex items-center gap-2">
        <span className="font-display text-[34px] leading-none text-live">1</span>
        <span className="rounded-full bg-live px-2.5 py-1 text-[11px] font-bold text-white">イチオシ</span>
        {item.label && <span className="text-[11.5px] font-bold text-live">{item.label}</span>}
      </span>

      <span className={wide ? "mt-3 grid gap-5 sm:grid-cols-[200px_minmax(0,1fr)]" : "block"}>
        <ProductImage
          item={item}
          className={`rounded-xl border border-line ${wide ? "aspect-square" : "mt-2.5 aspect-[16/10]"}`}
          pad={item.kind === "book" ? "p-5" : "p-3"}
          eager={!wide}
        />
        <span className={`flex min-w-0 flex-col ${wide ? "" : "mt-2.5"}`}>
          <span className="line-clamp-2 text-[15px] font-bold leading-[1.5] text-ink group-hover:underline">{item.name}</span>
          {reason && (
            <span className="mt-1.5 rounded-lg bg-surface px-2.5 py-2 text-[12px] leading-[1.6] text-ink-soft">
              <span className="font-bold text-ink">ここがおすすめ：</span>
              {reason}
            </span>
          )}
          <span className="mt-1.5">
            <Rating item={item} />
          </span>
          <span className="mt-1.5 flex items-baseline justify-between gap-2">
            <span className="index-num text-[23px] font-bold tracking-tight text-ink">{priceText(item)}</span>
            <span className="text-[11px] text-muted">{item.shop}</span>
          </span>
          <span className="mt-2.5 flex h-12 items-center justify-center gap-1.5 rounded-xl bg-live text-[14px] font-bold text-white shadow-[0_6px_16px_-8px_var(--live)] transition-transform group-hover:-translate-y-px motion-reduce:transition-none">
            {item.cta}
            <span aria-hidden>↗</span>
          </span>
        </span>
      </span>
    </a>
  );
}

function Row({ item, rank }: { item: OfferItem; rank: number }) {
  return (
    <li className="border-b border-line last:border-b-0">
      <a
        href={item.url}
        target="_blank"
        rel="sponsored noopener noreferrer"
        className="group grid grid-cols-[22px_72px_minmax(0,1fr)] items-center gap-3 px-4 py-3.5 hover:bg-surface"
      >
        <span className="font-display text-[22px] leading-none text-ink">{rank}</span>
        <ProductImage item={item} className="size-[72px] rounded-lg border border-line" pad="p-1.5" />
        <span className="min-w-0">
          {item.label && <span className="block text-[11px] font-bold text-live">{item.label}</span>}
          <span className="line-clamp-2 text-[13px] font-bold leading-snug text-ink group-hover:underline">{item.name}</span>
          <span className="mt-0.5 block">
            <Rating item={item} size={11} />
          </span>
          <span className="mt-1 flex items-center justify-between gap-2">
            <span className="index-num text-[14px] font-bold text-ink">{priceText(item)}</span>
            <span className="shrink-0 rounded-full bg-ink px-2.5 py-1 text-[11px] font-bold text-paper group-hover:opacity-85">
              見る ↗
            </span>
          </span>
        </span>
      </a>
    </li>
  );
}
