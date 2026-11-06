import data from "@/content/topic_lists.json";
import { getArticleSummary } from "@/lib/articles";
import { companyOf, OTHER } from "@/lib/companies";
import { displayHeadline, gateHeadline } from "@/lib/headline";

/**
 * 横断の一覧ページ（/roundups/<kind>。2026-11-07 オーナー「旬の情報をまとめてあげたり」・台帳 A52）。
 * 中身は scripts/topic_lists.py が公開中の記事から規則で作る content/topic_lists.json（LLM なし）。
 * 横断まとめ記事（記事の type "roundup"・lib/articles.ts の getRoundups）とは別もの。
 */
export type TopicKind = "price-hikes" | "outages" | "recalls" | "service-changes";

export type TopicEntry = {
  slug: string;
  /** この記事を載せた時刻（JST の ISO） */
  at: string;
  /** YYYY-MM（JST） */
  month: string;
  /** 公式の発表日（YYYY-MM-DD） */
  announced: string | null;
  title: string;
  /** 値上げ／値下げ／改定・障害／復旧・回収・注意・終了／提供開始 */
  change: string;
  /** 何が変わるか（記事のリードの1文目） */
  what: string;
  /** いつから・いつまで（記事にある言い方のまま） */
  effective: string | null;
  sourceName: string;
  sourceUrl: string;
};

export type TopicEntryView = TopicEntry & { company: string };

type Meta = {
  kind: TopicKind;
  label: string;
  /** 一覧の見出し（h1） */
  heading: string;
  /** 今週の件数を入れた題名（A50: 読む人が得るものを先に・件数を入れる・「〜とは？」にしない） */
  title: (week: number) => string;
  description: string;
  intro: string;
};

export const TOPIC_LISTS: Meta[] = [
  {
    kind: "price-hikes",
    label: "値上げ・料金改定",
    heading: "値上げ・料金改定の一覧",
    title: (n) => (n > 0 ? `今週の値上げ・料金改定${n}件　いつから・何が変わるかの一覧` : "値上げ・料金改定の一覧　いつから・何が変わるか"),
    description: "電気・ガス・食品・通信・サービスの値上げと料金改定を、公式の発表をもとに新しい順に並べています。いつからか・何が変わるかと公式の発表へのリンク付き。記事ができるたびに自動で更新。",
    intro: "電気・ガス・食品・通信・サービスの値上げ・値下げ・料金の改定を、公式の発表を確かめた記事から新しい順に並べています。",
  },
  {
    kind: "outages",
    label: "障害・復旧",
    heading: "通信・決済・交通の障害と復旧の一覧",
    title: (n) => (n > 0 ? `通信・決済・交通の障害と復旧　今週${n}件の一覧` : "通信・決済・交通・クラウドの障害と復旧の一覧"),
    description: "携帯電話・決済・鉄道・クラウドなどの障害と復旧を、各社の公式の発表をもとに新しい順に並べています。公式の発表へのリンク付き。記事ができるたびに自動で更新。",
    intro: "通信・決済・交通・クラウドの障害と復旧を、各社の公式の発表を確かめた記事から新しい順に並べています。",
  },
  {
    kind: "recalls",
    label: "リコール・回収",
    heading: "リコール・回収の一覧（製品・医薬品）",
    title: (n) => (n > 0 ? `リコール・回収の対象製品　今週${n}件の一覧（車・家電・医薬品など）` : "リコール・回収の対象製品の一覧（車・家電・医薬品など）"),
    description: "車・タイヤ・家電・日用品・医薬品のリコールと回収を、国土交通省・消費者庁・各社の公式の発表をもとに新しい順に並べています。公式の発表へのリンク付き。",
    intro: "車・家電・日用品・医薬品のリコールと回収を、公式の発表を確かめた記事から新しい順に並べています。持っている製品が対象か、記事と公式の発表で確かめてください。",
  },
  {
    kind: "service-changes",
    label: "サービス終了・提供開始",
    heading: "終わるサービス・日本で始まるサービスの一覧",
    title: (n) => (n > 0 ? `終わるサービス・日本で始まるサービス　今週${n}件の一覧` : "終わるサービス・日本で始まるサービスの一覧"),
    description: "サービス・サポートの終了と、日本での提供開始を、各社の公式の発表をもとに新しい順に並べています。いつからか・公式の発表へのリンク付き。記事ができるたびに自動で更新。",
    intro: "サービス・サポートの終了と、日本で使えるようになったサービスを、公式の発表を確かめた記事から新しい順に並べています。",
  },
];

/** 一覧の表示の期間（固定 URL のページ） */
export const RECENT_DAYS = 31;
/** これより少ない一覧は検索に出さない（薄いページにしない） */
export const MIN_INDEX_ENTRIES = 3;

const raw = data as unknown as { generatedAt: string; lists: Record<string, TopicEntry[]> };

export function topicMeta(kind: string): Meta | undefined {
  return TOPIC_LISTS.find((m) => m.kind === kind);
}

export function topicListsUpdatedAt(): string {
  return raw.generatedAt;
}

/** 表示用（今の記事の題名・会社。取り下げた記事は外す） */
function view(entry: TopicEntry): TopicEntryView | null {
  const article = getArticleSummary(entry.slug);
  if (!article) return null;
  const company = companyOf(article);
  return {
    ...entry,
    title: displayHeadline(gateHeadline(article.title, article.title)),
    company: company.slug === OTHER.slug ? entry.sourceName.replace(/（[^）]*）$/, "") : company.name,
  };
}

export function allEntries(kind: TopicKind): TopicEntryView[] {
  return (raw.lists?.[kind] ?? []).map(view).filter((e): e is TopicEntryView => e !== null);
}

function since(days: number, now = Date.now()): number {
  return now - days * 86_400_000;
}

/** 固定 URL のページに出す分（直近 RECENT_DAYS 日・新しい順） */
export function recentEntries(kind: TopicKind, now = Date.now()): TopicEntryView[] {
  const from = since(RECENT_DAYS, now);
  return allEntries(kind).filter((e) => Date.parse(e.at) >= from);
}

/** 今週（直近7日）の件数 */
export function weekCount(kind: TopicKind, now = Date.now()): number {
  const from = since(7, now);
  return allEntries(kind).filter((e) => Date.parse(e.at) >= from).length;
}

function monthOf(now = Date.now()): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit" }).format(now).slice(0, 7);
}

/** 月ごとの一覧（アーカイブ）。終わった月だけ（今月は固定 URL のページに出る） */
export function archiveMonths(kind: TopicKind, now = Date.now()): string[] {
  const current = monthOf(now);
  return [...new Set(allEntries(kind).map((e) => e.month))].filter((m) => m < current).sort().reverse();
}

export function monthEntries(kind: TopicKind, month: string): TopicEntryView[] {
  return allEntries(kind).filter((e) => e.month === month);
}

export function monthLabel(month: string): string {
  const [y, m] = month.split("-");
  return `${y}年${Number(m)}月`;
}

/** この記事が載っている一覧（記事のページの「この一覧に載っています」） */
export function listsForArticle(slug: string): Meta[] {
  return TOPIC_LISTS.filter((m) => (raw.lists?.[m.kind] ?? []).some((e) => e.slug === slug));
}
