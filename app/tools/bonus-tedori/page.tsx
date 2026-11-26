import { actionAdWithBenefits } from "@/lib/ad-benefits";
import type { Metadata } from "next";
import Link from "next/link";
import { withPageShare } from "@/lib/page-share";
import ToolPage, { ToolSection } from "@/components/calc/ToolPage";
import ActionAd from "@/components/ActionAd";
import { CALCULATORS, checkedDateJa } from "@/lib/calculators";
import { GUIDE_AD_POS, toolAd } from "@/lib/guide-ads";
import {
  BONUS_EXAMPLE,
  BONUS_SOURCES,
  HEALTH_BONUS_YEARLY_CAP,
  KOSEI_NENKIN_BONUS_CAP,
  KOSEI_NENKIN_RATE,
  KOYO_RATE_PER_MILLE,
  KYOKAI_HEALTH_RATES,
  KYOKAI_KAIGO_RATE,
  KYOKAI_SHIEN_RATE,
  bonusExampleTable,
  bonusTaxBand,
  bonusTedori,
  percentJa,
  prefectureRate,
  yenJa,
} from "@/lib/bonus-tedori";

const meta = CALCULATORS["bonus-tedori"];

export const metadata: Metadata = withPageShare("bonus-tedori", meta.href, {
  title: "冬のボーナス、手取りはいくら？ 社会保険料と所得税を引いた額を計算",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 出典は国税庁・協会けんぽ・厚生労働省。meta.checked（2026-11-26）に開いて、率・表・端数の扱い・上限を確かめた */
const CHECKED = `${checkedDateJa(meta.checked)}確認`;

const GUIDES = [
  { href: "/articles/winter-bonus-take-home-pay-calculation", label: "冬のボーナス50万円の手取りと、引かれるもの" },
  { href: "/articles/bonus-social-insurance-standard-cap", label: "ボーナスの社会保険料と標準賞与額の上限" },
  { href: "/articles/employment-insurance-rate-fy2026", label: "2026年度の雇用保険料率" },
  { href: "/articles/civil-servant-winter-bonus-date-2026", label: "公務員の冬のボーナスの支給日" },
  { href: CALCULATORS["furusato-limit"].href, label: CALCULATORS["furusato-limit"].title },
];

function Source({ source }: { source: { href: string; label: string } }) {
  return (
    <a href={source.href} target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
      {source.label}
    </a>
  );
}

/**
 * 結果の下の囲み: ふるさと納税（12月31日までの寄附がその年の分）。ボーナスの月は、年内の寄附先を決める時期と重なるため。
 * 提携先は記事の PR と同じ（content/offers.json の furusato）。見出しとつなぎの一文だけボーナスに合わせ、1行目に上限額の計算（サイト内）を出す。
 * 提携先が無ければ、上限額の計算への案内だけを出す（関係の無い広告は出さない）
 */
function bonusAd() {
  const furusato = toolAd("furusato");
  const internal = [{ href: CALCULATORS["furusato-limit"].href, label: "ふるさと納税の上限額を計算する" }];
  const title = "ボーナスの月は、ふるさと納税の寄附先選びも";
  const lead = "ふるさと納税は12月31日までの寄附がその年の分です。自己負担2,000円で済む上限額は年収と家族構成で変わるので、先に上限を確かめてから寄附先を選びます。";
  return furusato ? { ...furusato, title, lead, internal } : { key: "furusato", title, lead, items: [], internal };
}

export default function BonusTedoriPage() {
  const ad = actionAdWithBenefits(bonusAd(), "");
  // 例の数字と表は、すべて計算機と同じ bonusTedori() でビルドのときに出す（手で書かない）
  const ex = bonusTedori(BONUS_EXAMPLE);
  const exKaigo = bonusTedori({ ...BONUS_EXAMPLE, kaigo: true });
  const table = bonusExampleTable();
  const tokyo = prefectureRate("東京都")!;
  const band = bonusTaxBand(BONUS_EXAMPLE.prevNet, BONUS_EXAMPLE.dependents);
  const exampleLabel = `額面${yenJa(BONUS_EXAMPLE.bonus)}・前月の給与（社会保険料を引いた額）${yenJa(BONUS_EXAMPLE.prevNet)}・扶養0人・東京都の協会けんぽ・40歳未満`;
  const sorted = [...KYOKAI_HEALTH_RATES].sort((a, b) => a[1] - b[1]);
  const lowest = sorted[0];
  const highest = sorted[sorted.length - 1];
  return (
    <ToolPage
      kind="bonus-tedori"
      lead={`冬のボーナスが額面${yenJa(BONUS_EXAMPLE.bonus)}なら、手取りは${yenJa(ex.takeHome)}です（前月の給与が社会保険料を引いて${yenJa(BONUS_EXAMPLE.prevNet)}、扶養0人、東京都の協会けんぽ、40歳未満の場合）。ボーナスの額・前月の給与・扶養の数・年齢・都道府県を入れると、あなたの場合の手取りと、引かれる社会保険料と所得税の内訳が出ます。`}
      afterCalc={ad ? <ActionAd ad={ad} pos={GUIDE_AD_POS.tool} tool="bonus-tedori" className="mt-8" /> : null}
    >
      <ToolSection id="what" title="ボーナスから引かれるもの">
        <p>ボーナス（賞与）からは、社会保険料（健康保険料・介護保険料・子ども・子育て支援金・厚生年金保険料・雇用保険料）と所得税が引かれます。住民税は引かれません。</p>
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>{`健康保険料：協会けんぽは都道府県ごとに率が違います（2026年3月分から、合計で${percentJa(lowest[1])}の${lowest[0]}から${percentJa(highest[1])}の${highest[0]}まで）。会社と本人で半分ずつ負担します。`}</li>
          <li>{`介護保険料：40歳から64歳までの人だけです。協会けんぽは全国同じ${percentJa(KYOKAI_KAIGO_RATE)}（本人は半分）。`}</li>
          <li>{`子ども・子育て支援金：2026年4月分から始まりました。協会けんぽは${percentJa(KYOKAI_SHIEN_RATE)}（本人は半分）で、ボーナスにもかかります。`}</li>
          <li>{`厚生年金保険料：${percentJa(KOSEI_NENKIN_RATE)}（本人は半分の${percentJa(KOSEI_NENKIN_RATE / 2)}）。`}</li>
          <li>{`雇用保険料：2026年4月から2027年3月までは、一般の事業で本人負担が1,000分の${KOYO_RATE_PER_MILLE}です（前の年度は1,000分の5.5）。農林水産・清酒製造の事業と建設の事業は1,000分の6です。`}</li>
          <li>所得税：前月の給与（社会保険料を引いた額）と扶養の数で決まる率を、ボーナスから社会保険料を引いた額に掛けます。率には復興特別所得税も入っています。</li>
        </ul>
        <p>
          出典：
          <Source source={BONUS_SOURCES.kyokaiRate} />、<Source source={BONUS_SOURCES.kyokaiKaigo} />、<Source source={BONUS_SOURCES.kyokaiShien} />、<Source source={BONUS_SOURCES.mhlwKoyo} />、
          <Source source={BONUS_SOURCES.ntaRate} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="example" title="計算の例（サイソク編集部の計算）">
        <p>{`${exampleLabel}の場合、手取りは${yenJa(ex.takeHome)}です。`}</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[26em] border-collapse text-note tabular-nums" data-bonus-example>
            <caption className="pb-2 text-left text-ink-soft">{`額面${yenJa(BONUS_EXAMPLE.bonus)}から引かれるもの`}</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">項目</th>
                <th scope="col" className="py-2 pl-3 text-left font-bold text-ink">計算</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">金額</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">健康保険料</th>
                <td className="py-2 pl-3">{`${yenJa(ex.standard)}×${percentJa(tokyo / 2)}`}</td>
                <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(ex.health)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">介護保険料</th>
                <td className="py-2 pl-3">40歳未満はかからない</td>
                <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(ex.kaigo)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">子ども・子育て支援金</th>
                <td className="py-2 pl-3">{`${yenJa(ex.standard)}×${percentJa(KYOKAI_SHIEN_RATE / 2)}`}</td>
                <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(ex.shien)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">厚生年金保険料</th>
                <td className="py-2 pl-3">{`${yenJa(ex.pensionStandard)}×${percentJa(KOSEI_NENKIN_RATE / 2)}`}</td>
                <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(ex.pension)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">雇用保険料</th>
                <td className="py-2 pl-3">{`${yenJa(BONUS_EXAMPLE.bonus)}×${KOYO_RATE_PER_MILLE}/1,000`}</td>
                <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(ex.koyo)}</td>
              </tr>
              <tr className="border-b border-line">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">所得税</th>
                <td className="py-2 pl-3">{`（${yenJa(BONUS_EXAMPLE.bonus)}−社会保険料${yenJa(ex.social)}）×${percentJa(ex.taxRate ?? 0)}`}</td>
                <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(ex.tax ?? 0)}</td>
              </tr>
              <tr className="border-b border-line-strong">
                <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">手取り</th>
                <td className="py-2 pl-3">額面−社会保険料−所得税</td>
                <td className="whitespace-nowrap py-2 pl-3 text-right font-bold text-ink" data-bonus-example-takehome>{yenJa(ex.takeHome)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>{`所得税の率${percentJa(ex.taxRate ?? 0)}は、国税庁の算出率の表で「扶養0人」の欄の、前月の給与（社会保険料を引いた額）が${yenJa(band.from)}以上${yenJa(band.to ?? 0)}未満の行の率です。同じ条件で40歳から64歳までの人は、介護保険料${yenJa(exKaigo.kaigo)}が加わり、手取りは${yenJa(exKaigo.takeHome)}です。`}</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[26em] border-collapse text-note tabular-nums">
            <caption className="pb-2 text-left text-ink-soft">ボーナスの額ごとの手取り（前月の給与30万円・扶養0人・東京都の協会けんぽ・40歳未満。表は横に動かせます）</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">額面</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">社会保険料</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">所得税</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">手取り</th>
              </tr>
            </thead>
            <tbody>
              {table.map(({ bonus, result }) => (
                <tr key={bonus} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">{yenJa(bonus)}</th>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(result.social)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(result.tax ?? 0)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(result.takeHome)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          出典：
          <Source source={BONUS_SOURCES.kyokaiTable} />、<Source source={BONUS_SOURCES.ntaRate} />、<Source source={BONUS_SOURCES.ntaHow} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="faq" title="よくある疑問">
        <h3 className="font-bold text-ink">ボーナスから住民税は引かれますか</h3>
        <p>引かれません。住民税は前の年の所得で1年分の額が決まり、毎月の給与から分けて引かれます。ボーナスの額が増えても、その年の住民税は変わらず、翌年の住民税に反映されます。</p>
        <h3 className="font-bold text-ink">なぜ所得税の計算に前月の給与を使うのですか</h3>
        <p>国税庁の「賞与に対する源泉徴収税額の算出率の表」は、前月の給与（社会保険料を引いた額）と扶養の数で、ボーナスに掛ける率を決める仕組みだからです。前月の給与が多いほど率は高くなります。ボーナスから引かれた所得税は、年末調整で1年分の税額と比べて精算されます。</p>
        <h3 className="font-bold text-ink">標準賞与額とは何ですか</h3>
        <p>{`ボーナスの額から1,000円未満を切り捨てた額で、社会保険料はこの額に率を掛けて出します。厚生年金保険料は1回のボーナスで${yenJa(KOSEI_NENKIN_BONUS_CAP)}まで、健康保険料・介護保険料・子ども・子育て支援金は4月から翌年3月までの合計で${yenJa(HEALTH_BONUS_YEARLY_CAP)}までにかかります。それを超えた分には保険料がかかりません。`}</p>
        <h3 className="font-bold text-ink">明細の額と1円ずれるのはなぜですか</h3>
        <p>給与から引く保険料の1円未満の端数は、50銭以下を切り捨て、50銭を超えると切り上げるのが原則ですが、会社との取り決めがあればそれによります。また、協会けんぽの保険料額表は、40歳から64歳までの人の健康保険料と介護保険料を合わせた額で示しているため、合わせてから端数を処理すると1円ずれることがあります。この計算機は項目ごとに端数を処理しています。</p>
        <h3 className="font-bold text-ink">この計算機で出せないのはどんなときですか</h3>
        <p>前月に給与が無いときや、ボーナス（社会保険料を引いた額）が前月の給与（社会保険料を引いた額）の10倍を超えるときは、所得税を別の表（月額表）で計算するため、この計算機では所得税を出しません。扶養控除等申告書を出していない人（副業先など）の税率（乙欄）にも対応していません。</p>
        <p>
          出典：
          <Source source={BONUS_SOURCES.ntaRate} />、<Source source={BONUS_SOURCES.kyokaiTable} />、<Source source={BONUS_SOURCES.mhlwKoyoRound} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="sources" title="出典">
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>
            <Source source={BONUS_SOURCES.ntaRate} />（{CHECKED}）：扶養の数と前月の給与ごとの、ボーナスに掛ける率（甲欄）
          </li>
          <li>
            <Source source={BONUS_SOURCES.ntaHow} />（{CHECKED}）：扶養親族等の数の数え方、税額の1円未満の切り捨て、計算の設例
          </li>
          <li>
            <Source source={BONUS_SOURCES.kyokaiRate} />（{CHECKED}）：47都道府県の健康保険料率（2026年3月分から）
          </li>
          <li>
            <Source source={BONUS_SOURCES.kyokaiKaigo} />、<Source source={BONUS_SOURCES.kyokaiShien} />（{CHECKED}）：介護保険料率と子ども・子育て支援金率
          </li>
          <li>
            <Source source={BONUS_SOURCES.kyokaiTable} />（{CHECKED}）：標準賞与額と上限、厚生年金保険料率、本人負担分の端数の扱い
          </li>
          <li>
            <Source source={BONUS_SOURCES.mhlwKoyo} />、<Source source={BONUS_SOURCES.mhlwKoyoRound} />（{CHECKED}）：2026年度の雇用保険料率と、本人負担分の計算
          </li>
        </ul>
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
