import { actionAdWithBenefits } from "@/lib/ad-benefits";
import type { Metadata } from "next";
import Link from "next/link";
import { withPageShare } from "@/lib/page-share";
import ToolPage, { ToolSection } from "@/components/calc/ToolPage";
import ActionAd from "@/components/ActionAd";
import { CALCULATORS, checkedDateJa } from "@/lib/calculators";
import { FURUSATO_EXAMPLE, FURUSATO_EXAMPLE_RATES, furusatoExampleTable, furusatoLimit, furusatoSpecialShare, yen } from "@/lib/calc-math";
import { GUIDE_AD_POS, toolAd } from "@/lib/guide-ads";
import { FURUSATO_FAMILIES, FURUSATO_EASY_TABLE_FAMILIES, furusatoEasyTable } from "@/lib/furusato-easy";

const meta = CALCULATORS["furusato-limit"];

export const metadata: Metadata = withPageShare("furusato-limit", meta.href, {
  title: "ふるさと納税の上限額の計算　年収と家族構成から2026年の目安",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 出典はすべて公式ページ。meta.checked（2026-11-10）に開いて、式・数字・期限を確かめた */
const CHECKED = `${checkedDateJa(meta.checked)}確認`;
const SOURCES = {
  deduction: { href: "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/mechanism/deduction.html", label: "総務省 ふるさと納税ポータルサイト「税金の控除について」" },
  procedure: { href: "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/mechanism/procedure.html", label: "総務省 ふるさと納税ポータルサイト「ふるさと納税の流れ」" },
  faq: { href: "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/faq/", label: "総務省 ふるさと納税ポータルサイト「よくある質問」" },
  onestop: { href: "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/topics/20150401.html", label: "総務省「制度改正について（ふるさと納税ワンストップ特例制度）」" },
  nta1155: { href: "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1155.htm", label: "国税庁 タックスアンサー No.1155「ふるさと納税（寄附金控除）」" },
  nta2260: { href: "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2260.htm", label: "国税庁 タックスアンサー No.2260「所得税の税率」" },
  law: { href: "https://laws.e-gov.go.jp/law/325AC0000000226", label: "e-Gov 法令検索「地方税法」（第37条の2・第314条の7、附則第5条の6）" },
  kobe: { href: "https://www.city.kobe.lg.jp/documents/1882/20260511131050.pdf", label: "神戸市「特別徴収税額の決定・変更通知書の見方」（PDF）" },
  soumuTable: {
    href: "https://web.archive.org/web/20251023154903/https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/mechanism/deduction.html",
    label: "総務省「税金の控除について」2025年10月23日時点の写し（Web Archive。目安表が載っていたころ）",
  },
  nta1410: { href: "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1410.htm", label: "国税庁 タックスアンサー No.1410「給与所得控除」" },
  nta1411: { href: "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1411.htm", label: "国税庁 タックスアンサー No.1411「所得金額調整控除」" },
  mof2026: { href: "https://www.mof.go.jp/tax_policy/tax_reform/outline/fy2026/08taikou_gaiyou.pdf", label: "財務省「令和8年度税制改正の大綱の概要」（PDF）" },
} as const;

const GUIDES = [
  { href: "/dates/furusato-nozei-2026-deadline", label: "2026年分の期限（12月31日・確定申告・ワンストップ特例）" },
  { href: "/guides/furusato-how", label: "ふるさと納税のやり方" },
  { href: "/guides/furusato-limit", label: "上限額の仕組みと計算式" },
  { href: "/guides/furusato-onestop", label: "ワンストップ特例の条件" },
  { href: "/guides/furusato-kakutei", label: "ふるさと納税の確定申告" },
];

function Source({ source }: { source: { href: string; label: string } }) {
  return (
    <a href={source.href} target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
      {source.label}
    </a>
  );
}

export default function FurusatoLimitPage() {
  const ad = actionAdWithBenefits(toolAd("furusato"), "");
  // 「計算の例」の数字はすべて、計算機と同じ furusatoLimit() でビルドのときに出す（手で書かない）
  const example = furusatoLimit(FURUSATO_EXAMPLE.levy, FURUSATO_EXAMPLE.rate)!;
  const shareText = `${(furusatoSpecialShare(FURUSATO_EXAMPLE.rate) / 1000).toLocaleString("ja-JP", { maximumFractionDigits: 3 })}%`;
  const table = furusatoExampleTable();
  const easyTable = furusatoEasyTable();
  const familyLabel = (key: string) => FURUSATO_FAMILIES.find((f) => f.key === key)!.short;
  return (
    <ToolPage
      kind="furusato-limit"
      lead="年収と家族構成を選ぶだけで、自己負担2,000円で済むふるさと納税の寄附額の目安が出ます。住民税の決定通知書がある人は、通知書の「所得割額」からも計算できます。2026年（令和8年）の寄附が対象です。"
      afterCalc={ad ? <ActionAd ad={ad} pos={GUIDE_AD_POS.tool} className="mt-8" /> : null}
    >
      <ToolSection id="what" title="ふるさと納税の上限額とは">
        <p>
          ふるさと納税の上限額は、自己負担が2,000円で済む寄附額の上限です。住民税の特例分が「住民税の所得割額の2割」を超えない範囲で決まり、上限を超えて寄附すると自己負担は2,000円より多くなります。
        </p>
      </ToolSection>

      <ToolSection id="by-income" title="年収と家族構成別の目安（2026年の寄附）">
        <p>給与収入だけの人の目安です。上の「年収から（かんたん）」と同じ計算で出しています（1,000円未満切り捨て）。</p>
        <p id="by-income-caption" className="text-note text-ink-soft">自己負担2,000円で済む寄附額の目安（社会保険料は年収の15%、ほかの控除なし。表は横に動かせます）</p>
        <div className="overflow-x-auto">
          <table aria-describedby="by-income-caption" className="w-full border-collapse text-note tabular-nums">
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">年収</th>
                {FURUSATO_EASY_TABLE_FAMILIES.map((key) => (
                  <th key={key} scope="col" className="py-2 pl-3 text-right align-bottom font-bold leading-snug text-ink">{familyLabel(key)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {easyTable.map((row) => (
                <tr key={row.salary} className="border-b border-line">
                  <th scope="row" className="whitespace-nowrap py-2 pr-3 text-left font-bold text-ink">{`${(row.salary / 10000).toLocaleString("ja-JP")}万円`}</th>
                  {row.cells.map((cell) => (
                    <td key={cell.key} className="whitespace-nowrap py-2 pl-3 text-right">{cell.rounded ? yen(cell.rounded) : "ー"}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>「独身・共働き」は、配偶者控除を受けていない人です（配偶者の給与収入が201万円を超える共働きなど）。「高校生」は16〜18歳、「大学生」は19〜22歳の扶養している子です。中学生以下の子は上限に影響しません。</p>
      </ToolSection>

      <ToolSection id="easy-basis" title="「年収から」の計算の前提">
        <p>
          総務省のふるさと納税ポータルは、2025年10月まで、給与収入と家族構成別の「全額控除されるふるさと納税額（年間上限）の目安」の表を載せていました（社会保険料は給与収入の15%と仮定）。2026年11月11日に確かめたところ、この表と計算シートはポータルから外されていました。
        </p>
        <p>
          そこでこのツールは、総務省の表と同じ前提（給与収入だけ・社会保険料は年収の15%・住宅ローン控除や医療費控除などはなし）で、2026年の所得にかかる住民税のきまりで計算しています。年収300万〜900万円では、総務省が載せていた表の金額と、175か所のうち174か所で同じになることを確かめました（残る1か所も計算では14円の差）。
        </p>
        <p>
          年収が900万円を超えると、総務省の表は社会保険料を15%より少なく見ていたため、このツールの目安は表より少なめに出ます。源泉徴収票の社会保険料を「くわしく入れる」に入れると、実際に近づきます。
        </p>
        <p>
          上限は住民税の側で決まります（住民税の特例分は所得割額の2割まで）。2026年分の所得税の基礎控除の引き上げは住民税には入らないため、上限の目安はほとんど変わりません。給与所得控除の最低額の引き上げは、年収220万円未満の人だけに関係します。
        </p>
        <p>
          目安は、ワンストップ特例で申し込む場合です。確定申告で控除を受ける場合は、総務省の説明にあるとおり特例分の計算に使う税率と実際の所得税の税率が違うことがあり、負担が2,000円を少し超えることがあります。
        </p>
        <p>
          出典：
          <Source source={SOURCES.soumuTable} />、<Source source={SOURCES.deduction} />、<Source source={SOURCES.nta1410} />、<Source source={SOURCES.nta1411} />、<Source source={SOURCES.mof2026} />、<Source source={SOURCES.law} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="example" title="通知書から計算するときの例">
        <p>{`例：住民税の所得割額が${yen(FURUSATO_EXAMPLE.levy)}で、所得税の税率が${FURUSATO_EXAMPLE.rate}%の場合`}</p>
        <ol className="grid list-decimal gap-1.5 pl-5">
          <li>{`特例分の上限は、所得割額の20%で${yen(example.cap)}です。`}</li>
          <li>{`特例分の割合は、90% − ${FURUSATO_EXAMPLE.rate}% × 1.021 ＝ ${shareText}です。`}</li>
          <li>{`${yen(example.cap)} ÷ ${shareText} ＝ ${yen(example.limit - 2000)}（1円未満切り捨て）に2,000円を足して、寄附額の目安は${yen(example.limit)}です。`}</li>
        </ol>
        <p>ほかの所得割額と税率の目安は、次の表のとおりです（上の式で計算。1円未満切り捨て）。</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[30em] border-collapse text-note tabular-nums">
            <caption className="pb-2 text-left text-ink-soft">自己負担2,000円で済む寄附額の目安（2026年の寄附）</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">所得割額</th>
                {FURUSATO_EXAMPLE_RATES.map((rate) => (
                  <th key={rate} scope="col" className="py-2 pl-3 text-right font-bold text-ink">{`税率${rate}%`}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.map((row) => (
                <tr key={row.levy} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">{yen(row.levy)}</th>
                  {row.cells.map((cell) => (
                    <td key={cell.rate} className="py-2 pl-3 text-right">{yen(cell.limit)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>表は住民税の特例分の上限だけで計算した目安です。自分の数字は、上の計算で確かめてください。</p>
      </ToolSection>

      <ToolSection id="formula" title="計算のきまり（総務省の式）">
        <p>ふるさと納税をすると、寄附額から2,000円を引いた金額が、次の3つに分かれて税金から引かれます。</p>
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>所得税：（寄附額−2,000円）×所得税の税率</li>
          <li>住民税の基本分：（寄附額−2,000円）×10%</li>
          <li>住民税の特例分：（寄附額−2,000円）×（100%−10%−所得税の税率）</li>
        </ul>
        <p>
          特例分には「住民税の所得割額の2割まで」という上限があります。寄附額が増えて特例分がこの上限を超えると、超えた分は引かれず、自己負担は2,000円より多くなります。
        </p>
        <p>
          このツールは、特例分がちょうど上限になる寄附額を出しています。上の式を寄附額について解くと、次のとおりです。
        </p>
        <p className="rounded-xl bg-surface px-4 py-3 font-bold text-ink">寄附額の目安 ＝ 所得割額 × 20% ÷（90% − 所得税の税率 × 1.021）＋ 2,000円</p>
        <p>
          1.021を掛けるのは、所得税の税率に復興特別所得税（2.1%）を加えるためです。所得税がかからない人（税率0%）は、90%で割ります。
        </p>
        <p>
          出典：
          <Source source={SOURCES.deduction} />、<Source source={SOURCES.nta1155} />、<Source source={SOURCES.law} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="shotokuwari" title="通知書の所得割額はどこに書いてあるか">
        <p>
          住民税の決定通知書（給与から住民税が引かれている人は「特別徴収税額の決定通知書」）の税額の欄に、市区町村民税と道府県民税（東京都は都民税）のそれぞれの「所得割額」が書かれています。この2つを足した金額を入れてください。
        </p>
        <p>
          「均等割額」は入れません。「税額控除前所得割額」という欄がある通知書では、その欄ではなく、税額控除を引いたあとの「所得割額」を入れてください。
        </p>
        <p>
          通知書の所得割額は、前の年の所得で決まった金額です。2026年の寄附の上限は2026年の所得で決まるので、収入や家族の人数が変わった人は結果がずれます。前の年にふるさと納税や住宅ローン控除で住民税が引かれた人は、通知書の所得割額がその分小さくなっているため、結果は実際より少なめに出ます。
        </p>
        <p>
          通知書の様式は市区町村で少し違います。欄の並びの例：
          <Source source={SOURCES.kobe} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="tax-rate" title="所得税の税率の選び方">
        <p>所得税の税率は「課税される所得金額」で決まり、5%から45%の7段階です。選ぶ欄のかっこの中が、その税率になる金額の範囲です。所得税がかからない人は0%を選んでください。</p>
        <p>
          総務省の説明では、特例分の計算に使う税率は、住民税の課税総所得金額から人的控除差調整額を引いた金額に当てはめた所得税の税率で、実際の所得税の税率と違うことがあります。2つの税率の境目に近い人は、低いほうの税率を選ぶと、目安は少なめに出ます。
        </p>
        <p>
          出典：
          <Source source={SOURCES.nta2260} />、<Source source={SOURCES.deduction} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="estimate" title="結果は目安です">
        <p>
          このツールは、住民税の特例分の上限だけで計算しています。ほかに、所得税の控除は総所得金額等の40%まで、住民税の基本分は総所得金額等の30%までという上限があり、これらは計算に入れていません。
        </p>
        <p>
          正確な上限額は、その年の所得と、受けている控除で人ごとに変わります。総務省も、具体的な計算は住んでいる市区町村に問い合わせるよう案内しています。上限に近い金額を寄附する前に、市区町村の住民税の窓口で確かめてください。
        </p>
        <p>
          出典：
          <Source source={SOURCES.deduction} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="deadline" title="期限">
        <p>
          自己負担の2,000円と税金の控除は、1月から12月までの1年間の寄附の合計で計算します。2026年分に入れるには、12月31日までに寄附を済ませます。年末の寄附がどの年の扱いになるかは、寄附先の自治体の案内で確かめてください。
        </p>
        <p>確定申告で控除を受ける人は、寄附をした翌年の3月15日までに申告します。</p>
        <p>
          ワンストップ特例は、確定申告が不要な給与所得者などで、寄附先が5団体以内の人が使えます。申請書は、寄附をするときに寄附先の自治体へ出します。出したあとに住所などが変わったときは、寄附をした翌年の1月10日までに変更の届出書を出します。申請書の締め切りと出し方は、寄附先の自治体の案内で確かめてください。
        </p>
        <p>
          出典：
          <Source source={SOURCES.faq} />、<Source source={SOURCES.procedure} />、<Source source={SOURCES.onestop} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="faq" title="よくある質問">
        <h3 className="font-bold text-ink">上限額を超えて寄附するとどうなりますか</h3>
        <p>超えた分は住民税の特例分から引かれないため、自己負担が2,000円より多くなります。</p>
        <h3 className="font-bold text-ink">住民税の通知書がなくても計算できますか</h3>
        <p>できます。「年収から（かんたん）」を選び、今年の年収の見込みと家族構成を入れると目安が出ます。源泉徴収票の社会保険料や、iDeCoの掛金を入れると、実際に近づきます。</p>
        <h3 className="font-bold text-ink">所得割額はどこで分かりますか</h3>
        <p>住民税の決定通知書の税額の欄です。市区町村民税と道府県民税（東京都は都民税）の所得割額を足した金額を使います。</p>
        <h3 className="font-bold text-ink">いつまでに寄附すれば2026年分になりますか</h3>
        <p>1月から12月までの寄附の合計で計算するので、12月31日までに寄附を済ませます。年末の寄附の扱いは、寄附先の自治体の案内で確かめてください。</p>
        <p>
          出典：
          <Source source={SOURCES.deduction} />、<Source source={SOURCES.kobe} />、<Source source={SOURCES.faq} />（{CHECKED}）
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
