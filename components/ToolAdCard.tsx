import type { OfferItem } from "@/lib/offers";
import { AFFILIATE_REL } from "@/lib/affiliate";
import type { ToolAdCopy } from "@/lib/tool-ad";
import { AdThumb, Pixels, PrTag } from "@/components/rail/parts";

/**
 * 計算ツールの結果のすぐ下の PR、見た目 B（lib/tool-ad.ts。A/B は <html data-adv="b"> の人だけに見せる。app/globals.css の .tad-b）。
 * 囲みは今までと同じ白地に黒の細い枠・右上の小さな「PR」の札（ステマ規制の表示）。リンクは rel="sponsored"。
 * 中身: 提携先の名前（小さく）、小さなバナー（6:5）と見出し・1行、ボタン1つ。囲み全体が1つのリンク（ボタンは1つ）。
 * 出典の行・2つ目の提携先の行は出さない（数字の出典は lib/tool-ad.ts と content/ad_benefits.json に残す）。
 * 計算ツールのページ（components/calc/ToolPage.tsx）では、B の人だけ計算の結果のすぐ下（注記より前）に並べ替える。
 */
export default function ToolAdCard({ item, copy, pos, tool, pixels = [] }: { item: OfferItem; copy: ToolAdCopy; pos: string; tool?: string; pixels?: string[] }) {
  return (
    <aside data-aff-pos={pos} data-ad-ab="" data-tool-ad="b" data-tool={tool} aria-label="PR：広告" className="ad-box tad-b relative mt-5 max-w-[40em] overflow-hidden">
      <a href={item.url} target="_blank" rel={AFFILIATE_REL} data-aff-rank={1} className="tad-link group">
        <span className="tad-top">
          <span className="tad-sponsor">{item.name.replace(/[（(][^）)]*[）)]/g, "").trim()}</span>
          <PrTag />
        </span>
        <span className="tad-body">
          <AdThumb item={item} className="tad-thumb" />
          <span className="min-w-0">
            <span className="tad-head">{copy.headline}</span>
            <span className="tad-line">{copy.line}</span>
          </span>
        </span>
        <span className="pr-cta tad-cta">{copy.cta}</span>
      </a>
      <Pixels pixels={pixels} />
    </aside>
  );
}
