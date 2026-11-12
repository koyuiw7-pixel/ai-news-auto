import data from "@/content/money-dates.json";
import { getAllArticles, type ArticleSummary } from "@/lib/articles";
import { isDistributionEligible } from "@/lib/indexing";

/**
 * 暮らしとお金の日程ページ（/dates/[slug]）。イベントのページ（/events）で検索の上位に出た
 * 「いつ・どこ・いくら」の形を、年金・手当・税・料金の日付に広げたもの（2026-11-12）。
 * content/money-dates.json は、確認日（verifiedAt）に公式ページで読んだ日付・金額だけを手で入れる。
 * 催しではないので schema.org の Event は付けない（Article・FAQPage・BreadcrumbList だけ）。
 */
export type DateSource = { title: string; url: string };

export type DateAnswer = {
  /** 答えの欄の見出し（例「2026年12月の年金の支給日」） */
  label: string;
  /** 一番知りたい答え（日付・金額）。最初の画面に出す */
  items: { label: string; value: string }[];
  note?: string;
  source: DateSource;
};

export type MoneyDate = {
  slug: string;
  category: string;
  /** 一覧・パンくず・案内に出す短い名前 */
  name: string;
  title: string;
  /** after を過ぎたあとの題名（無ければ title のまま） */
  titleAfter?: string;
  description: string;
  lead: string;
  /** 数え日の基準の日（YYYY-MM-DD・日本時間）。無ければ数えない */
  keyDate: string | null;
  answer: DateAnswer;
  /** この時刻（UTC）を過ぎたら答えの欄を差し替える（古い答えを出し続けない） */
  after?: { at: string; answer: DateAnswer };
  facts: { label: string; value: string }[];
  answers: { q: string; a: string; sources?: DateSource[] }[];
  notes?: string[];
  /** サイト内の計算ツール・ガイド・関連の日程ページ */
  links: { href: string; label: string }[];
  /** 関連の記事（content/articles の slug）。記事からこのページへの案内にも使う */
  articles: string[];
  /** 記事の題名・タグに当てる正規表現（記事からこのページへの案内） */
  match: string;
  sources: DateSource[];
  verifiedAt: string;
};

const dates = (data as unknown as { dates: MoneyDate[] }).dates ?? [];

export function getAllMoneyDates(): MoneyDate[] {
  return dates;
}

export function getMoneyDate(slug: string): MoneyDate | undefined {
  return dates.find((d) => d.slug === slug);
}

/** 今出す答え（after の時刻を過ぎていれば差し替え） */
export function currentAnswer(entry: MoneyDate, now = Date.now()): DateAnswer {
  return entry.after && now >= Date.parse(entry.after.at) ? entry.after.answer : entry.answer;
}

export function currentTitle(entry: MoneyDate, now = Date.now()): string {
  return entry.after && entry.titleAfter && now >= Date.parse(entry.after.at) ? entry.titleAfter : entry.title;
}

const DAY = 86_400_000;

/** 基準の日まであと何日か（日本時間の日付で数える。過ぎていれば null） */
export function daysUntilKey(entry: MoneyDate, now = Date.now()): number | null {
  if (!entry.keyDate) return null;
  const key = Date.parse(`${entry.keyDate}T00:00:00+09:00`);
  const today = Date.parse(`${new Date(now + 9 * 3_600_000).toISOString().slice(0, 10)}T00:00:00+09:00`);
  const days = Math.round((key - today) / DAY);
  return days >= 0 ? days : null;
}

/** 「2026/11/12」 */
export const verifiedLabel = (entry: MoneyDate) => entry.verifiedAt.replaceAll("-", "/");

/** このページに並べる関連記事（載せている記事のうち、検索・配信に出してよいものだけ） */
export function moneyDateArticles(entry: MoneyDate): ArticleSummary[] {
  const bySlug = new Map(getAllArticles().map((a) => [a.slug, a]));
  return entry.articles.flatMap((slug) => {
    const article = bySlug.get(slug);
    return article && isDistributionEligible(article) ? [article] : [];
  });
}

const textOf = (article: ArticleSummary) => `${article.title} ${article.seoTitle ?? ""} ${article.tags.join(" ")}`;

/** 記事から案内する日程ページ（関連記事に載せた記事か、題名・タグが当たる記事。最初に当たった1つ） */
export function moneyDateForArticle(article: ArticleSummary): MoneyDate | undefined {
  return (
    dates.find((d) => d.articles.includes(article.slug)) ??
    dates.find((d) => new RegExp(d.match).test(textOf(article)))
  );
}
