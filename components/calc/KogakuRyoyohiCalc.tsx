"use client";

import { useId, useState } from "react";
import { KOGAKU_PERIOD, bandsFor, kogaku, manYen, yenJa, type KogakuAge, type KogakuBand } from "@/lib/kogaku-ryoyohi";
import { Field, INPUT_CLASS, ResultRow, Segmented, toNumber } from "@/components/calc/parts";

/**
 * 高額療養費の1か月の自己負担の上限（/tools/kogaku-ryoyohi と、見出しに「高額療養費」がある記事の中）。式は lib/kogaku-ryoyohi.ts。
 * 入力は画面の中の計算だけに使い、送信・保存はしない。
 * 入院の前は総医療費が分からないので、年齢と年収の区分だけで上限（定額の区分はその額、ほかは総医療費100万円のとき）をすぐ出す。総医療費は入れたときだけ使う。
 */
const AGES: { value: KogakuAge; label: string }[] = [
  { value: "under70", label: "69歳まで" },
  { value: "70to74", label: "70〜74歳" },
  { value: "75plus", label: "75歳以上" },
];

export default function KogakuRyoyohiCalc() {
  const id = useId();
  const [age, setAge] = useState<KogakuAge>("under70");
  const [band, setBand] = useState<KogakuBand>("u");
  const [total, setTotal] = useState("");
  const [many, setMany] = useState(false);
  const [outpatientOnly, setOutpatientOnly] = useState(false);
  const [share75, setShare75] = useState<"0.1" | "0.2">("0.1");

  const bands = bandsFor(age);
  const current = bands.find((b) => b.key === band) ?? bands[bands.length - 1];
  const senior = age !== "under70";
  const generalSenior = senior && current.outpatient !== undefined;
  const share = age === "75plus" && current.key === "e" ? Number(share75) : undefined;
  const result = kogaku({ age, band: current.key, totalMedical: toNumber(total) ?? undefined, many, outpatientOnly: generalSenior && outpatientOnly, share });
  const sharePercent = `${Math.round(result.share * 10)}割`;

  return (
    <div className="grid gap-5">
      <Segmented name={`${id}-age`} label="治療を受ける人の年齢" value={age} options={AGES} onChange={setAge} />
      <Segmented
        name={`${id}-band`}
        label="年収の区分（目安）"
        value={current.key}
        options={bands.map((b) => ({ value: b.key, label: b.label }))}
        onChange={setBand}
      />
      <p className="-mt-3 text-note leading-[1.7] text-ink-soft">
        {`正しくは：${(senior && current.seniorDetail) || current.detail}。会社の健康保険は本人（被保険者）の標準報酬月額で決まり、家族（被扶養者）も同じ区分です。`}
      </p>

      <Field
        id={`${id}-total`}
        label="1か月の総医療費（分かれば）"
        help="保険がきく医療費の全額（10割）です。空のままなら100万円で計算します。窓口で3割を払った額が分かるときは、その額÷0.3が総医療費です。"
      >
        <div className="flex items-center gap-2">
          <input id={`${id}-total`} inputMode="numeric" autoComplete="off" placeholder="1000000" value={total} onChange={(e) => setTotal(e.target.value)} className={INPUT_CLASS} />
          <span className="mt-1.5 shrink-0 text-note text-ink-soft">円</span>
        </div>
      </Field>

      {current.many !== undefined ? (
        <label className="flex items-start gap-2 text-note text-ink">
          <input type="checkbox" checked={many} onChange={(e) => setMany(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-accent" />
          <span>
            <span className="font-bold">直近12か月に、上限に達した月がすでに3か月以上ある</span>
            <span className="block text-ink-soft">4か月目からは上限が下がります（多数回該当）。</span>
          </span>
        </label>
      ) : null}
      {generalSenior ? (
        <label className="flex items-start gap-2 text-note text-ink">
          <input type="checkbox" checked={outpatientOnly} onChange={(e) => setOutpatientOnly(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-accent" />
          <span>
            <span className="font-bold">この月は外来（通院）だけで、入院していない</span>
            <span className="block text-ink-soft">70歳以上は、外来だけの月にひとりごとの上限があります（外来特例）。</span>
          </span>
        </label>
      ) : null}
      {age === "75plus" && current.key === "e" ? (
        <Segmented
          name={`${id}-share`}
          label="窓口の負担割合（保険証・資格確認書に書かれた割合）"
          value={share75}
          options={[
            { value: "0.1", label: "1割" },
            { value: "0.2", label: "2割" },
          ]}
          onChange={setShare75}
        />
      ) : null}

      <div className="rounded-xl bg-surface px-4 py-4" aria-live="polite" data-kogaku-result>
        <p className="text-meta font-bold text-accent">
          {`${result.capLabel}${!result.fixed && !result.entered ? "（総医療費100万円のとき）" : ""}`}
        </p>
        <p className="mt-1 text-ink">
          <span className="text-[2rem] font-bold leading-tight tabular-nums" data-kogaku-cap>{yenJa(result.cap)}</span>
          <span className="ml-1 text-desc font-bold">まで</span>
        </p>
        <dl className="mt-2">
          {!result.fixed && result.band.threshold !== undefined ? (
            <ResultRow label="上限の式" value={`${yenJa(result.band.base)}＋（総医療費−${yenJa(result.band.threshold)}）×1%`} />
          ) : null}
          {result.manyCap !== undefined && !many && !(generalSenior && outpatientOnly) ? <ResultRow label="4か月目から（多数回該当）" value={yenJa(result.manyCap)} /> : null}
          <ResultRow
            label={`総医療費${yenJa(result.totalMedical)}の窓口負担（${sharePercent}）`}
            value={yenJa(result.windowShare)}
            sub={result.over > 0 ? `上限を超える${yenJa(result.over)}は、払わずに済むか、あとで戻ります` : "上限より少ないので、高額療養費の払い戻しはありません"}
          />
          <ResultRow label="この月の自己負担" value={yenJa(result.pay)} strong />
          <ResultRow
            label="年間の上限（8月〜翌年7月）"
            value={manYen(result.yearly)}
            sub={result.outpatientYearly ? `外来だけの年間の上限は${manYen(result.outpatientYearly)}` : undefined}
          />
        </dl>
        <ul className="mt-3 grid list-disc gap-1 pl-5 text-note leading-[1.7] text-ink-soft">
          <li>{`${KOGAKU_PERIOD.from}から${KOGAKU_PERIOD.to}までの上限額です。`}</li>
          <li>入院中の食事代や差額ベッド代など、保険がきかない費用は含みません。</li>
        </ul>
      </div>

      <div className="rounded-xl border-2 border-accent px-4 py-4" data-kogaku-action>
        <p className="text-desc font-bold text-ink">マイナ保険証か限度額適用認定証を使えば、窓口の支払いは最初から上限までになります</p>
        <ul className="mt-2 grid list-disc gap-1.5 pl-5 text-note leading-[1.75] text-ink-soft">
          <li>マイナ保険証（健康保険証の利用登録をしたマイナンバーカード）なら、事前の申請は要りません。マイナ保険証での確認（オンライン資格確認）に対応した病院・薬局なら、受付で上限の情報が伝わります。</li>
          <li>マイナ保険証を使わないときは、入院や支払いの前に、加入している健康保険に「限度額適用認定証」を申請して、病院の窓口に出します。</li>
          <li>住民税が非課税の人は、マイナ保険証を使う場合でも「限度額適用・標準負担額減額認定証」の申請が必要です（協会けんぽの案内）。</li>
          <li>窓口で上限より多く払ったときも、あとで申請すれば上限を超えた分が戻ります。</li>
        </ul>
      </div>
    </div>
  );
}
