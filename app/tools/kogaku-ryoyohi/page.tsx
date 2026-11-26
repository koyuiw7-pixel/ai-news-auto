import { actionAdWithBenefits } from "@/lib/ad-benefits";
import type { Metadata } from "next";
import Link from "next/link";
import { withPageShare } from "@/lib/page-share";
import ToolPage, { ToolSection } from "@/components/calc/ToolPage";
import ActionAd from "@/components/ActionAd";
import { CALCULATORS, checkedDateJa } from "@/lib/calculators";
import { GUIDE_AD_POS, toolAd } from "@/lib/guide-ads";
import { KOGAKU_EXAMPLE_TOTALS, KOGAKU_LOW_YEARLY, KOGAKU_PERIOD, KOGAKU_SETAI_MIN, KOGAKU_SOURCES, bandsFor, kogaku, kogakuExampleTable, manYen, yenJa } from "@/lib/kogaku-ryoyohi";

const meta = CALCULATORS["kogaku-ryoyohi"];

export const metadata: Metadata = withPageShare("kogaku-ryoyohi", meta.href, {
  title: "医療費が高額になったら月いくらまで？ 高額療養費の自己負担の上限を年収で計算",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 出典は厚生労働省の資料と協会けんぽの案内。meta.checked（2026-11-26）に開いて、上限額・多数回該当・年間上限・世帯合算・認定証を確かめた */
const CHECKED = `${checkedDateJa(meta.checked)}確認`;

const GUIDES = [
  { href: "/guides/kogaku-ryoyohi", label: "高額療養費の上限額と申請のしかた" },
  { href: "/articles/kogaku-ryoyohi-2026-tasukai-kaisu", label: "4回目からの上限額（多数回該当）と年間上限" },
  { href: "/guides/iryohi-kojo", label: "医療費控除の対象を確かめる" },
];

function Source({ source }: { source: { href: string; label: string } }) {
  return (
    <a href={source.href} target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
      {source.label}
    </a>
  );
}

/**
 * 結果の下の囲み: 医療費控除の申告（確定申告ソフト）。記事の「医療費控除の申告」と同じ提携先（content/offers.json の tax）で、
 * 見出しとつなぎの一文だけ医療費に合わせる。提携先が無ければ、医療費控除のガイドへの案内だけを出す（関係の無い広告は出さない）
 */
function medicalAd() {
  const tax = toolAd("tax");
  const internal = [{ href: "/guides/iryohi-kojo", label: "医療費控除の対象を確かめる" }];
  const lead = "1年の医療費が一定額を超えると、確定申告で医療費控除を受けられます（高額療養費で戻った分は差し引きます）。料金・条件は各公式サイトで確認してください。";
  const title = "医療費が多かった年は、医療費控除の申告も";
  return tax ? { ...tax, title, lead, internal } : { key: "medical", title, lead, items: [], internal };
}

export default function KogakuRyoyohiPage() {
  const ad = actionAdWithBenefits(medicalAd(), "");
  // 例の表と例の文の数字は、すべて計算機と同じ kogaku() でビルドのときに出す（手で書かない）
  const table = kogakuExampleTable();
  const under70 = bandsFor("under70");
  const senior = bandsFor("75plus");
  const example = kogaku({ age: "under70", band: "u", totalMedical: 1_000_000 });
  const exampleMany = kogaku({ age: "under70", band: "u", totalMedical: 1_000_000, many: true });
  const u = under70.find((b) => b.key === "u")!;
  const e = under70.find((b) => b.key === "e")!;
  const seniorGeneral = senior.find((b) => b.key === "e")!;
  const seniorLow2 = senior.find((b) => b.key === "o")!;
  const seniorLow1 = senior.find((b) => b.key === "low1")!;
  return (
    <ToolPage
      kind="kogaku-ryoyohi"
      lead={`年齢と年収の区分を選ぶと、1か月の医療費の自己負担がいくらまでで済むか（高額療養費の上限額）がすぐに出ます。${KOGAKU_PERIOD.from}から${KOGAKU_PERIOD.to}までの額です。入院の前で総医療費が分からないときは、総医療費100万円のときの上限を出します。`}
      afterCalc={ad ? <ActionAd ad={ad} pos={GUIDE_AD_POS.tool} tool="kogaku-ryoyohi" className="mt-8" /> : null}
    >
      <ToolSection id="what" title="高額療養費とは">
        <p>同じ月の中で病院や薬局で払った医療費が上限額を超えたとき、超えた分が健康保険から戻る仕組みです。上限額は年齢と所得で決まります。</p>
        <p>{`例えば69歳までで年収約370万〜約770万円の人が、1か月の総医療費100万円の治療を受けると、窓口の3割は${yenJa(example.windowShare)}ですが、自己負担は${yenJa(example.pay)}までです（${yenJa(u.base)}＋（100万円−${yenJa(u.threshold!)}）×1%）。差の${yenJa(example.over)}は払わずに済むか、あとで戻ります。`}</p>
        <p>
          出典：
          <Source source={KOGAKU_SOURCES.mhlwPdf} />、<Source source={KOGAKU_SOURCES.kyokai} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="limits" title={`69歳までの上限額（${KOGAKU_PERIOD.from}〜${KOGAKU_PERIOD.to}）`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34em] border-collapse text-note tabular-nums">
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">区分</th>
                <th scope="col" className="py-2 pl-3 text-left font-bold text-ink">1か月の上限</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">4か月目から</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">年間の上限</th>
              </tr>
            </thead>
            <tbody>
              {under70.map((b) => (
                <tr key={b.key} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">{`${b.letter}：${b.label}`}</th>
                  <td className="py-2 pl-3 text-left">{b.threshold !== undefined ? `${yenJa(b.base)}＋（総医療費−${yenJa(b.threshold)}）×1%` : yenJa(b.base)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{b.many !== undefined ? yenJa(b.many) : "なし"}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{manYen(b.yearly)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>区分は年収そのものではなく、会社の健康保険なら標準報酬月額、国民健康保険なら旧ただし書き所得で決まります。年収は厚生労働省の資料にある目安です。区分が分からないときは、加入している健康保険に確かめてください。</p>
        <p>{`区分エ（年収約370万円まで）のうち、年収約200万円まで（会社の健康保険は標準報酬月額15万円以下）と確認できた人は、年間の上限が${manYen(KOGAKU_LOW_YEARLY)}になり、2027年8月以降に払い戻されます（協会けんぽの案内）。`}</p>
        <p>
          出典：
          <Source source={KOGAKU_SOURCES.mhlwPdf} />、<Source source={KOGAKU_SOURCES.kyokai} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="senior" title="70歳以上の上限額">
        <p>{`年収約370万円以上の「現役並み所得」の人は、69歳までと同じ式です。それ以外の人は定額で、外来（通院）だけの月はひとりごとの上限もあります（外来特例）。`}</p>
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>{`一般（年収約370万円まで）：外来だけならひとり${yenJa(seniorGeneral.outpatient!)}（年間の上限${manYen(seniorGeneral.outpatientYearly!)}）、入院を含めて世帯で${yenJa(seniorGeneral.base)}（4か月目から${yenJa(seniorGeneral.many!)}、年間の上限${manYen(seniorGeneral.yearly)}）`}</li>
          <li>{`住民税が非課税（低所得者Ⅱ）：外来だけならひとり${yenJa(seniorLow2.outpatient!)}（年間の上限${manYen(seniorLow2.outpatientYearly!)}）、入院を含めて世帯で${yenJa(seniorLow2.base)}（4か月目から${yenJa(seniorLow2.many!)}、年間の上限${manYen(seniorLow2.yearly)}）`}</li>
          <li>{`住民税が非課税で所得が一定以下（低所得者Ⅰ）：外来だけならひとり${yenJa(seniorLow1.outpatient!)}、入院を含めて世帯で${yenJa(seniorLow1.base)}（年間の上限${manYen(seniorLow1.yearly)}）`}</li>
        </ul>
        <p>窓口の負担割合は、現役並み所得の人が3割、それ以外は70〜74歳が2割、75歳以上が1割（一定以上の所得がある人は2割）です。</p>
        <p>
          出典：
          <Source source={KOGAKU_SOURCES.mhlwPdf} />、<Source source={KOGAKU_SOURCES.kyokai} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="window" title="窓口の支払いを最初から上限までにする">
        <p>高額療養費は、もともと「いったん窓口で払い、あとで申請して戻る」仕組みです。マイナ保険証を使うか、事前に限度額適用認定証を出せば、上限を超える分を窓口で払わずに済みます。</p>
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>マイナ保険証：申請は要りません。マイナ保険証での確認（オンライン資格確認）に対応した病院・薬局の受付で使います。</li>
          <li>限度額適用認定証：マイナ保険証を使わないときや、病院がオンライン資格確認に対応していないときに使います。支払いの前に、加入している健康保険（協会けんぽなら加入している都道府県支部）に申請します。</li>
          <li>住民税が非課税の人は、マイナ保険証を使う場合でも「限度額適用・標準負担額減額認定証」を申請します（協会けんぽの案内）。</li>
          <li>協会けんぽが2026年8月から出す限度額適用認定証の有効期限は、最長で2027年7月31日です（2027年8月に区分が変わるため）。</li>
        </ul>
        <p>複数の病院・薬局の分や家族の分を合わせて上限を超えたときは、あとで申請すると、超えた分が払い戻されます（世帯合算。下の「よくある疑問」）。</p>
        <p>
          出典：
          <Source source={KOGAKU_SOURCES.mhlw} />、<Source source={KOGAKU_SOURCES.nintei} />、<Source source={KOGAKU_SOURCES.kyokai} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="example" title="計算の例（サイソク編集部の計算）">
        <p id="example-caption" className="text-note text-ink-soft">
          69歳まで・窓口3割・1回目〜3回目の月の自己負担（総医療費は計算のために置いた例です。表は横に動かせます）
        </p>
        <div className="overflow-x-auto">
          <table aria-describedby="example-caption" className="w-full min-w-[34em] border-collapse text-note tabular-nums">
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">区分</th>
                {KOGAKU_EXAMPLE_TOTALS.map((t) => (
                  <th key={t} scope="col" className="py-2 pl-3 text-right font-bold text-ink">{`総医療費${manYen(t)}`}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.map((row) => (
                <tr key={row.band.key} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">{`${row.band.letter}：${row.band.label}`}</th>
                  {row.pays.map((pay, i) => (
                    <td key={KOGAKU_EXAMPLE_TOTALS[i]} className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(pay)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>{`総医療費${manYen(KOGAKU_EXAMPLE_TOTALS[0])}のとき、区分アとイは窓口の3割（${yenJa(KOGAKU_EXAMPLE_TOTALS[0] * 0.3)}）が上限より少ないため、払い戻しはありません。区分ウの人が4か月目（多数回該当）になると、上限は総医療費にかかわらず${yenJa(exampleMany.cap)}です。`}</p>
        <p>{`区分エ（${e.label}）とオ（住民税が非課税）は、総医療費が上がっても上限は同じです。`}</p>
      </ToolSection>

      <ToolSection id="faq" title="よくある疑問">
        <h3 className="font-bold text-ink">総医療費とは何ですか</h3>
        <p>保険がきく診察・検査・手術・薬などの費用の全額（10割）です。窓口で3割を払ったなら、払った額÷0.3がおおよその総医療費です。</p>
        <h3 className="font-bold text-ink">入院中の食事代や差額ベッド代も対象ですか</h3>
        <p>対象外です。入院中の食事代・生活費の自己負担や、差額ベッド代などの保険外の差額は、上限の計算に入りません。</p>
        <h3 className="font-bold text-ink">4か月目から下がる「多数回該当」とは</h3>
        <p>直近12か月のうちに、上限に達して高額療養費を受けた月が3か月以上あると、4か月目から上限が下がります。限度額適用認定証などで窓口で上限まで払った月も数に入ります。加入している健康保険が変わると、それまでの月数は引き継がれません。</p>
        <h3 className="font-bold text-ink">家族の医療費は合わせられますか</h3>
        <p>{`同じ月の自己負担は、家族の分（協会けんぽなら本人と扶養されている家族）や、複数の病院・薬局の分を合わせて上限と比べられます（世帯合算）。69歳までは、1つの医療機関での自己負担（医科の入院・外来、歯科の入院・外来はそれぞれ別）が${yenJa(KOGAKU_SETAI_MIN)}以上の分だけを合わせます。院外の薬局の分は、処方せんを出した医療機関の分に合わせます。70歳以上は金額にかかわらず合わせられます。`}</p>
        <h3 className="font-bold text-ink">新しくできた「年間の上限」とは</h3>
        <p>{`2026年8月から、毎年8月から翌年7月までの1年の自己負担にも上限ができました。毎月の上限に届かない月が続いても、1年の合計が年間の上限（69歳までの区分ウなら${manYen(u.yearly)}）に達したら、それ以上は戻ります。協会けんぽは、年間の上限の申請を2027年8月から受け付けると案内しています。ほかの健康保険や国民健康保険は、加入先の案内で確かめてください。`}</p>
        <h3 className="font-bold text-ink">2027年8月からは変わりますか</h3>
        <p>変わります。2027年8月診療分からは所得の区分が細かく分かれ、多くの区分で上限額が変わります。この計算機は2027年7月診療分までの額です。</p>
        <p>
          出典：
          <Source source={KOGAKU_SOURCES.mhlw} />、<Source source={KOGAKU_SOURCES.mhlwPdf} />、<Source source={KOGAKU_SOURCES.kyokai} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="sources" title="出典">
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>
            <Source source={KOGAKU_SOURCES.mhlwPdf} />（{CHECKED}）：2026年8月〜2027年7月診療分の上限額・4か月目からの額・年間の上限、70歳以上の外来の上限、2027年8月からの区分
          </li>
          <li>
            <Source source={KOGAKU_SOURCES.mhlw} />（{CHECKED}）：高額療養費の仕組み、多数回該当、年間の上限（8月〜翌年7月）、マイナ保険証か認定証で窓口の支払いが上限まで
          </li>
          <li>
            <Source source={KOGAKU_SOURCES.kyokai} />（{CHECKED}）：区分ア〜オ、世帯合算、年間の上限の申請の開始、食事代などが対象外であること
          </li>
          <li>
            <Source source={KOGAKU_SOURCES.nintei} />（{CHECKED}）：限度額適用認定証の申請、マイナ保険証なら申請が要らないこと、認定証の有効期限
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
