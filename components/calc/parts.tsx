import type { ReactNode } from "react";
import { checkedDateJa } from "@/lib/calculators";
import type { ReceiveGuide } from "@/lib/receive-steps";

/** 計算機の共通部品（サーバー・クライアントどちらからも使える見た目だけの部品） */

export const INPUT_CLASS =
  "mt-1.5 w-full rounded-lg border border-line-strong bg-paper px-3 py-2.5 text-desc text-ink tabular-nums focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

export function Field({ id, label, help, children }: { id: string; label: string; help?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="text-note font-bold text-ink">
        {label}
      </label>
      {children}
      {help ? <p className="mt-1.5 text-note leading-[1.7] text-ink-soft">{help}</p> : null}
    </div>
  );
}

/** 結果の1行（左に名前、右に大きな数字） */
export function ResultRow({ label, value, strong = false, sub }: { label: string; value: string; strong?: boolean; sub?: string }) {
  return (
    <div className={`flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2.5 ${strong ? "" : "border-b border-line"}`}>
      <dt className={`min-w-0 text-note ${strong ? "font-bold text-ink" : "text-ink-soft"}`}>{label}</dt>
      <dd className="ml-auto max-w-full text-right">
        <span className={`font-bold tabular-nums text-ink ${strong ? "text-[1.375rem] leading-tight" : "text-desc"}`}>{value}</span>
        {sub ? <span className="mt-0.5 block text-meta text-ink-soft">{sub}</span> : null}
      </dd>
    </div>
  );
}

/** 2択・3択の切り替え（ラジオボタン） */
export function Segmented<T extends string>({
  name,
  value,
  options,
  onChange,
  label,
}: {
  name: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="text-note font-bold text-ink">{label}</legend>
      <div className="mt-1.5 flex flex-wrap gap-2">
        {options.map((option) => (
          <label
            key={option.value}
            className={`cursor-pointer rounded-lg border px-3.5 py-2 text-note font-bold transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent ${
              value === option.value ? "border-accent bg-accent-soft text-ink" : "border-line-strong bg-paper text-ink-soft hover:border-ink"
            }`}
          >
            <input type="radio" name={name} value={option.value} checked={value === option.value} onChange={() => onChange(option.value)} className="sr-only" />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** 入力の文字列 → 数字（全角・カンマも受け付ける。読めなければ null） */
export function toNumber(text: string): number | null {
  const normalized = text.normalize("NFKC").replace(/[,，\s円$ドル]/g, "");
  if (normalized === "") return null;
  const value = Number(normalized);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

const STEP_MARKS = ["①", "②", "③", "④"];

/** 結果のすぐ下に出す「受け取るまでの流れ」（①誰が ②どこへ ③いつまでに ④いつ入る）。中身は制度ごとの lib に公式ページどおりに書く */
export function ReceiveSteps({ guide, className = "" }: { guide: ReceiveGuide; className?: string }) {
  return (
    <section aria-label={guide.title} className={`rounded-xl border border-line-strong bg-paper px-4 py-4 ${className}`} data-receive-steps>
      <h3 className="text-desc font-bold text-ink">{guide.title}</h3>
      <ol className="mt-2 grid gap-2.5">
        {guide.steps.map((step, i) => (
          <li key={step.label} className="grid grid-cols-[auto_1fr] gap-x-2 text-note leading-[1.7]">
            <span className="font-bold text-accent" aria-hidden="true">{STEP_MARKS[i]}</span>
            <p>
              <span className="font-bold text-ink">{step.label}</span>
              <span className="mt-0.5 block text-ink-soft">{step.text}</span>
            </p>
          </li>
        ))}
      </ol>
      <p className="mt-3 border-t border-line pt-3 text-meta leading-[1.7] text-ink-soft">
        {"公式の案内："}
        {guide.sources.map((source, i) => (
          <span key={source.href}>
            {i > 0 ? "、" : null}
            <a href={source.href} target="_blank" rel="noopener" className="text-accent underline underline-offset-2">
              {source.label}
            </a>
          </span>
        ))}
        {`（${checkedDateJa(guide.checked)}確認）`}
      </p>
    </section>
  );
}
