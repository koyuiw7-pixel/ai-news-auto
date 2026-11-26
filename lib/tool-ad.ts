import type { OfferItem } from "@/lib/offers";
import { CHILD_ALLOWANCE_NEXT_PAYMENT } from "@/lib/child-allowance";

/**
 * 計算ツールの結果のすぐ下の PR（pos "tool-result"）の新しい見た目 B（2026-11-27。A/B は <html data-adv="a|b">。A = 今までの囲み）。
 * 2026-11-27 オーナー「広告の選定は悪くはないと思ったけど、それ以上に配置と見た目が魅力０だった」:
 *   提携先は A と同じ（囲みの1つ目）。変えるのは場所（結果のすぐ下。注記より前）と見た目だけ。
 *   見出し = 計算したばかりの読者の次の一歩（読者の言葉）、1行 = 提携先の公式の事実（content/offers.json の pitch.merits・content/ad_benefits.json の数字）だけ、
 *   ボタン1つ（押した先で何ができるか）。出典の行・2つ目の提携先の行・大きな意味のない数字は出さない。
 * ここに無い組み合わせ（提携先が入れ替わったとき）は、商品の pitch.gain と1つ目の良いところで作る（出典のある事実だけ）。
 */
export type ToolKind =
  | "child-allowance"
  | "ikukyu-kyufu"
  | "pension-support-benefit"
  | "furusato-limit"
  | "bonus-tedori"
  | "denki-gas-discount"
  | "kogaku-ryoyohi"
  | "defense-tax";

export type ToolAdCopy = { headline: string; line: string; cta: string };

const payMonth = CHILD_ALLOWANCE_NEXT_PAYMENT.month;

