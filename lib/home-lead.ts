import popular from "@/content/popular.json";
import type { ArticleSummary } from "@/lib/articles";
import { isNewsOutletChannel } from "@/lib/news-outlets";
import { containPhoto } from "@/lib/photo-fit";
import { lifeLink, trendTopic } from "@/lib/indexing";
import { topicCluster } from "@/lib/related";
import { noReaderAction } from "@/lib/reader-urgency";

/**
 * トップ（玄関）の主役と「暮らしとお金」の列を選ぶ（2026-11-10 オーナー）。
 *
 * サイトの軸は「暮らしとお金の『自分ごと』ニュース」で、AI は脇役（台帳 A61）。
 * トップの主役が AI の企業向けの話（Northern Trust と Microsoft）で、しかも写真が無く文字だけの代わりの図版になっていた。
 *  - 主役は暮らし・お金の分野の記事から、実際に読まれている（content/popular.json。自前の計測で今日と昨日に外から読まれた回数）記事と、
 *    新しい記事を合わせた点数で選ぶ。暮らし・お金の速報（breaking）は新しいうちは先に出す
 *  - 主役・大きな写真の枠には、本物の写真か、話題とのつながりを確かめた AI のイメージ（札つき）がある記事だけを置く（photoOf）。
 *    文字の多いバナー・図、縦長・正方形の写真は主役にしない（16:9 の大きな枠で切り抜くと文字・主役が切れる。lib/photo-fit.ts）
 *  - 主役は公式の発表から（報道・調査会社の記事を主役にしない。台帳 W17）
 * AI の速報はヘッダー下の帯と「AI・テクノロジーの新着」で見えるまま。
 */

/** 暮らしとお金の分野（components/noir/NoirPopular.tsx の CORE と同じ） */
export const LIFE_MONEY_GENRES = new Set(["public", "lifestyle", "investment", "business", "real-estate"]);

const H = 3_600_000;
/** 主役・暮らしとお金の列に入れる記事の新しさの上限（読まれた回数の集計が今日と昨日なので、それより少し長め） */
const WINDOW_H = 72;

const views: Map<string, number> = new Map(
  ((popular as { items?: { slug: string; views: number }[] }).items ?? []).map((item) => [item.slug, Number(item.views) || 0]),
);

/** 今日と昨日に外から読まれた回数（計測が無ければ 0） */
export function viewsOf(slug: string): number {
  return views.get(slug) ?? 0;
}

function ageHours(a: ArticleSummary, now: number): number {
  const t = Date.parse(a.generatedAt || a.publishedAt);
  return Number.isNaN(t) ? Infinity : (now - t) / H;
}

/** 読まれた回数を新しさで割り引き、新しい記事・新しい速報には点を足す */
export function homeScore(a: ArticleSummary, now: number): number {
  const age = ageHours(a, now);
  const decay = age < 12 ? 1 : age < 24 ? 0.7 : age < 48 ? 0.5 : 0.3;
  const fresh = age < 3 ? 12 : age < 6 ? 9 : age < 12 ? 5 : age < 24 ? 2 : 0;
  const breaking = a.breaking && age < 3 ? 40 : 0;
  return viewsOf(a.slug) * decay + fresh + breaking;
}

function listable(a: ArticleSummary, now: number): boolean {
  const age = ageHours(a, now);
  return a.type !== "roundup" && !a.duplicate && !a.duplicateOf && age >= 0 && age <= WINDOW_H;
}

/** 主役に置いてよいか: 暮らしとお金の分野・公式の発表・写真がある（文字の多いバナー・図ではない） */
export function heroEligible(a: ArticleSummary, now: number): boolean {
  return (
    LIFE_MONEY_GENRES.has(a.genreSlug) &&
    !noReaderAction(a.title) &&
    listable(a, now) &&
    !isNewsOutletChannel(a.channelSlug) &&
    Boolean(a.photo) &&
    !containPhoto(a.photo)
  );
}

