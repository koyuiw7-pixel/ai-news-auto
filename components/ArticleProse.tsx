import type { ReactNode } from "react";
import { CALC_SLOT } from "@/lib/charts";
import { PRICE_SLOT } from "@/lib/price-slot";
import { COMPARE_SLOT } from "@/lib/compare-slot";

/**
 * 記事本文の HTML。計算機の置き場所の印（lib/charts.ts の CALC_SLOT）があれば、そこで本文を分けて計算機を挟む。
 * 印が無ければ今までどおり1つの <article> を出す。
 */
export default function ArticleProse({
  html,
  className,
  slot,
  priceSlot,
  compareSlot,
}: {
  html: string;
  className: string;
  slot?: ReactNode;
  /** 料金の章の最新の料金表（lib/price-slot.ts の PRICE_SLOT の位置に挟む） */
  priceSlot?: ReactNode;
  /** 比較記事の提携先の一覧（lib/comparison.ts の COMPARE_SLOT＝最初の比較表の直後に挟む） */
  compareSlot?: ReactNode;
}) {
  const compareAt = compareSlot ? html.indexOf(COMPARE_SLOT) : -1;
  if (compareAt >= 0) {
    const before = html.slice(0, compareAt);
    const after = html.slice(compareAt + COMPARE_SLOT.length);
    return (
      <>
        {before.trim() && <ArticleProse html={before} className={className} slot={slot} priceSlot={priceSlot} />}
        {compareSlot}
        {after.trim() && <ArticleProse html={after} className={className.replace(/\bmt-\d+\b/, "")} slot={slot} priceSlot={priceSlot} />}
      </>
    );
  }
  html = html.replace(COMPARE_SLOT, "");
  const priceAt = priceSlot ? html.indexOf(PRICE_SLOT) : -1;
  if (priceAt >= 0) {
    const before = html.slice(0, priceAt);
    const after = html.slice(priceAt + PRICE_SLOT.length);
    return (
      <>
        {before.trim() && <ArticleProse html={before} className={className} slot={slot} />}
        {priceSlot}
        {after.trim() && <ArticleProse html={after} className={className.replace(/\bmt-\d+\b/, "")} slot={slot} />}
      </>
    );
  }
  html = html.replace(PRICE_SLOT, "");
  const at = slot ? html.indexOf(CALC_SLOT) : -1;
  if (at < 0) return <article className={className} dangerouslySetInnerHTML={{ __html: html.replace(CALC_SLOT, "") }} />;
  const before = html.slice(0, at);
  const after = html.slice(at + CALC_SLOT.length);
  return (
    <>
      <article className={className} dangerouslySetInnerHTML={{ __html: before }} />
      {slot}
      {after.trim() && <article className={className.replace(/\bmt-\d+\b/, "")} dangerouslySetInnerHTML={{ __html: after }} />}
    </>
  );
}
