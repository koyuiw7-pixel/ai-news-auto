import data from "@/content/channel_labels.json";

/**
 * 発信元ページ（/channels/<slug>）の名前の表（SEO A11・2026-11-10）。中身は content/channel_labels.json。
 * これまでは新しい記事の発信元名（「厚生労働省「後期高齢者医療制度の…」（2026年4月10日公表）」のような資料名）を
 * ページの名前にしていた。組織の名前をここで決め、h1・題名・パンくず・足元の「情報源」に使う。
 */
const LABELS: Record<string, string> = data.labels;
const ALIASES: Record<string, string> = data.aliases;

/** 同じ組織の別の slug をまとめる（mhlw → mhlw-go-jp だけ） */
export function canonicalChannel(slug: string): string {
  return ALIASES[slug] ?? slug;
}

/** 表にある組織の名前（無ければ undefined） */
export function channelTableLabel(slug: string): string | undefined {
  return LABELS[canonicalChannel(slug)];
}

/** 表に名前がある発信元か（検索に出してよい発信元ページの条件の1つ） */
export function hasChannelLabel(slug: string): boolean {
  return Boolean(channelTableLabel(slug));
}

/** 画面に出す発信元の名前（表 → 記事の発信元名の順） */
export function channelName(slug: string, fallback: string): string {
  return channelTableLabel(slug) ?? fallback;
}
