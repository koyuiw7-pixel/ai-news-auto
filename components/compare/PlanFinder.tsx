"use client";

import { useId, useMemo, useState } from "react";
import type { PlanFinder as Finder, PlanFinderCell } from "@/lib/buying-guides";

/**
 * 比較ページの「あなたに合うのは」と、絞り込み・並べ替えの一覧（2026-11-11 COMPARE-2）。
 * 3つの質問の答えがそのまま一覧の条件になる。上位3件は「条件に合ういちばん安いプランの月額」の安い順だけで決め、
 * 提携先（PR）かどうかでは順番を変えない（同じ金額なら初めにかかる費用の安い順、その次は名前順）。
 */

export type FinderProduct = {
  key: string;
  name: string;
  href: string;
  sponsored: boolean;
  sources: { label: string; url: string }[];
};

type Sort = "price" | "initial" | "data";

const yen = (n: number) => `${n.toLocaleString("ja-JP")}円`;
/** ["ドコモ回線","au回線"] → "ドコモ・au回線"（札が「〜回線」のときだけまとめる） */
const lineText = (tags: string[]) => (tags.every((t) => t.endsWith("回線")) ? `${tags.map((t) => t.slice(0, -2)).join("・")}回線` : tags.join("・"));

function Choice<T extends string>({
  name,
  legend,
  value,
  options,
  onChange,
}: {
  name: string;
  legend: string;
  value: T;
  options: { key: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="text-note font-bold text-ink">{legend}</legend>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => (
          <label
            key={option.key}
            className={`flex min-h-11 cursor-pointer items-center rounded-lg border px-3.5 py-2 text-note font-bold leading-snug has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent ${
              value === option.key ? "border-accent bg-accent-soft text-ink" : "border-line-strong bg-paper text-ink-soft hover:border-ink"
            }`}
          >
            <input type="radio" name={name} value={option.key} checked={value === option.key} onChange={() => onChange(option.key)} className="sr-only" />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Pr() {
  return <span className="ad-pr ml-1.5 align-middle">PR</span>;
}

export default function PlanFinder({ finder, products, checkedLabel }: { finder: Finder; products: FinderProduct[]; checkedLabel: string }) {
  const id = useId();
  const byKey = useMemo(() => new Map(products.map((p) => [p.key, p])), [products]);
  const [tier, setTier] = useState(finder.tiers[0].key);
  const [option, setOption] = useState(finder.options?.[0].key ?? "any");
  const [tag, setTag] = useState("any");
  const [sort, setSort] = useState<Sort>("price");

  const rows = finder.items.flatMap((item) => {
    const product = byKey.get(item.id);
    if (!product) return [];
    const cell: PlanFinderCell = item.matrix[tier]?.[option] ?? null;
    return [{ item, product, cell }];
  });
  const matching = rows.filter((row) => tag === "any" || row.item.tags.includes(tag));
  const byPrice = (a: (typeof rows)[number], b: (typeof rows)[number]) =>
    (a.cell?.yen ?? Infinity) - (b.cell?.yen ?? Infinity) ||
    (a.item.initialYen ?? Infinity) - (b.item.initialYen ?? Infinity) ||
    a.product.name.localeCompare(b.product.name, "ja");
  const available = matching.filter((row) => row.cell).sort(byPrice);
  const top = available.slice(0, 3);
  const listed = [...available].sort((a, b) => {
    if (sort === "initial") return (a.item.initialYen ?? Infinity) - (b.item.initialYen ?? Infinity) || byPrice(a, b);
    if (sort === "data") return (b.cell?.gb ?? Infinity) - (a.cell?.gb ?? Infinity) || byPrice(a, b);
    return byPrice(a, b);
  });
  const missing = matching.filter((row) => !row.cell);
  const initialLabel = finder.initialLabel ?? "初めの費用";
  const hasGb = finder.items.some((i) => Object.values(i.matrix).some((r) => Object.values(r).some((c) => c?.gb !== undefined)));
  const tierLabel = finder.tiers.find((t) => t.key === tier)?.label ?? "";
  const optionLabel = finder.options?.find((o) => o.key === option)?.label;

  return (
    <div data-plan-finder>
      {/* あなたに合うのは：3つの質問 */}
      <div className="rounded-2xl border-2 border-ink p-4 sm:p-6">
        <p className="text-meta font-bold tracking-[0.1em] text-accent">3つ選ぶだけ</p>
        <h3 className="t-h3 mt-1">あなたに合うのは</h3>
        <div className="mt-4 grid gap-5">
          <Choice name={`${id}-tier`} legend={`1. ${finder.tierQuestion}`} value={tier} options={finder.tiers} onChange={setTier} />
          {finder.options && finder.optionQuestion ? (
            <Choice name={`${id}-opt`} legend={`2. ${finder.optionQuestion}`} value={option} options={finder.options} onChange={setOption} />
          ) : null}
          <Choice
            name={`${id}-tag`}
            legend={`${finder.options ? 3 : 2}. ${finder.tagQuestion}`}
            value={tag}
            options={[{ key: "any", label: finder.anyTag }, ...finder.tags.map((t) => ({ key: t, label: t }))]}
            onChange={setTag}
          />
        </div>

        <div className="mt-5 border-t border-line pt-4" aria-live="polite">
          <p className="text-note text-ink-soft">
            {[tierLabel, optionLabel, tag !== "any" ? tag : null].filter(Boolean).map((t) => `「${t}」`).join("")}で、月額の安い順（{finder.unit}）
          </p>
          {top.length > 0 ? (
            <ol className="mt-3 grid gap-3">
              {top.map(({ item, product, cell }, index) => (
                <li key={item.id} className="flex items-start gap-3 rounded-xl bg-surface px-3.5 py-3">
                  <span className="index-num pt-0.5 text-[20px] font-black leading-none text-accent">{index + 1}</span>
                  <span className="min-w-0 flex-1">
                    <a href={`#p-${item.id}`} className="text-[17px] font-black leading-snug text-ink underline-offset-4 hover:underline">
                      {product.name}
                    </a>
                    {product.sponsored && <Pr />}
                    <span className="mt-0.5 block text-note leading-snug text-ink-soft">{cell!.label}</span>
                    <span className="mt-0.5 block text-meta leading-snug text-muted">{item.kind}</span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="index-num block text-[19px] font-black leading-tight text-ink">{yen(cell!.yen)}</span>
                    <span className="block text-meta text-muted">月額</span>
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-note text-ink-soft">この条件に合うプランは、比べた中にはありません。条件を変えてみてください。</p>
          )}
          <p className="mt-3 text-meta leading-[1.7] text-muted">{finder.sortRule}</p>
        </div>
      </div>

      {/* 一覧 */}
      <div className="mt-8 flex flex-wrap items-end justify-between gap-3">
        <p className="text-note font-bold text-ink">
          この条件で使える{available.length}件
          {missing.length > 0 ? <span className="ml-1 font-normal text-muted">（ほか{missing.length}件は該当プランなし）</span> : null}
        </p>
        <label className="text-note text-ink-soft">
          <span className="mr-2">並べ替え</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="h-11 rounded-lg border border-line-strong bg-paper px-3 text-note font-bold text-ink">
            <option value="price">月額の安い順</option>
            <option value="initial">{initialLabel}の安い順</option>
            {hasGb ? <option value="data">データ量の多い順</option> : null}
          </select>
        </label>
      </div>
      <ul className="mt-3 grid gap-3">
        {listed.map(({ item, product, cell }) => (
          <Row key={item.id} item={item} product={product} cell={cell} initialLabel={initialLabel} />
        ))}
        {missing.map(({ item, product }) => (
          <Row key={item.id} item={item} product={product} cell={null} initialLabel={initialLabel} />
        ))}
      </ul>
      <p className="mt-3 text-meta leading-[1.7] text-muted">
        {checkedLabel}。金額は月額（{finder.unit}）。キャンペーンや期間限定の割引は入れていません。「公式で確認中」は公式ページで確かめられなかった項目です。
      </p>
    </div>
  );
}

function Row({ item, product, cell, initialLabel }: { item: Finder["items"][number]; product: FinderProduct; cell: PlanFinderCell; initialLabel: string }) {
  return (
    <li id={`p-${item.id}`} className={`scroll-mt-24 rounded-xl border border-line px-3.5 py-3 ${cell ? "" : "opacity-70"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-meta text-muted">{item.kind}・{lineText(item.tags)}</p>
          <p className="mt-0.5 text-[16px] font-black leading-snug text-ink">
            {product.name}
            {product.sponsored && <Pr />}
          </p>
          <p className="mt-0.5 text-note leading-snug text-ink-soft">{cell ? cell.label : "この条件のプランはありません"}</p>
        </div>
        <p className="shrink-0 text-right">
          <span className="index-num block text-[18px] font-black leading-tight text-ink">{cell ? yen(cell.yen) : "ー"}</span>
          <span className="block whitespace-nowrap text-meta text-muted">{item.initialYen === null ? `${initialLabel}：公式で確認中` : `${initialLabel} ${yen(item.initialYen)}`}</span>
        </p>
      </div>
      {item.change ? <p className="mt-2 rounded-md bg-accent-soft px-2.5 py-1.5 text-meta leading-[1.6] text-ink">{item.change}</p> : null}
      <details className="group mt-1">
        <summary className="-mb-2 flex min-h-11 cursor-pointer list-none items-center gap-1 text-note font-bold text-accent">
          くわしく（通話・5G・解約など）<span aria-hidden className="transition-transform group-open:rotate-45">＋</span>
        </summary>
        <dl className="mt-1 grid gap-1.5 text-note leading-[1.65]">
          {item.facts.map((fact) => (
            <div key={fact.label} className="grid grid-cols-[6.5em_minmax(0,1fr)] gap-2">
              <dt className="font-bold text-muted">{fact.label}</dt>
              <dd className={fact.value === "公式で確認中" ? "text-muted" : "text-ink-soft"}>{fact.value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-2 text-meta leading-relaxed text-muted">
          出典：
          {product.sources.map((source, index) => (
            <span key={source.url}>
              {index > 0 && "／"}
              <a href={source.url} target="_blank" rel="nofollow noopener" className="underline underline-offset-2 hover:text-accent">
                {source.label}
              </a>
            </span>
          ))}
        </p>
        <a
          href={product.href}
          target="_blank"
          rel={product.sponsored ? "sponsored nofollow noopener noreferrer" : "nofollow noopener"}
          data-aff-pos="compare"
          className="mt-3 flex h-11 items-center justify-center rounded-md bg-ink px-5 text-note font-bold text-paper hover:opacity-85"
        >
          {product.name}の公式サイト
          <span className="sr-only">（{product.sponsored ? "PR・" : ""}新しいタブで開きます）</span>
        </a>
      </details>
    </li>
  );
}
