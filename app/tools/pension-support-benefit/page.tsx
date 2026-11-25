import { actionAdWithBenefits } from "@/lib/ad-benefits";
import type { Metadata } from "next";
import Link from "next/link";
import { withPageShare } from "@/lib/page-share";
import ToolPage, { ToolSection } from "@/components/calc/ToolPage";
import ActionAd from "@/components/ActionAd";
import { CALCULATORS, checkedDateJa } from "@/lib/calculators";
import { yen } from "@/lib/calc-math";
import { GUIDE_AD_POS, toolAd } from "@/lib/guide-ads";
import {
  PENSION_SUPPORT,
  PENSION_SUPPORT_CONTACTS,
  PENSION_SUPPORT_EXAMPLES,
  PENSION_SUPPORT_HAGAKI_DEADLINE,
  PENSION_SUPPORT_NEXT_PAYMENT,
  PENSION_SUPPORT_PERIOD,
  pensionSupport,
  pensionSupportExampleTable,
} from "@/lib/pension-support-benefit";

const meta = CALCULATORS["pension-support-benefit"];

export const metadata: Metadata = withPageShare("pension-support-benefit", meta.href, {
  title: "年金生活者支援給付金はもらえる？ いくら？ 前年の収入と納めた年数で計算",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 出典はすべて公式ページ。meta.checked（2026-11-26）に開いて、金額・基準額・式・支払いの月・問い合わせ先を確かめた */
const CHECKED = `${checkedDateJa(meta.checked)}確認`;
const NENKIN = "https://www.nenkin.go.jp";
const SOURCES = {
  top: { href: `${NENKIN}/service/jukyu/seido/sonota-kyufu/shienkyufukin/20190805.html`, label: "日本年金機構「年金生活者支援給付金制度について」" },
  rourei: { href: `${NENKIN}/service/jukyu/seido/sonota-kyufu/shienkyufukin/rourei.html`, label: "日本年金機構「老齢（補足的老齢）年金生活者支援給付金」" },
  syougai: { href: `${NENKIN}/service/jukyu/seido/sonota-kyufu/shienkyufukin/syougai.html`, label: "日本年金機構「障害年金生活者支援給付金」" },
  izoku: { href: `${NENKIN}/service/jukyu/seido/sonota-kyufu/shienkyufukin/izoku.html`, label: "日本年金機構「遺族年金生活者支援給付金」" },
  amount: { href: `${NENKIN}/oshirase/taisetu/kojin/2026/202604/0401.html`, label: "日本年金機構「令和8年4月分からの年金生活者支援給付金額について」" },
  hagaki: { href: `${NENKIN}/service/jukyu/tetsuduki/sonota-kyufu/shienkyufukin/seikyu/ta.html`, label: "日本年金機構「年金生活者支援給付金請求書（はがき型）が届いた方へ」" },
  kigen: { href: `${NENKIN}/section/faq/jukyu/seido/sonota-kyufu/shienkyufukin/hagaki/kigen.html`, label: "日本年金機構 年金Q&A「手続きが遅れると年金生活者支援給付金は受け取れなくなりますか。」" },
  age65: { href: `${NENKIN}/service/jukyu/tetsuduki/sonota-kyufu/shienkyufukin/seikyu/roureikiso.html`, label: "日本年金機構「65歳の誕生日を迎える方で、老齢基礎年金を新規に請求する方」" },
  newClaim: { href: `${NENKIN}/service/jukyu/tetsuduki/sonota-kyufu/shienkyufukin/seikyu/syougaiizoku.html`, label: "日本年金機構「障害基礎年金または遺族基礎年金を新規に請求する方」" },
  couple: { href: `${NENKIN}/section/faq/jukyu/seido/sonota-kyufu/shienkyufukin/shikyuyouken/shikyuyouken04.html`, label: "日本年金機構 年金Q&A（夫婦2人とも受け取れるか）" },
  start: { href: `${NENKIN}/section/faq/jukyu/seido/sonota-kyufu/shienkyufukin/shikyuyouken/shikyuyouken05.html`, label: "日本年金機構 年金Q&A（いつから支給の対象になるか）" },
  period: { href: `${NENKIN}/section/faq/jukyu/seido/sonota-kyufu/shienkyufukin/shikyuyouken/shikyuyouken07.html`, label: "日本年金機構 年金Q&A（支給対象期間）" },
  tel: { href: `${NENKIN}/section/tel/toiawase_ippan.html`, label: "日本年金機構「ねんきんダイヤル」" },
  mhlw: { href: "https://www.mhlw.go.jp/nenkinkyuufukin/nenkinsupport.html", label: "厚生労働省「年金生活者支援給付金」" },
} as const;

const GUIDES = [
  { href: "/articles/pension-support-benefit-old-age-check", label: "年金生活者支援給付金の対象の確かめ方" },
  { href: "/articles/pension-support-benefit-scam-check", label: "年金生活者支援給付金をかたる電話に注意" },
  { href: "/dates", label: "暮らしとお金の日程（支給日・期限）" },
];

function Source({ source }: { source: { href: string; label: string } }) {
  return (
    <a href={source.href} target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
      {source.label}
    </a>
  );
}

export default function PensionSupportBenefitPage() {
  const ad = actionAdWithBenefits(toolAd("mobile"), "");
  // 「よくある例」と例の文の数字は、すべて計算機と同じ pensionSupport() でビルドのときに出す（手で書かない）
  const table = pensionSupportExampleTable();
  const example = PENSION_SUPPORT_EXAMPLES[2];
  const exampleResult = pensionSupport(example.input);
  const P = PENSION_SUPPORT;
  const T = P.threshold;
  const E = P.exempt;
  const pay = PENSION_SUPPORT_NEXT_PAYMENT;
  const C = PENSION_SUPPORT_CONTACTS;
  return (
    <ToolPage
      kind="pension-support-benefit"
      lead={`受けている年金の種類、世帯の住民税、${PENSION_SUPPORT_PERIOD.incomeYear}の収入、保険料を納めた年数を入れると、年金生活者支援給付金の対象かどうかの目安と、${P.fiscalYear}の月額・1回の支払い（2か月分）・1年分が出ます。`}
      afterCalc={ad ? <ActionAd ad={ad} pos={GUIDE_AD_POS.tool} className="mt-8" /> : null}
    >
      <ToolSection id="what" title="年金生活者支援給付金とは">
        <p>
          公的年金などの収入やその他の所得が一定の額以下の年金受給者に、年金に上乗せして支給されるお金です。老齢・障害・遺族の3種類があり、{P.fiscalYear}（令和8年4月分から）の基準額は月{yen(P.base)}です。
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-note tabular-nums">
            <caption className="pb-2 text-left text-ink-soft">{`${P.fiscalYear}の月額`}</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">種類</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">月額</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">老齢（40年すべて納めた場合）</th>
                <td className="py-2 pl-3 text-right">{yen(P.base)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">障害等級1級</th>
                <td className="py-2 pl-3 text-right">{yen(P.disability1)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">障害等級2級</th>
                <td className="py-2 pl-3 text-right">{yen(P.disability2)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">遺族</th>
                <td className="py-2 pl-3 text-right">{yen(P.survivor)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          出典：
          <Source source={SOURCES.amount} />、<Source source={SOURCES.top} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="old-age" title="老齢の給付金の条件と計算式">
        <p>次の3つをすべて満たす方が対象です。</p>
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>65歳以上で、老齢基礎年金を受けている</li>
          <li>本人を含む世帯全員の市町村民税が非課税</li>
          <li>{`前年の年金収入とその他の所得の合計が基準額以下（${PENSION_SUPPORT_PERIOD.span}は${PENSION_SUPPORT_PERIOD.incomeYear}の額。障害年金・遺族年金は入れない）`}</li>
        </ul>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[30em] border-collapse text-note tabular-nums">
            <caption className="pb-2 text-left text-ink-soft">前年の年金収入とその他の所得の合計</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">生まれた日</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">老齢の給付金</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">補足的老齢の給付金</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">昭和31年4月2日以後</th>
                <td className="py-2 pl-3 text-right">{`${yen(T.after.base)}以下`}</td>
                <td className="py-2 pl-3 text-right">{`${yen(T.after.base)}超〜${yen(T.after.upper)}以下`}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">昭和31年4月1日以前</th>
                <td className="py-2 pl-3 text-right">{`${yen(T.before.base)}以下`}</td>
                <td className="py-2 pl-3 text-right">{`${yen(T.before.base)}超〜${yen(T.before.upper)}以下`}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>{`月額は、(1) ${yen(P.base)}×保険料を納めた月数÷${P.months}月 と、(2) ${yen(E.after.full)}×保険料免除の月数÷${P.months}月 の合計です。(2) の額は、全額・4分の3・半額免除の月が${yen(E.after.full)}、4分の1免除の月が${yen(E.after.quarter)}です（昭和31年4月1日以前生まれの方は${yen(E.before.full)}と${yen(E.before.quarter)}）。`}</p>
        <p>{`補足的老齢の給付金は、${yen(P.base)}×納めた月数÷${P.months}月に、調整支給率（（${yen(T.after.upper)}－前年の年金収入とその他の所得の合計）÷${yen(P.supplementDivisor)}）を掛けた額です。免除の月は入りません。計算の結果の50銭未満は切り捨て、50銭以上は1円に切り上げます。`}</p>
        <p>昭和16年4月1日以前に生まれた方は、生年月日に応じて480月を短くして計算します。この計算機では金額を出していません。</p>
        <p>
          出典：
          <Source source={SOURCES.rourei} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="disability-survivor" title="障害・遺族の給付金の条件">
        <p>{`障害基礎年金か遺族基礎年金を受けていて、前年の所得が「${yen(P.incomeLimit)}＋扶養親族の数×${yen(P.dependent.general)}」以下の方が対象です。70歳以上の同一生計配偶者と老人扶養親族は1人${yen(P.dependent.elderly)}、特定扶養親族と16歳以上19歳未満の扶養親族は1人${yen(P.dependent.specified)}で数えます。障害年金・遺族年金は所得に入れません。`}</p>
        <p>{`月額は、障害等級1級が${yen(P.disability1)}、2級が${yen(P.disability2)}、遺族が${yen(P.survivor)}です。2人以上の子が遺族基礎年金を受けているときは、${yen(P.survivor)}を子の人数で割った額をそれぞれが受け取ります。老齢と違い、世帯の住民税の条件はありません。`}</p>
        <p>
          出典：
          <Source source={SOURCES.syougai} />、<Source source={SOURCES.izoku} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="payment" title="支払いの月と手続き">
        <p>{`原則として、偶数月の中旬に2か月分（前月と前々月の分）が、年金と同じ受取口座に、年金とは別に振り込まれます。${pay.year}年${pay.month}月の支払いは${pay.months[0]}月・${pay.months[1]}月分です。`}</p>
        <p>{`すでに年金を受けていて新しく受け取れる方には、毎年9月の第1営業日から順に「年金生活者支援給付金請求書（はがき型）」が届きます。${PENSION_SUPPORT_HAGAKI_DEADLINE}までに日本年金機構へ届くよう手続きすれば、令和8年10月分からさかのぼって受け取れます。過ぎても手続きはできますが、請求した月の翌月分からです。`}</p>
        <p>65歳になる方には、65歳になる3カ月前に届く年金請求書（事前送付用）に給付金の請求書が同封されます。65歳の誕生日の前日以降に、年金の請求書と一緒に年金事務所に出します。障害基礎年金・遺族基礎年金を新しく請求する方は、年金の請求のときに給付金の請求書（A4型）をあわせて出します。</p>
        <p>{`問い合わせは、${C.kyufukin.label} ${C.kyufukin.number}（${C.kyufukin.altNote}${C.kyufukin.alt}）、年金全般は${C.nenkin.label} ${C.nenkin.number}（${C.nenkin.altNote}${C.nenkin.alt}）です。受付は${C.hours}。`}</p>
        <p>
          出典：
          <Source source={SOURCES.top} />、<Source source={SOURCES.hagaki} />、<Source source={SOURCES.kigen} />、<Source source={SOURCES.age65} />、<Source source={SOURCES.newClaim} />、<Source source={SOURCES.tel} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="example" title="よくある例">
        <p>{`例：${example.label}（昭和31年4月2日以後生まれ・世帯全員が非課税）`}</p>
        <ul className="grid list-disc gap-1.5 pl-5 tabular-nums">
          {exampleResult.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
        <p>{`月額は${yen(exampleResult.monthly ?? 0)}、1回の支払い（2か月分）は${yen(exampleResult.perPayment ?? 0)}、1年分は${yen(exampleResult.annual ?? 0)}です。`}</p>
        <p id="example-caption" className="text-note text-ink-soft">ほかの例（老齢は昭和31年4月2日以後生まれ・世帯全員が非課税・その他の所得なし。表は横に動かせます）</p>
        <div className="overflow-x-auto">
          <table aria-describedby="example-caption" className="w-full min-w-[34em] border-collapse text-note tabular-nums">
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">例</th>
                <th scope="col" className="py-2 pl-3 text-left font-bold text-ink">判定</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">月額</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">1回（2か月分）</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">1年分</th>
              </tr>
            </thead>
            <tbody>
              {table.map((row) => (
                <tr key={row.label} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">{row.label}</th>
                  <td className="whitespace-nowrap py-2 pl-3">{row.verdict}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yen(row.monthly)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yen(row.perPayment)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yen(row.annual)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>{`1年分は${P.fiscalYear}の月額の12か月分です。給付額は毎年度、物価の変動に合わせて改定されます。`}</p>
      </ToolSection>

      <ToolSection id="faq" title="よくある疑問">
        <h3 className="font-bold text-ink">夫婦2人とも条件を満たせば、2人とも受け取れますか</h3>
        <p>受け取れます。給付金は1人ずつに支払われます。</p>
        <h3 className="font-bold text-ink">判定に使う収入はいつの分ですか</h3>
        <p>{`${PENSION_SUPPORT_PERIOD.span}の給付金は、${PENSION_SUPPORT_PERIOD.incomeYear}の収入と所得で判定します。判定の結果は10月分から翌年9月分まで反映されます。`}</p>
        <h3 className="font-bold text-ink">手続きが遅れると受け取れなくなりますか</h3>
        <p>{`はがきの提出期限を過ぎても手続きはできます。${PENSION_SUPPORT_HAGAKI_DEADLINE}までに日本年金機構へ届けば令和8年10月分から、それより後は請求した月の翌月分からです。`}</p>
        <h3 className="font-bold text-ink">いつから支給の対象になりますか</h3>
        <p>原則として、手続きをした翌月分からです。</p>
        <h3 className="font-bold text-ink">障害年金や遺族年金は収入に入りますか</h3>
        <p>入りません。障害年金・遺族年金などの非課税の収入は、判定に使う収入・所得に含みません。</p>
        <p>
          出典：
          <Source source={SOURCES.couple} />、<Source source={SOURCES.period} />、<Source source={SOURCES.kigen} />、<Source source={SOURCES.start} />、<Source source={SOURCES.rourei} />、<Source source={SOURCES.mhlw} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="guides" title="あわせて読む">
        <ul className="grid list-disc gap-1.5 pl-5">
          {GUIDES.map((guide) => (
            <li key={guide.href}>
              <Link href={guide.href} className="text-accent underline underline-offset-4">
                {guide.label}
              </Link>
            </li>
          ))}
        </ul>
      </ToolSection>
    </ToolPage>
  );
}
