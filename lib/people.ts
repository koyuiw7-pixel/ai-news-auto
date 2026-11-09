import data from "@/content/people.json";
import { getAllArticles, type ArticleSummary } from "@/lib/articles";
import { companyOf } from "@/lib/companies";

/**
 * 人物のまとめページ（/people/<slug>。2026-11-07 台帳 A53）。経歴は公式の一次情報だけ（content/people.json）。
 * 記事の一覧は match の正規表現で、題名・リード・要点・タグから自動で拾う。
 */
export type PersonFact = { text: string; source: { title: string; url: string } };
export type Person = {
  slug: string;
  name: string;
  nameJa: string;
  aliases: string[];
  jobTitle: string;
  organization: string;
  organizationUrl: string;
  companySlug: string;
  summary: string;
  facts: PersonFact[];
  sameAs: string[];
  match: string;
  verifiedAt: string;
};

const PEOPLE = ((data as unknown as { people: Person[] }).people ?? []).filter((p) => /^[a-z0-9-]+$/.test(p.slug));

export function getAllPeople(): Person[] {
  return PEOPLE;
}

export function getPerson(slug: string): Person | undefined {
  return PEOPLE.find((p) => p.slug === slug);
}

function haystack(a: ArticleSummary): string {
  return [a.title, a.seoTitle, a.lede, a.description, ...(a.highlights ?? []), ...(a.tags ?? []), ...(a.keywords ?? [])]
    .join(" ")
    .normalize("NFKC");
}

/**
 * 人物のページに並べる中身（2026-11-09 台帳 A68。/people/sam-altman が「最新ニュース（0本）」のまま検索に出ていた不具合の修正）。
 * 人物の記事が0本のときは「0本」の見出しを出さず、所属組織の最新の記事を主役にする。人物の記事も組織の記事も無いときだけ検索に出さない
 */
export function personPage(person: Person, articles: ArticleSummary[] = getAllArticles()) {
  const own = personArticles(person, articles);
  const org = organizationArticles(person, own.length >= 5 ? 5 : 10, articles).filter((a) => !own.some((b) => b.slug === a.slug));
  return { own, org, indexable: own.length + org.length > 0 };
}

/** この人物が出てくる記事（新しい順。まとめ記事・重複の印の記事は外す） */
export function personArticles(person: Person, articles: ArticleSummary[] = getAllArticles()): ArticleSummary[] {
  const re = new RegExp(person.match, "i");
  return articles.filter((a) => a.type !== "roundup" && !a.duplicate && re.test(haystack(a)));
}

/** 所属組織の最新の記事（人物が出てくる記事がまだ少ないときに並べる。人物の記事とは分けて見せる） */
export function organizationArticles(person: Person, limit = 10, articles: ArticleSummary[] = getAllArticles()): ArticleSummary[] {
  return articles.filter((a) => a.type !== "roundup" && !a.duplicate && companyOf(a).slug === person.companySlug).slice(0, limit);
}

/** 記事に出てくる人物（記事のページの「この記事の人物」） */
export function peopleInArticle(article: ArticleSummary): Person[] {
  const text = haystack(article);
  return PEOPLE.filter((p) => new RegExp(p.match, "i").test(text));
}

/** 企業のページに出す人物 */
export function peopleOfCompany(companySlug: string): Person[] {
  return PEOPLE.filter((p) => p.companySlug === companySlug);
}
