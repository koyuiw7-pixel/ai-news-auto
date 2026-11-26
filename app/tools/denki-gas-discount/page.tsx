import { actionAdWithBenefits } from "@/lib/ad-benefits";
import type { Metadata } from "next";
import Link from "next/link";
import { withPageShare } from "@/lib/page-share";
import ToolPage, { ToolSection } from "@/components/calc/ToolPage";
import ActionAd from "@/components/ActionAd";
import { CALCULATORS, checkedDateJa } from "@/lib/calculators";
import { GUIDE_AD_POS, toolAd } from "@/lib/guide-ads";
import { DENKI_GAS_DEFAULT, DENKI_GAS_MONTHS, DENKI_GAS_SOURCE, WINTER_RATIO, denkiGasDiscount, denkiGasExampleTable, inputFromDecember, unitPrice, yenDecimal } from "@/lib/denki-gas-discount";

const meta = CALCULATORS["denki-gas-discount"];

export const metadata: Metadata = withPageShare("denki-gas-discount", meta.href, {
  title: "うちの電気代・ガス代は冬にいくら安くなる？ 国の支援の値引き額を使用量で計算",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 出典は資源エネルギー庁の特設サイト。meta.checked（2026-11-26）に開いて、対象期間・値引き単価・式・対象外・詐欺の注意を確かめた */
const CHECKED = `${checkedDateJa(meta.checked)}確認`;

const GUIDES = [
  { href: "/articles/winter-electricity-gas-subsidy-2026", label: "冬の電気・ガス料金支援の単価と対象期間" },
  { href: "/articles/electricity-gas-support-phone-warning", label: "電気・ガス料金支援をかたる不審な電話に注意" },
  { href: "/dates", label: "暮らしとお金の日程（支給日・期限）" },
  { href: CALCULATORS["furusato-limit"].href, label: CALCULATORS["furusato-limit"].title },
  { href: CALCULATORS["child-allowance"].href, label: CALCULATORS["child-allowance"].title },
  { href: CALCULATORS["pension-support-benefit"].href, label: CALCULATORS["pension-support-benefit"].title },
];

function Source() {
  return (
    <a href={DENKI_GAS_SOURCE.href} target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
      {DENKI_GAS_SOURCE.label}
    </a>
  );
}

export default function DenkiGasDiscountPage() {
  const ad = actionAdWithBenefits(toolAd("energy"), "");
  // 例の表と例の文の数字は、すべて計算機と同じ denkiGasDiscount() でビルドのときに出す（手で書かない）
  const table = denkiGasExampleTable();
  const example = denkiGasDiscount(inputFromDecember(DENKI_GAS_DEFAULT.electricity, DENKI_GAS_DEFAULT.gas));
  const [dec, jan, feb] = DENKI_GAS_MONTHS;
  const ratioPercent = Math.round((WINTER_RATIO - 1) * 100);
  return (
    <ToolPage
      kind="denki-gas-discount"
      lead={`検針票の12月の電気（kWh）と都市ガス（㎥）の使用量を入れると、国の電気・ガス料金支援で${dec.label}から${feb.label}までの3か月に、いくら安くなるかの目安が出ます。1月・2月の使用量は12月の${WINTER_RATIO}倍が初期値で、書き換えられます。`}
      afterCalc={ad ? <ActionAd ad={ad} pos={GUIDE_AD_POS.tool} tool="denki-gas-discount" className="mt-8" /> : null}
    >
      <ToolSection id="what" title="電気・ガス料金支援とは">
        <p>{`経済産業省 資源エネルギー庁が行う、冬の電気代・都市ガス代の値引きです。対象は${dec.label}から${feb.label}まで。値引き額は「値引き単価×月々の使用量」で、使った量が多いほど値引きも大きくなります。`}</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[26em] border-collapse text-note tabular-nums">
            <caption className="pb-2 text-left text-ink-soft">値引き単価（家庭の電気は低圧）</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">使用分</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">電気（1kWhあたり）</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">都市ガス（1㎥あたり）</th>
              </tr>
            </thead>
            <tbody>
              {DENKI_GAS_MONTHS.map((m) => (
                <tr key={m.key} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">{m.label}</th>
                  <td className="py-2 pl-3 text-right">{unitPrice(m.electricity)}</td>
                  <td className="py-2 pl-3 text-right">{unitPrice(m.gas)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>{`12月使用分は単価が小さく、1月・2月使用分で大きくなります。工場やビルなどの高圧の電気は、${dec.label}が${unitPrice(dec.electricityHigh)}、${jan.label}・2月使用分が${unitPrice(jan.electricityHigh)}です（この計算機は家庭向けの低圧で計算します）。`}</p>
        <p>
          出典：
          <Source />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="meisai" title="明細（検針票）の使用量の見方">
        <p>電力会社・ガス会社から届く「電気ご使用量のお知らせ」（検針票）や、会社のアプリ・会員サイトの「ご使用量」の欄に、その月の使用量が載っています。電気はkWh、都市ガスは㎥（立方メートル）の数字を入れます。</p>
        <p>「12月使用分」は、原則として12月中の検針日から1月中の検針日までに使った分です。カレンダーの12月1日〜31日ではないので、検針票の期間を確かめてください。12月使用分の値引きは、多くの場合1月に届く請求に反映されます。</p>
        <p>{`1月・2月の使用量が分からないときは、特設サイトの試算と同じく、12月の約${ratioPercent}%増し（${WINTER_RATIO}倍）を初期値にしています。昨年の冬の検針票があれば、その数字に書き換えると目安が近くなります。`}</p>
      </ToolSection>

      <ToolSection id="not-covered" title="対象にならないもの">
        <p>プロパンガス（LPガス）は、この支援の対象外です。家のガスがプロパンガスなら、計算機の「家のガスはプロパンガス（LPガス）」に印を付けると、電気だけで計算します。</p>
        <p>値引きは、この支援に参加している電力会社・ガス会社の請求で反映されます。契約している会社が参加しているかは、特設サイトで探せます。</p>
        <p>
          出典：
          <Source />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="scam" title="申請は不要、詐欺に注意">
        <p>値引きを受けるための申請は要らず、手数料もかかりません。特設サイトは、この支援を名目に個人情報や手数料を求める電話は詐欺の可能性があるとして、注意を呼びかけています。そうした電話には応じず、契約している電力会社・ガス会社の公式の窓口に確かめてください。</p>
        <p>
          出典：
          <Source />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="example" title="計算の例">
        <p>{`例：12月の電気${DENKI_GAS_DEFAULT.electricity}kWh・都市ガス${DENKI_GAS_DEFAULT.gas}㎥で、1月・2月は12月の${WINTER_RATIO}倍のとき`}</p>
        <ul className="grid list-disc gap-1.5 pl-5 tabular-nums">
          {example.months.map((m, i) => (
            <li key={m.key}>{`${m.label}：電気 ${m.usage.electricity}kWh×${unitPrice(DENKI_GAS_MONTHS[i].electricity)}＝${yenDecimal(m.electricity)}、都市ガス ${m.usage.gas}㎥×${unitPrice(DENKI_GAS_MONTHS[i].gas)}＝${yenDecimal(m.gas)}、合計${yenDecimal(m.total)}`}</li>
          ))}
        </ul>
        <p>{`3か月の合計は${yenDecimal(example.total)}です（電気${yenDecimal(example.electricity)}、都市ガス${yenDecimal(example.gas)}）。`}</p>
        <p id="example-caption" className="text-note text-ink-soft">
          ほかの例（使用量は計算のために置いた例で、公式の平均ではありません。1月・2月は12月の{WINTER_RATIO}倍。表は横に動かせます）
        </p>
        <div className="overflow-x-auto">
          <table aria-describedby="example-caption" className="w-full min-w-[36em] border-collapse text-note tabular-nums">
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">例</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">12月の使用量</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">12月分</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">1月分</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">2月分</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">3か月の合計</th>
              </tr>
            </thead>
            <tbody>
              {table.map((row) => (
                <tr key={row.label} className="border-b border-line">
                  <th scope="row" className="whitespace-nowrap py-2 pr-3 text-left font-bold text-ink">{row.label}</th>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{`${row.decElectricity}kWh・${row.decGas}㎥`}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yenDecimal(row.dec)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yenDecimal(row.jan)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yenDecimal(row.feb)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right font-bold text-ink">{yenDecimal(row.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>実際の値引き額は、毎月の使用量と、会社ごとの端数の扱いで変わります。請求の明細で確かめてください。</p>
      </ToolSection>

      <ToolSection id="sources" title="出典">
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>
            <Source />（{CHECKED}）：対象期間、値引き単価、値引き額の考え方、申請不要、プロパンガスが対象外であること、詐欺の注意、対象の事業者の探し方
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
