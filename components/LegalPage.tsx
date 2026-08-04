import type { ReactNode } from "react";

/** 運営者情報・規約系ページの共通レイアウト */
export default function LegalPage({
  eyebrow,
  title,
  lead,
  updatedAt,
  children,
}: {
  eyebrow: string;
  title: string;
  lead?: string;
  updatedAt: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="display mt-2 text-[1.75rem] sm:text-[2.25rem]">{title}</h1>
      {lead && (
        <p className="mt-5 border-l-[3px] border-accent pl-4 text-[15px] leading-[1.9] text-ink-soft">
          {lead}
        </p>
      )}
      <p className="index-num mt-6 text-[11px] text-muted">
        最終更新: {updatedAt}
      </p>

      <div className="prose mt-10 max-w-none">{children}</div>
    </div>
  );
}
