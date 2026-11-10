import type { OfferItem } from "@/lib/offers";
import type { BenefitSource } from "@/lib/ad-benefits";

/**
 * 広告の「得のカード」の A/B（2026-11-11。台帳 W41）。デザインの元: out/strategy_20261110/design_round_ad/ad_directions.html
 *   arm "2" = 「比べて選ぶ」（基準）: 払うお金と得られるものを2本の棒（数字が1つしかない広告は数字を横に並べる）
 *   arm "1" = 「結果を先に見せる」（挑戦）: 読者に当てはまる結果を1つの大きな言い回しで
 * 2026-11-11 オーナー（スマホで見て）: 表示は「PR」の札だけ／スマホ 390px で高さ 260px ほどまで／数字と単位は同じ書体で単位を少し小さく／
 * 「所得割」「税率」のような言葉を使わない。総務省の「全額控除されるふるさと納税額（年間上限）の目安」の表の値をそのまま使い、出典と確認日を書く。
 * 順番: 誰の話か（平易な1行）→ 大きな結果 → ボタン1つ → 小さなリンクの1行 → 小さな出典。
 * 数字の無い広告（chips が空）は A/B に入れず、今までのカード（components/rail/parts.tsx の PrFeature）のまま。
 * 訪問者ごとの arm は app/layout.tsx の最初のスクリプトが <html data-abc="1|2"> に決める（?ab=1 / ?ab=2 で確認用に固定）。
 * 両方の arm を HTML に入れ、CSS で片方だけ見せる（描画前に決まるので画面がずれない。app/globals.css の .abx）
 */

export type AbArm = "1" | "2";
export const AB_ARMS: AbArm[] = ["1", "2"];

export type AbNumber = { pre?: string; num: string; unit?: string };
export type AbBar = { label: string; value: string; ratio: number; accent?: boolean };
export type AbChip = { label: string; value: string };

export type AbCard = {
  kind: "furusato" | "mf" | "generic";
  /** 誰の話か（平易な1行） */
  who: string;
  /** arm 1: 大きな結果（数字＋単位）と、続く言い回し */
  result: { number: AbNumber; after?: string; line?: string; line2?: string };
  /** arm 2: 比べる2本の棒、または横に並べる数字 */
  compare: { lead?: string; bars?: AbBar[]; chips?: AbChip[] };
  /** ボタン（行き先の名前が入る） */
  cta: string;
  /** サイト内の案内（ふるさと納税は「自分の年収で調べる」） */
  tool?: { href: string; label: string };
  /** 小さな出典・条件の1〜2行（arm ごと） */
  note: { arm1: string; arm2: string };
  sources: BenefitSource[];
};

/**
 * 総務省「全額（※）控除されるふるさと納税額（年間上限）の目安」（※2,000円を除く。令和2年以降に行うふるさと納税の目安。給与収入のみ・住宅ローン控除等なし・社会保険料は給与収入の15%と仮定）。
 * 元の PDF（https://www.soumu.go.jp/main_content/000408217.pdf）は 2026-11-11 時点で総務省のサイトから外れているので、同じファイルの保存版を出典にする。
 * 年収500万円の行。「共働き」は本人が配偶者（特別）控除を受けていない場合、中学生以下の子は計算に入らない（表の注）
 */
export const SOUMU_TABLE: BenefitSource = {
  name: "総務省「全額控除されるふるさと納税額（年間上限）の目安」",
  url: "https://web.archive.org/web/2024/https://www.soumu.go.jp/main_content/000408217.pdf",
  checkedAt: "2026-11-11",
};
export const SOUMU_500: { income: number; single: number; couple: number } = { income: 5_000_000, single: 61_000, couple: 49_000 };

export const MF_PRICE: BenefitSource = { name: "マネーフォワード クラウド確定申告の料金プラン", url: "https://biz.moneyforward.com/tax_return/price/", checkedAt: "2026-11-11" };
export const NTA_2072: BenefitSource = { name: "国税庁 No.2072 青色申告特別控除", url: "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2072.htm", checkedAt: "2026-11-11" };
/** マネーフォワード: パーソナルミニの年払い 10,800円（税抜）＝ 11,880円（税込）。2026年12月に料金体系の一部改定を予定（公式） */
export const MF_YEAR_TAXED = 11_880;
/** 65万円の控除 ×（所得税10%×1.021＋住民税10%）。所得税率10%の人の例 */
export const BLUE_65_SAVING = Math.round(650_000 * (0.1 * 1.021 + 0.1));

const FURUSATO = new Set(["rakuten-furusato", "aupay-furusato", "furusato-honpo"]);

const man = (yen: number) => (Math.floor(yen / 1000) / 10).toFixed(1).replace(/\.0$/, "");
const comma = (yen: number) => yen.toLocaleString("ja-JP");

/** 「（エブリィフレシャス）」のような括弧を外した短い名前（ボタンの言葉に使う） */
export function shortName(name: string): string {
  return name.replace(/[（(][^）)]*[）)]/g, "").trim();
}

