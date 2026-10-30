"use client";

import { useState } from "react";
import { estimateDifyCreditRuns, MAX_DIFY_CREDIT_INPUT, type CreditInputError } from "@/lib/dify-credits";

const INPUT_CLASS = "mt-2 w-full rounded-lg border border-line-strong bg-paper px-3 py-2.5 text-desc text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
const ERROR_MESSAGES: Record<CreditInputError, string> = {
  format: "0以上の半角数字で入力してください。カンマ・指数表記・負の数は使えません。",
  precision: "この計算欄では、小数点以下6桁まで入力できます。",
  range: "この計算欄の入力上限は1,000,000クレジットです。Difyの利用上限を示す数字ではありません。",
  zero: "1回の消費量には、0より大きい数を入力してください。消費が確認できない場合は回数を計算できません。",
};

/** 入力は画面内の計算だけに使用。通信・保存・追加計測は行わない。 */
export default function DifyCreditEstimator() {
  const [remaining, setRemaining] = useState("");
  const [perRun, setPerRun] = useState("");
  const estimate = estimateDifyCreditRuns(remaining, perRun);

  return (
    <section id="credit-estimator" aria-labelledby="credit-estimator-heading" className="mt-10 scroll-mt-24 rounded-xl border border-line bg-surface p-5 sm:p-6">
      <h2 id="credit-estimator-heading" className="t-h3">残りクレジットで、あと何回試せる？</h2>
      <p id="credit-estimator-description" className="mt-3 text-desc leading-[1.85] text-ink-soft">
        同じ処理を1回試し、前後で減ったクレジット数を入力します。モデルや呼び出し回数など、同じ条件が続く場合の目安を計算します。
      </p>

      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="credit-estimator-remaining" className="text-desc font-bold text-ink">現在の残りクレジット</label>
          <input
            id="credit-estimator-remaining"
            type="number"
            inputMode="decimal"
            min="0"
            max={MAX_DIFY_CREDIT_INPUT}
            step="any"
            value={remaining}
            onChange={(event) => setRemaining(event.target.value)}
            autoComplete="off"
            className={INPUT_CLASS}
            aria-invalid={estimate.remainingError !== null}
            aria-describedby={`credit-estimator-description credit-estimator-remaining-help${estimate.remainingError ? " credit-estimator-remaining-error" : ""}`}
          />
          <p id="credit-estimator-remaining-help" className="mt-2 text-note leading-[1.75] text-ink-soft">試運転が終わった後の残量です。0も入力できます。</p>
          {estimate.remainingError ? <p id="credit-estimator-remaining-error" className="mt-2 text-note font-semibold leading-[1.75] text-ink">{ERROR_MESSAGES[estimate.remainingError]}</p> : null}
        </div>
        <div>
          <label htmlFor="credit-estimator-per-run" className="text-desc font-bold text-ink">同じ処理1回の消費クレジット</label>
          <input
            id="credit-estimator-per-run"
            type="number"
            inputMode="decimal"
            min="0"
            max={MAX_DIFY_CREDIT_INPUT}
            step="any"
            value={perRun}
            onChange={(event) => setPerRun(event.target.value)}
            autoComplete="off"
            className={INPUT_CLASS}
            aria-invalid={estimate.perRunError !== null}
            aria-describedby={`credit-estimator-description credit-estimator-per-run-help${estimate.perRunError ? " credit-estimator-per-run-error" : ""}`}
          />
          <p id="credit-estimator-per-run-help" className="mt-2 text-note leading-[1.75] text-ink-soft">試運転前の残量から、試運転後の残量を引いた数です。</p>
          {estimate.perRunError ? <p id="credit-estimator-per-run-error" className="mt-2 text-note font-semibold leading-[1.75] text-ink">{ERROR_MESSAGES[estimate.perRunError]}</p> : null}
        </div>
      </div>

      <p role="status" aria-live="polite" aria-atomic="true" className="mt-5 border-l-2 border-accent pl-3 text-desc font-bold leading-[1.85] text-ink">
        {estimate.status === "ready"
          ? `同じ条件なら、あと約${estimate.runs?.toLocaleString("ja-JP")}回分が目安です。`
          : estimate.status === "invalid"
            ? "入力欄の案内を確認してください。目安はまだ計算していません。"
            : "残量と1回の消費量を入力すると、目安を表示します。"}
      </p>
      <p className="mt-3 text-desc leading-[1.85] text-ink-soft">
        消費量が変われば回数も変わります。この計算には自分のAPIキーの利用料金を含みません。実行できる回数や、追加の請求がないことを保証するものではありません。
      </p>
      <p className="mt-3 text-note leading-[1.75] text-ink-soft">この計算欄は、入力値を送信・保存しません。</p>

      <div className="mt-5 border-t border-line pt-4">
        <p className="text-desc font-bold leading-[1.85] text-ink">計算式：残りクレジット ÷ 1回の消費量（小数点以下を切り捨て）</p>
        <p className="mt-2 text-desc leading-[1.85] text-ink-soft">
          仮に残り200クレジットなら、1回1クレジットで200回、5クレジットで40回、10クレジットで20回です。これは計算例で、各モデルの実際の消費量を示していません。
        </p>
        <p className="mt-2 text-note leading-[1.75] text-ink-soft">200クレジットを毎月もらえる、どの質問も200回無料でできる、という意味ではありません。</p>
        <noscript><p className="mt-3 text-note leading-[1.75] text-ink-soft">入力による計算にはJavaScriptが必要です。上の式と例を使って、手元でも目安を計算できます。</p></noscript>
      </div>
    </section>
  );
}
