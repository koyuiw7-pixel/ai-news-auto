"use client";

import { useId, useState } from "react";
import { FURUSATO_TAX_RATES, furusatoLimit, furusatoSpecialShare, yen, type FurusatoTaxRate } from "@/lib/calc-math";
import { furusatoEasy, furusatoManYen, incomeTaxEstimate } from "@/lib/furusato-easy";
import { Field, INPUT_CLASS, Segmented, toNumber } from "@/components/calc/parts";

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

type Mode = "easy" | "notice";

/**
 * ふるさと納税の上限額の目安（/tools/furusato-limit と、ふるさと納税の記事の中）。
 * かんたん（年収と家族構成。lib/furusato-easy.ts）と、くわしく（住民税決定通知書の所得割額。lib/calc-math.ts）の2つ。
 * 入力は画面の中の計算だけに使い、送信・保存はしない。
 */
export default function FurusatoLimitCalc() {
  const id = useId();
  const [mode, setMode] = useState<Mode>("easy");
  return (
    <div>
      <Segmented
        name={`${id}-mode`}
        label="計算のしかた"
        value={mode}
        onChange={setMode}
        options={[
          { value: "easy", label: "年収から（かんたん）" },
          { value: "notice", label: "住民税の通知書から" },
        ]}
      />
      <div className="mt-5">{mode === "easy" ? <EasyMode /> : <NoticeMode />}</div>
    </div>
  );
}

/** 0〜3人の人数を選ぶ（スマホで押しやすいボタン） */
function Count({ name, label, help, value, onChange }: { name: string; label: string; help: string; value: number; onChange: (n: number) => void }) {
  return (
    <fieldset className="min-w-0">
      <legend className="text-note font-bold text-ink">{label}</legend>
      <div className="mt-1.5 flex gap-2">
        {[0, 1, 2, 3].map((n) => (
          <label
            key={n}
            className={`flex h-11 min-w-11 cursor-pointer items-center justify-center rounded-lg border px-3 text-note font-bold tabular-nums has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent ${
              value === n ? "border-accent bg-accent-soft text-ink" : "border-line-strong bg-paper text-ink-soft hover:border-ink"
            }`}
          >
            <input type="radio" name={name} value={n} checked={value === n} onChange={() => onChange(n)} className="sr-only" />
            {n === 3 ? "3人" : `${n}人`}
          </label>
        ))}
      </div>
      <p className="mt-1.5 text-note leading-[1.7] text-ink-soft">{help}</p>
    </fieldset>
  );
}