/** 「月495円〜」→ { pre: "月", num: "495", unit: "円〜" }。数字の無い値（「受け取り不要」）は num だけ */
export function splitNumber(value: string): AbNumber {
  const m = /^(\D*?)([\d][\d,.]*)(.*)$/.exec(value);
  if (!m) return { num: value };
  return { pre: m[1] || undefined, num: m[2], unit: m[3] || undefined };
}

function sourceLine(sources: BenefitSource[]): string {
  return sources.map((s) => `${s.name}（${Number(s.checkedAt.slice(5, 7))}/${Number(s.checkedAt.slice(8, 10))}確認）`).join("／");
}

/** この商品の A/B のカード。数字（chips）が無い商品は undefined（今までのカードのまま） */
export function abCardFor(item: OfferItem): AbCard | undefined {
  const benefit = item.benefit;
  if (item.kind !== "partner" || !benefit || benefit.chips.length === 0) return undefined;
  const name = shortName(item.name);

  if (FURUSATO.has(item.key)) {
    const kids = /子育て|子ども|子供|児童|保育|教育/.test(benefit.headline ?? "");
    const limit = SOUMU_500.single;
    // 表の注: 中学生以下の子は計算に入らない（「共働き＋子（中学生以下）」は「共働き」と同じ額）
    const who = kids ? "年収500万円・共働き・子どもは中学生まで" : "年収500万円・独身か共働きの方";
    return {
      kind: "furusato",
      who,
      result: { number: { pre: "約", num: man(limit), unit: "万円" }, after: "まで寄付して、負担は2,000円" },
      compare: {
        bars: [
          { label: `約${man(limit)}万円の寄付で、自分の負担`, value: "2,000円", ratio: 2000 / limit },
          { label: "税金が減る分（所得税と翌年の住民税）", value: `約${man(limit - 2000)}万円`, ratio: 1, accent: true },
        ],
      },
      cta: `${name}で返礼品を探す`,
      tool: { href: "/tools/furusato-limit", label: "自分の年収で調べる" },
      note: {
        arm1: `給与のみ・住宅ローン控除なしの目安。出典：${sourceLine([SOUMU_TABLE])}`,
        arm2: `給与のみ・住宅ローン控除なしの目安。出典：${sourceLine([SOUMU_TABLE])}`,
      },
      sources: [SOUMU_TABLE],
    };
  }

  if (item.key === "mf-kakutei") {
    return {
      kind: "mf",
      who: "副業や個人事業で確定申告をする方",
      result: { number: { num: "1", unit: "か月" }, after: "無料で試せる", line2: `カード登録なし。その後は年${comma(MF_YEAR_TAXED)}円（税込）から` },
      compare: {
        bars: [
          { label: "ソフト代（1年）", value: `${comma(MF_YEAR_TAXED)}円`, ratio: MF_YEAR_TAXED / BLUE_65_SAVING },
          { label: "帳簿をつけて申告すると減る税金の例", value: `約${man(BLUE_65_SAVING)}万円`, ratio: 1, accent: true },
        ],
      },
      cta: "マネーフォワードの料金と無料お試しを見る",
      note: {
        arm1: `12月に料金改定予定（公式）。出典：${sourceLine([MF_PRICE])}`,
        arm2: `青色申告の65万円控除（e-Tax・複式簿記が条件）、所得税率10%の例。料金は12月改定予定。出典：国税庁 No.2072・マネーフォワード公式（11/11確認）`,
      },
      sources: [MF_PRICE, NTA_2072],
    };
  }

  const [first, ...more] = benefit.chips;
  const who = benefit.headline ?? item.pitch?.gain ?? item.label ?? name;
  const subs = (chips: typeof benefit.chips) => chips.map((c) => (c.sub ? `${c.label}は${c.sub}` : "")).filter(Boolean).join("・");
  const bars = benefit.compare && benefit.compare.rows.length >= 2
    ? (() => {
        const max = Math.max(1, ...benefit.compare!.rows.map((r) => r.value));
        return benefit.compare!.rows.slice(0, 2).map((r, i) => ({ label: r.name, value: r.text, ratio: Math.max(0.04, r.value / max), accent: i === 1 }));
      })()
    : undefined;
  return {
    kind: "generic",
    who,
    result: { number: splitNumber(first.value), line: first.label, after: more[0] ? `${more[0].label} ${more[0].value}` : undefined },
    compare: bars ? { lead: benefit.compare!.label, bars } : { chips: benefit.chips.slice(0, 3).map((c) => ({ label: c.label, value: c.value })) },
    cta: `${name}で${item.pitch?.cta ?? (item.cta === "公式サイトで見る" ? "料金と条件を見る" : item.cta)}`,
    note: {
      arm1: [subs([first, ...more.slice(0, 1)]), `出典：${sourceLine(benefit.sources.filter((s) => !s.url.startsWith("/")))}`].filter(Boolean).join("。"),
      arm2: [subs(benefit.chips.slice(0, 3).filter((c) => /税込|税抜/.test(c.sub ?? ""))), `出典：${sourceLine(benefit.sources.filter((s) => !s.url.startsWith("/")))}`].filter(Boolean).join("。"),
    },
    sources: benefit.sources,
  };
}
