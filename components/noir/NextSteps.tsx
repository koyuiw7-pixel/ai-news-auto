import Link from "next/link";
import { getArticleSummary } from "@/lib/articles";
import { displayHeadline } from "@/lib/headline";
import type { NextStepsEntry } from "@/lib/next-steps";

/**
 * よく読まれる記事の「あなたは対象？」と「次にやること」（content/next_steps.json。2026-11-10 オーナー承認: 2ページ目に進む割合を上げる）。
 * 文は記事・リンク先の記事にある公式の事実だけ。リンク先が無い（取り下げた）記事の項目は出さない。
 * 矢印などの印は付けない（オーナー）。押した場所は components/ReadingBeacon.tsx が "story"（この話の続き）と同じく数える。
 */
type Check = NonNullable<NextStepsEntry["check"]>;

const hrefOf = (x: { slug?: string; href?: string }) =>
  x.slug ? (getArticleSummary(x.slug) ? `/articles/${x.slug}` : undefined) : x.href;

export function TargetCheck({ check }: { check: Check }) {
  return (
    <section aria-labelledby="target-check-heading" data-read-zone="story" className="nr-check my-8 max-w-[40em] rounded-2xl border-2 border-ink p-5">
      <h2 id="target-check-heading" className="text-desc font-bold leading-snug text-ink">
        {check.title}
      </h2>
      {check.note && <p className="mt-1 text-meta leading-relaxed text-muted">{check.note}</p>}
      <ul className="mt-3 grid gap-2.5">
        {check.items.map((item) => {
          const href = hrefOf(item);
          return (
            <li key={item.text} className="grid grid-cols-[18px_1fr] gap-2.5">
              <span aria-hidden className="mt-[5px] size-[15px] rounded-[3px] border-2 border-ink-soft" />
              <span className="text-desc leading-[1.65] text-ink">
                {item.text}
                {href && item.link && (
                  <>
                    {" "}
                    <Link href={href} className="whitespace-nowrap text-note font-bold text-accent underline underline-offset-4">
                      {item.link}
                    </Link>
                  </>
                )}
              </span>
            </li>
          );
        })}
      </ul>
      {check.branch && hrefOf(check.branch) && (
        <p className="mt-3.5 border-t border-line pt-3 text-note">
          <Link href={hrefOf(check.branch)!} className="font-bold text-ink underline underline-offset-4">
            {check.branch.text}
          </Link>
        </p>
      )}
    </section>
  );
}

export function NextStepsBox({ steps }: { steps: NonNullable<NextStepsEntry["next"]> }) {
  const rows = steps
    .map((s) => ({ ...s, article: getArticleSummary(s.slug) }))
    .filter((s): s is typeof s & { article: NonNullable<typeof s.article> } => Boolean(s.article))
    .slice(0, 3);
  if (rows.length === 0) return null;
  return (
    <section aria-labelledby="next-steps-heading" data-read-zone="story" className="nr-steps mt-12 max-w-[40em]">
      <h2 id="next-steps-heading" className="t-h2">
        次にやること
      </h2>
      <ol className="mt-4 grid gap-3">
        {rows.map((row, i) => (
          <li key={row.slug}>
            <Link href={`/articles/${row.slug}`} className="group grid grid-cols-[28px_1fr] gap-3 rounded-2xl border border-line-strong p-4 hover:border-ink">
              <span className="index-num grid size-7 place-items-center rounded-full bg-ink text-meta font-semibold text-paper">{i + 1}</span>
              <span className="min-w-0">
                <span className="block text-desc font-bold leading-snug text-ink">{row.step}</span>
                <span className="mt-1 block text-note leading-snug text-ink-soft group-hover:underline">{displayHeadline(row.article.title)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
