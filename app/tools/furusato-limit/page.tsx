import type { Metadata } from "next";
import Link from "next/link";
import { withPageShare } from "@/lib/page-share";
import ToolPage, { ToolSection } from "@/components/calc/ToolPage";
import ActionAd from "@/components/ActionAd";
import { CALCULATORS } from "@/lib/calculators";
import { GUIDE_AD_POS, toolAd } from "@/lib/guide-ads";

const meta = CALCULATORS["furusato-limit"];

export const metadata: Metadata = withPageShare("furusato-limit", meta.href, {
  title: "ふるさと納税の上限額の計算　住民税の所得割額から目安を出す",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 出典はすべて公式ページ。2026-11-10 に開いて、式・数字・期限を確かめた */
const CHECKED = "2026-11-10確認";
const SOURCES = {
  deduction: { href: "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/mechanism/deduction.html", label: "総務省 ふるさと納税ポータルサイト「税金の控除について」" },
  procedure: { href: "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/mechanism/procedure.html", label: "総務省 ふるさと納税ポータルサイト「ふるさと納税の流れ」" },
  faq: { href: "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/faq/", label: "総務省 ふるさと納税ポータルサイト「よくある質問」" },
  onestop: { href: "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/topics/20150401.html", label: "総務省「制度改正について（ふるさと納税ワンストップ特例制度）」" },
  nta1155: { href: "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1155.htm", label: "国税庁 タックスアンサー No.1155「ふるさと納税（寄附金控除）」" },
  nta2260: { href: "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2260.htm", label: "国税庁 タックスアンサー No.2260「所得税の税率」" },
  law: { href: "https://laws.e-gov.go.jp/law/325AC0000000226", label: "e-Gov 法令検索「地方税法」（第37条の2・第314条の7、附則第5条の6）" },
  kobe: { href: "https://www.city.kobe.lg.jp/documents/1882/20260511131050.pdf", label: "神戸市「特別徴収税額の決定・変更通知書の見方」（PDF）" },
} as const;

const GUIDES = [
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
  const ad = toolAd("furusato");
  return (
    <ToolPage
      kind="furusato-limit"
      lead="住民税の決定通知書にある「所得割額」と所得税の税率から、自己負担2,000円で済むふるさと納税の寄附額の目安を計算します。2026年（令和8年）の寄附が対象です。"
      afterCalc={ad ? <ActionAd ad={ad} pos={GUIDE_AD_POS.tool} className="mt-8" /> : null}
    >
      <ToolSection title="計算のきまり（総務省の式）">
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

      <ToolSection title="所得割額はどこに書いてあるか">
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

      <ToolSection title="所得税の税率の選び方">
        <p>所得税の税率は「課税される所得金額」で決まり、5%から45%の7段階です。選ぶ欄のかっこの中が、その税率になる金額の範囲です。所得税がかからない人は0%を選んでください。</p>
        <p>
          総務省の説明では、特例分の計算に使う税率は、住民税の課税総所得金額から人的控除差調整額を引いた金額に当てはめた所得税の税率で、実際の所得税の税率と違うことがあります。2つの税率の境目に近い人は、低いほうの税率を選ぶと、目安は少なめに出ます。
        </p>
        <p>
          出典：
          <Source source={SOURCES.nta2260} />、<Source source={SOURCES.deduction} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection title="結果は目安です">
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

      <ToolSection title="期限">
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

      <ToolSection title="手続きのガイド">
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
