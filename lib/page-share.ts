import type { Metadata } from "next";
import { siteConfig } from "@/site.config";

/**
 * 一覧・ツールなどの固定ページのシェア用の情報（og:title・og:description・og:image）。2026-11-03
 *
 * openGraph を書かないページは、レイアウトのトップページ用の og:title（「サイソクニュース AI・ビジネス・お金の…」）を
 * 引き継いでいた（/tools・/guides など）。ページごとの題名と、ページ名入りのシェア画像（app/og/[key]/route.tsx。
 * /news/share.png と同じ報道ネイビー×速報レッドの形）を出す。
 */
export type PageShare = {
  /** 画像の大きな見出し（短く。全角9字くらいまで） */
  heading: string;
  /** 見出しの下の2行 */
  lines: [string, string];
  /** 下の帯の1行 */
  footer: string;
};

export const PAGE_SHARE = {
  "defense-tax": { heading: "防衛特別所得税", lines: ["2027年から始まる新しい税", "自分の場合の税額を年ごとに計算"], footer: "サイソクの計算ツール" },
  "furusato-limit": { heading: "ふるさと納税の上限額", lines: ["住民税の所得割額と所得税の税率から", "自己負担2,000円で済む寄附額の目安を計算"], footer: "サイソクの計算ツール" },
  "ai-pricing": { heading: "AIの料金早見表", lines: ["ChatGPT・Claude・GeminiのAPIと月額プラン", "日本で使えるか・無料で試せるかも"], footer: "数字はすべて出典の記事で確認" },
  usable: { heading: "今すぐ使えるAI", lines: ["発表されたばかりの新機能・新モデルから", "今日から使えるものだけを毎日更新"], footer: "日本から使えるか・料金・無料かを判定" },
  guides: { heading: "手続きと使い方のガイド", lines: ["年末調整・確定申告からAIの料金まで", "公式の情報をもとに1ページで"], footer: "サイソクのガイド" },
  products: { heading: "AIサービス図鑑", lines: ["できること・料金・最新ニュース", "主なAIサービスを1か所で"], footer: "サイソクのガイド" },
  compare: { heading: "比較ガイド", lines: ["AI時代の道具を、公式情報で比べる", "料金・できること・向いている人"], footer: "サイソクのガイド" },
  digest: { heading: "朝のAIニュース", lines: ["毎朝7時30分に、昨夜から今朝までの", "AIニュースを3本だけ"], footer: "最速で、要点だけ。" },
  weekly: { heading: "今週のAIニュース", lines: ["1週間の大きな発表を、まとめて", "仕事・お金にどう関係するかまで"], footer: "最速で、要点だけ。" },
  newsletter: { heading: "メール配信", lines: ["毎朝7時に、前日のAIニュースから5本", "1本2行の要点とリンクで。無料"], footer: "いつでも解除できます" },
  about: { heading: "運営者情報", lines: ["サイソクニュースの運営者と", "記事の作り方・編集方針"], footer: "公式発表から最短数分で" },
  "editorial-policy": { heading: "編集方針", lines: ["記事の作り方・AIの使い方", "事実の確かめ方・訂正のしかた"], footer: "サイソクニュースの約束" },
  corrections: { heading: "訂正履歴", lines: ["公開後に訂正した記事の一覧", "いつ・何を直したかを公開"], footer: "サイソクニュースの約束" },
  // 2026-11-10（SEO A15）: トップ・一覧・発信元などのページも、ページ名入りのシェア画像を出す
  home: { heading: "サイソクニュース", lines: ["暮らしとお金の新しい動きを、公式発表から最速で", "自分は対象か・いくらか・何をすればいいか"], footer: "最速で、要点だけ。" },
  articles: { heading: "新着の記事", lines: ["公式発表から最短数分で記事に", "値段・手続き・給付・税の新しい動き"], footer: "最速で、要点だけ。" },
  events: { heading: "イベントの日程", lines: ["AI・テックの大きな発表会を日本時間で", "基調講演の時刻と発表の要点"], footer: "サイソクの行事ガイド" },
  choose: { heading: "選び方ガイド", lines: ["格安SIM・光回線・電気・保険の窓口など", "公式の情報で比べて選ぶ"], footer: "サイソクのガイド" },
  people: { heading: "人物のまとめ", lines: ["発表の場に立つ人の経歴と", "その人に関するニュース"], footer: "公式の発表で確かめた経歴" },
  dates: { heading: "暮らしとお金の日程", lines: ["年金・手当・ボーナス・税の期限", "いつ・いくらを公式の発表で確かめて"], footer: "サイソクの日程ガイド" },
  roundups: { heading: "値上げ・障害・リコールの一覧", lines: ["暮らしに関わる発表を種類ごとに", "公式の発表をもとに毎日更新"], footer: "サイソクの一覧" },
  hub: { heading: "サイソクニュース", lines: ["発表元・話題・ジャンルごとの最新ニュース", "公式発表をもとに要点3つで"], footer: "最速で、要点だけ。" },
} satisfies Record<string, PageShare>;

export type PageShareKey = keyof typeof PAGE_SHARE;

export const PAGE_SHARE_KEYS = Object.keys(PAGE_SHARE) as PageShareKey[];

/** シェア画像の URL（1200×630） */
export const pageShareImage = (key: PageShareKey) => `/og/${key}`;

/** ページの openGraph・twitter（題名・説明・URL・シェア画像） */
export function pageShareMetadata(
  key: PageShareKey,
  { title, description, url }: { title: string; description: string; url: string },
): Pick<Metadata, "openGraph" | "twitter"> {
  const image = { url: pageShareImage(key), width: 1200, height: 630, alt: title };
  return {
    openGraph: { type: "website", siteName: siteConfig.siteName, locale: siteConfig.locale, url, title, description, images: [image] },
    twitter: { card: "summary_large_image", title, description, images: [image.url] },
  };
}

/** 固定ページの metadata に openGraph・twitter（ページの題名・説明・シェア画像）を足す。ogTitle を省くと title を使う */
export function withPageShare(
  key: PageShareKey,
  url: string,
  meta: Metadata & { title: string; description: string },
  ogTitle?: string,
): Metadata {
  return { ...meta, ...pageShareMetadata(key, { title: ogTitle ?? meta.title, description: meta.description, url }) };
}
