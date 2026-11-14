import type { OfferItem } from "@/lib/offers";
import { AFFILIATE_REL } from "@/lib/affiliate";
import { priceIsFresh } from "@/lib/offer-time";
import Link from "next/link";
import type { Benefit } from "@/lib/ad-benefits";
import RowThumb from "@/components/rail/RowThumb";

const yen = new Intl.NumberFormat("ja-JP");
const dateFormat = new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", timeZone: "Asia/Tokyo" });

export function priceText(item: OfferItem): string | undefined {
  if (item.price != null) return `¥${yen.format(item.price)}`;
  return item.priceText;
}

/** 商品カタログのみ、確認後48時間を超えた金額は表示しない。 */
export function catalogPriceText(item: OfferItem, now: number | null): string | undefined {
  if ((item.price != null || item.priceText) && !priceIsFresh(item.priceFreshUntil, now)) return "最新価格を確認";
  return priceText(item);
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
    <span className="flex items-center gap-1 text-meta text-ink-soft">
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
  compact = false,
}: {
  item: OfferItem;
  className?: string;
  pad?: string;
  /** 最初から画面に見える位置（右上の1位など）は遅延読み込みしない */
  eager?: boolean;
  /** 小さな枠（72px の2〜3位など）。写真が無いときは頭文字の札だけを出す */
  compact?: boolean;
}) {
  return (
    <span className={`relative grid place-items-center overflow-hidden bg-white ${className}`}>
      {item.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.image} alt="" loading={eager ? "eager" : "lazy"} decoding="async" fetchPriority={eager ? undefined : "low"} className={`absolute inset-0 h-full w-full object-contain ${pad}`} />
      ) : compact ? (
        <span aria-hidden="true" className="grid size-full place-items-center bg-[#f3f5f8]">
          <span className="grid size-10 place-items-center rounded-lg bg-[#1d4a8f] text-[18px] font-black text-white">{initialOf(item.name)}</span>
        </span>
      ) : (
        // 写真の無いサービスは、頭文字の札（サイトの紺）と名前で見せる。「WEB SERVICE」のような意味のない英語の板は出さない
        // （2026-11-03 の点検: 文字だけの板が壊れた画像のように見えた）
        <span className="flex size-full flex-col items-center justify-center gap-2.5 bg-[#f3f5f8] px-4 text-center">
          <span aria-hidden="true" className="grid size-12 place-items-center rounded-xl bg-[#1d4a8f] text-[22px] font-black text-white">
            {initialOf(item.name)}
          </span>
          <span className="text-[16px] font-bold leading-tight text-[#0b1a33] text-balance">{item.name}</span>
          {item.label && <span className="text-badge font-bold text-[#1d4a8f]">{item.label}</span>}
        </span>
      )}
    </span>
  );
}

/** 写真の無いサービスの頭文字（「6週間チャレンジ オフィス英会話」→「6」、「松井証券」→「松」） */
export function initialOf(name: string): string {
  const first = Array.from((name ?? "").trim())[0] ?? "";
  return first.toUpperCase();
}

/**
 * 枠の下の注記。2026-11-10 オーナー決定（台帳 W37）: 「価格・在庫・利用条件はリンク先でご確認ください。リンク経由の購入で当サイトに紹介料が
 * 入ることがあります。」は出さない（広告に集中できない）。広告の表示はページ冒頭の「本ページはプロモーションを含みます」と枠の「PR」の札で足りる。
 * 価格・評価を出す枠（本）だけ、その数字がいつのものかを1行で残す（表示した価格の時点。広告の説明ではない）。それ以外は何も出さない
 */
export function PrNote({ checkedAt, hasBook }: { checkedAt: string; hasBook: boolean }) {
  if (!hasBook) return null;
  return (
    <p className="text-[11px] leading-relaxed text-muted">
      {/* 並びは閲覧履歴で変わり、本が見えていない枠もある（セキュリティソフトだけの枠に「書籍の」と出ていた）ので「書籍」とは言わない */}
      {checkedDate(checkedAt)}時点
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
        // 低優先度にして先読み（preload）させない。読み込み自体はすぐ始まるので計測は変わらない
        // eslint-disable-next-line @next/next/no-img-element
        <img key={pixel} src={pixel} width={1} height={1} alt="" loading="lazy" fetchPriority="low" className="absolute size-px opacity-0" />
      ))}
    </>
  );
}

/** ボタンの言葉（押した先で分かること）。「公式サイトで見る」だけの商品は「料金と条件を見る」にする */
export function ctaOf(item: OfferItem): string {
  return item.pitch?.cta ?? (item.cta === "公式サイトで見る" ? "料金と条件を見る" : item.cta);
}

/**
 * PR の囲みの良いところ（2〜3つ）。広告主の公式サイトにある事実だけ（scripts/a8_import.py の MERITS）。
 * 印はチェックの形（矢印は使わない。2026-11-09 オーナー）
 */
