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
  CHILD_ALLOWANCE_AMOUNTS,
  CHILD_ALLOWANCE_EXAMPLES,
  CHILD_ALLOWANCE_NEXT_PAYMENT,
  childAllowance,
  childAllowanceExampleTable,
  statusLabel,
  ymJa,
} from "@/lib/child-allowance";

const meta = CALCULATORS["child-allowance"];

export const metadata: Metadata = withPageShare("child-allowance", meta.href, {
  title: "児童手当はいくら？ 子どもの年齢と人数で12月の支給額を計算",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 出典はすべて公式ページ。meta.checked（2026-11-25）に開いて、金額・数え方・支給の月を確かめた */
const CHECKED = `${checkedDateJa(meta.checked)}確認`;
const SOURCES = {
  motto: { href: "https://www.cfa.go.jp/policies/kokoseido/jidouteate/mottoouen", label: "こども家庭庁「もっと子育て応援！児童手当」" },
  annai: { href: "https://www.cfa.go.jp/policies/kokoseido/jidouteate/annai", label: "こども家庭庁「児童手当制度のご案内」" },
  faq: { href: "https://www.cfa.go.jp/policies/kokoseido/jidouteate/faq/ippan", label: "こども家庭庁「児童手当の基本的な取扱いについて」（Q&A）" },
  count: {
    href: "https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/6a83b8eb-4e0e-4754-b96d-c83e66a6ac81/ef950131/20240809_policies_kokoseido_jidouteate_mottoouen_05.pdf",
    label: "こども家庭庁「「第3子以降」のカウント方法について」（PDF）",
  },
  gaiyou: {
    href: "https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/6a83b8eb-4e0e-4754-b96d-c83e66a6ac81/e935b433/20240809_policies_kokoseido_jidouteate_mottoouen_04.pdf",
    label: "こども家庭庁「児童手当制度の概要」（PDF）",
  },
  reform: {
    href: "https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/2013c0c1-d5f0-4555-920d-80d9428893be/9752a20d/20240904_policies_kodomokosodateshienkin_06.pdf",
    label: "こども家庭庁「子ども・子育て支援法等の一部を改正する法律（令和6年法律第47号）の概要」（PDF）",
  },
  law: { href: "https://laws.e-gov.go.jp/law/346AC0000000073", label: "e-Gov 法令検索「児童手当法」（第6条・第8条・第9条）" },
} as const;

const GUIDES = [
  { href: "/guides/jidou-teate", label: "児童手当の金額と対象、申請のしかた" },
  { href: "/articles/child-allowance-eligibility-check", label: "児童手当の対象かどうかの確かめ方" },
  { href: "/dates", label: "暮らしとお金の日程（支給日・期限）" },
];

function Source({ source }: { source: { href: string; label: string } }) {
  return (
    <a href={source.href} target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
      {source.label}
    </a>
  );
}

export default function ChildAllowancePage() {
  const ad = actionAdWithBenefits(toolAd("kids"), "");
  // 「よくある家族の例」と例の文の数字は、すべて計算機と同じ childAllowance() でビルドのときに出す（手で書かない）
  const table = childAllowanceExampleTable();
  const example = CHILD_ALLOWANCE_EXAMPLES[3];
  const exampleResult = childAllowance(example.children.map((category) => ({ kind: "category", category }) as const));
  const pay = CHILD_ALLOWANCE_NEXT_PAYMENT;
  const months = exampleResult.next.months;
  const A = CHILD_ALLOWANCE_AMOUNTS;
  return (
    <ToolPage
      kind="child-allowance"
      lead={`子どもの生まれた年月（または年齢の区分）を入れると、第何子になるか、1か月の児童手当、${ymJa(pay)}の支給額（${months[0].month}月・${months[1].month}月分）、1年分が出ます。所得制限はなく、高校生年代まで受け取れます。`}
      afterCalc={ad ? <ActionAd ad={ad} pos={GUIDE_AD_POS.tool} className="mt-8" /> : null}
    >
      <ToolSection id="what" title="児童手当の月額">
        <p>
          児童手当は、0歳から18歳に達する日以後の最初の3月31日まで（高校生年代まで）の子を育てている人に支給されます。令和6年（2024年）10月分から所得制限がなくなり、所得にかかわらず同じ額です。
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-note tabular-nums">
            <caption className="pb-2 text-left text-ink-soft">子ども1人あたりの月額</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">子の年齢</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">第1子・第2子</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">第3子以降</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">3歳未満</th>
                <td className="py-2 pl-3 text-right">{yen(A.under3)}</td>
                <td className="py-2 pl-3 text-right">{yen(A.third)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">3歳〜高校生年代</th>
                <td className="py-2 pl-3 text-right">{yen(A.from3)}</td>
                <td className="py-2 pl-3 text-right">{yen(A.third)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          出典：
          <Source source={SOURCES.motto} />、<Source source={SOURCES.gaiyou} />、<Source source={SOURCES.reform} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="third-child" title="第3子の数え方">
        <p>
          「第3子以降」は、手当を受ける子と、その上の子（兄姉等）を合わせて、年齢が上の子から数えて3人目以降の子です。兄姉等は、18歳の年度末を過ぎてから22歳の年度末（22歳に達する日以後の最初の3月31日）までの子のうち、親などが生活費を負担している子です。大学生でなくても数えます。
        </p>
        <p>
          18歳の年度末を過ぎた子に手当は出ませんが、数には入ります。たとえば大学生年代の子（生活費を負担）と高校生・中学生がいる家庭では、中学生が第3子で{yen(A.third)}です。上の子が22歳の年度末を過ぎたり、生活費の負担がなくなったりすると数から外れ、下の子の順番が1つずつ繰り上がります。
        </p>
        <p>
          子が3人以上いても、必ず第3子以降として数えるわけではありません。兄姉等を数えるには、市区町村に「監護相当・生計費の負担についての確認書」などを出します。
        </p>
        <p>
          出典：
          <Source source={SOURCES.count} />、<Source source={SOURCES.annai} />、<Source source={SOURCES.gaiyou} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="payment" title="支給の月と12月の支給">
        <p>
          児童手当は、毎年2月・4月・6月・8月・10月・12月（偶数月）に、それぞれの前月分まで（2か月分）が支給されます。{`${ymJa(pay)}の支給は、${ymJa(months[0])}分と${ymJa(months[1])}分です。`}
        </p>
        <p>支給日の日にちは、こども家庭庁の案内には書かれていません。お住まいの市区町村（公務員は勤務先）の案内で確かめてください。</p>
        <p>
          出典：
          <Source source={SOURCES.motto} />、<Source source={SOURCES.gaiyou} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="example" title="よくある家族の例">
        <p>{`例：${example.label}の場合（上の子から第1子・第2子・第3子）`}</p>
        <ol className="grid list-decimal gap-1.5 pl-5">
          {exampleResult.children.map((child, i) => (
            <li key={i}>{`${statusLabel(child)}：月${yen(child.amount)}`}</li>
          ))}
        </ol>
        <p>{`1か月の合計は${yen(exampleResult.monthly)}、${ymJa(pay)}の支給は2か月分で${yen(exampleResult.next.amount)}、1年分（支給6回）で${yen(exampleResult.year.total)}です。`}</p>
        <p id="example-caption" className="text-note text-ink-soft">ほかの家族の例（年齢の区分が1年間変わらない場合。表は横に動かせます）</p>
        <div className="overflow-x-auto">
          <table aria-describedby="example-caption" className="w-full min-w-[30em] border-collapse text-note tabular-nums">
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">子ども（上の子から）</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">月額</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">{`${pay.month}月の支給`}</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">1年分</th>
              </tr>
            </thead>
            <tbody>
              {table.map((row) => (
                <tr key={row.label} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">{row.label}</th>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yen(row.monthly)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yen(row.payment)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yen(row.year)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>「大学生」は18歳の年度末を過ぎて22歳の年度末までの子です。生活費を負担しているかどうかで、下の子の額が変わります。</p>
      </ToolSection>

      <ToolSection id="rules" title="生まれた年月で計算するときのきまり">
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>生まれた月の分は出ません。申請した月の翌月分から支給されるため、生まれてすぐ申請した場合として、生まれた月の翌月から数えています。</li>
          <li>3歳の誕生月までは3歳未満の額です。額が下がるときは、そのことがあった月の翌月から変わるため、誕生月の翌月から3歳以上の額にしています。</li>
          <li>18歳に達する日以後の最初の3月31日がある3月の分まで支給されます。その翌月からは、生活費を負担していれば22歳の年度末まで数にだけ入ります。</li>
          <li>生まれた日は使っていません。4月1日生まれの子は、ほかの4月生まれの子と年度の区切りが違うため、結果がずれることがあります。</li>
        </ul>
        <p>
          出典：
          <Source source={SOURCES.law} />、<Source source={SOURCES.annai} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="faq" title="よくある疑問">
        <h3 className="font-bold text-ink">所得が多くても受け取れますか</h3>
        <p>受け取れます。令和6年10月分から所得制限はなくなりました。</p>
        <h3 className="font-bold text-ink">大学生の子がいると、下の子は第3子になりますか</h3>
        <p>22歳の年度末までで、親などが生活費を負担していれば数に入ります。大学生でなくても同じです。大学生年代の子に手当は出ません。</p>
        <h3 className="font-bold text-ink">支給日は何日ですか</h3>
        <p>偶数月に前月分までの2か月分が支給されますが、日にちはこども家庭庁の案内に書かれていません。お住まいの市区町村の案内で確かめてください。</p>
        <h3 className="font-bold text-ink">子どもが生まれたら、いつから受け取れますか</h3>
        <p>出生日の次の日から15日以内に、お住まいの市区町村（公務員は勤務先）に申請します。原則として、申請した月の翌月分から支給されます。申請が遅れると、遅れた月分は受け取れません。</p>
        <h3 className="font-bold text-ink">高校を卒業する年は、いつの分まで受け取れますか</h3>
        <p>18歳に達する日以後の最初の3月31日までが対象なので、その3月分までです。3月分は、2月分と合わせて4月に支給されます。</p>
        <p>
          出典：
          <Source source={SOURCES.reform} />、<Source source={SOURCES.count} />、<Source source={SOURCES.motto} />、<Source source={SOURCES.faq} />、<Source source={SOURCES.law} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="guides" title="手続きのガイド">
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
