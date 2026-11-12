import type { ArticleSummary } from "@/lib/articles";
// 判定の材料（文字数・ジャンル・話題の正規表現）は scripts/indexnow.py --export-rules が書き出す。
// 正本は scripts/indexnow.py と scripts/persona.py（読者像）。ここに値を複製しない。
import rules from "./index-rules.json";
// 14日間訪問0の記事の一覧（2026-11-10 オーナー承認。正本は content/noindex_zero_visit.json。scripts/indexnow.py も同じファイルを読む）
import zeroVisit from "../content/noindex_zero_visit.json";
// 検索に出したままにする一覧ページ（2026-11-12 AdSense 監査。読まれた一覧は、記事が少なくても外さない）
import listGuard from "../content/list_pages_protected.json";

/**
 * Google に見せる記事を選ぶ（サイトでは全記事を読める。noindex でも一覧・内部リンクには残す）。
 * scripts/indexnow.py の is_indexable と同じ基準にしておくこと。
 *
 * 検索に出す条件（手動指定 indexable が最優先。まとめ記事は常に対象）:
 *  1. プレスリリース配信サービスではない。個人・他媒体の YouTube チャンネルの要約記事ではない（CREATOR_CHANNELS）
 *  2. 本文が THIN_BODY 文字以上（薄い要約を出さない）
 *  3. 読者像（scripts/persona.py）の話題: AI・テック（ジャンル ai / tech-gadget、または題名・タグにAI関連語）／
 *     ビジネス・投資・不動産のジャンル／制度・暮らし・テックのジャンルでお金・税・補助金・起業の話題（persona.is_persona_topic）／
 *     エンタメのビジネス・テックの目線（scripts/genre_focus.py: 料金・決算・販売本数・市場規模・AI・規約。告知・ゴシップは外す）／
 *     日本のスポーツ（persona.sports_scope。海外のリーグ・選手だけの話題は外す。世界的な大会は海外選手も可）／
 *     公共性の高い話題と、広げた暮らしの話題（scripts/public_interest.py の focus_topic・wide_category。台帳 A40・A56）
 *  4. 日本の読者向けの価値がある（「日本で使える？」判定 verdict、または
 *     「日本・無料・料金・使い方・始め方・使える」の見出し）
 *  5. 同じ発表の重複記事（duplicateOf。scripts/story.py が付ける）や、同じ題名・同じ出典URLの重複のうち代表1本以外ではない
 *
 * 重複記事は noindex にし、canonical を代表の記事に向ける（app/articles/[slug]/page.tsx の canonicalPathOf）。
 */

/** プレスリリースの配信サービス（量が多く、言い換えになりやすい） */
export const WIRE_SOURCES = new Set(["prtimes", "prtimes-all", "atpress", "value-press", "kyodo-prwire", "dreamnews"]);
/** 個人・他媒体の YouTube チャンネル（公式ではない）。他人の動画の要約記事は検索に出さない（正本は scripts/indexnow.py） */
export const CREATOR_CHANNELS = new Set<string>(rules.creatorChannels);
/** 本文の最低文字数（Markdown の本文の文字数） */
export const THIN_BODY: number = rules.thinBody;
/** いつでも主題として扱うジャンル（AI・テック） */
export const FOCUS_GENRES = new Set<string>(rules.focusGenres);
/** それ以外のジャンルでもAIの話題なら対象にする */
export const AI_TOPIC = new RegExp(rules.aiTopic.source, rules.aiTopic.flags);
/** 読者像のジャンル（persona.PERSONA_GENRES）と、お金・制度の話題なら対象にするジャンル（persona.PERSONA_EXTRA_GENRES） */
const PERSONA_GENRES = new Set<string>(rules.personaGenres);
const PERSONA_EXTRA_GENRES = new Set<string>(rules.personaExtraGenres);
const PRIORITY_TOPIC = new RegExp(rules.priorityTopic.source, rules.priorityTopic.flags);
const SPORTS_GENRES = new Set<string>(rules.sportsGenres);
/** エンタメはビジネス・テックの目線（料金・決算・販売本数・市場規模・AI・規約）だけ（scripts/genre_focus.py の entertainment_focus） */
const ENTERTAINMENT_GENRES = new Set<string>(rules.entertainmentGenres);
const ENTERTAINMENT_BUSINESS = new RegExp(rules.entertainmentBusiness.source, rules.entertainmentBusiness.flags);
const ENTERTAINMENT_EXCLUDE = new RegExp(rules.entertainmentExclude.source, rules.entertainmentExclude.flags);
/** ゲーム機・ゲームのサービスの公式の発表（genre_focus.official_game_news。台帳 A43） */
const GAME_OFFICIAL_SOURCES = new Set<string>(rules.gameOfficialSources);
const GAME_PLATFORM = new RegExp(rules.gamePlatform.source, rules.gamePlatform.flags);
const GAME_ANNOUNCE = new RegExp(rules.gameAnnounce.source, rules.gameAnnounce.flags);
const GAME_EXCLUDE = new RegExp(rules.gameExclude.source, rules.gameExclude.flags);
const GLOBAL_EVENT = new RegExp(rules.globalEvent.source, rules.globalEvent.flags);
const JAPAN_SPORTS = new RegExp(rules.japanSports.source, rules.japanSports.flags);
const FOREIGN_SPORTS = new RegExp(rules.foreignSports.source, rules.foreignSports.flags);
/** 公共性の高い話題（情報漏えい・ミサイル・災害・リコール・詐欺・暮らしのお金の変更。scripts/public_interest.py・台帳 A40） */
const PUBLIC_INTEREST_GENRES = new Set<string>(rules.publicInterestGenres);
const PUBLIC_INTEREST_TOPIC = new RegExp(rules.publicInterestTopic.source, rules.publicInterestTopic.flags);