export function MeritList({ merits, className = "" }: { merits: string[]; className?: string }) {
  if (merits.length === 0) return null;
  return (
    <ul className={`grid gap-1.5 ${className}`} aria-label="主な特徴（公式サイトの情報）">
      {merits.slice(0, 3).map((merit, i) => (
        // スマホは2つまで（囲みを高くしない。2026-11-10 オーナー承認「PR は小さく」）
        <li key={merit} className={`${i >= 2 ? "max-sm:hidden " : ""}grid grid-cols-[16px_minmax(0,1fr)] items-start gap-2 text-note leading-[1.55] text-ink`}>
          <svg aria-hidden="true" viewBox="0 0 16 16" className="pr-check mt-[3px] size-4 shrink-0">
            <circle cx="8" cy="8" r="8" />
            <path d="M4.6 8.3 7 10.6l4.4-4.9" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>{merit}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * 広告主のバナー（A8 の 300×250 など）を、縦横比 6:5 の白い枠に小さく収める。切り抜かず（文字が欠けない）、
 * 幅・高さを先に取るので読み込みで画面がずれない。画像の無い商品は頭文字の札。表示の計測（A8 のバナー）はこの画像で数えられる
 */
export function AdThumb({ item, className = "" }: { item: OfferItem; className?: string }) {
  return (
    <span className={`relative block aspect-[6/5] shrink-0 overflow-hidden rounded-lg border border-line bg-white ${className}`}>
      {item.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.image} alt="" width={300} height={250} loading="lazy" decoding="async" fetchPriority="low" className="absolute inset-0 h-full w-full object-contain" />
      ) : (
        <span aria-hidden="true" className="grid size-full place-items-center bg-[#f3f5f8]">
          <span className="grid size-9 place-items-center rounded-lg bg-[#1d4a8f] text-[17px] font-black text-white">{initialOf(item.name)}</span>
        </span>
      )}
    </span>
  );
}

/**
 * PR の囲みの1つ目（2026-11-10 オーナー「広告が魅力的じゃない。わざとらしすぎず、でも目立って押してしまうような」）。
 * 見出しは読者がこの商品で確かめられること（pitch.gain）→ 小さな画像と名前 → 良いところ2〜3つ（公式の事実）→ 色のあるボタン → 移動先の名前。
 * wide は本文の列（PC は画像を左に大きく、ボタンを横に）、それ以外は右の列・スマホ（縦に積む）。
 * ボタンの色は A/B（<html data-adv>。app/layout.tsx で訪問者ごとに a/b を決める。a=赤、b=サイトの基本色）。CSS は app/globals.css の .pr-cta
 */
export function PrFeature({
  item,
  wide = false,
  price,
  onClick,
  rank = 1,
}: {
  item: OfferItem;
  wide?: boolean;
  price?: string;
  onClick?: () => void;
  rank?: number;
}) {
  // 見出しは記事ごとの読者の状況（benefit.headline。lib/ad-benefits.ts）→ 読者が確かめられること（pitch.gain）。
  // 無い商品は見出しを付けず、画像と名前から始める（枠の上の1行が話題を示す）
  const benefit = item.benefit;
  const numbers = Boolean(benefit && (benefit.chips.length > 0 || benefit.compare));
  const gain = benefit?.headline ?? item.pitch?.gain;
  // 良いところ（公式の事実）。無ければ確認済みの仕様（facts）
  const merits = item.pitch?.merits ?? item.facts ?? [];
  // どちらも無い商品は、公式の情報から書いた1行（point / note。本は楽天の売れ筋・レビュー）を代わりに出す
  const point = merits.length === 0 ? (item.pitch?.point ?? reasonOf(item)) : undefined;
  return (
    <>
    <a
      href={item.url}
      target="_blank"
      rel={AFFILIATE_REL}
      data-aff-rank={rank}
      data-benefit={numbers ? "numbers" : benefit ? "headline" : undefined}
      onClick={onClick}
      className={`group block ${wide ? "p-4 sm:p-6" : "p-4"} ${benefit && (benefit.link || benefit.sources.length > 0) ? "pb-3 sm:pb-3" : ""}`}
    >
      {gain && <span className={`block font-bold leading-[1.45] text-ink text-pretty ${wide ? "text-[17px] sm:text-[19px]" : "text-[17px]"}`}>{gain}</span>}
      <span className={`${gain ? "mt-3" : ""} grid items-start gap-x-3.5 gap-y-3 ${wide ? "grid-cols-[96px_minmax(0,1fr)] sm:grid-cols-[168px_minmax(0,1fr)] sm:gap-x-6" : "grid-cols-[96px_minmax(0,1fr)]"}`}>
        <AdThumb item={item} className={wide ? "w-[96px] sm:row-span-2 sm:w-[168px]" : "w-[96px]"} />
        <span className="min-w-0 self-center">
          {/* 分類の1行（「ふるさと納税」など）は出さない。見出しと名前で分かる（2026-11-11 オーナー「文字ばっか」） */}
          <span className="block text-[16px] font-bold leading-snug text-ink group-hover:underline">{item.name}</span>
          <span className="mt-1 block empty:hidden">
            <Rating item={item} />
          </span>
          {price && <span className="mt-1 block text-[18px] font-bold tabular-nums text-ink">{price}</span>}
        </span>
        <span className={`col-span-2 block ${wide ? "sm:col-span-1 sm:col-start-2" : ""}`}>
          {/* 得のカード: 大きな数字（3つまで）と前後の比べ。数字のある広告は良いところの文を出さない（説明にしない。2026-11-10 オーナー） */}
          {benefit && numbers ? (
            <BenefitNumbers benefit={benefit} />
          ) : merits.length > 0 ? (
            <MeritList merits={merits} />
          ) : (
            point && <span className="block text-note leading-[1.6] text-ink-soft">{point}</span>
          )}
          {item.caution && <span className="mt-2 block text-meta leading-[1.6] text-muted">{item.caution}</span>}
          {item.imageNote && <span className="mt-2 block text-meta leading-[1.5] text-muted">{item.imageNote}</span>}
          {item.activeUntil && (
            <span className="mt-2 block text-meta font-bold text-ink-soft">
              販売終了予定：{new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit", hourCycle: "h23" }).format(new Date(item.activeUntil))}（変更の場合あり）
            </span>
          )}
          {/* ボタンは1つの囲みに1つだけ。下の「〇〇のサイトが開きます」の1行は出さない（2026-11-11 オーナー「文字ばっか」） */}
          <span className={`mt-3.5 flex ${wide ? "sm:block" : ""}`}>
            <span className={`pr-cta flex h-12 w-full items-center justify-center rounded-lg px-6 text-[15px] font-bold tracking-wide shadow-[0_2px_0_rgb(0_0_0/0.18)] transition-[filter,transform] group-hover:brightness-110 group-active:translate-y-px motion-reduce:transition-none ${wide ? "sm:inline-flex sm:w-auto sm:min-w-[17em]" : ""}`}>
              {ctaOf(item)}
            </span>
          </span>
        </span>
      </span>
    </a>
    {benefit && <BenefitFoot benefit={benefit} wide={wide} />}
    </>
  );
}

/** 得のカードの大きな数字（チップ）と、前と後の比べの棒。数字はすべて出典つき（lib/ad-benefits.ts が出典の無い数字を捨てる） */
export function BenefitNumbers({ benefit }: { benefit: Benefit }) {
  const max = Math.max(1, ...(benefit.compare?.rows.map((r) => r.value) ?? [1]));
  return (
    <span className="block">
      {benefit.chips.length > 0 && (
        <span className={`grid gap-2 ${benefit.chips.length >= 3 ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2"}`}>
          {benefit.chips.map((chip) => (
            <span key={`${chip.label}-${chip.value}`} className={`ad-chip block rounded-xl px-3 py-2.5 ${Array.from(chip.value).length > 7 ? "max-sm:col-span-2" : ""}`}>
              <span className="block text-meta font-bold leading-snug text-muted">{chip.label}</span>
              <span className={`mt-0.5 block font-black leading-tight tabular-nums text-ink ${Array.from(chip.value).length > 7 ? "text-[20px]" : "text-[20px] sm:text-[22px]"} whitespace-nowrap`}>{chip.value}</span>
              {chip.sub && <span className="mt-0.5 block text-[11px] leading-snug text-muted">{chip.sub}</span>}
            </span>
          ))}
        </span>
      )}
      {benefit.compare && (
        <span className="mt-3 block" aria-label={benefit.compare.label}>
          <span className="block text-meta font-bold text-ink-soft">{benefit.compare.label}</span>
          {benefit.compare.rows.map((row) => (
            <span key={row.name} className="mt-1.5 grid grid-cols-[5.5em_minmax(0,1fr)] items-center gap-2 text-meta">
              <span className="text-muted">{row.name}</span>
              <span className="flex items-center gap-2">
                <span aria-hidden="true" className="ad-bar block h-2.5 rounded-full" style={{ width: `${Math.max(6, (row.value / max) * 100)}%` }} />
                <span className="shrink-0 font-bold tabular-nums text-ink">{row.text}</span>
              </span>
            </span>
          ))}
        </span>
      )}
    </span>
  );
}

/** 得のカードの下: サイト内の案内（計算ツールなど。広告ではない）と、数字の出典・確認日（小さく1行） */
export function BenefitFoot({ benefit, wide }: { benefit: Benefit; wide: boolean }) {
  if (!benefit.link && benefit.sources.length === 0) return null;
  return (
    <span className={`block pb-3 ${wide ? "px-4 sm:px-6" : "px-4"}`}>
      {benefit.link && (
        <Link href={benefit.link.href} data-money-link="" className="block text-note font-bold text-ink underline decoration-line-strong underline-offset-4 hover:text-accent">
          {benefit.link.label}
        </Link>
      )}
      {benefit.sources.length > 0 && (
        <span className="mt-1 block text-[11px] leading-relaxed text-muted">
          出典・確認日：
          {benefit.sources.map((s, i) => (
            <span key={s.url}>
              {i > 0 && "／"}
              {s.url.startsWith("/") ? (
                <Link href={s.url} className="underline underline-offset-2">
                  {s.name}
                </Link>
              ) : (
                <a href={s.url} target="_blank" rel="noopener" className="underline underline-offset-2">
                  {s.name}
                </a>
              )}
              （{shortDay(s.checkedAt)}）
            </span>
          ))}
        </span>
      )}
    </span>
  );
}

function shortDay(iso: string): string {
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${Number(m[1])}/${Number(m[2])}` : iso;
}

/** PR の囲みの2つ目以降（小さく1行ずつ）。見出しの代わりに、確かめられること（gain）か向く人を1行 */
export function PrRow({ item, rank, onClick, price }: { item: OfferItem; rank: number; onClick?: () => void; price?: string }) {
  const line = item.pitch?.gain ?? (item.pitch?.fit ? `向く人：${item.pitch.fit}` : (item.pitch?.point ?? item.note));
  return (
    <a
      href={item.url}
      target="_blank"
      rel={AFFILIATE_REL}
      data-aff-rank={rank}
      onClick={onClick}
      className="group flex items-center gap-3 px-4 py-3 hover:bg-surface"
    >
      {/* 画像の無い商品・読み込めなかった画像は枠ごと出さない（空の白い枠にしない。2026-11-11） */}
      {item.image && <RowThumb src={item.image} className="w-16 rounded-md" />}
      <span className="min-w-0 flex-1">
        <span className="block text-note font-bold leading-snug text-ink group-hover:underline">{item.name}</span>
        {line && <span className="mt-0.5 block text-meta leading-snug text-ink-soft">{line}</span>}
        {price && <span className="mt-0.5 block text-note font-bold tabular-nums text-ink">{price}</span>}
        {/* 矢印の印は付けない（2026-11-09 オーナー）。押した先で分かることを文字で */}
        <span className="pr-link mt-1 block text-meta font-bold underline underline-offset-2">{ctaOf(item)}</span>
      </span>
    </a>
  );
}

/**
 * 囲みの2つ目以降のサイト（2026-11-11 オーナー「返礼品を探すボタンも2個あってどっちなんだ？違うふるさと納税なのかって思ったり」）。
 * 1つの囲みにボタンは1つ（PrFeature）。ほかの提携先は画像もボタンも付けず、小さな文字のリンクを1行に並べる「ほかのサイト：au PAY ふるさと納税」。
 * 分類が1つ目と違う商品（スマホの囲みのふるさと本舗など）だけ、名前のあとに分類を（）で添える。
 * リンクは rel=sponsored・data-aff-rank のまま（囲みの data-aff-pos で置き場所ごとに数える。components/AffClickTracker.tsx）
 */
export function OtherSites({
  items,
  first,
  onClick,
  className = "",
}: {
  items: OfferItem[];
  first?: OfferItem;
  onClick?: (item: OfferItem) => void;
  className?: string;
}) {
  if (items.length === 0) return null;
  return (
    <p data-other-sites="" className={`text-note leading-relaxed text-ink-soft ${className}`}>
      ほかのサイト：
      {items.map((item, index) => {
        const tag = item.label && item.label !== first?.label && !item.name.includes(item.label) ? `（${item.label}）` : "";
        return (
          <span key={item.key}>
            {index > 0 && "／"}
            <a
              href={item.url}
              target="_blank"
              rel={AFFILIATE_REL}
              data-aff-rank={index + 2}
              onClick={onClick ? () => onClick(item) : undefined}
              className="font-bold text-ink underline decoration-line-strong underline-offset-2 hover:decoration-ink"
            >
              {item.name}
            </a>
            {tag}
          </span>
        );
      })}
    </p>
  );
}

/**
 * 囲みの右上の小さな「PR」の札（ステマ規制の「広告であることが分かる表示」。大きくしない。2026-11-09 オーナー）。
 * 2026-11-10（台帳 W37）: 囲みの注記を外したので、塗りの札ではっきり示す。2026-11-11: 黒地に白（app/globals.css の .ad-pr。黄色・砂色は使わない）
 */
export function PrTag() {
  return <span className="ad-pr">PR</span>;
}