const byScore = (now: number) => (x: ArticleSummary, y: ArticleSummary) =>
  homeScore(y, now) - homeScore(x, now) || Date.parse(y.generatedAt || y.publishedAt) - Date.parse(x.generatedAt || x.publishedAt);

/**
 * トップの主役。暮らしとお金の記事で写真のあるものから点数の高い順。
 * 無ければ（暮らしとお金の記事が無い日）写真のある新しい公式の記事、それも無ければいちばん新しい記事
 */
export function pickHomeLead(all: ArticleSummary[], now: number = Date.now()): ArticleSummary | undefined {
  const ranked = all.filter((a) => heroEligible(a, now)).sort(byScore(now));
  if (ranked[0]) return ranked[0];
  return (
    all.find((a) => listable(a, now) && !isNewsOutletChannel(a.channelSlug) && a.photo && !containPhoto(a.photo)) ??
    all.find((a) => a.type !== "roundup" && !a.duplicate) ??
    all[0]
  );
}

/**
 * 主役のすぐ下の「暮らしとお金」の列。写真のある記事だけ（代わりの図版をトップの写真の枠に並べない）。
 * 前半は読まれている順、後半は新しい順（読まれている記事だけで埋めず、新しい話も入口に出す）
 */
export function pickLifeMoney(all: ArticleSummary[], exclude: Set<string>, limit = 8, now: number = Date.now()): ArticleSummary[] {
  // 話題の記事（isTrendingFresh。2026-11-13）は、暮らしとお金の分野でなくても候補に入れる（紅白・スポーツなどの話題を分野で隠さない）
  const pool = all.filter((a) => (LIFE_MONEY_GENRES.has(a.genreSlug) || isTrendingFresh(a, now)) && !noReaderAction(a.title) && listable(a, now) && a.photo && !exclude.has(a.slug));
  const half = Math.ceil(limit / 2);
  const read = pool.filter((a) => viewsOf(a.slug) > 0).sort(byScore(now)).slice(0, half);
  const taken = new Set(read.map((a) => a.slug));
  const fresh = pool.filter((a) => !taken.has(a.slug)).slice(0, limit - read.length);
  return [...read, ...fresh];
}

/**
 * 暮らしとお金の「自分ごと」の記事か（トップの見出し・ヘッダー下の帯。2026-11-11 読者目線レビュー 1位・2位・11位）。
 * 暮らしとお金の分野で、題名がお金か暮らしにつながり（lib/indexing.ts の lifeLink。台帳 A61）、面会・式典・人事などの読者がすることの無い発表ではない
 */
export function isLifeMoneyStory(a: ArticleSummary): boolean {
  return LIFE_MONEY_GENRES.has(a.genreSlug) && lifeLink(a.title ?? "") && !noReaderAction(a.title);
}

/** 話題の記事として扱う新しさ（載せてからの時間） */
export const TRENDING_WINDOW_H = 24;
/** 見出しの欄のうち、暮らしとお金の決まりでは出ない話題の記事に取っておく数 */
export const TRENDING_SLOTS = 3;

/**
 * 話題の記事か（2026-11-13 オーナー「とにかく数字」「Googleからの流入対策」）。
 * 話題のレーンの記事（急上昇の言葉から作った記事。trendKeyword）か、Muse に頼んで書いた記事（writer: "muse"）で、載せて24時間以内。
 * うわさ・事件・訃報の題名（lib/indexing.ts の trendTopic）と、読者がすることの無い発表は除く。分野は問わない
 * （紅白の出場歌手の一覧のように、暮らしとお金の分野・題名の決まりに当たらない話題も、トップの上から必ずたどれるようにする）
 */
export function isTrendingFresh(a: ArticleSummary, now: number = Date.now()): boolean {
  const age = ageHours(a, now);
  if (!(age >= 0 && age <= TRENDING_WINDOW_H)) return false;
  if (a.type === "roundup" || a.duplicate || a.duplicateOf || noReaderAction(a.title)) return false;
  return trendTopic(a) || a.writer === "muse";
}

