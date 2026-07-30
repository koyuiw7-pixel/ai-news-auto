import type { AffiliateLink } from "@/lib/articles";

type Props = {
  links: AffiliateLink[];
  compact?: boolean;
};

/**
 * 記事内で言及されたツールのアフィリエイトリンク。
 * Google の品質ガイドラインに従い rel="sponsored" を必ず付与し、PR表記を併記する。
 */
export default function AffiliateBox({ links, compact }: Props) {
  if (links.length === 0) return null;

  return (
    <section
      className={`rounded-2xl border border-ink-100 bg-white ${compact ? "p-5" : "p-6"}`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <h2 className={`font-bold text-ink-950 ${compact ? "text-sm" : "text-lg"}`}>
          この記事で紹介したツール
        </h2>
        <span className="shrink-0 rounded bg-ink-100 px-1.5 py-0.5 text-[10px] text-ink-500">
          PR
        </span>
      </div>

      <ul className={`mt-4 ${compact ? "space-y-2.5" : "space-y-3"}`}>
        {links.map((link) => (
          <li key={link.url}>
            <a
              href={link.url}
              target="_blank"
              rel="sponsored noopener noreferrer"
              className="group flex items-start gap-3 rounded-xl border border-ink-100 px-4 py-3 transition-colors hover:border-accent hover:bg-accent-soft/40"
            >
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-md bg-accent text-[11px] font-bold text-white">
                ↗
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-ink-950 group-hover:text-accent">
                  {link.label}
                </span>
                {link.note && (
                  <span className="mt-0.5 block text-xs leading-relaxed text-ink-500">
                    {link.note}
                  </span>
                )}
              </span>
            </a>
          </li>
        ))}
      </ul>

      <p className="mt-4 text-[11px] leading-relaxed text-ink-300">
        ※ 上記リンクはアフィリエイトリンクを含みます。リンク経由で申し込まれた場合、
        当サイトに紹介料が支払われることがあります。価格・提供条件は各公式サイトをご確認ください。
      </p>
    </section>
  );
}
