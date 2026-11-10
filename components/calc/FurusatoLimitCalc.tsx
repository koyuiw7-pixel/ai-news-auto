"use client";

import { useId, useState } from "react";
import { FURUSATO_TAX_RATES, furusatoLimit, furusatoSpecialShare, yen, type FurusatoTaxRate } from "@/lib/calc-math";
import { Field, INPUT_CLASS, toNumber } from "@/components/calc/parts";

/**
 * 所得税の税率と「課税される所得金額」の区切り（国税庁 タックスアンサー No.2260「所得税の税率」の速算表。2026-11-10 確認）。
 * 表の書き方は「1,950,000円から3,299,000円まで」（課税される所得金額は1,000円未満を切り捨てた額）。
 * スマホの選ぶ欄に収まるよう、同じ区切りを「195万〜330万円未満」と書いている（切り捨て前の金額で見ても同じ範囲）。
 * 0% は所得税がかからない人（国税庁 No.1155 の注「所得税率が0％である場合」）。
 */
const RATE_LABELS: Record<FurusatoTaxRate, string> = {
  0: "0%（所得税がかからない）",
  5: "5%（195万円未満）",
  10: "10%（195万〜330万円未満）",
  20: "20%（330万〜695万円未満）",
  23: "23%（695万〜900万円未満）",
  33: "33%（900万〜1,800万円未満）",
  40: "40%（1,800万〜4,000万円未満）",
  45: "45%（4,000万円以上）",
};

/**
 * ふるさと納税の上限額の目安（/tools/furusato-limit と、ふるさと納税の記事の中）。
 * 住民税の所得割額×20% ÷（90%−所得税の税率×1.021）＋2,000円（総務省の計算式。lib/calc-math.ts の furusatoLimit）。
 * 入力は画面の中の計算だけに使い、送信・保存はしない。
 */
export default function FurusatoLimitCalc() {
  const id = useId();
  const [city, setCity] = useState("");
  const [pref, setPref] = useState("");
  const [rate, setRate] = useState("");
  const levy = (toNumber(city) ?? 0) + (toNumber(pref) ?? 0);
  const ratePercent = rate === "" ? null : (Number(rate) as FurusatoTaxRate);
  const result = ratePercent === null ? null : furusatoLimit(levy, ratePercent);
  const share = ratePercent === null ? null : furusatoSpecialShare(ratePercent) / 1000;

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          id={`${id}-city`}
          label="市区町村民税の所得割額（円）"
          help="住民税決定通知書の「所得割額」の欄の金額です。均等割額は入れません。"
        >
          <input id={`${id}-city`} type="text" inputMode="numeric" autoComplete="off" placeholder="例：120000" value={city} onChange={(e) => setCity(e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field
          id={`${id}-pref`}
          label="道府県民税（都民税）の所得割額（円）"
          help="2つの合計が分かっているときは、合計を1つ目の欄に入れて、ここは空のままで計算できます。"
        >
          <input id={`${id}-pref`} type="text" inputMode="numeric" autoComplete="off" placeholder="例：80000" value={pref} onChange={(e) => setPref(e.target.value)} className={INPUT_CLASS} />
        </Field>
      </div>
      <div className="mt-4">
        <Field
          id={`${id}-rate`}
          label="所得税の税率（かっこの中は、課税される所得金額）"
          help="迷うときは低いほうの税率を選ぶと、目安は少なめに出ます。"
        >
          <select id={`${id}-rate`} value={rate} onChange={(e) => setRate(e.target.value)} className={INPUT_CLASS}>
            <option value="">選んでください</option>
            {FURUSATO_TAX_RATES.map((r) => (
              <option key={r} value={r}>
                {RATE_LABELS[r]}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div className="mt-5 rounded-xl bg-surface px-4 py-4" aria-live="polite" data-furusato-result>
        {result && share !== null ? (
          <>
            <p className="text-note font-bold text-ink">自己負担2,000円で済む寄附額の目安（1年間の合計）</p>
            <p className="mt-1 text-[1.75rem] font-bold leading-tight tabular-nums text-ink">{yen(result.limit)}</p>
            <dl className="mt-3 divide-y divide-line border-t border-line text-note text-ink-soft">
              <div className="flex items-baseline justify-between gap-4 py-2">
                <dt>1,000円未満を切り捨てた額</dt>
                <dd className="font-bold tabular-nums text-ink">{yen(result.rounded)}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-4 py-2">
                <dt>所得割額の合計</dt>
                <dd className="tabular-nums text-ink">{yen(Math.floor(levy))}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-4 py-2">
                <dt>住民税の特例分の上限（所得割額×20%）</dt>
                <dd className="tabular-nums text-ink">{yen(result.cap)}</dd>
              </div>
            </dl>
            <p className="mt-2 text-note leading-[1.7] text-ink-soft">
              式：{yen(Math.floor(levy))} × 20% ÷ {share}% ＋ 2,000円（{share}% ＝ 90% − 所得税の税率 × 1.021）
            </p>
          </>
        ) : (
          <p className="text-note leading-[1.7] text-ink-soft">所得割額を入れて税率を選ぶと、ここに寄附額の目安が出ます。</p>
        )}
      </div>
      <p className="mt-3 text-note leading-[1.7] text-ink-soft">
        通知書の所得割額は、前の年の収入で決まった金額です。今年の収入や家族の人数が変わった人は、目安もずれます。去年の住民税で寄附金の控除や住宅ローン控除を受けた人は、所得割額がその分小さくなっているので、目安は少なめに出ます。
      </p>
    </div>
  );
}
