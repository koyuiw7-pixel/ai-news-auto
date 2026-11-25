"use client";

import { useId, useState } from "react";
import {
  PENSION_SUPPORT,
  PENSION_SUPPORT_NEXT_PAYMENT,
  PENSION_SUPPORT_PERIOD,
  VERDICT_LABELS,
  nextSteps,
  pensionSupport,
  yearsToMonths,
  type Answer,
  type BirthGroup,
  type Dependents,
  type PensionKind,
  type PensionSupportInput,
} from "@/lib/pension-support-benefit";
import { yen } from "@/lib/calc-math";
import { Field, INPUT_CLASS, ResultRow, Segmented, toNumber } from "@/components/calc/parts";

/**
 * 年金生活者支援給付金の「自分の場合」（/tools/pension-support-benefit と、年金生活者支援給付金の記事の中）。式は lib/pension-support-benefit.ts。
 * 入力は画面の中の計算だけに使い、送信・保存はしない。
 */
type MonthMode = "full" | "years" | "months";

function NumberInput({ id, label, help, value, onChange, unit }: { id: string; label: string; help?: string; value: string; onChange: (v: string) => void; unit: string }) {
  return (
    <Field id={id} label={label} help={help}>
      <div className="flex items-center gap-2">
        <input id={id} inputMode="numeric" autoComplete="off" value={value} onChange={(e) => onChange(e.target.value)} className={INPUT_CLASS} />
        <span className="mt-1.5 shrink-0 text-note text-ink-soft">{unit}</span>
      </div>
    </Field>
  );
}

const num = (text: string) => toNumber(text) ?? 0;

