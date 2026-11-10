import { getAllGenres } from "@/lib/articles";
import { broadSection } from "@/lib/sections";

export type NavItem = { href: string; label: string };

/**
 * ジャンルのタブの並び（読者像の順。AGENTS.md「0. 読者」・docs/persona-20261102.md）。
 * 速報 → 税・制度（社会・行政）→ 暮らし → 仕事とお金（ビジネス・投資・不動産）→ AI → ガジェット → スポーツ → エンタメ。
 * 軸は「暮らしとお金の自分ごとニュース」で、AI は脇役（2026-11-08 のオーナー方針）。読まれているのも年金・手当・流出の記事なので、その順に並べる。
 * 「起業・副業」はジャンルのページが無い（記事も数本だけ）ので、ページができたらここに足す。
 * 科学・宇宙は読者像の外なので、タブには出さず /news の切り替えから辿る。
 */
export const GENRE_NAV_ORDER = [
  "public",
  "lifestyle",
  "business",
  "investment",
  "real-estate",
  "ai",
  "tech-gadget",
  "sports",
  "entertainment",
] as const;

/** ジャンル名。ジャンルのページ（/genres/<slug>）の見出しと同じ名前（記事の genre を優先し、無ければ幅広い話題の静的な名前） */
export function genreLabel(slug: string): string {
  return getAllGenres().find((g) => g.slug === slug)?.label ?? broadSection(slug)?.label ?? slug;
}

/** ヘッダーのジャンルのタブ。先頭は全ジャンルの新着（速報）。記事の無いジャンルはページが 404 になるので出さない */
export function genreNav(): NavItem[] {
  const live = new Set(getAllGenres().map((g) => g.slug));
  return [
    { href: "/articles", label: "速報" },
    ...GENRE_NAV_ORDER.filter((slug) => live.has(slug)).map((slug) => ({ href: `/genres/${slug}`, label: genreLabel(slug) })),
  ];
}

/**
 * 暮らしとお金の入口（PC は帯の右、スマホはジャンルのタブの先頭。2026-11-11 読者目線レビュー 14位）。
 * 以前は「使い方ガイド・AI料金表・AIサービス図鑑・値上げ・障害一覧」で、年金や児童手当の投稿から来た人に AI のサイトに見えていた。
 * 行き先は実在するページだけ（タグのページ・値上げの一覧・選び方と計算の一覧）。AI の定番ページはフッターから辿れる
 */
export const MONEY_NAV: NavItem[] = [
  { href: `/tags/${encodeURIComponent("年金")}`, label: "年金・給付金" },
  { href: `/tags/${encodeURIComponent("子育て支援")}`, label: "子育て" },
  { href: `/tags/${encodeURIComponent("税金")}`, label: "税金・年末調整" },
  { href: "/roundups/price-hikes", label: "電気・ガス・値上げ" },
  { href: "/choose", label: "比較・計算" },
];

/** PC の帯の右に出す定番ページ（今は暮らしとお金の入口） */
export const UTILITY_NAV: NavItem[] = MONEY_NAV;
