import { actionAdWithBenefits } from "@/lib/ad-benefits";
import type { Metadata } from "next";
import Link from "next/link";
import { withPageShare } from "@/lib/page-share";
import ToolPage, { ToolSection } from "@/components/calc/ToolPage";
import ActionAd from "@/components/ActionAd";
import { CALCULATORS, checkedDateJa } from "@/lib/calculators";
import { GUIDE_AD_POS } from "@/lib/guide-ads";
import { actionAdRules, partnerItem } from "@/lib/offers";
import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import {
  DAILY_WAGE_MAX,
  DAILY_WAGE_MIN,
  FIRST_DAYS,
  IKUKYU_EXAMPLE,
  IKUKYU_PERIOD,
  IKUKYU_SOURCES,
  MONTHLY_MAX,
  MONTHLY_MIN,
  RATE_FIRST,
  RATE_LATER,
  RATE_SHUSSEI,
  SHUSSEI_MAX_DAYS,
  SHUSSEI_MIN_DAYS,
  ikukyuExampleTable,
  ikukyuKyufu,
  yenJa,
} from "@/lib/ikukyu-kyufu";

const meta = CALCULATORS["ikukyu-kyufu"];

export const metadata: Metadata = withPageShare("ikukyu-kyufu", meta.href, {
  title: "育休中にもらえるお金はいくら？ 月給から育児休業給付金を計算",
  description: meta.description,
  alternates: { canonical: meta.href },
});

/** 出典は厚生労働省と日本年金機構。meta.checked（2026-11-26）に開いて、式・率・上限額と下限額・要件・非課税と保険料の免除を確かめた */
const CHECKED = `${checkedDateJa(meta.checked)}確認`;

const GUIDES = [
  { href: "/articles/childcare-leave-benefit-rates", label: "育児休業給付金は181日目から50％に、13％の上乗せの条件" },
  { href: "/articles/childcare-leave-benefit-50-percent-day181", label: "181日目の切り替わりの数え方と申請期限" },
  { href: "/guides/shussan-ichijikin", label: "出産育児一時金（原則50万円）の対象と申請" },
  { href: CALCULATORS["child-allowance"].href, label: CALCULATORS["child-allowance"].title },
];

function Source({ source }: { source: { href: string; label: string } }) {
  return (
    <a href={source.href} target="_blank" rel="noopener" className="text-accent underline underline-offset-4">
      {source.label}
    </a>
  );
}

/**
 * 結果の下の囲み: 記事の PR と同じ「出産・育休」の話題（content/offers.json の actionAds の childbirth。育休の記事に出している提携先）。
 * 1行目はサイト内の案内（児童手当の計算・出産育児一時金のガイド）。提携先が無ければ案内だけを出す（関係の無い広告は出さない）
 */
function ikukyuAd(): ActionAdData {
  const rule = actionAdRules().find((r) => r.key === "childbirth");
  const items = (rule?.partners ?? []).map((key) => partnerItem(key)).filter((x): x is NonNullable<typeof x> => Boolean(x)).slice(0, rule?.max ?? 2);
  const internal = [
    { href: CALCULATORS["child-allowance"].href, label: "児童手当の額を計算する" },
    { href: "/guides/shussan-ichijikin", label: "出産育児一時金の申請を確かめる" },
  ];
  return {
    key: "childbirth",
    // 見出しは記事の PR の見出し（読者への呼びかけ）を使わず、このページに合わせる
    title: "育休の前に、あわせて確かめること",
    reason: rule?.reason,
    lead: rule?.lead,
    items,
    internal,
  };
}

