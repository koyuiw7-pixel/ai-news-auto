import { AFFILIATE_REL } from "@/lib/affiliate";
import type { ShopLink } from "@/lib/amazon";

/** 記事の製品を Amazon / 楽天 の検索で見る1行（価格・画像は出さない。PR は小さく明示） */
export default function ShopLinks({ link, className = "" }: { link: ShopLink; className?: string }) {
  return (
    <p data-aff-pos="shop-line" className={`max-w-[40em] text-note leading-relaxed text-ink-soft ${className}`}>
      <span className="font-bold text-ink">{link.name}</span>を
      <a href={link.amazon} target="_blank" rel={AFFILIATE_REL} className="mx-1 text-accent underline underline-offset-4">
        Amazonで見る
      </a>
      /
      <a href={link.rakuten} target="_blank" rel={AFFILIATE_REL} className="mx-1 text-accent underline underline-offset-4">
        楽天で見る
      </a>
      <span className="text-muted">（PR）</span>
    </p>
  );
}
