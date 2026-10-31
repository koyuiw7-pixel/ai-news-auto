import data from "@/content/events.json";
import { getAllArticles, type ArticleSummary } from "@/lib/articles";
import { isDistributionEligible } from "@/lib/indexing";

/**
 * イベント速報ページ（/events/[slug]）。content/events.json は公式サイトで確かめた情報だけを手で入れ、
 * 日本時間・開催状況・発表内容のまとめは scripts/events.py が毎晩更新する。
 * 関連記事はビルドのたびにここで集め直す（記事が増えるとデプロイされるので、開催中も追従する）。
 */
export type EventKeynote = {
  title: string;
  speaker: string | null;
  /** 現地時間 */
  startLocal: string;
  startUtc: string | null;
};

export type TechEvent = {
  slug: string;
  name: string;
  nameJa: string;
  organizer: string;
  companySlug: string;
  startDate: string;
  endDate: string;
  location: string;
  timezone: string;
  keynotes: EventKeynote[];
  officialUrl: string | null;
  sources: { title: string; url: string }[];
  confirmed: string[];
  livestream: string | null;
  confidence: "official" | "reported";
  summary: string;
  /** 関連記事を見つける正規表現（題名・タグ・説明に照合） */
  match: string;
  verifiedAt: string;
  startUtc: string;
  endUtc: string;
  recap?: { text: string; slug: string }[];
  recapAt?: string;
};

export type EventStatus = "upcoming" | "live" | "ended";

const DAY = 86_400_000;
/** 会期の何日前から何日後までの記事を「このイベントの記事」とみなすか（scripts/events.py と同じ） */
const WINDOW_BEFORE = DAY;
const WINDOW_AFTER = 3 * DAY;

const events = ((data as unknown as { events: TechEvent[] }).events ?? []).sort((a, b) =>
  a.startUtc.localeCompare(b.startUtc),
);

export function getAllEvents(): TechEvent[] {
  return events;
}

export function getEvent(slug: string): TechEvent | undefined {
  return events.find((event) => event.slug === slug);
}

export function eventStatus(event: TechEvent, now = Date.now()): EventStatus {
  if (now < Date.parse(event.startUtc)) return "upcoming";
  if (now <= Date.parse(event.endUtc)) return "live";
  return "ended";
}

/** 開催までの日数（当日・開催中は0） */
export function daysUntil(event: TechEvent, now = Date.now()): number {
  return Math.max(0, Math.ceil((Date.parse(event.startUtc) - now) / DAY));
}

function text(article: ArticleSummary): string {
  return `${article.title} ${article.seoTitle ?? ""} ${article.tags.join(" ")} ${article.description}`;
}

const articleCache = new Map<string, ArticleSummary[]>();

/** 会期の前後に出た、このイベントに関係する記事（新しい順） */
export function eventArticles(event: TechEvent): ArticleSummary[] {
  const cached = articleCache.get(event.slug);
  if (cached) return cached;
  const pattern = new RegExp(event.match, "i");
  const from = Date.parse(event.startUtc) - WINDOW_BEFORE;
  const to = Date.parse(event.endUtc) + WINDOW_AFTER;
  const found = getAllArticles().filter((article) => {
    const at = Date.parse(article.generatedAt || article.publishedAt);
    return at >= from && at <= to && isDistributionEligible(article) && pattern.test(text(article));
  });
  articleCache.set(event.slug, found);
  return found;
}

/** 開催前の文脈: 直前45日の関連ニュース（主催企業・製品の最近の動き） */
export function eventLeadUp(event: TechEvent, limit = 6): ArticleSummary[] {
  const pattern = new RegExp(event.match, "i");
  const to = Date.parse(event.startUtc) - WINDOW_BEFORE;
  const from = to - 45 * DAY;
  return getAllArticles()
    .filter((article) => {
      const at = Date.parse(article.generatedAt || article.publishedAt);
      return at >= from && at < to && article.genreSlug === "ai" && isDistributionEligible(article) && pattern.test(text(article));
    })
    .slice(0, limit);
}

/** 記事が会期中のイベントに当たるか（記事ページからイベントページへ案内するため） */
export function eventForArticle(article: ArticleSummary): TechEvent | undefined {
  const at = Date.parse(article.generatedAt || article.publishedAt);
  return events.find((event) => {
    const from = Date.parse(event.startUtc) - WINDOW_BEFORE;
    const to = Date.parse(event.endUtc) + WINDOW_AFTER;
    return at >= from && at <= to && new RegExp(event.match, "i").test(text(article));
  });
}

const jstDate = new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", weekday: "short", timeZone: "Asia/Tokyo" });
const jstTime = new Intl.DateTimeFormat("ja-JP", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Tokyo" });

/** 「11月18日(水) 03:00」（日本時間） */
export function formatJst(iso: string): string {
  const date = new Date(iso);
  return `${jstDate.format(date)} ${jstTime.format(date)}`;
}

/** 「2026年11月17日〜20日」（現地の日付） */
export function localDateRange(event: TechEvent): string {
  const [sy, sm, sd] = event.startDate.split("-").map(Number);
  const [ey, em, ed] = event.endDate.split("-").map(Number);
  if (event.startDate === event.endDate) return `${sy}年${sm}月${sd}日`;
  if (sy !== ey) return `${sy}年${sm}月${sd}日〜${ey}年${em}月${ed}日`;
  if (sm !== em) return `${sy}年${sm}月${sd}日〜${em}月${ed}日`;
  return `${sy}年${sm}月${sd}日〜${ed}日`;
}

/** 現地時間の「10:00」 */
export function localTime(startLocal: string): string {
  return startLocal.split("T")[1] ?? "";
}

/** 現地の日付の「11月17日」 */
export function localDay(startLocal: string): string {
  const [, m, d] = startLocal.split("T")[0].split("-").map(Number);
  return `${m}月${d}日`;
}
