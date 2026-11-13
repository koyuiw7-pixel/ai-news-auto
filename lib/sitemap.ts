import { getAllChooseGuides } from "@/lib/choose";
import { isIndexable, isListingIndexable, isProtectedListing, isVideoListing } from "@/lib/indexing";
import {
  getAllArticles,
  getAllChannels,
  getAllGenres,
  getAllTags,
  getArticlesByChannel,
  getArticlesByGenre,
  getArticlesByTag,
  genreTwinOfTag,
  lastModifiedOf,
  tagSlug,
  type ArticleSummary,
} from "@/lib/articles";
import corrections from "@/content/corrections.json";
import { companyCounts, companyOf } from "@/lib/companies";
import { getAllGuides, guideArticles, isThinGuide } from "@/lib/guides";
import { getAllHowtos } from "@/lib/howto";
import { getIndexableBuyingGuides } from "@/lib/buying-guides";
import { eventArticles, getAllEvents } from "@/lib/events";
import { getAllMoneyDates } from "@/lib/money-dates";
import { getPricing } from "@/lib/pricing";
import { listedProducts, productProfile, supersedesGuide } from "@/lib/products";
import { getAllPeople } from "@/lib/people";
import { archiveMonths, MIN_INDEX_ENTRIES, monthEntries, recentEntries, TOPIC_LISTS, topicListsUpdatedAt } from "@/lib/topic-lists";
import { getAllWeeks, weekPublishedAt } from "@/lib/weekly";
import { isBroadGenre } from "@/lib/sections";
import { isThinSourceChannel } from "@/lib/news-outlets";
import { canonicalChannel, hasChannelLabel } from "@/lib/channel-labels";
import { siteConfig } from "@/site.config";

/**
 * サイトマップの1行。lastmod は「中身が本当に変わった日時」だけ（SEO A16）。分からないページは書かない。
 * changefreq・priority は Google が使わないので出さない。
 */
export type SitemapEntry = {
  url: string;
  lastModified?: Date;
};

/**
 * 固定のページ（文面を手で書いたページ）の最終更新日。文面を変えたら手で直す（ビルドの時刻を使わない）。
 * 2026-11-10 時点は各ページのファイルを最後に直した日。
 */
export const STATIC_LASTMOD: Record<string, string> = {
  "/about": "2026-11-10",
  "/editorial-policy": "2026-11-09",
  "/privacy": "2026-11-09",
  "/disclaimer": "2026-11-09",
  "/contact": "2026-11-03",
  "/corrections": "2026-11-03",
  "/newsletter": "2026-11-10",
  "/tools/defense-tax": "2026-11-10",
  "/tools/furusato-limit": "2026-11-10",
};

const toDate = (value: string | undefined | null): Date | undefined => {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
};

/** 一覧ページの最終更新 = 載っている記事のうち、いちばん新しい公開・更新の日時（載る記事が無ければ書かない） */
export function newestOf(articles: ArticleSummary[]): Date | undefined {
  let best: Date | undefined;
  for (const article of articles) {
    const at = toDate(lastModifiedOf(article));
    if (at && (!best || at > best)) best = at;
  }
  return best;
}

const newestDate = (values: (string | undefined | null)[]): Date | undefined =>
  values.map(toDate).filter((d): d is Date => Boolean(d)).sort((a, b) => b.getTime() - a.getTime())[0];

/** 1ファイルに載せる URL の上限（仕様上は5万。余裕を持たせる） */
export const SITEMAP_CHUNK = 40000;