const newestFirst = (x: ArticleSummary, y: ArticleSummary) => Date.parse(y.generatedAt || y.publishedAt) - Date.parse(x.generatedAt || x.publishedAt);

/**
 * 暮らしとお金の決まり（isLifeMoneyStory）では見出しの欄に出ない話題の記事を、話題ごとに1本ずつ選ぶ。
 * 同じ話題を何本も書いた話（紅白の3本など。lib/related.ts の topicCluster）を先に、次に読まれている順 → 新しい順。
 * 同じ話題の中の代表は、読まれている記事 → 最初に載せた記事。
 * 同じ話題の残りの記事は、選んだ記事のページの「この話の続き」から結ぶ
 */
export function pickTrending(all: ArticleSummary[], exclude: Set<string>, limit = TRENDING_SLOTS, now: number = Date.now()): ArticleSummary[] {
  const pool = all.filter((a) => isTrendingFresh(a, now) && !isLifeMoneyStory(a) && !exclude.has(a.slug));
  if (pool.length === 0 || limit <= 0) return [];
  const siblings = new Map(pool.map((a) => [a.slug, topicCluster(a, all, 5).map((b) => b.slug)]));
  const ranked = [...pool].sort(
    (x, y) =>
      (siblings.get(y.slug)?.length ?? 0) - (siblings.get(x.slug)?.length ?? 0) || viewsOf(y.slug) - viewsOf(x.slug) || newestFirst(x, y),
  );
  const out: ArticleSummary[] = [];
  const covered = new Set<string>();
  for (const a of ranked) {
    if (out.length >= limit) break;
    if (covered.has(a.slug)) continue;
    // 同じ話題の中では、読まれている記事 → 最初に載せた記事（話題の元の記事。紅白なら出場歌手の一覧）を代表にする
    const group = [a, ...pool.filter((b) => (siblings.get(a.slug) ?? []).includes(b.slug) && !covered.has(b.slug))];
    const pick = group.sort((x, y) => viewsOf(y.slug) - viewsOf(x.slug) || newestFirst(y, x))[0];
    out.push(pick);
    covered.add(a.slug);
    for (const b of group) covered.add(b.slug);
    for (const slug of siblings.get(a.slug) ?? []) covered.add(slug);
  }
  return out;
}

/**
 * スマホの最初の画面に並べる、暮らしとお金の見出し（写真なし・文字だけ。Yahoo!ニュースの最初の画面は見出し6本）。
 * 写真の有無は問わない。前半は実際に読まれている順（content/popular.json の回数を新しさで割り引いた点数）、後半は新しい順。
 * 人が選ぶのではなく、分野・題名・読まれた回数で決める。
 * 2026-11-13: 話題の記事（isTrendingFresh）は分野・題名の決まりに当たらなくても候補に入れ、そのうち暮らしとお金の決まりでは出ない記事に
 * TRENDING_SLOTS 本ぶんの席を取っておく（pickTrending。席は limit の外に足す。話題の記事が無い日は今までどおり limit 本）
 */
export function pickHomeHeadlines(all: ArticleSummary[], exclude: Set<string>, limit = 6, now: number = Date.now()): ArticleSummary[] {
  const trending = pickTrending(all, exclude, TRENDING_SLOTS, now);
  const reserved = new Set(trending.map((a) => a.slug));
  const pool = all.filter((a) => isLifeMoneyStory(a) && listable(a, now) && !exclude.has(a.slug) && !reserved.has(a.slug));
  const half = Math.ceil(limit / 2);
  const read = pool.filter((a) => viewsOf(a.slug) > 0).sort(byScore(now)).slice(0, half);
  const taken = new Set(read.map((a) => a.slug));
  const fresh = pool
    .filter((a) => !taken.has(a.slug))
    .sort(newestFirst)
    .slice(0, limit - read.length);
  return [...read, ...fresh, ...trending];
}