const FAQ = (ex: ReturnType<typeof ikukyuKyufu>) => [
  {
    q: "育児休業給付金に税金はかかりますか",
    a: "かかりません。育児休業等給付は非課税です。また、育休中は会社が申し出ることで健康保険と厚生年金の保険料が本人・会社とも免除され、会社から給与が出なければ雇用保険料もかかりません。免除された期間も、将来の年金額では保険料を納めた期間として扱われます。",
  },
  {
    q: "67%と13%で「手取り10割相当」になるのはなぜですか",
    a: `給付金が非課税で、育休中は社会保険料も免除されるため、額面の${RATE_FIRST + RATE_SHUSSEI}%（${RATE_FIRST}%＋${RATE_SHUSSEI}%）を受け取ると、働いていたときの手取りとほぼ同じになると厚生労働省が説明しています。ただし13%の上乗せは最大${SHUSSEI_MAX_DAYS}日分で、休業開始時賃金日額には上限（${yenJa(DAILY_WAGE_MAX)}）があります。`,
  },
  {
    q: "出生後休業支援給付金は、夫婦の片方だけが育休でももらえますか",
    a: "原則は、本人と配偶者がそれぞれ決まった期間に14日以上の育休を取ることが必要です。ただし、配偶者がいない、配偶者が自営業やフリーランス・無職・産後休業中などの場合は、配偶者の育休を要件としません。この場合も、本人が決まった期間に14日以上の育休を取ることが必要です。",
  },
  {
    q: "給付金はいつ、どうやって受け取りますか",
    a: "申請は原則として会社がハローワークに行い、育児休業給付金は原則2か月に一度申請します。出生後休業支援給付金は、育児休業給付金などと同じ申請書で一緒に申請するのが原則です。給付金は、支給が決まってから約1週間で本人の口座に振り込まれます。",
  },
  {
    q: "月給が高いと、いくらまでもらえますか",
    a: `${IKUKYU_PERIOD.from}から${IKUKYU_PERIOD.to}までは、休業開始時賃金日額の上限が${yenJa(DAILY_WAGE_MAX)}です。月給がおよそ${yenJa(MONTHLY_MAX)}を超える人は、最初の6か月の1か月（30日）が${yenJa(ex.firstMonthly)}、7か月目からが${yenJa(ex.laterMonthly)}で頭打ちになり、出生後休業支援給付金は${SHUSSEI_MAX_DAYS}日分で${yenJa(ex.shussei)}が上限です。上限額は毎年8月1日に見直されます。`,
  },
];

