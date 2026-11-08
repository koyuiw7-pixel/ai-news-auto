import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import { AFFILIATE_REL } from "@/lib/affiliate";
import { Pixels } from "@/components/rail/parts";

/**
 * 「すぐにできること」のすぐ下に置く PR の囲み（1記事に1つ。lib/action-ad.ts）。
 * 広告だと一目で分かるよう「PR・広告」を見出しに出し、名前と1行の説明（公式の名前と中立な説明）だけを並べる。
 * クリックは data-aff-pos="action-ad"（components/AffClickTracker.tsx → scripts/aff_stats.py）で、ほかの置き場所と分けて数える。
 */
export default function ActionAd({ ad, className = "mt-4" }: { ad: ActionAdData; className?: string }) {
  if (ad.items.length === 0) return null;
  return (
    <aside
      data-aff-pos="action-ad"
      data-action-ad={ad.key}
      aria-label="PR：広告"
      className={`relative max-w-[40em] rounded-2xl border border-line bg-surface p-4 sm:p-5 ${className}`}
    >
      <p className="flex items-center gap-2 text-meta font-bold text-muted">
        <span className="rounded border border-current px-1.5 tracking-wider">PR</span>
        広告・{ad.title}
      </p>
      <ul className="mt-3 grid gap-2.5">
        {ad.items.map(({ item }, index) => (
          <li key={item.key}>
            <a
              href={item.url}
              target="_blank"
              rel={AFFILIATE_REL}
              data-aff-rank={index + 1}
              className="group flex items-center justify-between gap-3 rounded-xl border border-line bg-paper px-4 py-3 transition-colors hover:border-accent"
            >
              <span className="min-w-0">
                <span className="block text-note font-bold text-ink group-hover:text-accent">{item.name}</span>
                {item.note && <span className="mt-0.5 block text-meta leading-relaxed text-muted">{item.note}</span>}
              </span>
              <span className="shrink-0 text-meta font-bold text-accent">{item.cta} →</span>
            </a>
          </li>
        ))}
      </ul>
      <p className="mt-2.5 text-meta leading-relaxed text-muted">
        ※ 広告（アフィリエイトリンク）です。申し込みがあると当サイトに紹介料が支払われることがあります。料金・条件は各公式サイトで確認してください。
      </p>
      <Pixels pixels={ad.items.map(({ pixel }) => pixel).filter((p): p is string => Boolean(p))} />
    </aside>
  );
}
