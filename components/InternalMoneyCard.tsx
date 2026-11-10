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
    // 2026-11-11 オーナー「文字ばっか」: 「サイソクの案内」の小見出しは出さず（読み上げ用の名前に残す）、ふつうの文字のリンクだけ。矢印は付けない
    <div data-internal-card="" role="group" aria-label="サイソクの案内" className={`px-4 py-2.5 sm:px-6 ${className}`}>
      <ul className="grid gap-1">
        {links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="text-note font-bold leading-snug text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