const PUBLIC_INTEREST_SHORT_TOPIC = new RegExp(rules.publicInterestShortTopic.source, rules.publicInterestShortTopic.flags);
const SHORT_NOTICE_TOPIC = new RegExp(rules.shortNoticeTopic.source, rules.shortNoticeTopic.flags);
/** 速報・お知らせ・注意喚起・ミサイル・災害の記事の本文の下限（公式の発表が短いため。public_interest.SHORT_BODY。台帳 A10） */
const THIN_BODY_PUBLIC_INTEREST: number = rules.thinBodyPublicInterest;

/** public_interest.short_ok と同じ */
export function isShortArticle(article: Pick<ArticleSummary, "breaking" | "newsType" | "title" | "seoTitle" | "genreSlug">): boolean {
  if (article.breaking === true || article.newsType === "breaking") return true;
  const head = `${article.title ?? ""} ${article.seoTitle ?? ""}`.normalize("NFKC");
  if (SHORT_NOTICE_TOPIC.test(head)) return true;
  if (!PUBLIC_INTEREST_GENRES.has(article.genreSlug || "")) return false;
  return PUBLIC_INTEREST_SHORT_TOPIC.test(head);
}

/** 広げた暮らしの話題（交通・天気・値上げ・サービス終了・障害・給付・コンビニ/外食/家電/スマホの発売。2026-11-07 台帳 A56） */
const WIDE_TOPICS: { name: string; re: RegExp }[] = rules.wideTopics.map((t) => ({ name: t.name, re: new RegExp(t.source, t.flags) }));
const WIDE_EXCLUDE = new RegExp(rules.wideExclude.source, rules.wideExclude.flags);
const WIDE_NOT_OUTAGE = new RegExp(rules.wideNotOutage.source, rules.wideNotOutage.flags);
const LAUNCH_TOPIC = new RegExp(rules.launchTopic.source, rules.launchTopic.flags);
const LAUNCH_CONTEXT = new RegExp(rules.launchContext.source, rules.launchContext.flags);
const LAUNCH_SOURCES = new Set<string>(rules.launchSources);

/** public_interest.wide_category と同じ（題名だけで見る。事件〔犯罪〕・不祥事・ゴシップは null。2026-11-08 台帳 A23） */
export function wideCategory(title: string, sourceSlug = ""): string | null {
  const text = (title ?? "").normalize("NFKC");
  if (!text || WIDE_EXCLUDE.test(text)) return null;
  for (const { name, re } of WIDE_TOPICS) {
    if (!re.test(text)) continue;
    if (name === "outage" && WIDE_NOT_OUTAGE.test(text)) continue;
    return name;
  }
  if (LAUNCH_TOPIC.test(text) && (LAUNCH_CONTEXT.test(text) || LAUNCH_SOURCES.has(sourceSlug))) return "launch";
  return null;
}

