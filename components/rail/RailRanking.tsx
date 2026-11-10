import type { Offer } from "@/lib/offers";
import RankingBody from "./RankingBody";
import { Pixels, PrNote, PrTag } from "./parts";
import TimedPixels from "./TimedPixels";
import InternalMoneyCard from "@/components/InternalMoneyCard";

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
  const hasBook = offer.items.some((i) => i.kind === "book");
  const heading = title ?? offer.headline;

  return (
    <aside
      id={id}
      data-aff-pos={pos ?? (wide ? "ranking-inline" : "ranking-rail")}
      data-ad-ab=""
      aria-label="PR：広告・紹介"
      className="ad-box relative overflow-hidden rounded-2xl border border-line"
    >
      <Header text={heading} wide={wide} />

      <RankingBody items={offer.items} visible={visible} wide={wide} />

      {/* 枠の話題に合うサイト内のお金のページ（例: 児童手当の記事 → ふるさと納税の上限額の計算。lib/offers.ts の money。広告ではない） */}
      {offer.money && <InternalMoneyCard links={[offer.money]} className="border-t border-line" />}

      {/* 価格・評価を出す枠だけ、その時点の1行（広告の長い注記は出さない。2026-11-10 オーナー決定・台帳 W37） */}
      {hasBook && (
        <div className="border-t border-line px-4 py-2">
          <PrNote checkedAt={offer.checkedAt} hasBook={hasBook} />
        </div>
      )}
      {countImpression && <><Pixels pixels={offer.pixels} /><TimedPixels enabled={process.env.VERCEL_ENV === "production"} pixels={offer.timedPixels ?? []} /></>}
    </aside>
  );
}

/**
 * 枠の上の1行。この枠の話題（offer.headline。本文中は別の見出し）を小さく、右上に小さな「PR」の札。
 * 2026-11-10 オーナー「広告が魅力的じゃない」: 大きな見出しは、話題の一般論（「スマホの回線は、乗り換えで料金と条件を比べられる」）ではなく、
 * 1つ目の商品で読者が確かめられること（pitch.gain。RankingBody → PrFeature）にした。
 * 2つの話題が並ぶ枠でも見出しは商品ごとなので、見出しと商品がずれない（2026-11-10 チームの点検: 「子どもの学び…」の見出しにふるさと納税が出ていた）
 * 広告であることは札・aria-label・砂色の枠で示す（ステマ規制の表示は残す。枠の下の長い注記は 2026-11-10 に外した・台帳 W37）
 */
function Header({ text, wide }: { text: string; wide: boolean }) {
  return (
    <div className={`ad-head flex items-center justify-between gap-3 border-b border-line ${wide ? "px-4 py-2.5 sm:px-6" : "px-4 py-2.5"}`}>
      <p className="min-w-0 text-meta font-bold leading-snug text-ink-soft">{text}</p>
      <PrTag />
    </div>
  );
}
