"use client";

import { useId, useState } from "react";
import { BONUS_EXAMPLE, KYOKAI_HEALTH_RATES, bonusTedori, percentJa, yenJa } from "@/lib/bonus-tedori";
import { Field, INPUT_CLASS, ResultRow, Segmented, toNumber } from "@/components/calc/parts";

/**
 * 冬のボーナス（賞与）の手取り（/tools/bonus-tedori と、見出しに「ボーナス」「賞与」がある記事の中）。式は lib/bonus-tedori.ts。
 * 入力は画面の中の計算だけに使い、送信・保存はしない。最初の値はページの「計算の例」と同じ（BONUS_EXAMPLE）。
 */
const DEPENDENTS = ["0", "1", "2", "3", "4", "5", "6", "7"] as const;

export default function BonusTedoriCalc() {
  const id = useId();
  const [bonus, setBonus] = useState(String(BONUS_EXAMPLE.bonus));
  const [prev, setPrev] = useState(String(BONUS_EXAMPLE.prevNet));
  const [dependents, setDependents] = useState<(typeof DEPENDENTS)[number]>(String(BONUS_EXAMPLE.dependents) as (typeof DEPENDENTS)[number]);
  const [kaigo, setKaigo] = useState(BONUS_EXAMPLE.kaigo);
  const [insurer, setInsurer] = useState<"kyokai" | "kumiai">("kyokai");
  const [prefecture, setPrefecture] = useState(BONUS_EXAMPLE.prefecture ?? "東京都");
  const [kumiaiHealth, setKumiaiHealth] = useState("");
  const [kumiaiKaigo, setKumiaiKaigo] = useState("");
  const [kumiaiShien, setKumiaiShien] = useState("");

  const bonusValue = toNumber(bonus) ?? 0;
  const result = bonusTedori({
    bonus: bonusValue,
    prevNet: toNumber(prev) ?? 0,
    dependents: Number(dependents),
    kaigo,
    prefecture,
    insurer,
    kumiaiHealth: toNumber(kumiaiHealth) ?? 0,
    kumiaiKaigo: toNumber(kumiaiKaigo) ?? 0,
    kumiaiShien: toNumber(kumiaiShien) ?? 0,
  });
  const rate = (value: number) => `本人負担 ${percentJa(value)}`;

  return (
    <div className="grid gap-5">
      <Field id={`${id}-bonus`} label="ボーナスの額面（支給額）" help="明細の「支給額」です。何も引かれていない額を入れます。">
        <div className="flex items-center gap-2">
          <input id={`${id}-bonus`} inputMode="numeric" autoComplete="off" value={bonus} onChange={(e) => setBonus(e.target.value)} className={INPUT_CLASS} />
          <span className="mt-1.5 shrink-0 text-note text-ink-soft">円</span>
        </div>
      </Field>
      <Field
        id={`${id}-prev`}
        label="前月の給与から社会保険料を引いた額"
        help="ボーナスの前の月の給与明細で、支給額（総支給額）から健康保険・厚生年金・雇用保険などの社会保険料を引いた額です。所得税と住民税は引きません。所得税の率はこの額で決まります。"
      >
        <div className="flex items-center gap-2">
          <input id={`${id}-prev`} inputMode="numeric" autoComplete="off" value={prev} onChange={(e) => setPrev(e.target.value)} className={INPUT_CLASS} />
          <span className="mt-1.5 shrink-0 text-note text-ink-soft">円</span>
        </div>
      </Field>
      <Segmented
        name={`${id}-dep`}
        label="扶養親族等の数（年末調整の書類に書いた人数）"
        value={dependents}
        options={DEPENDENTS.map((d) => ({ value: d, label: d === "7" ? "7人以上" : `${d}人` }))}
        onChange={setDependents}
      />
      <p className="-mt-3 text-note leading-[1.7] text-ink-soft">
        会社に出した「扶養控除等申告書」に書いた、所得の少ない配偶者（源泉控除対象配偶者）と16歳以上の扶養している家族の数です。16歳未満の子どもは原則として数えません（本人や家族が障害者に当たるときなどは、人数を足します）。分からないときは給与明細の「扶養人数」を見てください。
      </p>
      <label className="flex items-start gap-2 text-note text-ink">
        <input type="checkbox" checked={kaigo} onChange={(e) => setKaigo(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-accent" />
        <span>
          <span className="font-bold">40歳から64歳まで</span>
          <span className="block text-ink-soft">この年齢の人は、介護保険料も引かれます。</span>
        </span>
      </label>
      <Segmented
        name={`${id}-ins`}
        label="加入している健康保険"
        value={insurer}
        options={[
          { value: "kyokai", label: "協会けんぽ" },
          { value: "kumiai", label: "健康保険組合（率を入れる）" },
        ]}
        onChange={setInsurer}
      />
      {insurer === "kyokai" ? (
        <Field id={`${id}-pref`} label="会社（勤め先の事業所）がある都道府県" help="協会けんぽの健康保険料率は、都道府県ごとに違います。保険証や資格確認書に「全国健康保険協会」とあれば協会けんぽです。">
          <select id={`${id}-pref`} value={prefecture} onChange={(e) => setPrefecture(e.target.value)} className={INPUT_CLASS}>
            {KYOKAI_HEALTH_RATES.map(([name, value]) => (
              <option key={name} value={name}>{`${name}（${percentJa(value)}）`}</option>
            ))}
          </select>
        </Field>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id={`${id}-kh`} label="健康保険料率（本人負担・%）" help="健康保険組合の案内に書かれた、本人（被保険者）が負担する率です。">
            <input id={`${id}-kh`} inputMode="decimal" autoComplete="off" value={kumiaiHealth} onChange={(e) => setKumiaiHealth(e.target.value)} className={INPUT_CLASS} />
          </Field>
          <Field id={`${id}-kk`} label="介護保険料率（本人負担・%）" help="40歳から64歳までの人だけ使います。">
            <input id={`${id}-kk`} inputMode="decimal" autoComplete="off" value={kumiaiKaigo} onChange={(e) => setKumiaiKaigo(e.target.value)} className={INPUT_CLASS} />
          </Field>
          <Field id={`${id}-ks`} label="子ども・子育て支援金率（本人負担・%）" help="2026年4月分から始まった支援金の率です。">
            <input id={`${id}-ks`} inputMode="decimal" autoComplete="off" value={kumiaiShien} onChange={(e) => setKumiaiShien(e.target.value)} className={INPUT_CLASS} />
          </Field>
          <p className="text-note leading-[1.7] text-ink-soft sm:col-span-3">空のままの欄は0%として計算します。率は健康保険組合のホームページや会社の案内で確かめてください。</p>
        </div>
      )}

      <div className="rounded-xl bg-surface px-4 py-4" aria-live="polite" data-bonus-result>
        <p className="text-meta font-bold text-accent">{result.tax === null ? "手取りの目安（所得税を引く前）" : "ボーナスの手取りの目安"}</p>
        <p className="mt-1 text-ink">
          <span className="text-[2rem] font-bold leading-tight tabular-nums" data-bonus-takehome>{yenJa(result.takeHome)}</span>
        </p>
        <p className="text-note text-ink-soft">{`額面${yenJa(bonusValue)}から、合わせて${yenJa(bonusValue - result.takeHome)}が引かれます`}</p>
        <dl className="mt-2">
          <ResultRow label="健康保険料" value={yenJa(result.health)} sub={rate(result.rates.health)} />
          {kaigo ? <ResultRow label="介護保険料" value={yenJa(result.kaigo)} sub={rate(result.rates.kaigo)} /> : null}
          <ResultRow label="子ども・子育て支援金" value={yenJa(result.shien)} sub={rate(result.rates.shien)} />
          <ResultRow
            label="厚生年金保険料"
            value={yenJa(result.pension)}
            sub={result.pensionStandard < result.standard ? `${rate(result.rates.pension)}。1回150万円までにかかります` : rate(result.rates.pension)}
          />
          <ResultRow label="雇用保険料" value={yenJa(result.koyo)} sub={rate(result.rates.koyo)} />
          <ResultRow
            label="所得税（復興特別所得税を含む）"
            value={result.tax === null ? "この計算では出せません" : yenJa(result.tax)}
            sub={result.taxRate !== null ? `社会保険料を引いた${yenJa(bonusValue - result.social)}×${percentJa(result.taxRate)}` : undefined}
          />
          <ResultRow label="手取り" value={yenJa(result.takeHome)} strong />
        </dl>
        {result.taxNote ? (
          <p className="mt-2 text-note leading-[1.7] text-ink">
            {result.taxNote === "no-prev"
              ? "前月の給与が無いときは、ボーナスの所得税は別の表（月額表）で計算するため、この計算機では出せません。上の手取りは所得税を引く前の額です。"
              : "ボーナス（社会保険料を引いた額）が前月の給与（社会保険料を引いた額）の10倍を超えるときは、所得税は別の表（月額表）で計算するため、この計算機では出せません。上の手取りは所得税を引く前の額です。"}
          </p>
        ) : null}
        <ul className="mt-3 grid list-disc gap-1 pl-5 text-note leading-[1.7] text-ink-soft">
          <li>住民税はボーナスからは引かれません（毎月の給与から引かれます）。</li>
          <li>社会保険料は、ボーナスの1,000円未満を切り捨てた額（標準賞与額）に率を掛けます。雇用保険料はボーナスの額そのものに掛けます。</li>
        </ul>
      </div>
    </div>
  );
}
