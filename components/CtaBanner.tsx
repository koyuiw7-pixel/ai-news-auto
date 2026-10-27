import { getCta, type CtaSlot } from "@/lib/monetization";

type Props = {
  genreSlug: string;
  slot: CtaSlot;
  className?: string;
};

/**
 * 収益導線。ジャンルごとに monetization.json から出し分ける。
 * URL が未設定（YOUR_ID のまま）なら何も描画しないので、誤リンクは公開されない。
 * アフィリエイト計測リンクなので rel="sponsored" と PR 表記を必ず付ける。
 */
export default function CtaBanner({ genreSlug, slot, className }: Props) {
  const cta = getCta(genreSlug, slot);
  if (!cta) return null;

  if (slot === "inline") return <InlineCta cta={cta} className={className} />;
  return <BlockCta cta={cta} className={className} compact={slot === "secondary"} />;
}

function BlockCta({
  cta,
  className,
  compact,
}: {
  cta: ReturnType<typeof getCta>;
  className?: string;
  compact?: boolean;
}) {
  if (!cta) return null;

  return (
    <section
      className={`relative overflow-hidden rounded-2xl border border-accent/25 bg-accent-soft ${
        compact ? "p-5" : "p-6 sm:p-8"
      } ${className ?? ""}`}
    >
      {cta.isAffiliate && (
        <span className="absolute right-3 top-3 rounded bg-surface/70 px-1.5 py-0.5 text-badge font-semibold text-muted">
          PR
        </span>
      )}

      {cta.eyebrow && <p className="eyebrow">{cta.eyebrow}</p>}

      <h2
        className={`display mt-2 pr-10 text-ink ${
          compact ? "text-[1.0625rem]" : "text-[1.25rem] sm:text-[1.4rem]"
        }`}
      >
        {cta.title}
      </h2>

      {cta.body && !compact && (
        <p className="mt-3 text-desc leading-[1.9] text-ink-soft">{cta.body}</p>
      )}

      <a
        href={cta.url}
        target="_blank"
        rel={
          cta.isAffiliate
            ? "sponsored noopener noreferrer"
            : "nofollow noopener noreferrer"
        }
        className={`mt-5 inline-flex items-center gap-2 rounded-md bg-accent font-bold text-accent-ink transition-transform hover:scale-[1.02] ${
          compact ? "px-5 py-2.5 text-meta" : "px-7 py-3.5 text-note"
        }`}
      >
        {cta.buttonLabel}
        <span aria-hidden>→</span>
      </a>

      {cta.note && (
        <p className="mt-3 text-meta text-muted">
          {cta.note}
          {cta.isAffiliate && "／当サイトは広告収入を得ています"}
        </p>
      )}
    </section>
  );
}

function InlineCta({
  cta,
  className,
}: {
  cta: ReturnType<typeof getCta>;
  className?: string;
}) {
  if (!cta) return null;

  return (
    <aside
      className={`flex flex-col gap-4 border-y-2 border-accent/30 py-5 sm:flex-row sm:items-center sm:justify-between ${
        className ?? ""
      }`}
    >
      <div className="min-w-0">
        {cta.isAffiliate && (
          <p className="text-meta font-bold tracking-widest text-muted">PR</p>
        )}
        <p className="mt-1 text-[15px] font-bold leading-[1.6] text-ink">
          {cta.title}
        </p>
        {cta.note && (
          <p className="mt-1 text-meta text-muted">{cta.note}</p>
        )}
      </div>

      <a
        href={cta.url}
        target="_blank"
        rel={
          cta.isAffiliate
            ? "sponsored noopener noreferrer"
            : "nofollow noopener noreferrer"
        }
        className="shrink-0 self-start rounded-md border-2 border-accent px-5 py-2.5 text-meta font-bold text-accent transition-colors hover:bg-accent hover:text-accent-ink sm:self-auto"
      >
        {cta.buttonLabel} →
      </a>
    </aside>
  );
}
