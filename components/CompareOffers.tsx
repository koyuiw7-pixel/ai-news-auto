import { AFFILIATE_REL } from "@/lib/affiliate";
import type { CompareOffer } from "@/lib/comparison";
import { Pixels } from "@/components/rail/parts";

/**
 * 比較記事（kind: "comparison"）の提携先の一覧（lib/comparison.ts の compareOffersFor）。
 * 置き場所は判断が終わった場所: ①本文の最初の比較表の直後（pos="compare-table"） ②記事の終わり（pos="compare-end"）。
 * 1行ごとに 名前・短い説明・向く人（あれば）・「公式サイトで見る」（A8 のリンク・rel="sponsored nofollow"）。
 * 広告だと一目で分かるよう見出しに「PR」を出し、計測ピクセルは表の直後の1回だけ数える（同じページで二重に数えない）。
 * クリックは data-aff-pos（components/AffClickTracker.tsx → scripts/aff_stats.py）で置き場所ごとに数える。
 */
export default function CompareOffers({
  offers,
  pos,
  countImpression = true,
  className = "my-8",
}: {
  offers: { topic: string; title: string; items: CompareOffer[] };
  pos: "compare-table" | "compare-end";
  countImpression?: boolean;
  className?: string;
}) {
  if (offers.items.length === 0) return null;
  return (
    <aside
      data-aff-pos={pos}
      data-compare-topic={offers.topic}
      aria-label="PR：広告"
      className={`relative max-w-[46em] rounded-2xl border border-line-strong bg-surface p-4 sm:p-5 ${className}`}
    >
      <p className="flex items-center gap-2 text-meta font-bold text-muted">
        <span className="rounded border border-current px-1.5 tracking-wider">PR</span>
        {pos === "compare-table" ? "比べた候補の公式サイト" : "申し込みは公式サイトで"}
      </p>
      <ul className="mt-3 grid gap-2.5">
        {offers.items.map(({ item, fit }, index) => (
          <li key={item.key} className="grid gap-3 rounded-xl border border-line bg-paper p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4">
            <span className="min-w-0">
              <span className="block text-desc font-bold text-ink">{item.name}</span>
              {item.label && <span className="mt-0.5 block text-meta font-bold text-muted">{item.label}</span>}
              {item.note && <span className="mt-1 block text-note leading-relaxed text-ink-soft">{item.note}</span>}
              {fit && (
                <span className="mt-1.5 block text-note leading-relaxed text-ink">
                  <b className="mr-1">向く人</b>
                  {fit}
                </span>
              )}
              {item.caution && <span className="mt-1 block text-meta leading-relaxed text-muted">※ {item.caution}</span>}
            </span>
            <a
              href={item.url}
              target="_blank"
              rel={AFFILIATE_REL}
              data-aff-rank={index + 1}
              className="inline-flex w-full items-center justify-center rounded-lg bg-accent px-4 py-2.5 text-note font-bold text-accent-ink hover:opacity-90 sm:w-auto"
            >
              公式サイトで見る
            </a>
          </li>
        ))}
      </ul>
      <p className="mt-2.5 text-meta leading-relaxed text-muted">
        ※ 広告（アフィリエイトリンク）です。申し込みがあると当サイトに紹介料が支払われることがあります。並びは記事の評価ではありません。料金・条件は各公式サイトで確認してください。
      </p>
      {countImpression && <Pixels pixels={offers.items.map(({ pixel }) => pixel).filter((p): p is string => Boolean(p))} />}
    </aside>
  );
}