/** public_interest.focus_topic と同じ */
function isPublicInterest(article: ArticleSummary): boolean {
  if (!PUBLIC_INTEREST_GENRES.has(article.genreSlug || "")) return false;
  const text = `${article.title ?? ""} ${article.seoTitle ?? ""} ${(article.tags ?? []).join(" ")}`.normalize("NFKC");
  if (PUBLIC_INTEREST_TOPIC.test(text)) return true;
  return wideCategory(`${article.title ?? ""} ${article.seoTitle ?? ""}`, article.channelSlug ?? "") !== null;
}

/** persona.is_persona_topic と同じ */
function isPersonaTopic(article: ArticleSummary): boolean {
  const genre = article.genreSlug || "";
  if (PERSONA_GENRES.has(genre)) return true;
  const text = `${article.title ?? ""} ${article.seoTitle ?? ""} ${(article.tags ?? []).join(" ")}`;
  return PERSONA_EXTRA_GENRES.has(genre) && PRIORITY_TOPIC.test(text);
}

/** persona.sports_scope(text) と同じ（発信元が海外かは記事に残らないので、日本の発信元として扱う） */
function isJapanSports(text: string): boolean {
  const t = text.normalize("NFKC");
  if (GLOBAL_EVENT.test(t) || JAPAN_SPORTS.test(t)) return true;
  return !FOREIGN_SPORTS.test(t);
}

/** genre_focus.entertainment_focus と同じ（ゴシップ・告知だけの題名は外し、ビジネス・テックの目印があれば主題） */
export function isOfficialGameNews(title: string, channelSlug: string): boolean {
  if (!GAME_OFFICIAL_SOURCES.has(channelSlug || "")) return false;
  const t = (title ?? "").normalize("NFKC");
  return GAME_PLATFORM.test(t) && GAME_ANNOUNCE.test(t) && !GAME_EXCLUDE.test(t);
}

function isEntertainmentFocus(article: ArticleSummary): boolean {
  if (isOfficialGameNews(article.title ?? "", article.channelSlug ?? "")) return true;
  const title = (article.title ?? "").normalize("NFKC");
  if (ENTERTAINMENT_EXCLUDE.test(title)) return false;
  return ENTERTAINMENT_BUSINESS.test(`${title} ${(article.tags ?? []).join(" ")}`);
}

/** 読者像の話題か（scripts/indexnow.py の is_focus と同じ） */
export function isFocus(article: ArticleSummary): boolean {
  const text = `${article.title ?? ""} ${(article.tags ?? []).join(" ")}`;
  if (FOCUS_GENRES.has(article.genreSlug) || AI_TOPIC.test(text)) return true;
  if (isPersonaTopic(article)) return true;
  if (isPublicInterest(article)) return true;
  if (ENTERTAINMENT_GENRES.has(article.genreSlug)) return isEntertainmentFocus(article);
  if (SPORTS_GENRES.has(article.genreSlug)) return isJapanSports(text);
  return false;
}

/** 14日間訪問0で、検索に出さない記事（content/noindex_zero_visit.json の slugs） */
const ZERO_VISIT = new Set<string>(zeroVisit.slugs);

/**
 * 14日間訪問0の記事か（2026-11-10 オーナー承認）。公開したまま・一覧やリンクからは読めるが、検索に出さず、広告・提携の囲みも出さない。
 * 手動の indexable（記事 JSON）があればそちらが先（noindexReason）
 */
export function isZeroVisit(slug: string | undefined | null): boolean {
  return Boolean(slug) && ZERO_VISIT.has(slug as string);
}

/** 本文が無いとみなす字数（scripts/indexnow.py の NO_BODY） */
export const NO_BODY: number = rules.noBody;

/**
 * 検索に出さない理由（出すなら null）。scripts/indexnow.py の noindex_reason と同じ。
 * 2026-11-08 オーナー承認（台帳 A61）: 出さないのは本当の重複（duplicateOf）・本文が無い記事・お金にも暮らしにもつながらない話題だけ。
 * 主題外・日本の読者向けの章が無い・短い公式のお知らせ・配信・動画の要約でも、お金か暮らしにつながれば検索に出す。
 */
