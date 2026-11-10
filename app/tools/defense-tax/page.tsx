import type { Metadata } from "next";
import { withPageShare } from "@/lib/page-share";
import ToolPage, { ToolSection } from "@/components/calc/ToolPage";
import { CALCULATORS, checkedDateJa } from "@/lib/calculators";
import { DEFENSE_TAX_DEFAULT_BASE, DEFENSE_TAX_PERIODS, defenseTaxExampleSentence, surtax, yen, type Surtax } from "@/lib/calc-math";

const meta = CALCULATORS["defense-tax"];

/** 出典（財務省の大綱・国税庁の税額表）を開いて税率と期間を確かめた日（meta.checked） */
const CHECKED = `${checkedDateJa(meta.checked)}確認`;
/** 「計算の例」の所得税額。計算機の最初の値と同じ定数を使う */
const EXAMPLE_BASE = DEFENSE_TAX_DEFAULT_BASE;

export const metadata: Metadata = withPageShare("defense-tax", meta.href, {
  title: "防衛特別所得税はいつから・いくら　2027年から・年ごとの税額",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 例：「2027〜2037年分：3,150円（防衛 1,500円、復興 1,650円）。改正前のきまりでは3,150円」 */
function exampleLine(row: { label: string; now: Surtax; before: Surtax }): string {
  const parts = [row.now.defense ? `防衛 ${yen(row.now.defense)}` : "", row.now.reconstruction ? `復興 ${yen(row.now.reconstruction)}` : ""].filter(Boolean);
  return `${row.label}：${yen(row.now.total)}${parts.length ? `（${parts.join("、")}）` : ""}。改正前のきまりでは${yen(row.before.total)}`;
}

export default function DefenseTaxPage() {
  // 例の税額は、計算機と同じ surtax() でビルドのときに出す（手で書かない）
  const rows = DEFENSE_TAX_PERIODS.map((period) => ({ ...period, now: surtax(EXAMPLE_BASE, period.year), before: surtax(EXAMPLE_BASE, period.year, true) }));
  return (
    <ToolPage kind="defense-tax" lead="2027年分から始まる防衛特別所得税と、税率が変わる復興特別所得税を、所得税額から年ごとに計算します。">
      <ToolSection id="what" title="防衛特別所得税とは">
        <p>防衛特別所得税は、防衛力の強化の財源にするため、2027年（令和9年）分の所得税から始まる国の税です。税額は、その年の基準所得税額の1%です。</p>
      </ToolSection>
      <ToolSection id="example" title="計算の例">
        <p>{defenseTaxExampleSentence(EXAMPLE_BASE)}</p>
        <ul className="grid list-disc gap-1.5 pl-5">
          {rows.map((row) => (
            <li key={row.label}>{exampleLine(row)}</li>
          ))}
        </ul>
        <p>{`計算機の最初の値も、この${yen(EXAMPLE_BASE)}です。自分の所得税額に書き換えると、年ごとの税額が出ます。`}</p>
      </ToolSection>
      <ToolSection id="when" title="いつから・いくら">
        <p>防衛特別所得税は、2027年（令和9年）分の所得税から始まります。税率は、基準所得税額の1%です。</p>
        <p>同じ2027年分から、復興特別所得税の税率が2.1%から1.1%に下がります。2027年から2037年までは、2つを足した税率が2.1%のままなので、年の合計の額は変わりません。たとえば基準所得税額が15万円なら、2026年分も2027年分も合計は3,150円です。</p>
        <p>違いが出るのは2038年分からです。改正前は2037年で終わるはずだった復興特別所得税が2047年まで続くため、2038年から2047年までは合計2.1%、2048年分からは防衛特別所得税の1%だけになります。</p>
      </ToolSection>
      <ToolSection id="rule" title="きまり（財務省の資料）">
        <p>防衛特別所得税＝その年の基準所得税額×1%。2027年（令和9年）分から当分の間です。</p>
        <p>復興特別所得税は、2027年分から税率を2.1%から1.1%に下げ、課税する期間を2037年までから2047年までに延ばします。</p>
        <p>
          出典：
          <a href="https://www.mof.go.jp/tax_policy/tax_reform/outline/fy2026/08taikou_06.htm" target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
            財務省「令和8年度税制改正の大綱」
          </a>
          、
          <a href="https://www.nta.go.jp/publication/pamph/gensen/zeigakuhyo2027/data/00.pdf" target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
            国税庁「令和9年分 源泉徴収税額表」
          </a>
          （{CHECKED}）
        </p>
      </ToolSection>
      <ToolSection id="base" title="基準所得税額とは">
        <p>所得税から、住宅ローン控除などの税額控除を引いたあとの金額です。確定申告書に欄があります。会社員の源泉徴収票の「源泉徴収税額」は、これに復興特別所得税を足した金額なので、1.021で割ると目安になります。</p>
        <p>どちらも手元にないときは、計算機の「年収から」で目安を出せます。給与収入だけ・社会保険料は年収の15%・扶養なしとして、2027年分の所得税のきまり（基礎控除・給与所得控除は国税庁のタックスアンサーNo.1199・No.1410）で計算します。</p>
      </ToolSection>
      <ToolSection id="faq" title="よくある質問">
        <h3 className="font-bold text-ink">2027年から税金は増えますか</h3>
        <p>2027年から2037年までは、防衛特別所得税1%と復興特別所得税1.1%の合計が2.1%で、今までの復興特別所得税2.1%と同じです。基準所得税額が同じなら、合計の額は変わりません。</p>
        <h3 className="font-bold text-ink">いつまで続きますか</h3>
        <p>防衛特別所得税は、2027年分から当分の間です。復興特別所得税は、課税する期間が2037年までから2047年までに延びます。</p>
        <h3 className="font-bold text-ink">源泉徴収票から計算できますか</h3>
        <p>できます。源泉徴収票の「源泉徴収税額」は復興特別所得税を含んだ金額なので、1.021で割ると基準所得税額の目安になります。計算機で「源泉徴収票の税額」を選ぶと、この計算をします。</p>
        <p>
          出典：
          <a href="https://www.mof.go.jp/tax_policy/tax_reform/outline/fy2026/08taikou_06.htm" target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
            財務省「令和8年度税制改正の大綱」
          </a>
          （{CHECKED}）
        </p>
      </ToolSection>
    </ToolPage>
  );
}
