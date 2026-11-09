import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import type { OfferItem } from "@/lib/offers";
import { AFFILIATE_REL } from "@/lib/affiliate";
import { Pixels } from "@/components/rail/parts";

/**
 * 「すぐにできること」のすぐ下に置く、編集部の言葉で書いた PR の囲み（1記事に1つ。lib/action-ad.ts）。
 *
 * 2026-11-09 オーナー「PRさ、もっと上手くできないかな？これ売れるのかな？」「PRってこんな大きく書いてる？みんな」:
 *  - 黒い見出しの帯（「PR 広告・紹介」を大きく）をやめ、本文と同じ白地の囲みにする。広告の表示は右上の小さな「PR」の札と、
 *    囲みの下の注記（ステマ規制の「広告であることが分かる表示」。サイト全体の「本ページはプロモーションを含みます」もある）
 *  - 見出しは記事の困りごとから商品へつなぐ一文（ad.lead。例: 停電の夜に困るのは、灯りとスマホの充電です）
 *  - 1つ目を大きく（写真・向く人・特徴・押した先で分かることを書いたボタン）、残り2つは小さな比べ表（向く人・特徴）
 *  - 特徴は公式の情報の範囲だけ（scripts/a8_import.py の PITCH）。価格・容量など、手元に確かな数字が無いものは書かない
 * バナーは縦横比 6:5 の場所を先に取り、読み込みで画面がずれない。ポップアップは出さない。
 * クリックは data-aff-pos="action-ad"（components/AffClickTracker.tsx → cloudflare/aff.ts の byPlacement）で、置き場所×提携先ごとに数える。
 */
export default function ActionAd({ ad, className = "mt-4" }: { ad: ActionAdData; className?: string }) {
  if (ad.items.length === 0) return null;
  const [first, ...rest] = ad.items;
  const lead = ad.lead ?? ad.reason;
  return (
    <aside
      data-aff-pos="action-ad"
      data-action-ad={ad.key}
      aria-label="PR：広告"
      className={`relative max-w-[40em] rounded-2xl border border-line bg-paper p-4 shadow-[0_1px_2px_rgb(11_26_51/0.04)] sm:p-5 ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-meta font-bold text-accent">{ad.title}</p>
        <span className="shrink-0 rounded-sm border border-line-strong px-1.5 text-[11px] leading-[18px] font-semibold tracking-wider text-muted">PR</span>
      </div>
      {lead && <p className="mt-1.5 text-desc font-bold leading-[1.7] text-ink">{lead}</p>}

      <FeaturedCard item={first.item} />

      {rest.length > 0 && (
        <div className="mt-4">
          <p className="text-meta font-bold text-ink-soft">ほかの選び方</p>
          <ul className="mt-2 divide-y divide-line overflow-hidden rounded-xl border border-line">
            {rest.map(({ item }, index) => (
              <li key={item.key}>
                <CompareRow item={item} rank={index + 2} />
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-muted">
        広告（アフィリエイトリンク）を含みます。申し込みがあると当サイトに紹介料が入ることがあります。料金・条件は各公式サイトで確認してください。
      </p>
      <Pixels pixels={ad.items.map(({ pixel }) => pixel).filter((p): p is string => Boolean(p))} />
    </aside>
  );
}

const ctaOf = (item: OfferItem) => item.pitch?.cta ?? (item.cta === "公式サイトで見る" ? "料金と条件を見る" : item.cta);
const pointOf = (item: OfferItem) => item.pitch?.point ?? item.note;

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

function FeaturedCard({ item }: { item: OfferItem }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel={AFFILIATE_REL}
      data-aff-rank={1}
      className="group mt-3.5 grid grid-cols-[112px_minmax(0,1fr)] items-start gap-3.5 rounded-xl bg-surface p-3 sm:grid-cols-[168px_minmax(0,1fr)] sm:gap-5 sm:p-4"
    >
      <Banner item={item} className="w-full rounded-lg border border-line" />
      <span className="min-w-0">
        {item.label && <span className="block text-[12px] font-bold text-accent">{item.label}</span>}
        <span className="mt-0.5 block text-[16px] font-bold leading-snug text-ink group-hover:underline">{item.name}</span>
        {item.pitch?.fit && (
          <span className="mt-2 block text-note leading-[1.6] text-ink-soft">
            <span className="mr-1.5 rounded-sm bg-paper px-1.5 py-0.5 text-[11px] font-bold text-ink">向く人</span>
            {item.pitch.fit}
          </span>
        )}
        {pointOf(item) && <span className="mt-1.5 block text-note leading-[1.6] text-ink-soft">{pointOf(item)}</span>}
        <span className="mt-3 hidden h-11 items-center justify-center gap-1 rounded-lg bg-accent px-6 text-note font-bold text-accent-ink transition-opacity group-hover:opacity-90 sm:inline-flex">
          {ctaOf(item)}
        </span>
      </span>
      {/* スマホは写真の横が狭いので、ボタンは囲みの幅いっぱいに */}
      <span className="col-span-2 flex h-11 items-center justify-center gap-1 rounded-lg bg-accent text-note font-bold text-accent-ink sm:hidden">
        {ctaOf(item)}
      </span>
    </a>
  );
}

function CompareRow({ item, rank }: { item: OfferItem; rank: number }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel={AFFILIATE_REL}
      data-aff-rank={rank}
      className="group grid grid-cols-[56px_minmax(0,1fr)] items-center gap-x-3 gap-y-1 bg-paper px-3 py-2.5 hover:bg-surface sm:grid-cols-[56px_minmax(0,1fr)_auto]"
    >
      <Banner item={item} className="w-14 rounded-md border border-line" />
      <span className="min-w-0">
        <span className="block text-note font-bold leading-snug text-ink group-hover:underline">{item.name}</span>
        {item.pitch?.fit ? (
          <span className="mt-0.5 block text-meta leading-snug text-ink-soft">向く人：{item.pitch.fit}</span>
        ) : (
          pointOf(item) && <span className="mt-0.5 block text-meta leading-snug text-ink-soft">{pointOf(item)}</span>
        )}
      </span>
      {/* 矢印の印は付けない（2026-11-09 オーナー「→みたいな印はいらない」）。押した先で分かることを文字で書く */}
      <span className="col-span-2 -mt-1 text-meta font-bold text-accent underline underline-offset-2 sm:col-span-1 sm:mt-0 sm:no-underline">{ctaOf(item)}</span>
    </a>
  );
}
