import Link from "next/link";
import type { MoneyTarget } from "@/lib/money-pages";

/**
 * 記事の要点のすぐ下の1行「自分は対象か確かめる → …」（2026-11-10 M2。行き先は lib/money-pages.ts）。
 * 囲みは作らない1行の内部リンク。広告ではないので PR の印（data-aff-pos・rel="sponsored"）は付けない。
 * data-money-link は読まれ方の記録（components/ReadingBeacon.tsx）で「押した場所」を money として数えるための印
 */
export default function MoneyCheckLink({ target, className = "" }: { target: MoneyTarget | undefined; className?: string }) {
  if (!target) return null;
  return (
    <p className={`text-note ${className}`}>
      <Link
        href={target.href}
        data-money-link=""
        className="font-bold text-ink underline decoration-accent underline-offset-4 hover:text-accent"
      >
        自分は対象か確かめる → {target.label}
      </Link>
    </p>
  );
}