export default function IkukyuKyufuPage() {
  const ad = actionAdWithBenefits(ikukyuAd(), "");
  // 例の数字と表は、すべて計算機と同じ ikukyuKyufu() でビルドのときに出す（手で書かない）
  const ex = ikukyuKyufu(IKUKYU_EXAMPLE);
  const top = ikukyuKyufu({ ...IKUKYU_EXAMPLE, monthly: MONTHLY_MAX });
  const table = ikukyuExampleTable();
  const faq = FAQ(top);
  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faq.map((item) => ({ "@type": "Question", name: item.q, acceptedAnswer: { "@type": "Answer", text: item.a } })),
  };
  return (
    <ToolPage
      kind="ikukyu-kyufu"
      lead={`育休前の月給が${yenJa(IKUKYU_EXAMPLE.monthly)}なら、育休の最初の6か月は1か月あたり${yenJa(ex.firstMonthly)}、7か月目からは${yenJa(ex.laterMonthly)}が育児休業給付金の目安です。条件に合えば、最初の${SHUSSEI_MAX_DAYS}日分に出生後休業支援給付金${yenJa(ex.shussei)}が上乗せされます。月給と育休の長さを入れると、あなたの場合の1か月の額と合計が出ます。`}
      afterCalc={ad && (ad.items.length > 0 || ad.internal?.length) ? <ActionAd ad={ad} pos={GUIDE_AD_POS.tool} className="mt-8" /> : null}
    >
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      <ToolSection id="what" title="育休中にもらえる2つの給付金">
        <p>{`会社員など雇用保険に入っている人が育休を取ると、雇用保険から育児休業給付金が出ます。額は「休業開始時賃金日額×日数×${RATE_FIRST}%」で、育休を始めてから${FIRST_DAYS}日（約6か月）を過ぎると${RATE_LATER}%になります。`}</p>
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>休業開始時賃金日額：育休を始める前の6か月の賃金（残業代・通勤手当を含み、ボーナスは除く）の合計を180で割った額です。月給がいつも同じなら、月給の30分の1です。</li>
          <li>{`上限と下限：${IKUKYU_PERIOD.from}から${IKUKYU_PERIOD.to}までは、日額の上限が${yenJa(DAILY_WAGE_MAX)}、下限が${yenJa(DAILY_WAGE_MIN)}です（月給にすると約${yenJa(MONTHLY_MAX)}と約${yenJa(MONTHLY_MIN)}）。毎年8月1日に見直されます。`}</li>
          <li>{`産後パパ育休（出生時育児休業）で給付を受けた日数は、${RATE_FIRST}%の${FIRST_DAYS}日に含まれます。`}</li>
          <li>母親の産後休業（出産の翌日から8週間）は育児休業給付金の対象ではありません。この間は加入している健康保険の出産手当金の対象です。</li>
        </ul>
        <p>{`2025年4月からは、出生後休業支援給付金が始まりました。条件に合うと、育児休業給付金などに「休業開始時賃金日額×日数（${SHUSSEI_MAX_DAYS}日まで）×${RATE_SHUSSEI}%」が上乗せされます。条件は次の2つです。`}</p>
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>{`本人が、子の出生後の決まった期間に、給付の対象になる育休を合わせて${SHUSSEI_MIN_DAYS}日以上取ること（父親や養子の場合は出生後8週間、産後休業をした母親は出生後16週間を経過する日の翌日まで）。`}</li>
          <li>{`配偶者も、出生後8週間を経過する日の翌日までに合わせて${SHUSSEI_MIN_DAYS}日以上の育休を取ること。ただし、配偶者がいない、配偶者が自営業・フリーランス・無職・産後休業中などの場合は、配偶者の育休は要りません。`}</li>
        </ul>
        <p>{`給付金は非課税で、育休中は健康保険と厚生年金の保険料が免除されます。このため、${RATE_FIRST}%と${RATE_SHUSSEI}%を合わせた${RATE_FIRST + RATE_SHUSSEI}%を受け取る間は、手取りの10割に近い額になると厚生労働省は説明しています。`}</p>
        <p>
          出典：
          <Source source={IKUKYU_SOURCES.pamphlet} />、<Source source={IKUKYU_SOURCES.limit} />、<Source source={IKUKYU_SOURCES.nenkin} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="example" title="月給ごとの目安（サイソク編集部の計算）">
        <p>{`育休前の月給が${yenJa(IKUKYU_EXAMPLE.monthly)}で、12か月の育休を取り、出生後休業支援給付金も受け取る場合、合計の目安は${yenJa(ex.total)}です（最初の6か月${yenJa(ex.firstTotal)}、7か月目から${yenJa(ex.laterTotal)}、上乗せ${yenJa(ex.shussei)}）。`}</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[26em] border-collapse text-note tabular-nums" data-ikukyu-example>
            <caption className="pb-2 text-left text-ink-soft">月給ごとの1か月（30日）の目安（休業中に給与が出ない場合。表は横に動かせます）</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 pr-3 text-left font-bold text-ink">月給（額面）</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">{`最初の6か月（${RATE_FIRST}%）`}</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">{`7か月目から（${RATE_LATER}%）`}</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold text-ink">{`上乗せ（${SHUSSEI_MAX_DAYS}日分×${RATE_SHUSSEI}%）`}</th>
              </tr>
            </thead>
            <tbody>
              {table.map(({ monthly, result }) => (
                <tr key={monthly} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-bold text-ink">{yenJa(monthly)}</th>
                  <td className="whitespace-nowrap py-2 pl-3 text-right font-bold text-ink" data-ikukyu-example-first>{yenJa(result.firstMonthly)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(result.laterMonthly)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right">{yenJa(result.shussei)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>{`厚生労働省の手引の例（休業開始時賃金日額10,000円＝月給30万円）でも、育児休業給付金は1か月（30日）で${yenJa(ikukyuKyufu({ ...IKUKYU_EXAMPLE, days: 30 }).firstMonthly)}、出生後休業支援給付金は${SHUSSEI_MAX_DAYS}日で${yenJa(ex.shussei)}です。実際の額は、会社が出す賃金の証明（休業開始時賃金月額証明書）をもとにハローワークが決めるため、ここでの目安と少しずれることがあります。`}</p>
        <p>
          出典：
          <Source source={IKUKYU_SOURCES.pamphlet} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="faq" title="よくある疑問">
        {faq.map((item) => (
          <div key={item.q} className="grid gap-1.5">
            <h3 className="font-bold text-ink">{item.q}</h3>
            <p>{item.a}</p>
          </div>
        ))}
        <p>
          出典：
          <Source source={IKUKYU_SOURCES.pamphlet} />、<Source source={IKUKYU_SOURCES.limit} />、<Source source={IKUKYU_SOURCES.nenkin} />（{CHECKED}）
        </p>
      </ToolSection>

      <ToolSection id="sources" title="出典">
        <ul className="grid list-disc gap-1.5 pl-5">
          <li>
            <Source source={IKUKYU_SOURCES.pamphlet} />（{CHECKED}）：支給額の式、休業開始時賃金日額の出し方と上限額・下限額、出生後休業支援給付金の要件、非課税と保険料の免除、申請の流れ
          </li>
          <li>
            <Source source={IKUKYU_SOURCES.limit} />（{CHECKED}）：2026年8月1日からの支給上限額と賃金月額の上限・下限
          </li>
          <li>
            <Source source={IKUKYU_SOURCES.mhlw} />（{CHECKED}）：育児休業等給付の制度の案内
          </li>
          <li>
            <Source source={IKUKYU_SOURCES.nenkin} />（{CHECKED}）：育休中の健康保険・厚生年金保険の保険料の免除
          </li>
        </ul>
        <p>{`更新日：${checkedDateJa(meta.checked)}`}</p>
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
