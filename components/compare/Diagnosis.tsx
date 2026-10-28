"use client";

import { useId, useMemo, useState } from "react";

export type DiagnosisProduct = {
  key: string;
  name: string;
  maker?: string;
  category?: string;
  image?: string | null;
  price: string;
  priceNote?: string;
  bestFor: string;
  sponsored: boolean;
  url: string;
  fit: Record<string, string[]>;
};

type Question = { key: string; label: string; options: { value: string; label: string }[] };

/**
 * C：3つの質問で絞り込む診断。答えは端末の中だけで計算し、どこにも送らない。
 * 点数は「公式の記載で対応している場面・予算・端末」に当てはまるかだけで決める（評価点ではない）。
 */
export default function Diagnosis({ quiz, products }: { quiz: Question[]; products: DiagnosisProduct[] }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const baseId = useId();
  const answered = Object.keys(answers).length;

  const ranked = useMemo(() => {
    if (answered === 0) return [];
    return products
      .map((product) => {
        let score = 0;
        const matched: string[] = [];
        const missed: string[] = [];
        for (const question of quiz) {
          const value = answers[question.key];
          if (!value) continue;
          const label = question.options.find((o) => o.value === value)?.label ?? value;
          const fits = product.fit[question.key] ?? [];
          if (fits.includes(value)) {
            score += question.key === "use" ? 3 : 2;
            // 「0円で」と答えた人には、無料枠ではなく完全に無料のものを少しだけ優先する
            if (question.key === "budget" && value === "free" && fits.length === 1) score += 1;
            matched.push(label);
          } else {
            // 専用端末でしか動かないもの（iPhone標準・Pixel標準）を他の端末の人に出さない
            const hardMiss = question.key === "platform" && fits.length === 1;
            const budgetMiss = question.key === "budget" && value === "free";
            score -= hardMiss ? 8 : budgetMiss ? 4 : 1;
            missed.push(label);
          }
        }
        return { product, score, matched, missed };
      })
      .sort((a, b) => b.score - a.score);
  }, [answers, answered, products, quiz]);

  const best = ranked[0];
  const runners = ranked.slice(1, 3).filter((r) => r.score > 0);

  return (
    <div>
      {best && (
        // 比較表の中で、いちばん当てはまる列を強調する
        <style>{`[data-col="${best.product.key}"]{background:var(--accent-soft)}`}</style>
      )}
      <form className="grid gap-5" onSubmit={(event) => event.preventDefault()}>
        {quiz.map((question, qIndex) => (
          <fieldset key={question.key} className="min-w-0">
            <legend className="flex items-baseline gap-2 text-[15px] font-black text-ink">
              <span className="index-num text-meta font-semibold text-accent">Q{qIndex + 1}</span>
              {question.label}
            </legend>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
              {question.options.map((option) => {
                const id = `${baseId}-${question.key}-${option.value}`;
                const checked = answers[question.key] === option.value;
                return (
                  <label
                    key={option.value}
                    htmlFor={id}
                    className={`flex min-h-11 cursor-pointer items-center justify-center rounded-lg border-2 px-3 py-2 text-center text-note font-bold leading-snug transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent motion-reduce:transition-none ${
                      checked ? "border-accent bg-accent text-white" : "border-line-strong bg-paper text-ink hover:border-ink"
                    }`}
                  >
                    <input
                      id={id}
                      type="radio"
                      name={`${baseId}-${question.key}`}
                      value={option.value}
                      checked={checked}
                      onChange={() => setAnswers((prev) => ({ ...prev, [question.key]: option.value }))}
                      className="sr-only"
                    />
                    {option.label}
                  </label>
                );
              })}
            </div>
          </fieldset>
        ))}
      </form>

      <div aria-live="polite" className="mt-6">
        {!best ? (
          <p className="rounded-xl border border-dashed border-line-strong px-4 py-5 text-center text-note text-muted">
            質問に答えると、条件に合う候補がここに出ます（1問だけでも絞り込めます）。
          </p>
        ) : (
          <div className="grid gap-3">
            <div className="rounded-2xl border-2 border-accent p-4 sm:p-5">
              <p className="text-meta font-bold text-accent">
                {answered < quiz.length ? `${answered}問の答えで、いちばん当てはまる候補` : "あなたの条件にいちばん当てはまる候補"}
              </p>
              <div className="mt-3 flex items-start gap-4">
                <Visual product={best.product} className="size-20 shrink-0 rounded-xl sm:size-24" />
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 text-[22px] font-black leading-tight text-ink">
                    {best.product.name}
                    {best.product.sponsored && <Pr />}
                  </p>
                  <p className="index-num mt-1 text-note font-semibold text-ink">
                    {best.product.price}
                    <span className="ml-2 font-sans text-meta font-normal text-muted">{best.product.priceNote}</span>
                  </p>
                  <p className="mt-1 text-meta text-ink-soft">{best.product.bestFor}</p>
                </div>
              </div>
              <ul className="mt-3 grid gap-1 text-meta text-ink-soft">
                {best.matched.map((label) => (
                  <li key={label}><span aria-hidden className="mr-1 text-go">○</span>「{label}」に公式の記載が合う</li>
                ))}
                {best.missed.map((label) => (
                  <li key={label}><span aria-hidden className="mr-1 text-muted">△</span>「{label}」には当てはまらない</li>
                ))}
              </ul>
              <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                <a
                  href={`#p-${best.product.key}`}
                  className="flex h-11 flex-1 items-center justify-center rounded-lg border border-ink text-note font-bold text-ink hover:bg-ink hover:text-paper"
                >
                  できること・注意点を見る
                </a>
                <a
                  href={best.product.url}
                  target="_blank"
                  rel={best.product.sponsored ? "sponsored nofollow noopener noreferrer" : "nofollow noopener"}
                  data-aff-pos="diagnosis"
                  className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-lg bg-accent text-note font-bold text-white hover:opacity-90"
                >
                  公式サイトで見る <span aria-hidden>↗</span>
                </a>
              </div>
            </div>
            {runners.length > 0 && (
              <div className="grid gap-2 sm:grid-cols-2">
                {runners.map(({ product, matched }) => (
                  <a key={product.key} href={`#p-${product.key}`} className="flex items-center gap-3 rounded-xl border border-line p-3 hover:border-ink">
                    <Visual product={product} className="size-12 shrink-0 rounded-lg" small />
                    <span className="min-w-0">
                      <span className="block text-meta font-bold text-muted">次の候補{product.sponsored ? "・PR" : ""}</span>
                      <span className="block text-[15px] font-black leading-snug text-ink">{product.name}</span>
                      <span className="block truncate text-meta text-ink-soft">{matched.join("・") || product.bestFor}</span>
                    </span>
                  </a>
                ))}
              </div>
            )}
            <button
              type="button"
              onClick={() => setAnswers({})}
              className="justify-self-start text-meta font-bold text-muted underline underline-offset-2 hover:text-ink"
            >
              答えをリセット
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Pr() {
  return (
    <span className="inline-grid h-[18px] place-items-center rounded-[3px] border border-current px-1 text-badge font-bold leading-none tracking-wider text-muted">
      PR
    </span>
  );
}

function Visual({ product, className, small = false }: { product: DiagnosisProduct; className: string; small?: boolean }) {
  if (product.image) {
    return (
      <span className={`grid place-items-center overflow-hidden bg-white ${className}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={product.image} alt={product.name} className="size-full object-contain p-1.5" />
      </span>
    );
  }
  return (
    <span
      role="img"
      aria-label={product.name}
      className={`flex flex-col justify-between border border-line bg-surface p-1.5 ${className}`}
    >
      <span className="index-num text-meta font-semibold uppercase tracking-[0.1em] text-muted">{product.maker}</span>
      <span className={`font-black leading-tight text-ink ${small ? "text-meta" : "text-meta"}`}>{product.name}</span>
    </span>
  );
}
