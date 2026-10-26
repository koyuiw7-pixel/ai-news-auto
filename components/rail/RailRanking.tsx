import type { Offer } from "@/lib/offers";
import RankingBody from "./RankingBody";
import { Pixels, PrNote } from "./parts";

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
}: {
  offer: Offer;
  wide?: boolean;
  id?: string;
  /** 見出し。右側と本文中で同じ見出しが並ばないよう、本文中では変える */
  title?: string;
  /** 同じ枠をページ内に2回出すとき、表示の計測を二重にしないよう片方は false にする */
  countImpression?: boolean;
}) {
  // 本文中の枠は右側の「イチオシ」と並ぶので、1位の札を変える
  const badge = title ? "注目" : "イチオシ";
  const hasBook = offer.items.some((i) => i.kind === "book");

  return (
    <aside id={id} aria-label="PR：サイソクのおすすめ" className="relative overflow-hidden rounded-2xl border border-ink bg-paper">
      <Header offer={offer} wide={wide} title={title ?? `サイソクのおすすめ${Math.min(3, offer.items.length)}選`} />

      <RankingBody items={offer.items} visible={3} wide={wide} badge={badge} />

      <div className="border-t border-line bg-surface px-4 py-2.5">
        <PrNote checkedAt={offer.checkedAt} hasBook={hasBook} />
      </div>
      {countImpression && <Pixels pixels={offer.pixels} />}
    </aside>
  );
}

function Header({ offer, wide, title }: { offer: Offer; wide: boolean; title: string }) {
  return (
    <div className={`bg-ink text-paper ${wide ? "px-5 py-4 sm:px-6" : "px-4 py-3.5"}`}>
      <p className="flex items-center gap-2 text-[11px] font-bold opacity-75">
        <span className="rounded border border-current px-1.5 text-[10px] tracking-wider">PR</span>
        {offer.eyebrow}
      </p>
      <p className={`font-display mt-1.5 leading-snug ${wide ? "text-[22px]" : "text-[19px]"}`}>
        {title}
      </p>
      <p className="mt-1 text-[12.5px] leading-snug opacity-85">{offer.headline}</p>
    </div>
  );
}

