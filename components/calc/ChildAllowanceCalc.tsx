"use client";

import Link from "next/link";
import { useId, useState } from "react";
import {
  CHILD_ALLOWANCE_NEXT_PAYMENT,
  CHILD_CATEGORIES,
  childAllowance,
  statusByBirth,
  statusLabel,
  ymJa,
  type ChildCategory,
  type ChildInput,
  CHILD_ALLOWANCE_RECEIVE,
} from "@/lib/child-allowance";
import { yen } from "@/lib/calc-math";
import { INPUT_CLASS, ReceiveSteps, ResultRow, Segmented } from "@/components/calc/parts";

/**
 * 児童手当の「自分の場合」（/tools/child-allowance と、児童手当の記事の中）。式は lib/child-allowance.ts。
 * 子どもごとに、生まれた年月か年齢の区分を入れる。入力は画面の中の計算だけに使い、送信・保存はしない。
 */
type Mode = "birth" | "category";
type Row = { key: number; year: string; month: string; supported: boolean; category: ChildCategory };

const MAX_CHILDREN = 8;
const FIRST_YEAR = 2003;
const LAST_YEAR = 2027;
const YEARS = Array.from({ length: LAST_YEAR - FIRST_YEAR + 1 }, (_, i) => LAST_YEAR - i);
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

/** 最初に出しておく例（小学生と2歳の子）。結果がすぐ見えるように */
const START: Row[] = [
  { key: 1, year: "2017", month: "6", supported: false, category: "from3" },
  { key: 2, year: "2024", month: "2", supported: false, category: "under3" },
];

function toInput(row: Row, mode: Mode): ChildInput | null {
  if (mode === "category") return { kind: "category", category: row.category };
  const year = Number(row.year);
  const month = Number(row.month);
  if (!year || !month) return null;
  return { kind: "birth", year, month, supported: row.supported };
}