export function noindexReason(article: ArticleSummary): string | null {
  if (typeof article.indexable === "boolean") return article.indexable ? null : "manual";
  if (article.type === "roundup") return null;
  if ((article.bodyLength ?? 0) < NO_BODY) return "no-body";
  // 重複の印は記事 JSON の duplicateOf と、索引を作るときの予備の判定（lib/article-index.mjs の markDuplicates）
  if (article.duplicate || (article.duplicateOf && article.duplicateOf !== article.slug)) return "duplicate";
  // 14日間訪問0の記事（content/noindex_zero_visit.json。2026-11-10 オーナー承認。記事は消さない）
  if (isZeroVisit(article.slug)) return "zero-visit";
  // 今まで検索に出していた主題（isFocus）はそのまま出す（ゆるめるだけで、出していた記事を外さない）
  // 地震・災害の記事は題名に「地震」などがあるのでつながる（scripts/indexnow.py は disaster も見る）
  if (!lifeLink(article.title ?? "") && !isFocus(article)) return "no-life-link";
  return null;
}

const LIFE_MONEY = new RegExp(rules.lifeMoney.source, rules.lifeMoney.flags);
const NO_LIFE_LINK = new RegExp(rules.noLifeLink.source, rules.noLifeLink.flags);
const LIFE_GENERAL = new RegExp(rules.lifeGeneral.source, rules.lifeGeneral.flags);

/**
 * 題名がお金か暮らしにつながる話題か（scripts/indexnow.py の life_link と同じ。台帳 A61「暮らしとお金の自分ごとニュース」）。
 * お金の語 → つながる。無ければ、ゴシップ・物語/キャラクター・海外の試合結果の語 → つながらない。無ければ暮らし・サービス・仕事の語 → つながる
 */
export function lifeLink(title: string): boolean {
  const text = (title ?? "").normalize("NFKC");
  if (LIFE_MONEY.test(text)) return true;
  if (NO_LIFE_LINK.test(text)) return false;
  return LIFE_GENERAL.test(text);
}

/** 2026-11-08 までの検索の基準（主題・日本の読者向け・本文の長さ）。scripts/indexnow.py の focus_reason と同じ（説明・集計用） */
export function focusReason(article: ArticleSummary): string | null {
  if (typeof article.indexable === "boolean") return article.indexable ? null : "manual";
  if (article.type === "roundup") return null;
  if (WIRE_SOURCES.has(article.channelSlug)) return "wire";
  if (CREATOR_CHANNELS.has(article.channelSlug)) return "creator-video";
  if (article.bodyLength < (isShortArticle(article) ? THIN_BODY_PUBLIC_INTEREST : THIN_BODY)) return "thin";
  if (!isFocus(article)) return "off-focus";
  if (!article.verdict && !article.hasJapanValue) return "no-japan-value";
  // 重複の印は記事 JSON の duplicateOf と、索引を作るときの予備の判定（lib/article-index.mjs の markDuplicates）
  if (article.duplicate || (article.duplicateOf && article.duplicateOf !== article.slug)) return "duplicate";
  return null;
}

export function isIndexable(article: ArticleSummary): boolean {
  return noindexReason(article) === null;
}

/** 記事ページの canonical（重複記事は代表の記事へ） */
export function canonicalPathOf(article: Pick<ArticleSummary, "slug" | "duplicateOf">): string {
  const target = article.duplicateOf && article.duplicateOf !== article.slug ? article.duplicateOf : article.slug;
  return `/articles/${target}`;
}

/** ニュース用サイトマップに載せる期間（Google の仕様は公開から2日） */
export const NEWS_WINDOW_MS = 2 * 86_400_000;
/** 元の発表からこれ以上たって作った記事は「速報」ではないのでニュース用サイトマップに載せない */
export const NEWS_MAX_SOURCE_AGE_MS = 48 * 3_600_000;

