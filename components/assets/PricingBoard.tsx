"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { formatMoney, formatYen } from "@/lib/money";
import type { PriceRow } from "@/lib/pricing";

type Sort = "cost" | "input" | "output" | "company" | "newest";

const SORT_LABEL: Record<Sort, string> = {
  cost: "月の目安が安い順",
  input: "入力が安い順",
  output: "出力が安い順",
  company: "会社ごと",
  newest: "記事が新しい順",
};

const day = new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", timeZone: "Asia/Tokyo" });

/** 企業色をうっすら敷く（暗い画面でも背景になじむよう color-mix で薄める） */
const tint = (color: string, percent = 7) => `color-mix(in srgb, ${color} ${percent}%, var(--paper))`;

/** 月の費用（ドル）。入力・出力のどちらかが記事に無く、その量を使う設定なら計算しない */
function monthlyCost(row: PriceRow, inMan: number, outMan: number): number | null {
  if (row.input === null && inMan > 0) return null;
  if (row.output === null && outMan > 0) return null;
  return ((row.input ?? 0) * inMan + (row.output ?? 0) * outMan) / 100;
}

/**
 * 早見表の本体（API の比較と計算機、月額プラン）。
 * 一覧はサーバーで描画済みの初期状態のまま検索エンジンにも読める。操作は並び替え・絞り込み・計算だけ。
 */
