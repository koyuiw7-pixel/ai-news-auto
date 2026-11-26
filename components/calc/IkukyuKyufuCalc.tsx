"use client";

import Link from "next/link";
import { useId, useState } from "react";
import {
  FIRST_DAYS,
  IKUKYU_EXAMPLE,
  MONTHLY_MAX,
  MONTHLY_MIN,
  PERIOD_DAYS,
  SHUSSEI_MAX_DAYS,
  SHUSSEI_MIN_DAYS,
  daysJa,
  ikukyuKyufu,
  yenJa,
  IKUKYU_RECEIVE,
} from "@/lib/ikukyu-kyufu";
import { Field, INPUT_CLASS, ReceiveSteps, ResultRow, Segmented, toNumber } from "@/components/calc/parts";

/**
 * 育児休業給付金と出生後休業支援給付金の目安（/tools/ikukyu-kyufu と、見出しに「育児休業給付」「育休」がある記事の中）。式は lib/ikukyu-kyufu.ts。
 * 入力は画面の中の計算だけに使い、送信・保存はしない。最初の値はページの「計算の例」と同じ（IKUKYU_EXAMPLE）。
 */
export default function IkukyuKyufuCalc() {
  const id = useId();
  const [monthly, setMonthly] = useState(String(IKUKYU_EXAMPLE.monthly));
  const [unit, setUnit] = useState<"month" | "day">("month");
  const [length, setLength] = useState(String(IKUKYU_EXAMPLE.days / PERIOD_DAYS));
  const [shussei, setShussei] = useState(IKUKYU_EXAMPLE.shussei);

  const monthlyValue = toNumber(monthly) ?? 0;
  const lengthValue = Math.max(0, Math.floor(toNumber(length) ?? 0));
  const days = unit === "month" ? lengthValue * PERIOD_DAYS : lengthValue;
  const r = ikukyuKyufu({ monthly: monthlyValue, days, shussei });
  const ready = monthlyValue > 0 && days > 0;

  return (
    <div className="grid gap-5">
      <Field
        id={`${id}-monthly`}
        label="育休の前の月給（額面）"
        help="育休を始める前の6か月の平均の目安です。残業代や通勤手当も入れ、税金や社会保険料を引く前の額にします。ボーナスは入れません。"
      >
        <div className="flex items-center gap-2">
          <input id={`${id}-monthly`} inputMode="numeric" autoComplete="off" value={monthly} onChange={(e) => setMonthly(e.target.value)} className={INPUT_CLASS} />
          <span className="mt-1.5 shrink-0 text-note text-ink-soft">円</span>
        </div>
      </Field>
      <Segmented
        name={`${id}-unit`}
        label="育休の長さの入れ方"
        value={unit}
        options={[
          { value: "month", label: "月数で" },
          { value: "day", label: "日数で" },
        ]}
        onChange={(next) => {
          setUnit(next);
          setLength(next === "day" ? String(lengthValue * PERIOD_DAYS) : String(Math.max(1, Math.round(lengthValue / PERIOD_DAYS))));
        }}
      />
      <Field
        id={`${id}-length`}
        label={unit === "month" ? "育休の予定（か月）" : "育休の予定（日）"}
        help="母親は、産後休業（出産の翌日から8週間）のあとから数えます。産後休業の間は健康保険の出産手当金で、この給付金の対象ではありません。1か月は30日で計算します。"
      >
        <div className="flex items-center gap-2">
          <input id={`${id}-length`} inputMode="numeric" autoComplete="off" value={length} onChange={(e) => setLength(e.target.value)} className={INPUT_CLASS} />
          <span className="mt-1.5 shrink-0 text-note text-ink-soft">{unit === "month" ? "か月" : "日"}</span>
        </div>
      </Field>
      <label className="flex items-start gap-2 text-note text-ink">
        <input type="checkbox" checked={shussei} onChange={(e) => setShussei(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-accent" />
        <span>
          <span className="font-bold">出生後休業支援給付金（13%の上乗せ）も受け取る</span>
          <span className="block text-ink-soft">
            子の出生後の決まった期間（父親は8週間、産後休業をした母親は16週間）に本人が14日以上の育休を取り、配偶者も出生後8週間までに14日以上の育休を取ると受け取れます。配偶者が自営業・無職・産後休業中のときなどは、配偶者の育休は要りません。
          </span>
        </span>
      </label>

      <div className="rounded-xl bg-surface px-4 py-4" aria-live="polite" data-ikukyu-result>
        {ready ? (
          <>
            <p className="text-meta font-bold text-accent">育休の最初の6か月にもらえる1か月の目安</p>
            <p className="mt-1 text-ink">
              <span className="text-[2rem] font-bold leading-tight tabular-nums" data-ikukyu-first>{yenJa(r.firstMonthly)}</span>
            </p>
            <p className="text-note text-ink-soft">{`月給${yenJa(monthlyValue)}の67%です（1か月＝30日分）`}</p>
            <dl className="mt-2">
              <ResultRow label="最初の6か月（180日まで）の1か月" value={yenJa(r.firstMonthly)} sub="給付率67%" />
              <ResultRow label="7か月目からの1か月" value={yenJa(r.laterMonthly)} sub="給付率50%" />
              <ResultRow
                label="出生後休業支援給付金（上乗せ）"
                value={r.shusseiDays > 0 ? yenJa(r.shussei) : "なし"}
                sub={r.shusseiDays > 0 ? `${r.shusseiDays}日分×13%` : shussei ? `育休が${SHUSSEI_MIN_DAYS}日未満のため対象外` : "受け取らない場合"}
              />
              <ResultRow label={`育児休業給付金（${daysJa(days)}分）`} value={yenJa(r.kyufuTotal)} sub={r.laterDays > 0 ? `67%が${r.firstDays}日、50%が${r.laterDays}日` : `67%が${r.firstDays}日`} />
              <ResultRow label="育休中にもらえる合計の目安" value={yenJa(r.total)} strong />
            </dl>
            {r.capped === "max" ? (
              <p className="mt-2 text-note leading-[1.7] text-ink">{`月給が${yenJa(MONTHLY_MAX)}を超えるときは、上限（日額16,540円）で計算します。最初の6か月の1か月は${yenJa(r.firstMonthly)}が上限です。`}</p>
            ) : null}
            {r.capped === "min" ? (
              <p className="mt-2 text-note leading-[1.7] text-ink">{`月給が${yenJa(MONTHLY_MIN)}より少ないときは、下限（日額3,203円）で計算します。`}</p>
            ) : null}
            <ul className="mt-3 grid list-disc gap-1 pl-5 text-note leading-[1.7] text-ink-soft">
              <li>給付金に税金はかからず、育休中は健康保険・厚生年金の保険料も免除されます。このため67%と13%を合わせた80%で、手取りの10割に近い額になります（上乗せは最初の{SHUSSEI_MAX_DAYS}日分まで）。</li>
              <li>{`産後パパ育休（出生時育児休業）で給付を受けた日数は、67%の${FIRST_DAYS}日に含まれます。`}</li>
              <li>実際の額は、会社が出す賃金の証明（休業開始時賃金月額証明書）をもとにハローワークが決めます。休業中に会社から給与が出ると減ることがあります。</li>
            </ul>
            <p className="mt-3 border-t border-line pt-3 text-note leading-[1.7]" data-ikukyu-next>
              <span className="font-bold text-ink">子どもが生まれたらもう1つ：</span>
              <Link href="/tools/child-allowance" className="font-bold text-accent underline underline-offset-2">
                児童手当の額を計算する
              </Link>
              <span className="text-ink-soft">（申請は市区町村へ、出生日の翌日から15日以内）</span>
            </p>
          </>
        ) : (
          <p className="text-note leading-[1.7] text-ink-soft">月給と育休の長さを入れると、ここに金額が出ます。</p>
        )}
      </div>
      <ReceiveSteps guide={IKUKYU_RECEIVE} />
    </div>
  );
}