/** 計算ツール × 提携先 → 見出し・1行・ボタン。数字と事実の出どころは各行のコメント */
const COPY: Record<string, ToolAdCopy> = {
  // デジタネ: 14日間の無料体験・マインクラフトなどのゲームで学べる（offers.json pitch.merits、ad_benefits.json digitane。公式 11/10 確認）
  "child-allowance:digitane": {
    headline: `${payMonth}月の児童手当の使い道に、まず14日間の無料体験`,
    line: "マインクラフトなどのゲームを題材に、子どもがプログラミングを学べる教材です。",
    cta: "デジタネの無料体験を見る",
  },
  // LITALICOワンダー: ロボットやプログラミングのITものづくり教室（offers.json pitch.point）
  "child-allowance:litalico": {
    headline: `${payMonth}月の児童手当の使い道に、ものづくりの教室を`,
    line: "ロボットやプログラミングで、子どもがものづくりを体験できる教室です。",
    cta: "LITALICOワンダーの教室を見る",
  },
  // エブリィフレシャス: 水道水を入れて使う浄水型・月額 税込2,750円から（水道代は別）（ad_benefits.json frecious。公式 11/10 確認）
  "ikukyu-kyufu:frecious": {
    headline: "育休中の、重い水の買い出しを減らす",
    line: "水道水を入れて使う浄水型サーバー。月額は税込2,750円から（水道代は別）。",
    cta: "料金と設置条件を見る",
  },
  // BB.exciteモバイル: 低速通信のみの月は音声SIM 月495円（税込）・解約事務手数料0円（ad_benefits.json bb-excite。公式 11/10 確認）
  "pension-support-benefit:bb-excite": {
    headline: "年金の暮らしの固定費、スマホ代から見直す",
    line: "音声SIMは、低速通信だけの月なら月495円（税込）から。解約の手数料は0円です。",
    cta: "BB.exciteモバイルの料金を見る",
  },
  // ふるさと本舗: 5万件以上の返礼品を掲載（offers.json pitch.merits）。今年分は12月31日までの寄附（総務省）
  "furusato-limit:furusato-honpo": {
    headline: "上限がわかったら、その中で返礼品を選ぶ",
    line: "全国の5万件以上の返礼品から探せます。今年分の寄附は12月31日までです。",
    cta: "ふるさと本舗で返礼品を探す",
  },
  "furusato-limit:rakuten-furusato": {
    headline: "上限がわかったら、その中で返礼品を選ぶ",
    line: "楽天市場の中で返礼品を探して寄付できます。今年分の寄附は12月31日までです。",
    cta: "楽天ふるさと納税で返礼品を探す",
  },
  "furusato-limit:aupay-furusato": {
    headline: "上限がわかったら、その中で返礼品を選ぶ",
    line: "返礼品を探して、そのまま寄附できます。今年分の寄附は12月31日までです。",
    cta: "au PAY ふるさと納税で返礼品を探す",
  },
  // 自己負担2,000円（総務省 ふるさと納税など個人住民税の寄附金税制。ad_benefits.json furusato）
  "bonus-tedori:furusato-honpo": {
    headline: "ボーナスが出たら、今年のふるさと納税を",
    line: "上限の中の寄附なら、自己負担は2,000円。今年分は12月31日までです。",
    cta: "ふるさと本舗で返礼品を探す",
  },
  "bonus-tedori:rakuten-furusato": {
    headline: "ボーナスが出たら、今年のふるさと納税を",
    line: "上限の中の寄附なら、自己負担は2,000円。今年分は12月31日までです。",
    cta: "楽天ふるさと納税で返礼品を探す",
  },
  "bonus-tedori:aupay-furusato": {
    headline: "ボーナスが出たら、今年のふるさと納税を",
    line: "上限の中の寄附なら、自己負担は2,000円。今年分は12月31日までです。",
    cta: "au PAY ふるさと納税で返礼品を探す",
  },
  "defense-tax:furusato-honpo": {
    headline: "所得税を確かめたら、今年のふるさと納税も",
    line: "上限の中の寄附なら、自己負担2,000円を除いて所得税と住民税から控除されます。",
    cta: "ふるさと本舗で返礼品を探す",
  },
  "defense-tax:rakuten-furusato": {
    headline: "所得税を確かめたら、今年のふるさと納税も",
    line: "上限の中の寄附なら、自己負担2,000円を除いて所得税と住民税から控除されます。",
    cta: "楽天ふるさと納税で返礼品を探す",
  },
  "defense-tax:aupay-furusato": {
    headline: "所得税を確かめたら、今年のふるさと納税も",
    line: "上限の中の寄附なら、自己負担2,000円を除いて所得税と住民税から控除されます。",
    cta: "au PAY ふるさと納税で返礼品を探す",
  },
  // エルピオでんき: 切り替え手数料0円・解約手数料0円（ad_benefits.json elpio。公式 11/10 確認）
  "denki-gas-discount:elpio": {
    headline: "値引きが終わったあとの電気代も、今のうちに比べる",
    line: "エルピオでんきは、切り替えの手数料も解約の手数料も0円です。",
    cta: "エルピオでんきの料金プランを見る",
  },
  // エネピ: 見積もりから切り替えまで費用は無料・手続きはエネピが行う（ad_benefits.json enepi。登録が必要）
  "denki-gas-discount:enepi": {
    headline: "値引きが終わったあとの電気・ガス代も、今のうちに比べる",
    line: "見積もりから切り替えの手続きまで無料で任せられます（登録が必要）。",
    cta: "エネピで料金の見直しを相談する",
  },
  // 医療費控除は確定申告で受ける（国税庁。ページの本文と同じ）。freee: 無料お試しはクレジットカード登録不要（offers.json pitch.merits）
  "kogaku-ryoyohi:freee": {
    headline: "医療費が多かった年は、確定申告で医療費控除",
    line: "freee会計は、クレジットカードを登録せずに無料で試せます。",
    cta: "freee会計の料金プランを見る",
  },
  // マネーフォワード: 1か月の無料お試し・カード登録なし（ad_benefits.json mf-kakutei。公式 11/11 確認）
  "kogaku-ryoyohi:mf-kakutei": {
    headline: "医療費が多かった年は、確定申告で医療費控除",
    line: "マネーフォワード クラウド確定申告は、カード登録なしで1か月無料で試せます。",
    cta: "マネーフォワードの無料お試しを見る",
  },
  // 弥生: 税務署に行かずe-Taxで申告できる（offers.json pitch.merits）
  "kogaku-ryoyohi:yayoi-kakutei": {
    headline: "医療費が多かった年は、確定申告で医療費控除",
    line: "弥生のクラウド確定申告ソフトなら、税務署に行かずにe-Taxで申告できます。",
    cta: "弥生の料金と無料期間を見る",
  },
};

/** 計算ツールを指定していないページ（受け取るまでの流れを足している3つのページ）は、話題（ad.key）から決める */
const TOOL_BY_RULE: Record<string, ToolKind> = {
  kids: "child-allowance",
  childbirth: "ikukyu-kyufu",
  mobile: "pension-support-benefit",
  energy: "denki-gas-discount",
  medical: "kogaku-ryoyohi",
};

export function toolKindFor(tool: ToolKind | undefined, ruleKey: string): ToolKind | undefined {
  return tool ?? TOOL_BY_RULE[ruleKey];
}

const short = (name: string) => name.replace(/[（(][^）)]*[）)]/g, "").trim();

/** B の見出し・1行・ボタン。決めた文が無ければ商品の公式の言葉から作る（無ければ undefined で B を出さない） */
export function toolAdCopy(tool: ToolKind | undefined, item: OfferItem): ToolAdCopy | undefined {
  const fixed = tool ? COPY[`${tool}:${item.key}`] : undefined;
  if (fixed) return fixed;
  const headline = item.pitch?.gain ?? item.benefit?.headline;
  const line = item.pitch?.merits?.[0] ?? item.pitch?.point ?? item.note;
  if (!headline || !line) return undefined;
  const verb = item.pitch?.cta ?? (item.cta === "公式サイトで見る" ? "料金と条件を見る" : item.cta);
  return { headline, line: /[。．]$/.test(line) ? line : `${line}。`, cta: `${short(item.name)}で${verb}` };
}

/** テスト用: 決めた文の一覧 */
export const TOOL_AD_COPY = COPY;