export default function PensionSupportCalc() {
  const id = useId();
  const [kind, setKind] = useState<PensionKind>("old");
  // 老齢
  const [age65, setAge65] = useState<"yes" | "no">("yes");
  const [household, setHousehold] = useState<Answer>("yes");
  const [birth, setBirth] = useState<BirthGroup>("after");
  const [pension, setPension] = useState("700000");
  const [other, setOther] = useState("0");
  const [monthMode, setMonthMode] = useState<MonthMode>("full");
  const [paid, setPaid] = useState("40");
  const [exemptFull, setExemptFull] = useState("0");
  const [exemptQuarter, setExemptQuarter] = useState("0");
  // 障害・遺族
  const [grade, setGrade] = useState<"1" | "2">("2");
  const [sharing, setSharing] = useState("1");
  const [income, setIncome] = useState("0");
  const [dep, setDep] = useState({ general: "0", elderly: "0", specified: "0" });

  const toMonths = (text: string) => (monthMode === "years" ? yearsToMonths(num(text)) : Math.round(num(text)));
  const dependents: Dependents = { general: num(dep.general), elderly: num(dep.elderly), specified: num(dep.specified) };
  const input: PensionSupportInput =
    kind === "old"
      ? {
          kind: "old",
          age65: age65 === "yes",
          household,
          birth,
          pensionIncome: num(pension),
          otherIncome: num(other),
          paidMonths: monthMode === "full" ? PENSION_SUPPORT.months : toMonths(paid),
          exemptFullMonths: monthMode === "full" ? 0 : toMonths(exemptFull),
          exemptQuarterMonths: monthMode === "full" ? 0 : toMonths(exemptQuarter),
        }
      : kind === "disability"
        ? { kind: "disability", grade: grade === "1" ? 1 : 2, income: num(income), dependents }
        : { kind: "survivor", sharing: Number(sharing), income: num(income), dependents };
  const result = pensionSupport(input);
  const steps = nextSteps(input, result);
  const unit = monthMode === "years" ? "年" : "か月";
  const pay = PENSION_SUPPORT_NEXT_PAYMENT;

  return (
    <div className="grid gap-5">
      <Segmented
        name={`${id}-kind`}
        label="受けている年金"
        value={kind}
        onChange={setKind}
        options={[
          { value: "old", label: "老齢基礎年金" },
          { value: "disability", label: "障害基礎年金" },
          { value: "survivor", label: "遺族基礎年金" },
        ]}
      />

      {kind === "old" ? (
        <>
          <Segmented
            name={`${id}-age`}
            label="65歳以上ですか"
            value={age65}
            onChange={setAge65}
            options={[
              { value: "yes", label: "はい" },
              { value: "no", label: "いいえ" },
            ]}
          />
          <Segmented
            name={`${id}-household`}
            label="世帯全員の住民税（市町村民税）が非課税ですか"
            value={household}
            onChange={setHousehold}
            options={[
              { value: "yes", label: "はい" },
              { value: "no", label: "いいえ" },
              { value: "unknown", label: "わからない" },
            ]}
          />
          <Segmented
            name={`${id}-birth`}
            label="生まれた日"
            value={birth}
            onChange={setBirth}
            options={[
              { value: "after", label: "1956年（昭和31年）4月2日以後" },
              { value: "before", label: "1941年4月2日〜1956年4月1日" },
              { value: "veryOld", label: "1941年（昭和16年）4月1日以前" },
            ]}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberInput
              id={`${id}-pension`}
              label={`${PENSION_SUPPORT_PERIOD.incomeYear}の公的年金等の収入`}
              help="1年分の額面。障害年金・遺族年金は入れません。"
              value={pension}
              onChange={setPension}
              unit="円"
            />
            <NumberInput id={`${id}-other`} label="同じ年のその他の所得" help="年金のほかに所得がなければ0。" value={other} onChange={setOther} unit="円" />
          </div>
          <Segmented
            name={`${id}-months`}
            label="保険料を納めた期間"
            value={monthMode}
            onChange={setMonthMode}
            options={[
              { value: "full", label: "40年すべて納めた" },
              { value: "years", label: "年数で入れる" },
              { value: "months", label: "月数で入れる" },
            ]}
          />
          {monthMode !== "full" ? (
            <div className="grid gap-4 sm:grid-cols-3">
              <NumberInput id={`${id}-paid`} label="納めた期間" value={paid} onChange={setPaid} unit={unit} />
              <NumberInput id={`${id}-exf`} label="全額・4分の3・半額免除" value={exemptFull} onChange={setExemptFull} unit={unit} />
              <NumberInput id={`${id}-exq`} label="4分の1免除" value={exemptQuarter} onChange={setExemptQuarter} unit={unit} />
              <p className="text-note leading-[1.7] text-ink-soft sm:col-span-3">
                納めた期間と免除の期間は、年金証書や支給額変更通知書で確かめられます。合計は40年（480か月）までです。
              </p>
            </div>
          ) : null}
        </>
      ) : (
        <>
          {kind === "disability" ? (
            <Segmented
              name={`${id}-grade`}
              label="障害等級"
              value={grade}
              onChange={setGrade}
              options={[
                { value: "1", label: "1級" },
                { value: "2", label: "2級" },
              ]}
            />
          ) : (
            <div className="min-w-0">
              <label htmlFor={`${id}-sharing`} className="text-note font-bold text-ink">遺族基礎年金を受けている人</label>
              <select id={`${id}-sharing`} value={sharing} onChange={(e) => setSharing(e.target.value)} className={INPUT_CLASS}>
                <option value="1">配偶者、または子が1人</option>
                {[2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>{`子が${n}人`}</option>
                ))}
              </select>
            </div>
          )}
          <NumberInput
            id={`${id}-income`}
            label={`${PENSION_SUPPORT_PERIOD.incomeYear}の所得`}
            help="障害年金・遺族年金は入れません。"
            value={income}
            onChange={setIncome}
            unit="円"
          />
          <div className="grid gap-4 sm:grid-cols-3">
            <NumberInput id={`${id}-dg`} label="扶養親族（下の2つ以外）" value={dep.general} onChange={(v) => setDep({ ...dep, general: v })} unit="人" />
            <NumberInput id={`${id}-de`} label="70歳以上の配偶者・老人扶養親族" value={dep.elderly} onChange={(v) => setDep({ ...dep, elderly: v })} unit="人" />
            <NumberInput id={`${id}-ds`} label="特定扶養親族・16〜18歳" value={dep.specified} onChange={(v) => setDep({ ...dep, specified: v })} unit="人" />
          </div>
        </>
      )}

      <div className="rounded-xl bg-surface px-4 py-4" aria-live="polite" data-pension-support-result>
        <p className="text-meta font-bold text-accent">{result.benefit}</p>
        <p className="mt-1 text-[1.25rem] font-bold leading-tight text-ink" data-verdict={result.verdict}>{VERDICT_LABELS[result.verdict]}</p>
        {result.monthly !== null && result.monthly > 0 ? (
          <dl className="mt-2">
            <ResultRow label={`1回の支払い（2か月分。${pay.year}年${pay.month}月なら${pay.months[0]}月・${pay.months[1]}月分）`} value={yen(result.perPayment ?? 0)} strong />
            <ResultRow label="月額" value={yen(result.monthly)} />
            <ResultRow label="1年分（12か月）" value={yen(result.annual ?? 0)} sub={`${PENSION_SUPPORT.fiscalYear}の額のまま`} />
          </dl>
        ) : null}
        <ul className="mt-3 grid list-disc gap-1 pl-5 text-note leading-[1.7] text-ink-soft">
          {result.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        {result.steps.length > 0 ? (
          <ul className="mt-3 grid gap-1 border-t border-line pt-3 text-note tabular-nums text-ink-soft">
            {result.steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        ) : null}
        <p className="mt-3 border-t border-line pt-3 text-note font-bold text-ink">次にすること</p>
        <ul className="mt-1 grid list-disc gap-1 pl-5 text-note leading-[1.7] text-ink-soft">
          {steps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
