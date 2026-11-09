import type { Offer } from "@/lib/offers";
import RankingBody from "./RankingBody";
import { Pixels, PrNote } from "./parts";
import TimedPixels from "./TimedPixels";

/**
 * 「サイソクのおすすめ3選」。記事の文脈に合う商品を番号つきで並べ、1位を大きく推す。
 * wide は本文中（横長）、それ以外は右側の縦長。どちらも中身は同じ。
 */
export default function RailRanking({
  offer,
  wide = false,
  id,
  title,
  countImpression = true,
  pos,
  visible = 3,
}: {
  offer: Offer;
  wide?: boolean;
  id?: string;
  /** 見出し。右側と本文中で同じ見出しが並ばないよう、本文中では変える */
  title?: string;
  /** 同じ枠をページ内に2回出すとき、表示の計測を二重にしないよう片方は false にする */
  countImpression?: boolean;
  /** クリックの置き場所の名前（data-aff-pos）。既定は本文中なら ranking-inline、右側なら ranking-rail。記事末のスマホ用は ranking-end */
  pos?: string;
  /** 見せる商品の数（ノワールの記事の本文の列は2つ。2026-11-10 オーナー承認「PR は小さく」） */
  visible?: number;
}) {
  // 掲載順は閲覧履歴で変わるため、順位や実機評価に基づく「イチオシ」とは言わない。
  const badge = "紹介";
  const hasBook = offer.items.some((i) => i.kind === "book");

  return (
    <aside id={id} data-aff-pos={pos ?? (wide ? "ranking-inline" : "ranking-rail")} aria-label="PR：広告・紹介" className="relative overflow-hidden rounded-2xl border border-line bg-paper">
      <Header offer={offer} wide={wide} title={title ?? offer.headline} />

      <RankingBody items={offer.items} visible={visible} wide={wide} badge={badge} />

      <div className="border-t border-line bg-surface px-4 py-2.5">
        <PrNote checkedAt={offer.checkedAt} hasBook={hasBook} />
      </div>
      {countImpression && <><Pixels pixels={offer.pixels} /><TimedPixels enabled={process.env.VERCEL_ENV === "production"} pixels={offer.timedPixels ?? []} /></>}
    </aside>
  );
}

function Header({ offer, wide, title }: { offer: Offer; wide: boolean; title: string }) {
  // 2026-11-09 オーナー「PRってこんな大きく書いてる？みんな」: 黒い帯に大きな「PR 広告・紹介」をやめ、白地の見出し＋右上の小さな「PR」の札にする。
  // 広告であることは札・aria-label・枠の下の注記で示す（ステマ規制の表示は残す）
  return (
    <div className={`flex items-start justify-between gap-3 border-b border-line ${wide ? "px-5 pt-4 pb-3.5 sm:px-6" : "px-4 pt-3.5 pb-3"}`}>
      <div className="min-w-0">
        <p className={`font-bold leading-snug text-ink ${wide ? "text-[18px]" : "text-[16px]"}`}>{title}</p>
        {title !== offer.headline && <p className="mt-0.5 text-meta leading-snug text-ink-soft">{offer.headline}</p>}
      </div>
      <span className="mt-0.5 shrink-0 rounded-sm border border-line-strong px-1.5 text-[11px] leading-[18px] font-semibold tracking-wider text-muted">PR</span>
    </div>
  );
}
