import thirdChild from "@/content/flagship/third-child-1000man.json";

/**
 * 特集（/stories/<slug>）。1本＝事実の JSON（content/flagship/<slug>.json）＋計算の lib（lib/child-allowance.ts など）。
 * 2026-11-28 オーナー「近未来的な世界最高峰の見た目、機能」の記事の型。新しい特集は JSON を1つ足し、下の FLAGSHIP_STORIES に並べ、
 * 計算の部品（components/flagship/calculators.tsx の CALCULATOR_VIEWS）を選ぶだけで作れる。
 * 決まり（tests/test_flagship_20261128.cjs）:
 *  - 書く事実はすべて出典（sources の id）につなぐ。公式を先、報道を後に並べ、確かめた日を書く
 *  - 決まっていないことは「決まっていない」と書き、金額を作らない（数字は計算の lib か出典にあるものだけ）
 *  - 読者の文に「｜」「**」「→」「ざっくり」「〜の人へ」を使わない。広告の枠は1ページに1つ（pos は FLAGSHIP_AD_POS）
 */
export type SourceKind = "official" | "report";
export type FlagshipSource = { id: string; kind: SourceKind; org: string; title: string; url: string; checked: string };
export type Sourced = { sources: string[] };
export type StatusItem = Sourced & { label: string; detail: string };
export type WatchItem = Sourced & { when: string; what: string; detail: string };
export type ChecklistItem = Sourced & { id: string; title: string; deadline: string; detail: string; birthDeadline?: boolean };
export type NextLink = { href: string; label: string; why: string; when: "always" | "newborn" };
export type FlagshipCalculator = "child-allowance";

export type FlagshipStory = {
  slug: string;
  title: string;
  description: string;
  kicker: string;
  genre: { label: string; href: string };
  publishedAt: string;
  updatedAt: string;
  /** 本文の数字・状況が「いつ時点」か（YYYY-MM-DD） */
  asOf: string;
  keywords: string[];
  answer: Sourced & { lead: string; sub: string };
  status: { decided: StatusItem[]; undecided: StatusItem[] };
  calculator: FlagshipCalculator;
  proposal: {
    title: string;
    badge: string;
    lead: string;
    known: (Sourced & { text: string })[];
    watch: WatchItem[];
    /** {max} に計算の結果が入る */
    insight: string;
    insightBirth: { year: number; month: number };
    insightSources: string[];
  };
  checklist: ChecklistItem[];
  faq: { q: string; a: string }[];
  next: NextLink[];
  /** 広告の話題（content/offers.json の actionAds の key。lib/guide-ads.ts の toolAd）と、見た目 B の文の計算ツール */
  ad: { rule: string; tool: string };
  /** この特集へリンクする記事（記事の要点のすぐ下に案内を出す） */
  article: string;
  /** この特集へリンクする計算ツール */
  tool: string;
  share: { heading: string; lines: [string, string]; footer: string };
  sources: FlagshipSource[];
};

export { FLAGSHIP_AD_POS } from "@/lib/flagship-pos";

export const FLAGSHIP_STORIES: FlagshipStory[] = [thirdChild as FlagshipStory];

export const flagshipHref = (slug: string) => `/stories/${slug}`;

export function getFlagship(slug: string): FlagshipStory | undefined {
  return FLAGSHIP_STORIES.find((story) => story.slug === slug);
}

/** 記事の slug → その記事から案内する特集 */
export function flagshipForArticle(articleSlug: string): { href: string; title: string } | undefined {
  const story = FLAGSHIP_STORIES.find((s) => s.article === articleSlug);
  return story ? { href: flagshipHref(story.slug), title: story.title } : undefined;
}

/** 計算ツールの URL → その計算を使う特集 */
export function flagshipForTool(toolHref: string): { href: string; title: string } | undefined {
  const story = FLAGSHIP_STORIES.find((s) => s.tool === toolHref);
  return story ? { href: flagshipHref(story.slug), title: story.title } : undefined;
}

/** 出典を公式→報道の順に（同じ種類の中は JSON の順） */
export function orderedSources(story: FlagshipStory): FlagshipSource[] {
  return [...story.sources.filter((s) => s.kind === "official"), ...story.sources.filter((s) => s.kind === "report")];
}

export { birthDeadline, dateJa } from "@/lib/flagship-date";
