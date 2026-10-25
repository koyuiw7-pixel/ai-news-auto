import type { OfferItem } from "@/lib/offers";

const yen = new Intl.NumberFormat("ja-JP");
const dateFormat = new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", timeZone: "Asia/Tokyo" });

export function priceText(item: OfferItem): string | undefined {
  if (item.price != null) return `¥${yen.format(item.price)}`;
  return item.priceText;
}

export function checkedDate(iso: string): string {
  return dateFormat.format(Date.parse(iso));
}

/** 楽天の売れ筋で上位のときだけ出す実データのバッジ */
export function rankBadge(item: OfferItem): string | undefined {
  if (item.kind !== "book" || !item.rank || item.rank > 10) return undefined;
  return `楽天売れ筋${item.rank}位`;
}

/** 1位に添える「ここがおすすめ」。提携商品は編集部の一言、本は楽天の実データから作る */
export function reasonOf(item: OfferItem): string | undefined {
  if (item.note) return item.note;
  if (item.kind !== "book") return undefined;
  const parts: string[] = [];
  if (item.rank && item.rank <= 10 && item.keyword) parts.push(`楽天ブックス「${item.keyword}」の売れ筋${item.rank}位`);
  if (item.rating != null && item.reviews && item.reviews >= 3) parts.push(`レビュー${item.reviews}件で平均${item.rating.toFixed(1)}`);
  return parts.length > 0 ? parts.join("。") : undefined;
}

export function Stars({ value, size = 12 }: { value: number; size?: number }) {
  const percent = Math.max(0, Math.min(100, (value / 5) * 100));
  return (
    <span
      aria-label={`5点中${value.toFixed(1)}点`}
      className="relative inline-block leading-none tracking-[1px]"
      style={{ fontSize: size }}
    >
      <span className="text-line-strong">★★★★★</span>
      <span className="absolute inset-0 overflow-hidden whitespace-nowrap text-[#e8a33d]" style={{ width: `${percent}%` }}>
        ★★★★★
      </span>
    </span>
  );
}

export function Rating({ item, size = 12 }: { item: OfferItem; size?: number }) {
  if (item.rating == null || !item.reviews) return null;
  return (
    <span className="flex items-center gap-1 text-[12px] text-ink-soft">
      <Stars value={item.rating} size={size} />
      <span className="index-num font-semibold">{item.rating.toFixed(1)}</span>
      <span className="index-num text-muted">（{item.reviews}件）</span>
    </span>
  );
}

/** 商品写真。白地で見せる（ダーク表示でも商品の色が正しく見えるように） */
export function ProductImage({
  item,
  className = "",
  pad = "p-4",
  eager = false,
}: {
  item: OfferItem;
  className?: string;
  pad?: string;
  /** 最初から画面に見える位置（右上の1位など）は遅延読み込みしない */
  eager?: boolean;
}) {
  return (
    <span className={`relative grid place-items-center overflow-hidden bg-white ${className}`}>
      {item.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.image} alt="" loading={eager ? "eager" : "lazy"} className={`size-full object-contain ${pad}`} />
      ) : (
        // 写真の無いサービス（ConoHa AI Canvas など）は、名前と一言を文字で見せる
        <span className="flex size-full flex-col items-center justify-center gap-2 bg-[linear-gradient(135deg,#eef6fb,#ffffff_55%,#f3f0fb)] px-4 text-center">
          <span className="text-[10px] font-bold tracking-[0.2em] text-[#0a6fa0]">{item.badge ?? "WEB SERVICE"}</span>
          <span className="text-[17px] font-bold leading-tight text-[#111111] text-balance">{item.name}</span>
          {item.label && (
            <span className="rounded-full bg-[#111111] px-2.5 py-1 text-[10.5px] font-bold text-white">{item.label}</span>
          )}
        </span>
      )}
    </span>
  );
}

export function PrNote({ checkedAt, hasBook }: { checkedAt: string; hasBook: boolean }) {
  return (
    <p className="text-[10.5px] leading-relaxed text-muted">
      価格{hasBook ? "・評価" : ""}は{checkedDate(checkedAt)}時点{hasBook ? "（楽天ブックス・各公式サイト）" : "（各公式サイト）"}。
      リンク経由の購入で当サイトに紹介料が入ることがあります。
    </p>
  );
}

/**
 * ASPの表示回数計測ピクセル。本番（Vercel の production）でだけ読み込む。
 * 開発中やプレビューの確認で表示回数が水増しされ、レポートが読めなくなるのを防ぐ。
 */
const COUNT_IMPRESSIONS = process.env.VERCEL_ENV === "production";

export function Pixels({ pixels }: { pixels: string[] }) {
  if (!COUNT_IMPRESSIONS) return null;
  return (
    <>
      {pixels.map((pixel) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={pixel} src={pixel} width={1} height={1} alt="" className="absolute size-px opacity-0" />
      ))}
    </>
  );
}