/** サイトマップに載せる全 URL（記事は全件） */
export function sitemapEntries(): SitemapEntry[] {
  const base = siteConfig.url;
  // 全ジャンルが対象。ただし薄くなりやすい記事は検索に出さないので載せない（lib/indexing.ts）
  const allArticles = getAllArticles();
  const articles = allArticles.filter(isIndexable);
  const liveChannels = new Set(articles.map((a) => canonicalChannel(a.channelSlug)));
  const liveTags = new Set(articles.flatMap((a) => a.tags.map(tagSlug)));
  // 一覧ページの noindex 方針に合わせる。発信元は名前の表にある組織（SEO A11）、タグは記事が2本以上。
  // 件数はページと同じく全記事で数え、同じ記事内の重複タグは1本として扱う。
  const tagArticleCounts = new Map<string, number>();
  for (const article of allArticles) {
    for (const slug of new Set(article.tags.map(tagSlug))) {
      tagArticleCounts.set(slug, (tagArticleCounts.get(slug) ?? 0) + 1);
    }
  }
  // 図鑑は中身がそろった製品だけ（ほかは noindex。2026-11-03 台帳 W13）
  const products = listedProducts();
  const guides = getAllGuides().filter((guide) => !supersedesGuide(guide.slug) && !isThinGuide(guide));
  const howtos = getAllHowtos();
  // 一覧ページの最終更新は、載っている記事のいちばん新しい日時（ビルドの時刻や、全ページ同じ日時は使わない。SEO A16）
  const newestArticle = newestOf(articles);
  const fixed = (path: string) => ({ url: `${base}${path}`, lastModified: toDate(STATIC_LASTMOD[path]) });
  const productDates = products.map((product) => ({ product, at: toDate(productProfile(product).updatedAt) }));

  return [
    { url: base, lastModified: newestArticle },
    { url: `${base}/articles`, lastModified: newestArticle },
    ...(allArticles.some((article) => isBroadGenre(article.genreSlug))
      ? [{ url: `${base}/news`, lastModified: newestOf(articles.filter((a) => isBroadGenre(a.genreSlug))) }]
      : []),
    ...["/about", "/editorial-policy", "/privacy", "/disclaimer", "/contact", "/newsletter"].map(fixed),
    // 訂正のページは、いちばん新しい訂正の日
    { url: `${base}/corrections`, lastModified: newestDate([STATIC_LASTMOD["/corrections"], ...corrections.map((c) => c.date)]) },
    ...articles.map((article) => ({
      url: `${base}/articles/${article.slug}`,
      // 続報・事実を足した記事は最終更新日時（更新履歴のある updatedAt だけ。lib/article-index.mjs trustedUpdatedAt）
      lastModified: toDate(lastModifiedOf(article))
    })),
    ...getAllGenres()
      .filter((genre) => (genre.slug === "ai" || isBroadGenre(genre.slug)) && isListingIndexable(getArticlesByGenre(genre.slug)))
      .map((genre) => ({
      url: `${base}/genres/${genre.slug}`,
      lastModified: newestOf(getArticlesByGenre(genre.slug).filter(isIndexable))
    })),
    ...getAllChannels()
      // 報道機関の発信元・各社が混ざった radar-official は薄いページなので入れない（台帳 W12。ページ側も noindex）
      // 名前の表にある組織で、検索に出す記事が3本以上（ジャンルは問わない。ページの robots と同じ。SEO A11）
      // 2026-11-12 AdSense 監査: 公開の記事が5本未満・YouTube の動画の要約の一覧は入れない（読まれた一覧 list_pages_protected.json は残す。ページの robots と同じ）
      .filter((channel) => !isThinSourceChannel(channel.slug) && liveChannels.has(channel.slug) && hasChannelLabel(channel.slug)
        && isListingIndexable(getArticlesByChannel(channel.slug), `/channels/${channel.slug}`)
        && (!isVideoListing(getArticlesByChannel(channel.slug)) || isProtectedListing(`/channels/${channel.slug}`)))
      .map((channel) => ({
      url: `${base}/channels/${channel.slug}`,
      lastModified: newestOf(getArticlesByChannel(channel.slug).filter(isIndexable))
    })),
    { url: `${base}/usable`, lastModified: newestOf(articles.filter((a) => a.genreSlug === "ai")) },
    // 料金早見表・週まとめ・イベント（被リンクとブックマークを狙う定番ページ）
    { url: `${base}/ai-pricing`, lastModified: toDate(getPricing().updatedAt) },
    // 計算ツールは防衛特別所得税と、ふるさと納税の上限額（2026-11-10 追加）。AIプランの費用計算・ドル建てサブスクの円換算は 2026-11-03 に終了・410。/tools は転送
    ...["/tools/defense-tax", "/tools/furusato-limit"].map(fixed),
    // 選び方ガイド（回線・転職など。公式情報で比べた常設ページ）
    ...getAllChooseGuides().map((guide) => ({
      url: `${base}/choose/${guide.slug}`,
      lastModified: toDate(guide.updatedAt)
    })),
    ...(getAllWeeks().length > 0
      ? [{ url: `${base}/weekly`, lastModified: toDate(weekPublishedAt(getAllWeeks()[0])) }]
      : []),
    ...getAllWeeks().map((week) => ({
      url: `${base}/weekly/${week.id}`,
      lastModified: toDate(week.generatedAt)
    })),
    // 人物のまとめ（台帳 A53）
    // 人物の一覧は2人以上になってから載せる（1人だけの一覧は薄い。2026-11-12 AdSense 監査。ページも noindex）
    ...(getAllPeople().length >= 2 ? [{ url: `${base}/people`, lastModified: newestDate(getAllPeople().map((p) => p.verifiedAt)) }] : []),
    ...getAllPeople().map((p) => ({ url: `${base}/people/${p.slug}`, lastModified: toDate(p.verifiedAt) })),
    // 値上げ・障害・リコール・サービス終了の一覧（台帳 A52）。載っている発表が少ない一覧は検索に出さないので載せない
    // 一覧の最終更新は、いちばん新しく載せた発表の時刻（まとめを作り直した時刻ではない）
    { url: `${base}/roundups`, lastModified: newestDate(TOPIC_LISTS.flatMap((m) => recentEntries(m.kind).map((e) => e.at))) ?? toDate(topicListsUpdatedAt()) },
    ...TOPIC_LISTS.filter((m) => recentEntries(m.kind).length >= MIN_INDEX_ENTRIES).map((m) => ({
      url: `${base}/roundups/${m.kind}`,
      lastModified: newestDate(recentEntries(m.kind).map((e) => e.at))
    })),
    ...TOPIC_LISTS.flatMap((m) => archiveMonths(m.kind).filter((month) => monthEntries(m.kind, month).length >= MIN_INDEX_ENTRIES).map((month) => ({
      url: `${base}/roundups/${m.kind}/${month}`,
      lastModified: newestDate(monthEntries(m.kind, month).map((e) => e.at))
    }))),
    // 暮らしとお金の日程。更新日は公式のページで確かめ直した日（verifiedAt）
    ...(getAllMoneyDates().length > 0
      ? [{ url: `${base}/dates`, lastModified: newestDate(getAllMoneyDates().map((d) => `${d.verifiedAt}T09:00:00+09:00`)) }]
      : []),
    ...getAllMoneyDates().map((d) => ({ url: `${base}/dates/${d.slug}`, lastModified: toDate(`${d.verifiedAt}T09:00:00+09:00`) })),
    { url: `${base}/events`, lastModified: newestOf(getAllEvents().flatMap((event) => eventArticles(event))) },
    // 行事のページは、その行事の記事のいちばん新しい日時（記事が無ければ書かない）
    ...getAllEvents().map((event) => ({
      url: `${base}/events/${event.slug}`,
      lastModified: newestOf(eventArticles(event))
    })),
    // 製品のまとめページ（「〇〇とは」「料金」の検索の受け皿）
    ...(products.length > 0
      ? [{ url: `${base}/products`, lastModified: newestDate(productDates.map((d) => d.at?.toISOString())) }]
      : []),
    // 製品は「中身か公式の料金が変わった日」（毎日の確認の日ではない。lib/products.ts）
    ...productDates.map(({ product, at }) => ({
      url: `${base}/products/${product.slug}`,
      lastModified: at
    })),
    // まとめページへ移した製品ガイドは転送しているので載せない
    ...(guides.length > 0 || howtos.length > 0
      ? [{ url: `${base}/guides`, lastModified: newestDate([
          ...howtos.map((g) => (g.checkedAt > g.updatedAt ? g.checkedAt : g.updatedAt)),
          ...guides.map((g) => guideArticles(g)[0]?.publishedAt),
        ]) }]
      : []),
    // 使い方ガイド（長く検索される「使い方・料金・無料でどこまで」）。公式ページで確認し直した日を更新日にする
    ...howtos.map((guide) => ({
      url: `${base}/guides/${guide.slug}`,
      lastModified: toDate(guide.checkedAt > guide.updatedAt ? guide.checkedAt : guide.updatedAt)
    })),
    ...guides.map((guide) => ({
      url: `${base}/guides/${guide.slug}`,
      lastModified: toDate(guideArticles(guide)[0]?.publishedAt)
    })),
    // 比較ガイド（購買意図の強い検索の受け皿）
    // 検索に出す比較ページだけ（作り直した新形式。2026-11-11 オーナー承認・台帳 W42）
    ...(getIndexableBuyingGuides().length > 0
      ? [{ url: `${base}/compare`, lastModified: newestDate(getIndexableBuyingGuides().map((g) => g.updatedAt)) }]
      : []),
    ...getIndexableBuyingGuides().map((guide) => ({
      url: `${base}/compare/${guide.slug}`,
      lastModified: toDate(guide.updatedAt)
    })),
    ...companyCounts(articles).filter(({ company }) => isListingIndexable(allArticles.filter((a) => a.genreSlug === "ai" && companyOf(a).slug === company.slug), `/companies/${company.slug}`)).map(({ company }) => ({
      url: `${base}/companies/${company.slug}`,
      lastModified: newestOf(articles.filter((a) => companyOf(a).slug === company.slug))
    })),
    ...getAllTags()
      // ジャンルと同じ名前のタグは載せない（ページは noindex・canonical はジャンルの一覧。lib/articles.ts の genreTwinOfTag）
      .filter((tag) => liveTags.has(tag.slug) && (tagArticleCounts.get(tag.slug) ?? 0) >= 2 && !genreTwinOfTag(tag.slug) && isListingIndexable(getArticlesByTag(tag.slug), `/tags/${tag.slug}`))
      .map((tag) => ({
      url: `${base}/tags/${encodeURIComponent(tag.slug)}`,
      lastModified: newestOf(getArticlesByTag(tag.slug).filter(isIndexable))
    })),
  ];
}

/** URL 数が上限を超えたら分割する。分割後のファイル数 */
export function sitemapChunkCount(): number {
  return Math.max(1, Math.ceil(sitemapEntries().length / SITEMAP_CHUNK));
}

const escapeXml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");

export function renderUrlset(entries: SitemapEntry[]): string {
  const urls = entries
    .map(
      (e) =>
        `<url>\n<loc>${escapeXml(e.url)}</loc>\n${!e.lastModified || Number.isNaN(e.lastModified.getTime()) ? "" : `<lastmod>${e.lastModified.toISOString()}</lastmod>\n`}</url>`,
    )
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

export function renderIndex(count: number): string {
  // 分けたファイルの lastmod は書かない（ビルドの時刻は「中身が変わった日時」ではない。SEO A16）
  const items = Array.from(
    { length: count },
    (_, i) => `<sitemap>\n<loc>${siteConfig.url}/sitemaps/${i}.xml</loc>\n</sitemap>`,
  ).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${items}\n</sitemapindex>\n`;
}

export const XML_HEADERS = { "Content-Type": "application/xml; charset=utf-8" };
