import Link from "next/link";
import type { ReactNode } from "react";

/**
 * 早見表・週まとめ・イベントの3ページの外枠。
 * 書体はサイト共通の Noto Sans JP（docs/typography.md）。以前は細い Zen Kaku を避けて OS の書体にしていたが、
 * Windows では細い游ゴシックになるため共通の書体に戻した。
 */
export const CALM_FONT = "var(--font-sans)";

export default function AssetShell({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <div
      className={`mx-auto px-4 py-8 sm:px-8 sm:py-12 ${wide ? "max-w-[1120px]" : "max-w-[860px]"}`}
      style={{ fontFamily: CALM_FONT, fontFeatureSettings: '"palt" 1' }}
    >
      {children}
    </div>
  );
}

/** パンくず（ホーム / 親 / 今のページ） */
export function Crumbs({ items }: { items: { href?: string; label: string }[] }) {
  return (
    <nav aria-label="パンくず" className="flex flex-wrap items-center gap-1.5 text-meta text-muted">
      {items.map((item, index) => (
        <span key={item.label} className="flex items-center gap-1.5">
          {index > 0 && <span aria-hidden>/</span>}
          {item.href ? (
            <Link href={item.href} className="hover:text-ink hover:underline">
              {item.label}
            </Link>
          ) : (
            <span className="text-ink-soft">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

/** 疑問形の見出し（読みやすさの規則: 見出しは読者の問いにする） */
export function QHeading({ id, children, note }: { id: string; children: ReactNode; note?: ReactNode }) {
  return (
    <div className="mb-5 border-b border-line-strong pb-2.5">
      <h2 id={id} className="t-h2">
        {children}
      </h2>
      {note && <p className="mt-1 text-note leading-relaxed text-muted">{note}</p>}
    </div>
  );
}
