import type { Offer, OfferItem } from "@/lib/offers";

const yen = new Intl.NumberFormat("ja-JP");
const dateFormat = new Intl.DateTimeFormat("ja-JP", {
  month: "numeric",
  day: "numeric",
  timeZone: "Asia/Tokyo",
});

/**
 * 記事の文脈に合わせた「試すなら」枠（PR）。
 * 商品の実物写真・価格・評価を並べ、広告であることは見出しの横と注記で明示する。
 * Google の指針に従いリンクには rel="sponsored" を付ける。
 */
export default function OfferCard({ offer }: { offer: Offer }) {
  const columns =
    offer.items.length >= 3 ? "sm:grid-cols-3" : offer.items.length === 2 ? "sm:grid-cols-2" : "";
  const hasBook = offer.items.some((item) => item.kind === "book");

  return (
    <aside aria-labelledby={`offer-${offer.topic}`} className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[12px] font-bold text-muted">{offer.eyebrow}</p>
        <span className="shrink-0 rounded border border-line-strong px-1.5 py-[1px] text-[10px] font-bold tracking-wider text-muted">
          PR
        </span>
      </div>
      <h2 id={`offer-${offer.topic}`} className="mt-1.5 text-[18px] font-bold leading-snug text-ink text-balance">
        {offer.headline}
      </h2>
      <p className="mt-1.5 max-w-[46em] text-[13.5px] leading-[1.8] text-ink-soft">{offer.lead}</p>

      <ul className={`mt-4 grid gap-3 ${columns}`}>
        {offer.items.map((item) => (
          <li key={item.key}>
            <OfferTile item={item} />
          </li>
        ))}
      </ul>

      <p className="mt-3.5 text-[11px] leading-relaxed text-muted">
        価格{hasBook ? "・評価" : ""}は{dateFormat.format(Date.parse(offer.checkedAt))}時点の
        {hasBook ? "楽天ブックス・" : ""}各公式サイトの情報です。リンク経由で購入・申し込みがあると、当サイトに紹介料が支払われることがあります。
      </p>
      {offer.pixels.map((pixel) => (
        // ASPの表示回数計測（1x1）。見た目には影響しない
        // eslint-disable-next-line @next/next/no-img-element
        <img key={pixel} src={pixel} width={1} height={1} alt="" className="absolute size-px opacity-0" />
      ))}
    </aside>
  );
}

function OfferTile({ item }: { item: OfferItem }) {
  const price =
    item.price != null ? `¥${yen.format(item.price)}` : item.priceText ? item.priceText : undefined;

  return (
    <a
      href={item.url}
      target="_blank"
      rel="sponsored noopener noreferrer"
      className="group grid h-full grid-cols-[96px_minmax(0,1fr)] gap-3.5 rounded-xl border border-line bg-paper p-3 transition-colors hover:border-ink sm:grid-cols-1 sm:gap-0 sm:p-0"
    >
      {/* 商品写真は白地で見せる（ダーク表示でも商品の色が正しく見えるように） */}
      <span className="relative grid aspect-square place-items-center overflow-hidden rounded-lg bg-white sm:rounded-b-none sm:rounded-t-xl">
        {item.image ? (
          // 楽天・提携先の画像CDNを直接使う（next/image の最適化対象外）
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={item.image}
            alt=""
            loading="lazy"
            className={`size-full object-contain transition-transform duration-500 group-hover:scale-[1.03] motion-reduce:transition-none ${
              item.kind === "book" ? "p-3 sm:p-5" : "p-1.5 sm:p-3"
            }`}
          />
        ) : (
          <span className="grid size-full place-items-center bg-ink px-3 text-center">
            <span className="text-[15px] font-bold leading-tight text-paper sm:text-[19px]">{item.name}</span>
          </span>
        )}
      </span>

      <span className="flex min-w-0 flex-col sm:p-3.5">
        {item.label && <span className="text-[11px] font-bold text-accent">{item.label}</span>}
        <span className="mt-0.5 line-clamp-2 text-[14px] font-bold leading-[1.5] text-ink group-hover:underline">
          {item.name}
        </span>
        {item.note && (
          <span className="mt-1 line-clamp-2 text-[12px] leading-[1.6] text-muted">{item.note}</span>
        )}
        {item.kind === "book" && item.author && (
          <span className="mt-0.5 truncate text-[12px] text-muted">{item.author}</span>
        )}
        {item.rating != null && item.reviews ? (
          <span className="mt-1 flex items-center gap-1 text-[12px] text-ink-soft">
            <Stars value={item.rating} />
            <span className="index-num font-semibold">{item.rating.toFixed(1)}</span>
            <span className="index-num text-muted">（{item.reviews}件）</span>
          </span>
        ) : null}

        <span className="mt-auto flex items-end justify-between gap-2 pt-2.5">
          {price && <span className="index-num text-[16px] font-bold text-ink">{price}</span>}
          <span className="text-[11px] text-muted">{item.shop}</span>
        </span>
        <span className="mt-2.5 hidden items-center justify-center gap-1 rounded-full bg-ink py-2 text-[12.5px] font-bold text-paper transition-opacity group-hover:opacity-85 sm:flex">
          {item.cta}
          <span aria-hidden>↗</span>
        </span>
      </span>
    </a>
  );
}

function Stars({ value }: { value: number }) {
  const percent = Math.max(0, Math.min(100, (value / 5) * 100));
  return (
    <span aria-label={`5点中${value.toFixed(1)}点`} className="relative inline-block text-[12px] leading-none tracking-[1px]">
      <span className="text-line-strong">★★★★★</span>
      <span className="absolute inset-0 overflow-hidden whitespace-nowrap text-[#e8a33d]" style={{ width: `${percent}%` }}>
        ★★★★★
      </span>
    </span>
  );
}