export default function PricingBoard({ rows }: { rows: PriceRow[] }) {
  const [company, setCompany] = useState("all");
  const [japanOnly, setJapanOnly] = useState(false);
  const [showLegacy, setShowLegacy] = useState(false);
  const [sort, setSort] = useState<Sort>("cost");
  const [inMan, setInMan] = useState(100);
  const [outMan, setOutMan] = useState(30);
  const [rate, setRate] = useState(150);

  const companies = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of rows) if (!seen.has(row.companySlug)) seen.set(row.companySlug, row.companyName);
    return [...seen.entries()];
  }, [rows]);

  const apis = useMemo(() => {
    const list = rows
      .filter((row) => row.kind === "api")
      .filter((row) => showLegacy || !row.legacy)
      .filter((row) => company === "all" || row.companySlug === company)
      .filter((row) => !japanOnly || row.japan === "ok" || row.japan === "partial")
      .map((row) => ({ row, cost: monthlyCost(row, inMan, outMan) }));
    const num = (v: number | null) => (v === null ? Number.POSITIVE_INFINITY : v);
    list.sort((a, b) => {
      if (sort === "cost") return num(a.cost) - num(b.cost);
      if (sort === "input") return num(a.row.input) - num(b.row.input);
      if (sort === "output") return num(a.row.output) - num(b.row.output);
      if (sort === "newest") return b.row.source.publishedAt.localeCompare(a.row.source.publishedAt);
      return a.row.companyName.localeCompare(b.row.companyName) || num(a.cost) - num(b.cost);
    });
    return list;
  }, [rows, company, japanOnly, showLegacy, sort, inMan, outMan]);

  const plans = useMemo(
    () =>
      rows
        .filter((row) => row.kind === "plan")
        .filter((row) => company === "all" || row.companySlug === company)
        .filter((row) => !japanOnly || row.japan === "ok" || row.japan === "partial")
        .sort((a, b) => (a.monthly ?? 0) - (b.monthly ?? 0)),
    [rows, company, japanOnly],
  );

  const costs = apis.map((a) => a.cost).filter((c): c is number => c !== null);
  const maxCost = Math.max(...costs, 0);
  const minCost = costs.length ? Math.min(...costs) : null;
  const cheapest = apis.find((a) => a.cost !== null && a.cost === minCost && !a.row.legacy);
  const legacyCount = rows.filter((row) => row.kind === "api" && row.legacy).length;

  return (
    <div>
      {/* 絞り込み（全体にかかる） */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-xl border border-line bg-surface px-4 py-3 text-[13px]">
        <label className="flex items-center gap-2">
          <span className="font-bold text-ink-soft">会社</span>
          <select
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            className="rounded-md border border-line-strong bg-paper px-2 py-1 text-[13px] text-ink"
          >
            <option value="all">すべて</option>
            {companies.map(([slug, name]) => (
              <option key={slug} value={slug}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={japanOnly} onChange={(e) => setJapanOnly(e.target.checked)} className="size-4 accent-[var(--go)]" />
          <span className="font-bold text-ink-soft">日本で使えるものだけ</span>
        </label>
      </div>

      {/* ---------------- API ---------------- */}
      <section aria-labelledby="api-heading" className="mt-10">
        <div className="mb-4 border-b border-line-strong pb-2.5">
          <h2 id="api-heading" className="text-[1.2rem] font-bold leading-snug text-ink sm:text-[1.35rem]">
            APIはいくら？月にどれくらいかかる？
          </h2>
          <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
            料金は100万トークンあたり（米ドル）。入力＝AIに渡す文章、出力＝AIが書いた文章です。
          </p>
        </div>

        {/* 計算機 */}
        <div className="rounded-xl border border-ink/80 p-4 sm:p-5">
          <p className="text-[14px] font-bold text-ink">月にどれくらい使う？</p>
          <div className="mt-3 grid grid-cols-3 gap-2.5 sm:gap-4">
            <NumberField label="入力" unit="万トークン" value={inMan} onChange={setInMan} step={10} />
            <NumberField label="出力" unit="万トークン" value={outMan} onChange={setOutMan} step={10} />
            <NumberField label="1ドル" unit="円" value={rate} onChange={setRate} step={1} />
          </div>
          <p className="mt-4 text-[14px] leading-[1.8] text-ink" aria-live="polite">
            {cheapest ? (
              <>
                この使い方なら、いちばん安いのは
                <strong className="mx-1 font-bold">{cheapest.row.product}</strong>
                で月
                <strong className="mx-1 font-bold tabular-nums">{formatMoney(cheapest.cost!, "USD")}</strong>
                <span className="text-muted">（{formatYen(cheapest.cost! * rate)}）</span>です。
              </>
            ) : (
              "条件に合うモデルがありません。"
            )}
          </p>
          <p className="mt-1 text-[11.5px] text-muted">為替は目安です。実際の請求は各社の公式料金と、税・為替手数料で変わります。</p>
        </div>

        {/* 並び替え */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[12.5px] text-muted">
            <span className="tabular-nums">{apis.length}</span>件
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px]">
            {legacyCount > 0 && (
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={showLegacy} onChange={(e) => setShowLegacy(e.target.checked)} className="size-4" />
                <span className="text-ink-soft">以前のモデルも表示（{legacyCount}件）</span>
              </label>
            )}
            <label className="flex items-center gap-2">
              <span className="text-ink-soft">並び替え</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as Sort)}
                className="rounded-md border border-line-strong bg-paper px-2 py-1 text-[13px] text-ink"
              >
                {(Object.keys(SORT_LABEL) as Sort[]).map((key) => (
                  <option key={key} value={key}>
                    {SORT_LABEL[key]}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {/* 見出し行（広い画面だけ） */}
        <div
          aria-hidden
          className="mt-3 hidden grid-cols-[minmax(0,1.5fr)_6.5rem_5rem_7.5rem_minmax(0,1.5fr)] gap-4 border-b border-ink px-4 pb-2 text-[11.5px] font-bold text-muted md:grid"
        >
          <span>モデル</span>
          <span className="text-right">入力</span>
          <span className="text-right">出力</span>
          <span>日本・無料枠</span>
          <span>月の目安（上の使い方）</span>
        </div>

        <ul className="mt-3 grid gap-2.5 md:mt-0 md:gap-0">
          {apis.map(({ row, cost }) => (
            <li
              key={row.id}
              className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-2.5 rounded-xl border border-line py-3.5 pl-4 pr-4 md:grid-cols-[minmax(0,1.5fr)_6.5rem_5rem_7.5rem_minmax(0,1.5fr)] md:items-center md:rounded-none md:border-x-0 md:border-t-0"
              style={{ borderLeft: `4px solid ${row.color}`, background: tint(row.color, row.legacy ? 3 : 6) }}
            >
              {/* モデル */}
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  {row.productSlug ? (
                    <Link
                      href={`/products/${row.productSlug}`}
                      className="text-[15.5px] font-bold leading-snug text-ink underline decoration-transparent underline-offset-[3px] hover:decoration-ink"
                    >
                      {row.product}
                    </Link>
                  ) : (
                    <span className="text-[15.5px] font-bold leading-snug text-ink">{row.product}</span>
                  )}
                  {cheapest?.row.id === row.id && (
                    <span className="rounded-[4px] bg-go px-1.5 py-[1px] text-[10.5px] font-bold text-paper">最安</span>
                  )}
                  {row.legacy && <span className="rounded-[4px] border border-line-strong px-1.5 text-[10.5px] text-muted">以前のモデル</span>}
                </p>
                <p className="mt-0.5 text-[12px] text-muted">
                  <span className="font-bold" style={{ color: row.color }}>
                    {row.companyName}
                  </span>
                  <SourceLink row={row} />
                </p>
              </div>

              {/* スマホ: 価格を右上にまとめる */}
              <div className="text-right tabular-nums md:hidden">
                <p className="text-[13px] text-ink">
                  <span className="text-[11px] text-muted">入力 </span>
                  <Price value={row.input} />
                </p>
                <p className="text-[13px] text-ink">
                  <span className="text-[11px] text-muted">出力 </span>
                  <Price value={row.output} />
                </p>
              </div>

              {/* 広い画面: 入力・出力の列 */}
              <p className="hidden text-right text-[14px] tabular-nums text-ink md:block">
                <Price value={row.input} />
                {row.cachedInput !== null && (
                  <span className="block whitespace-nowrap text-[11px] text-muted">キャッシュ {formatMoney(row.cachedInput, "USD")}</span>
                )}
              </p>
              <p className="hidden text-right text-[14px] tabular-nums text-ink md:block">
                <Price value={row.output} />
              </p>

              {/* 日本・無料枠 */}
              <div className="col-span-2 flex flex-wrap items-center gap-1.5 md:col-span-1 md:flex-col md:items-start md:gap-1">
                <JapanCue japan={row.japan} status={row.status} />
                <FreeCue free={row.free} kind="api" />
              </div>

              {/* 月の目安 */}
              <div className="col-span-2 md:col-span-1">
                {cost === null ? (
                  <p className="text-[12px] text-muted">{row.input === null ? "入力" : "出力"}の料金が記事に無いため計算できません</p>
                ) : (
                  <>
                    <p className="flex items-baseline justify-between gap-2 text-[13px] tabular-nums">
                      <span className="font-bold text-ink">{formatMoney(cost, "USD")}</span>
                      <span className="text-muted">{formatYen(cost * rate)}</span>
                    </p>
                    <div className="mt-1.5 h-[6px] overflow-hidden rounded-full bg-line" aria-hidden>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${maxCost > 0 ? Math.max(2, (cost / maxCost) * 100) : 0}%`,
                          background: cheapest?.row.id === row.id ? "var(--go)" : row.color,
                        }}
                      />
                    </div>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
        {apis.length === 0 && <p className="py-8 text-center text-[13px] text-muted">条件に合うモデルがありません。</p>}
      </section>

      {/* ---------------- 月額プラン ---------------- */}
      <section aria-labelledby="plan-heading" className="mt-14">
        <div className="mb-4 border-b border-line-strong pb-2.5">
          <h2 id="plan-heading" className="text-[1.2rem] font-bold leading-snug text-ink sm:text-[1.35rem]">
            月額プランはいくら？日本で使える？
          </h2>
          <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
            ChatGPT・Claude・Geminiなどの個人向け有料プラン。記事で金額を確認できたものだけ載せています。
          </p>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2">
          {plans.map((row) => (
            <li
              key={row.id}
              className="rounded-xl border border-line p-4"
              style={{ borderLeft: `4px solid ${row.color}`, background: tint(row.color) }}
            >
              <p className="text-[12px] font-bold" style={{ color: row.color }}>
                {row.companyName}
              </p>
              <p className="mt-0.5 flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="text-[17px] font-bold text-ink">
                  {row.product} {row.plan}
                </span>
                <span className="tabular-nums">
                  <span className="text-[11px] text-muted">月額 </span>
                  <span className="text-[17px] font-bold text-ink">{formatMoney(row.monthly ?? 0, row.currency)}</span>
                  {row.currency === "USD" && <span className="ml-1 text-[12px] text-muted">{formatYen((row.monthly ?? 0) * rate)}</span>}
                </span>
              </p>
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <JapanCue japan={row.japan} status={row.status} />
                <FreeCue free={row.free} kind="plan" />
              </div>
              <p className="mt-2.5 text-[12px] text-muted">
                <SourceLink row={row} bare />
              </p>
            </li>
          ))}
        </ul>
        {plans.length === 0 && <p className="py-6 text-center text-[13px] text-muted">条件に合うプランがありません。</p>}
      </section>
    </div>
  );
}

function Price({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted">—</span>;
  return <>{formatMoney(value, "USD")}</>;
}

function NumberField({
  label,
  unit,
  value,
  onChange,
  step,
  className = "",
}: {
  label: string;
  unit: string;
  value: number;
  onChange: (value: number) => void;
  step: number;
  className?: string;
}) {
  return (
    <label className={`grid min-w-0 gap-1 ${className}`}>
      <span className="text-[12px] font-bold text-ink-soft">
        {label}
        <span className="ml-1 font-normal text-muted">（{unit}）</span>
      </span>
      <input
        type="number"
        inputMode="decimal"
        min={0}
        step={step}
        value={Number.isFinite(value) ? value : 0}
        onChange={(e) => onChange(Math.max(0, Number(e.target.value) || 0))}
        className="w-full min-w-0 rounded-md border border-line-strong bg-paper px-2.5 py-1.5 text-right text-[15px] tabular-nums text-ink"
      />
    </label>
  );
}

/** 出典の記事（いつの記事で確かめた数字か） */
function SourceLink({ row, bare = false }: { row: PriceRow; bare?: boolean }) {
  return (
    <>
      {!bare && <span aria-hidden> · </span>}
      <Link
        href={`/articles/${row.source.slug}`}
        title={`記事の記載:「${row.source.quote}」`}
        className="underline decoration-line-strong underline-offset-2 hover:text-ink"
      >
        {day.format(Date.parse(row.source.publishedAt))}の記事で確認
      </Link>
      {row.confirmedIn > 1 && <span>（{row.confirmedIn}本の記事で一致）</span>}
    </>
  );
}

const JAPAN: Record<PriceRow["japan"], { label: string; className: string; icon: "ok" | "partial" | "no" | "unknown" }> = {
  ok: { label: "日本で使える", className: "bg-go-soft text-go", icon: "ok" },
  partial: { label: "日本は条件付き", className: "border border-official/50 text-official", icon: "partial" },
  no: { label: "日本は未提供", className: "border border-line-strong text-ink-soft", icon: "no" },
  unknown: { label: "日本対応は未確認", className: "text-muted", icon: "unknown" },
};

export function JapanCue({ japan, status }: { japan: PriceRow["japan"]; status: PriceRow["status"] }) {
  const pre = status === "soon" || status === "demo";
  const item = pre ? { label: "提供前", className: "border border-line-strong text-muted", icon: "unknown" as const } : JAPAN[japan];
  return (
    <span className={`inline-flex items-center gap-1 rounded-[5px] px-1.5 py-[2px] text-[11.5px] font-bold ${item.className}`}>
      <CueIcon kind={item.icon} />
      {item.label}
    </span>
  );
}

export function FreeCue({ free, kind }: { free: boolean | null; kind: "api" | "plan" }) {
  if (free === true) {
    return (
      <span className="inline-flex items-center rounded-[5px] border border-go/60 px-1.5 py-[1px] text-[11.5px] font-bold text-go">
        {kind === "plan" ? "無料プランあり" : "無料で試せる"}
      </span>
    );
  }
  if (free === false) return <span className="text-[11.5px] text-muted">有料のみ</span>;
  return null;
}

function CueIcon({ kind }: { kind: "ok" | "partial" | "no" | "unknown" }) {
  const common = { width: 11, height: 11, viewBox: "0 0 12 12", fill: "none", stroke: "currentColor", strokeWidth: 2, "aria-hidden": true } as const;
  if (kind === "ok") return <svg {...common}><path d="M2 6.5 5 9.5 10 3" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (kind === "partial") return <svg {...common}><path d="M6 2 10.5 10h-9Z" strokeLinejoin="round" /></svg>;
  if (kind === "no") return <svg {...common}><path d="M3 3l6 6M9 3 3 9" strokeLinecap="round" /></svg>;
  return <svg {...common}><circle cx="6" cy="6" r="4.5" /></svg>;
}
