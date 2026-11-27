import Link from "next/link";

/**
 * 記事・計算ツールから特集（/stories/<slug>。lib/flagship.ts）への案内。広告ではないので PR の印は付けない。
 * 矢印の印は付けない（2026-11-09 オーナー「→みたいな印はいらない」）
 */
export default function FlagshipLink({ target, note, className = "" }: { target: { href: string; title: string } | undefined; note?: string; className?: string }) {
  if (!target) return null;
  return (
    <Link
      href={target.href}
      data-flagship-link=""
      data-money-link=""
      className={`group block max-w-[40em] rounded-xl border border-line-strong bg-paper px-4 py-3 no-underline hover:border-accent ${className}`}
    >
      <span className="block text-meta font-bold text-signal">計算つきの特集</span>
      <span className="mt-1 block text-desc font-bold leading-snug text-ink group-hover:text-accent group-hover:underline">{target.title}</span>
      <span className="mt-1 block text-note leading-[1.7] text-ink-soft">{note ?? "子どもの年齢を入れると、うちの児童手当と次の支給がその場で分かります。"}</span>
    </Link>
  );
}