export default function ChildAllowanceCalc() {
  const id = useId();
  const [mode, setMode] = useState<Mode>("birth");
  const [rows, setRows] = useState<Row[]>(START);
  const [nextKey, setNextKey] = useState(START.length + 1);

  const update = (key: number, patch: Partial<Row>) => setRows((list) => list.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const add = () => {
    if (rows.length >= MAX_CHILDREN) return;
    setRows((list) => [...list, { key: nextKey, year: "", month: "", supported: false, category: "from3" }]);
    setNextKey((n) => n + 1);
  };
  const remove = (key: number) => setRows((list) => (list.length > 1 ? list.filter((row) => row.key !== key) : list));

  const inputs = rows.map((row) => toInput(row, mode));
  const ready = inputs.filter((x): x is ChildInput => x !== null);
  const result = ready.length > 0 ? childAllowance(ready) : null;
  // 入れた順の子 → 結果の行（年月が未入力の子は飛ばす）
  const resultOf = (i: number) => {
    if (!result || inputs[i] === null) return null;
    return result.children[inputs.slice(0, i).filter((x) => x !== null).length];
  };
  const latest = result?.next.months[1];
  const span = result ? `${ymJa(result.year.payments[0].months[0])}〜${ymJa(result.year.payments[5].months[1])}分` : "";

  return (
    <div>
      <Segmented
        name={`${id}-mode`}
        label="子どもの入れ方"
        value={mode}
        onChange={setMode}
        options={[
          { value: "birth", label: "生まれた年月で" },
          { value: "category", label: "年齢の区分で" },
        ]}
      />
      <p className="mt-2 text-note leading-[1.7] text-ink-soft">
        {mode === "birth"
          ? "18歳の年度末を過ぎた子（大学生年代）も入れてください。手当は出ませんが、生活費を負担していれば第3子の数え方に入ります。"
          : "上の子から順に入れてください。区分は今（2026年11月）の年齢で選びます。"}
      </p>

      <ol className="mt-4 grid gap-3">
        {rows.map((row, i) => {
          const r = resultOf(i);
          const birth = inputs[i]?.kind === "birth" ? (inputs[i] as Extract<ChildInput, { kind: "birth" }>) : null;
          // 18歳の年度末を過ぎる子（今か、これから1年のうち）だけに「生活費を負担」を出す
          const older =
            birth !== null &&
            [{ year: 2026, month: 11 }, { year: 2027, month: 9 }].some((ym) => {
              const s = statusByBirth({ ...birth, supported: true }, ym);
              return s === "olderCounted";
            });
          return (
            <li key={row.key} className="rounded-xl border border-line px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-note font-bold text-ink">{`子ども${i + 1}`}</span>
                {rows.length > 1 ? (
                  <button type="button" onClick={() => remove(row.key)} className="text-meta text-ink-soft underline underline-offset-4 hover:text-ink">
                    この子を消す
                  </button>
                ) : null}
              </div>
              {mode === "birth" ? (
                <div className="mt-2 grid grid-cols-2 gap-3">
                  <div className="min-w-0">
                    <label htmlFor={`${id}-y-${row.key}`} className="text-meta font-bold text-ink-soft">生まれた年</label>
                    <select id={`${id}-y-${row.key}`} value={row.year} onChange={(e) => update(row.key, { year: e.target.value })} className={INPUT_CLASS}>
                      <option value="">選ぶ</option>
                      {YEARS.map((y) => (
                        <option key={y} value={y}>{`${y}年`}</option>
                      ))}
                    </select>
                  </div>
                  <div className="min-w-0">
                    <label htmlFor={`${id}-m-${row.key}`} className="text-meta font-bold text-ink-soft">生まれた月</label>
                    <select id={`${id}-m-${row.key}`} value={row.month} onChange={(e) => update(row.key, { month: e.target.value })} className={INPUT_CLASS}>
                      <option value="">選ぶ</option>
                      {MONTHS.map((m) => (
                        <option key={m} value={m}>{`${m}月`}</option>
                      ))}
                    </select>
                  </div>
                  {older ? (
                    <label className="col-span-2 flex cursor-pointer items-start gap-2 text-note leading-[1.7] text-ink">
                      <input type="checkbox" checked={row.supported} onChange={(e) => update(row.key, { supported: e.target.checked })} className="mt-1 h-4 w-4 shrink-0 accent-accent" />
                      <span>親が生活費を負担している（学生でなくてもかまいません。22歳の年度末まで）</span>
                    </label>
                  ) : null}
                </div>
              ) : (
                <div className="mt-2">
                  <label htmlFor={`${id}-c-${row.key}`} className="sr-only">{`子ども${i + 1}の年齢の区分`}</label>
                  <select
                    id={`${id}-c-${row.key}`}
                    value={row.category}
                    onChange={(e) => update(row.key, { category: e.target.value as ChildCategory })}
                    className={INPUT_CLASS}
                  >
                    {CHILD_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
              )}
              {r ? (
                <p className="mt-2 flex flex-wrap items-baseline justify-between gap-x-4 text-note tabular-nums">
                  <span className="text-ink-soft">{statusLabel(r)}</span>
                  <span className="font-bold text-ink">{r.amount > 0 ? `月${yen(r.amount)}` : "0円"}</span>
                </p>
              ) : null}
            </li>
          );
        })}
      </ol>
      {rows.length < MAX_CHILDREN ? (
        <button
          type="button"
          onClick={add}
          className="mt-3 rounded-lg border border-line-strong bg-paper px-3.5 py-2 text-note font-bold text-ink hover:border-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          ＋ 子どもを足す
        </button>
      ) : null}

      <div className="mt-5 rounded-xl bg-surface px-4 py-4" aria-live="polite" data-child-allowance-result>
        {result && latest ? (
          <>
            <dl>
              <ResultRow label={`${ymJa(CHILD_ALLOWANCE_NEXT_PAYMENT)}の支給（${result.next.months[0].month}月・${result.next.months[1].month}月分）`} value={yen(result.next.amount)} strong />
              <ResultRow label={`1か月の合計（${ymJa(latest)}分）`} value={yen(result.monthly)} />
              <ResultRow label="12月から1年分（支給6回）" value={yen(result.year.total)} sub={span} />
            </dl>
            <ul className="mt-3 grid gap-1 border-t border-line pt-3 text-note tabular-nums text-ink-soft">
              {result.year.payments.map((p) => (
                <li key={`${p.pay.year}-${p.pay.month}`} className="flex items-baseline justify-between gap-4">
                  <span>{`${ymJa(p.pay)}（${p.months[0].month}月・${p.months[1].month}月分）`}</span>
                  <span className="text-ink">{yen(p.amount)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-meta leading-[1.7] text-ink-soft">
              {mode === "birth"
                ? "年齢が上がると、その月から額が変わる分も入れています（3歳の誕生月の翌月から10,000円、18歳の年度末の3月分まで）。支給日の日にちは市区町村で違います。"
                : "区分が1年間変わらないとして計算しています。年齢で額が変わる月まで入れるなら「生まれた年月で」を選んでください。支給日の日にちは市区町村で違います。"}
            </p>
            <p className="mt-3 border-t border-line pt-3 text-note leading-[1.7]" data-child-allowance-next>
              <span className="font-bold text-ink">12月にもう1つ：</span>
              <Link href="/tools/furusato-limit" className="font-bold text-accent underline underline-offset-2">
                うちのふるさと納税の上限を計算する
              </Link>
              <span className="text-ink-soft">（今年の分は12月31日の寄附まで）</span>
            </p>
          </>
        ) : (
          <p className="text-note leading-[1.7] text-ink-soft">子どもの生まれた年と月を選ぶと、ここに金額が出ます。</p>
        )}
      </div>
      <ReceiveSteps guide={CHILD_ALLOWANCE_RECEIVE} className="mt-4" />
    </div>
  );
}
