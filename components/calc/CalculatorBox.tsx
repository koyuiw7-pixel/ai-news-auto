import Link from "next/link";
import { CALCULATORS, type ArticleCalculator } from "@/lib/calculators";
import dynamic from "next/dynamic";

// 計算機は記事ごとに1種類だけ。使う種類の JS だけを読むよう、種類ごとに分けて読み込む（サーバーでの描画はそのまま）
const DefenseTaxCalc = dynamic(() => import("@/components/calc/DefenseTaxCalc"));
const FurusatoLimitCalc = dynamic(() => import("@/components/calc/FurusatoLimitCalc"));
const ChildAllowanceCalc = dynamic(() => import("@/components/calc/ChildAllowanceCalc"));
const PensionSupportCalc = dynamic(() => import("@/components/calc/PensionSupportCalc"));
const DenkiGasDiscountCalc = dynamic(() => import("@/components/calc/DenkiGasDiscountCalc"));
const KogakuRyoyohiCalc = dynamic(() => import("@/components/calc/KogakuRyoyohiCalc"));
const BonusTedoriCalc = dynamic(() => import("@/components/calc/BonusTedoriCalc"));
const IkukyuKyufuCalc = dynamic(() => import("@/components/calc/IkukyuKyufuCalc"));

/** 計算機ごとの注意書き（数字の前提。必ず表示する） */
export const CALC_NOTES: Record<ArticleCalculator["kind"], string> = {
  "defense-tax":
    "国の税（防衛特別所得税・復興特別所得税）だけの計算で、住民税は入っていません。財務省「令和8年度税制改正の大綱」の税率で、1円未満は切り捨てています。実際の申告では所得税と合わせて100円未満を切り捨てるため、少しずれることがあります。個別の税額は税務署・税理士にご確認ください。",
  "furusato-limit":
    "2026年（令和8年）の寄附の目安です。住民税の特例分は所得割額の2割まで、という総務省「税金の控除について」の計算式で出しています。「年収から」は給与収入だけ・社会保険料は年収の15%（総務省が以前載せていた目安表と同じ前提）で計算します。正確な上限額は、お住まいの市区町村に確認してください。",
  "child-allowance":
    "こども家庭庁の案内（令和6年10月分からの制度）の月額で計算しています。生まれた月の分は出ず、申請した月の翌月分から支給されます。18歳の年度末を過ぎた子は、親が生活費を負担しているときだけ第3子の数え方に入ります。支給日の日にちと実際の金額は、お住まいの市区町村（公務員は勤務先）で確かめてください。",
  "pension-support-benefit":
    "日本年金機構の案内（令和8年度の額、令和8年10月分から令和9年9月分までの判定）で計算した目安です。判定には令和7年の収入・所得を使い、障害年金・遺族年金は収入に入れません。原則、偶数月の中旬に2か月分が年金と同じ口座に、年金とは別に振り込まれます。実際に受け取れるか・金額は、届いた請求書や日本年金機構の通知で確かめてください。",
  "denki-gas-discount":
    "経済産業省 資源エネルギー庁「電気・ガス料金支援」特設サイトの値引き単価（2026年12月使用分〜2027年2月使用分、家庭の電気＝低圧と都市ガス）で計算した目安です。値引き額は値引き単価×月々の使用量で、1月・2月の使用量の初期値は12月の1.2倍です。申請は不要で、参加している電力・ガス会社の請求で値引きされます。プロパンガス（LPガス）は対象外です。実際の額は検針票や請求の明細で確かめてください。",
  "kogaku-ryoyohi":
    "厚生労働省「高額療養費制度の見直しについて（令和８年８月診療分から）」と協会けんぽの案内の、2026年8月診療分から2027年7月診療分までの上限額で計算した目安です。総医療費は保険がきく医療費の全額（10割）で、入れなければ100万円で計算します。入院中の食事代や差額ベッド代などは含みません。区分は年収ではなく標準報酬月額（会社の健康保険）や所得（国民健康保険）で決まるため、実際の額は加入している健康保険で確かめてください。",
  "bonus-tedori":
    "協会けんぽの令和8年度の健康保険料率・介護保険料率（令和8年3月分から）と子ども・子育て支援金率（令和8年4月分から）、厚生年金保険料率18.3%、厚生労働省の2026年度の雇用保険料率（一般の事業）、国税庁「賞与に対する源泉徴収税額の算出率の表（令和8年分）」の甲欄で計算した目安です。本人負担分の1円未満は50銭以下を切り捨て、所得税は1円未満を切り捨てています。健康保険組合の人は、組合の率を入れてください。実際の額はボーナスの明細で確かめてください。",
  "ikukyu-kyufu":
    "厚生労働省「育児休業等給付の内容と支給申請手続」（2026年8月1日改訂版）の式と、2026年8月1日から2027年7月31日までの上限額・下限額（休業開始時賃金日額16,540円・3,203円）で計算した目安です。休業開始時賃金日額は月給×6÷180、1か月は30日、休業中に会社から給与が出ない場合として、1円未満は切り捨てています。実際の額は、会社が出す賃金の証明をもとにハローワークが決めます。",
};

/** 記事の中に置く計算機（本文の章の下、または本文の終わり） */
export default function CalculatorBox({ calc, className = "" }: { calc: ArticleCalculator; className?: string }) {
  const meta = CALCULATORS[calc.kind];
  const headingId = `calc-${calc.kind}-heading`;
  return (
    <section aria-labelledby={headingId} data-calc={calc.kind} className={`max-w-[42.5rem] rounded-2xl border border-line-strong bg-paper p-5 sm:p-6 ${className}`}>
      <p className="text-meta font-bold text-accent">計算してみる</p>
      <h2 id={headingId} className="t-h3 mt-0.5">
        {meta.title}
      </h2>
      <div className="mt-4">
        <Calculator calc={calc} />
      </div>
      <p className="mt-4 text-note leading-[1.7] text-ink-soft">{CALC_NOTES[calc.kind]}</p>
      <p className="mt-2 text-note">
        <Link href={meta.href} className="font-bold text-accent underline decoration-line-strong underline-offset-4 hover:decoration-accent">
          {meta.title}のページで開く →
        </Link>
      </p>
    </section>
  );
}

export function Calculator({ calc }: { calc: Pick<ArticleCalculator, "kind"> }) {
  if (calc.kind === "furusato-limit") return <FurusatoLimitCalc />;
  if (calc.kind === "child-allowance") return <ChildAllowanceCalc />;
  if (calc.kind === "pension-support-benefit") return <PensionSupportCalc />;
  if (calc.kind === "denki-gas-discount") return <DenkiGasDiscountCalc />;
  if (calc.kind === "kogaku-ryoyohi") return <KogakuRyoyohiCalc />;
  if (calc.kind === "bonus-tedori") return <BonusTedoriCalc />;
  if (calc.kind === "ikukyu-kyufu") return <IkukyuKyufuCalc />;
  return <DefenseTaxCalc />;
}
