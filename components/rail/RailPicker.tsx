"use client";

import { useState } from "react";
import type { Offer } from "@/lib/offers";
import { Pixels, ProductImage, Rating, checkedDate, priceText, rankBadge } from "./parts";

/** 案C「切り替え型」：黒地で目立たせ、下のサムネで商品を切り替える */
export default function RailPicker({ offer }: { offer: Offer }) {
  const [active, setActive] = useState(0);
  const item = offer.items[active] ?? offer.items[0];
  const badge = rankBadge(item);
  const hasBook = offer.items.some((i) => i.kind === "book");

  return (
    <aside aria-label="PR：おすすめ商品" className="relative overflow-hidden rounded-2xl bg-ink p-4 text-paper">
      <p className="flex items-center gap-2 text-[11px] font-bold opacity-70">
        <span className="rounded border border-current px-1.5 text-[10px] tracking-wider">PR</span>
        {offer.eyebrow}
      </p>
      <p className="mt-1.5 text-[16px] font-bold leading-snug text-balance">{offer.headline}</p>

      <a href={item.url} target="_blank" rel="sponsored noopener noreferrer" className="group mt-3 block">
        <span className="relative block">
          <ProductImage item={item} className="aspect-[4/3] rounded-xl" pad={item.kind === "book" ? "p-5" : "p-3"} />
          {(item.label || badge) && (
            <span className="absolute left-2.5 top-2.5 rounded-full bg-live px-2.5 py-1 text-[11px] font-bold text-white">
              {badge ?? item.label}
            </span>
          )}
        </span>
        <span className="mt-3 block line-clamp-2 text-[14.5px] font-bold leading-[1.5] group-hover:underline">{item.name}</span>
        {item.note && <span className="mt-1 block text-[12px] leading-[1.65] opacity-75">{item.note}</span>}
        {item.rating != null && item.reviews ? (
          <span className="mt-1.5 block [&_.text-ink-soft]:text-paper [&_.text-muted]:text-paper/60">
            <Rating item={item} />
          </span>
        ) : null}
        <span className="mt-2 flex items-baseline justify-between">
          <span className="index-num text-[22px] font-bold">{priceText(item)}</span>
          <span className="text-[11px] opacity-60">{item.shop}</span>
        </span>
        <span className="mt-3 flex h-11 items-center justify-center gap-1.5 rounded-xl bg-paper text-[13.5px] font-bold text-ink group-hover:opacity-90">
          {item.cta}
          <span aria-hidden>↗</span>
        </span>
      </a>

      {offer.items.length > 1 && (
        <div className="mt-3.5 grid grid-cols-3 gap-2" role="tablist" aria-label="商品を切り替える">
          {offer.items.map((candidate, index) => (
            <button
              key={candidate.key}
              type="button"
              role="tab"
              aria-selected={index === active}
              aria-label={candidate.name}
              onClick={() => setActive(index)}
              className={`overflow-hidden rounded-lg outline-none transition-shadow focus-visible:ring-2 focus-visible:ring-paper ${
                index === active ? "ring-2 ring-live" : "opacity-60 hover:opacity-100"
              }`}
            >
              <ProductImage item={candidate} className="aspect-square" pad="p-1.5" />
            </button>
          ))}
        </div>
      )}

      <p className="mt-3 text-[10.5px] leading-relaxed opacity-55">
        価格{hasBook ? "・評価" : ""}は{checkedDate(offer.checkedAt)}時点。リンク経由の購入で当サイトに紹介料が入ることがあります。
      </p>
      <Pixels pixels={offer.pixels} />
    </aside>
  );
}