/** 元の発表の時刻（web 記事は sourcePublishedAt、動画は投稿時刻 publishedAt） */
export function sourceTimeOf(article: Pick<ArticleSummary, "sourcePublishedAt" | "publishedAt" | "kind">): number {
  if (article.sourcePublishedAt) return Date.parse(article.sourcePublishedAt);
  // 元の発表の時刻が分からない記事: ニュース（kind なし）は publishedAt で代用。比較・選び方の記事（kind あり）の publishedAt は
  // 元の発表の時刻ではないので代用しない（不明＝NaN。SEO A5。scripts/indexnow.py news_reason と同じ）
  if (article.kind) return NaN;
  return Date.parse(article.publishedAt || "");
}

/**
 * ニュース用サイトマップに載せないときの理由（載せるなら null）。scripts/indexnow.py の news_reason と同じ。
 * 公開日は最初に載せた時刻（generatedAt。続報や書き直しで変えない）。
 */
export function newsSitemapReason(article: ArticleSummary, now = Date.now()): string | null {
  const reason = noindexReason(article);
  if (reason) return reason;
  if (article.type === "roundup") return "roundup";
  if (article.angleOf) return "angle";
  if (article.late) return "late";
  const published = Date.parse(article.generatedAt || article.publishedAt || "");
  if (!Number.isFinite(published) || now - published >= NEWS_WINDOW_MS) return "old";
  const source = sourceTimeOf(article);
  if (Number.isFinite(source) && published - source > NEWS_MAX_SOURCE_AGE_MS) return "stale-source";
  return null;
}

/** 一覧ページ（タグ・チャンネル・企業・ジャンル）を検索に出す最低本数（検索対象の記事で数える） */
export const MIN_LISTING = 3;
/**
 * 一覧ページを検索に出す、公開中の記事の最低本数（2026-11-12 AdSense 監査）。
 * 同じ型の文で記事が数本だけの一覧（タグ・発信元が327件・サイトマップの22%）は、自動で作った薄いページに見えるため。
 * content/list_pages_protected.json にある一覧（読まれた一覧）は、この本数に届かなくても検索に出したまま
 */
export const MIN_LISTING_LIVE = 5;
const LIST_PROTECTED = new Set<string>(listGuard.paths);

function decodedPath(path: string): string {
  try {
    return decodeURIComponent(path).replace(/\/+$/, "");
  } catch {
    return path;
  }
}

/** 読まれた一覧として、検索に出したままにする一覧か */
export function isProtectedListing(path?: string): boolean {
  return Boolean(path) && LIST_PROTECTED.has(decodedPath(path as string));
}

/** 検索対象の記事が少ない一覧は noindex（ページ自体は残す）。path を渡すと、守る一覧（list_pages_protected.json）は公開の本数の条件を外す */
export function isListingIndexable(articles: ArticleSummary[], path?: string): boolean {
  let n = 0;
  for (const a of articles) if (isIndexable(a) && ++n >= MIN_LISTING) break;
  if (n < MIN_LISTING) return false;
  return isProtectedListing(path) || articles.length >= MIN_LISTING_LIVE;
}

/**
 * YouTube の動画から作った記事の一覧か（記事の半分以上が動画の要約）。他のサイトの動画の要約を集めたページに見えるため、
 * 守る一覧でなければ検索に出さない（2026-11-12 AdSense 監査。/channels/openai・/channels/microsoft-research など）
 */
export function isVideoListing(articles: ArticleSummary[]): boolean {
  if (articles.length === 0) return false;
  const videos = articles.filter((a) => a.sourceType !== "web" && Boolean(a.videoId)).length;
  return videos * 2 >= articles.length;
}

/** 一覧ページの robots 指定（検索に出すなら空） */
export function listingRobots(articles: ArticleSummary[], path?: string) {
  return isListingIndexable(articles, path) ? {} : { robots: { index: false, follow: true } };
}

/** 外部配信・既存のメール等は、検索方針の変更による内容の急変を防ぎ従来基準を保持する。 */
export function isDistributionEligible(article: ArticleSummary): boolean {
  if (typeof article.indexable === "boolean") return article.indexable;
  if (article.sourceType !== "web" || article.type === "roundup") return true;
  if (WIRE_SOURCES.has(article.channelSlug)) return false;
  return article.bodyLength >= 2000;
}
