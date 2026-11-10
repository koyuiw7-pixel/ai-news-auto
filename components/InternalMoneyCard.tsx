import Link from "next/link";
import type { MoneyTarget } from "@/lib/money-pages";

/**
 * PR の囲みの中に出す、サイト内のお金のページへの案内（「サイソクの案内」。2026-11-10 M3）。
 * 広告ではないので rel=sponsored・data-aff-rank を付けない（人によるクリックの計測 components/AffClickTracker.tsx は sponsored のリンクだけを数える）。
 * 行き先は lib/money-pages.ts の表だけ。
 */
export default function InternalMoneyCard({ links, className = "" }: { links: MoneyTarget[]; className?: string }) {
  if (links.length === 0) return null;
  return (
    <div data-internal-card="" className={`px-4 py-3 sm:px-6 ${className}`}>
      <p className="text-badge font-bold tracking-wider text-muted">サイソクの案内</p>
      <ul className="mt-1 grid gap-1">
        {links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="text-desc font-bold leading-snug text-accent underline decoration-line-strong underline-offset-4 hover:decoration-accent">
              {link.label}
              <span aria-hidden className="ml-1">→</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