function EasyMode() {
  const id = useId();
  const [salary, setSalary] = useState("500");
  const [spouse, setSpouse] = useState<"no" | "yes">("no");
  const [teens, setTeens] = useState(0);
  const [students, setStudents] = useState(0);
  const [social, setSocial] = useState("");
  const [ideco, setIdeco] = useState("");
  const [other, setOther] = useState("");
  const [loan, setLoan] = useState("");

  const man = toNumber(salary);
  const salaryYen = man === null ? 0 : Math.round(man * 10000);
  const socialYen = toNumber(social);
  const input = {
    salary: salaryYen,
    spouse: spouse === "yes",
    teens,
    students,
    socialInsurance: socialYen === null || social.trim() === "" ? undefined : socialYen,
    ideco: toNumber(ideco) ?? 0,
    otherDeductions: toNumber(other) ?? 0,
  };
  const result = salaryYen > 0 ? furusatoEasy(input) : null;
  const loanYen = toNumber(loan) ?? 0;
  const incomeTax = loanYen > 0 && salaryYen > 0 ? incomeTaxEstimate(input) : 0;
  const advancedUsed = input.socialInsurance !== undefined || input.ideco > 0 || input.otherDeductions > 0;

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id={`${id}-salary`} label="今年の給与の年収（額面・万円）" help="ボーナスを含む、税金などが引かれる前の金額です。見込みでかまいません。">
          <div className="relative">
            <input
              id={`${id}-salary`}
              type="text"
              inputMode="decimal"
              autoComplete="off"
              placeholder="例：500"
              value={salary}
              onChange={(e) => setSalary(e.target.value)}
              className={`${INPUT_CLASS} pr-12`}
            />
            <span className="pointer-events-none absolute right-3 top-1/2 mt-[3px] -translate-y-1/2 text-note text-ink-soft">万円</span>
          </div>
        </Field>
        <Segmented
          name={`${id}-spouse`}
          label="配偶者"
          value={spouse}
          onChange={setSpouse}
          options={[
            { value: "no", label: "いない・共働き" },
            { value: "yes", label: "収入のない配偶者がいる" },
          ]}
        />
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Count name={`${id}-teens`} label="16〜18歳の子（高校生など）" help="扶養している人数です。" value={teens} onChange={setTeens} />
        <Count name={`${id}-students`} label="19〜22歳の子（大学生など）" help="中学生以下の子は、上限に影響しません。" value={students} onChange={setStudents} />
      </div>

      <details className="group mt-4 rounded-xl border border-line px-4 py-3">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-note font-bold text-ink">
          <span>くわしく入れる（任意）</span>
          <span aria-hidden className="text-muted transition-transform group-open:rotate-45">＋</span>
        </summary>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field id={`${id}-social`} label="社会保険料の年額（円）" help="源泉徴収票の「社会保険料等の金額」。空のままなら年収の15%で計算します。">
            <input id={`${id}-social`} type="text" inputMode="numeric" autoComplete="off" placeholder="例：750000" value={social} onChange={(e) => setSocial(e.target.value)} className={INPUT_CLASS} />
          </Field>
          <Field id={`${id}-ideco`} label="iDeCo・小規模企業共済の掛金の年額（円）" help="掛金は所得から引かれるので、上限は少し下がります。">
            <input id={`${id}-ideco`} type="text" inputMode="numeric" autoComplete="off" placeholder="例：276000" value={ideco} onChange={(e) => setIdeco(e.target.value)} className={INPUT_CLASS} />
          </Field>
          <Field id={`${id}-other`} label="ほかの所得控除の合計（円）" help="生命保険料控除・医療費控除など。住民税の控除額で入れます。">
            <input id={`${id}-other`} type="text" inputMode="numeric" autoComplete="off" placeholder="例：70000" value={other} onChange={(e) => setOther(e.target.value)} className={INPUT_CLASS} />
          </Field>
          <Field id={`${id}-loan`} label="住宅ローン控除の年額（円）" help="上限が変わるかどうかを下に出します。">
            <input id={`${id}-loan`} type="text" inputMode="numeric" autoComplete="off" placeholder="例：200000" value={loan} onChange={(e) => setLoan(e.target.value)} className={INPUT_CLASS} />
          </Field>
        </div>
      </details>

      <div className="mt-5 rounded-xl bg-surface px-4 py-5" aria-live="polite" data-furusato-result="easy">
        {result && result.rounded >= 3000 ? (
          <>
            <p className="text-[1.5rem] font-bold leading-snug text-ink sm:text-[1.75rem]">
              約<span className="tabular-nums">{furusatoManYen(result.rounded)}</span>万円まで寄附して、負担は2,000円
            </p>
            <p className="mt-1.5 text-note tabular-nums text-ink-soft">{`計算では${yen(result.limit)}（1年間の寄附の合計。1,000円未満は切り捨てて表示）`}</p>
            <p className="mt-3 text-meta leading-[1.7] text-ink-soft">
              {advancedUsed
                ? "給与収入だけ・入れた控除のほかは控除なし・ワンストップ特例で申し込む場合の目安です。"
                : "給与収入だけ・社会保険料は年収の15%・ほかの控除なし・ワンストップ特例で申し込む場合の目安です。"}
              {salaryYen > 9_000_000 && input.socialInsurance === undefined ? "年収900万円を超える人は社会保険料が15%より少ないことが多く、目安は少なめに出ます。" : ""}
            </p>
          </>
        ) : result ? (
          <p className="text-note leading-[1.7] text-ink-soft">この条件では住民税の所得割がほとんどかからないため、ふるさと納税で2,000円を超えて戻る分はほとんどありません。</p>
        ) : (
          <p className="text-note leading-[1.7] text-ink-soft">年収を入れると、ここに寄附額の目安が出ます。</p>
        )}
        {result && loanYen > 0 ? (
          <p className="mt-3 border-t border-line pt-3 text-note leading-[1.7] text-ink-soft">
            {loanYen <= incomeTax
              ? `住宅ローン控除（${yen(loanYen)}）は、所得税の目安（${yen(incomeTax)}）の中で引ききれる見込みです。上の目安は変わりません。`
              : `住宅ローン控除（${yen(loanYen)}）が所得税の目安（${yen(incomeTax)}）より大きい見込みです。ワンストップ特例で申し込むなら上の目安のままですが、確定申告をする年（住宅ローン控除の1年目など）は、上限が下がることがあります。`}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function NoticeMode() {
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
        <Field id={`${id}-city`} label="市区町村民税の所得割額（円）" help="住民税決定通知書の「所得割額」の欄の金額です。均等割額は入れません。">
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
        <Field id={`${id}-rate`} label="所得税の税率（かっこの中は、課税される所得金額）" help="迷うときは低いほうの税率を選ぶと、目安は少なめに出ます。">
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

      <div className="mt-5 rounded-xl bg-surface px-4 py-4" aria-live="polite" data-furusato-result="notice">
        {result && share !== null ? (
          <>
            <p className="text-[1.5rem] font-bold leading-snug text-ink sm:text-[1.75rem]">
              約<span className="tabular-nums">{furusatoManYen(result.rounded)}</span>万円まで寄附して、負担は2,000円
            </p>
            <dl className="mt-3 divide-y divide-line border-t border-line text-note text-ink-soft">
              <div className="flex items-baseline justify-between gap-4 py-2">
                <dt>計算した寄附額の目安</dt>
                <dd className="font-bold tabular-nums text-ink">{yen(result.limit)}</dd>
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
