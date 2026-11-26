"use client";

import { useId, useState } from "react";
import { DENKI_GAS_DEFAULT, DENKI_GAS_MONTHS, denkiGasDiscount, unitPrice, winterUsage, yenDecimal, type DenkiGasMonthKey } from "@/lib/denki-gas-discount";
import { Field, INPUT_CLASS, ResultRow, toNumber } from "@/components/calc/parts";

/**
 * 冬の電気・ガス料金支援の「うちの場合」（/tools/denki-gas-discount と、電気・ガス料金支援の記事の中）。式は lib/denki-gas-discount.ts。
 * 入力は画面の中の計算だけに使い、送信・保存はしない。
 * 1月・2月の使用量は、書き換えるまでは12月×1.2（特設サイトの試算と同じ約2割増し）に合わせて動く。
 */
function NumberInput({ id, label, help, value, onChange, unit, disabled }: { id: string; label: string; help?: string; value: string; onChange: (v: string) => void; unit: string; disabled?: boolean }) {
  return (
    <Field id={id} label={label} help={help}>
      <div className="flex items-center gap-2">
        <input id={id} inputMode="decimal" autoComplete="off" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} className={`${INPUT_CLASS} disabled:opacity-50`} />
        <span className="mt-1.5 shrink-0 text-note text-ink-soft">{unit}</span>
      </div>
    </Field>
  );
}

const num = (text: string) => toNumber(text) ?? 0;
type Override = { electricity?: string; gas?: string };

export default function DenkiGasDiscountCalc() {
  const id = useId();
  const [decElectricity, setDecElectricity] = useState(String(DENKI_GAS_DEFAULT.electricity));
  const [decGas, setDecGas] = useState(String(DENKI_GAS_DEFAULT.gas));
  const [propane, setPropane] = useState(false);
  const [override, setOverride] = useState<Record<"jan" | "feb", Override>>({ jan: {}, feb: {} });

  const autoElectricity = String(winterUsage(num(decElectricity)));
  const autoGas = String(winterUsage(num(decGas)));
  const value = (key: "jan" | "feb", kind: "electricity" | "gas") => override[key][kind] ?? (kind === "electricity" ? autoElectricity : autoGas);
  const setValue = (key: "jan" | "feb", kind: "electricity" | "gas", v: string) => setOverride({ ...override, [key]: { ...override[key], [kind]: v } });

  const result = denkiGasDiscount({
    dec: { electricity: num(decElectricity), gas: num(decGas) },
    jan: { electricity: num(value("jan", "electricity")), gas: num(value("jan", "gas")) },
    feb: { electricity: num(value("feb", "electricity")), gas: num(value("feb", "gas")) },
    propane,
  });
  const unitOf = (key: DenkiGasMonthKey) => DENKI_GAS_MONTHS.find((m) => m.key === key)!;

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <NumberInput
          id={`${id}-dec-e`}
          label="12月の電気の使用量"
          help="検針票や電力会社のアプリの「ご使用量」。家庭の電気（低圧）です。"
          value={decElectricity}
          onChange={setDecElectricity}
          unit="kWh"
        />
        <NumberInput
          id={`${id}-dec-g`}
          label="12月の都市ガスの使用量"
          help="ガスを使っていなければ0。"
          value={propane ? "0" : decGas}
          onChange={setDecGas}
          unit="㎥"
          disabled={propane}
        />
      </div>
      <label className="flex items-start gap-2 text-note text-ink">
        <input type="checkbox" checked={propane} onChange={(e) => setPropane(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-accent" />
        <span>
          <span className="font-bold">家のガスはプロパンガス（LPガス）</span>
          <span className="block text-ink-soft">プロパンガスはこの支援の対象外です。ガスの値引きを0円にして、電気だけを計算します。</span>
        </span>
      </label>

      <details className="rounded-xl border border-line px-4 py-3">
        <summary className="cursor-pointer text-note font-bold text-ink">1月・2月の使用量を変える（初期値は12月の1.2倍）</summary>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {(["jan", "feb"] as const).map((key) => (
            <div key={key} className="contents">
              <NumberInput
                id={`${id}-${key}-e`}
                label={`${unitOf(key).label}の電気`}
                value={value(key, "electricity")}
                onChange={(v) => setValue(key, "electricity", v)}
                unit="kWh"
              />
              <NumberInput
                id={`${id}-${key}-g`}
                label={`${unitOf(key).label}の都市ガス`}
                value={propane ? "0" : value(key, "gas")}
                onChange={(v) => setValue(key, "gas", v)}
                unit="㎥"
                disabled={propane}
              />
            </div>
          ))}
        </div>
        <p className="mt-3 text-note leading-[1.7] text-ink-soft">昨年の1月・2月の検針票があれば、その使用量を入れると目安が近くなります。</p>
      </details>

      <div className="rounded-xl bg-surface px-4 py-4" aria-live="polite" data-denki-gas-result>
        <p className="text-meta font-bold text-accent">2026年12月〜2027年2月使用分の3か月で</p>
        <p className="mt-1 text-ink">
          <span className="text-[2rem] font-bold leading-tight tabular-nums" data-denki-gas-total>{yenDecimal(result.total)}</span>
          <span className="ml-1 text-desc font-bold">安くなる目安</span>
        </p>
        <dl className="mt-2">
          {result.months.map((m) => (
            <ResultRow
              key={m.key}
              label={m.label}
              value={yenDecimal(m.total)}
              sub={`電気 ${yenDecimal(m.electricity)}（${m.usage.electricity.toLocaleString("ja-JP")}kWh×${unitPrice(unitOf(m.key).electricity)}）・ガス ${yenDecimal(m.gas)}（${m.usage.gas.toLocaleString("ja-JP")}㎥×${unitPrice(unitOf(m.key).gas)}）`}
            />
          ))}
          <ResultRow label="3か月の合計（電気）" value={yenDecimal(result.electricity)} />
          <ResultRow label="3か月の合計（都市ガス）" value={yenDecimal(result.gas)} />
        </dl>
        <ul className="mt-3 grid list-disc gap-1 pl-5 text-note leading-[1.7] text-ink-soft">
          <li>申請は不要です。参加している電力・ガス会社の請求で、自動で値引きされます。</li>
          {propane ? <li>プロパンガス（LPガス）は対象外のため、ガスの値引きは0円です。</li> : null}
          <li>実際の値引き額は、検針票や請求の明細で確かめてください（端数の扱いは会社ごとに異なります）。</li>
        </ul>
      </div>
    </div>
  );
}
