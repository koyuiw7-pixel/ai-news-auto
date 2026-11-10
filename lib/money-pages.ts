/**
 * 話題 → サイト内のお金のページ（対象の確かめ方の記事・手続きガイド・計算ツール）の対応表。1か所だけに置く（2026-11-10 M2）。
 * お金のページへのリンクは、すべてここを読む（記事の要点の下の「自分は対象か確かめる」、使い方ガイドの振り分け、計算ツールのページの関連リンク。
 * あとから足す内部の案内カードも同じ表を使う）。
 *
 * 上ほど具体的。最初に当たった行だけを使う。照合は記事の見出し・短い題名・タグ。
 * 行き先（href・second）・guide・guides・articles は、どれも実在するページだけ（tests/test_money_pages.cjs が確かめる）。
 * 自分自身へのリンクは出さない（second があればそれ、無ければ何も出さない）。
 */
export type MoneyTarget = { href: string; label: string };

export type MoneyPage = MoneyTarget & {
  key: string;
  match: RegExp;
  /** 行き先が記事そのものだったときの代わり */
  second?: MoneyTarget;
  /**
   * この話題の記事に出す使い方ガイド（content/howto の slug）。null は「出さない」（関係の薄いガイドを出さない）。
   * 書かなければ、今までどおりガイドの match で選ぶ（lib/howto.ts・lib/guide-links.ts）
   */
  guide?: string | null;
  /** 計算ツールのページ（/tools/*）に出す関連のガイド（content/howto の slug） */
  guides?: string[];
  /** 計算ツールのページに出す関連の記事（見出しで当たる記事に加えて、本文で扱う記事。content/articles の slug） */
  articles?: string[];
};

export const MONEY_PAGES: MoneyPage[] = [
  {
    key: "pension-support",
    match: /年金生活者支援給付金/,
    href: "/articles/pension-support-benefit-old-age-check",
    label: "年金生活者支援給付金の対象を確かめる",
    // 「年金」の1語で当たる年金の確定申告・年金の税金のガイドは、この話題には出さない
    guide: null,
  },
  {
    key: "childbirth",
    match: /出産手当金|出産育児一時金|産休/,
    href: "/articles/childbirth-allowance-eligibility-check",
    label: "出産手当金を受けられるかを確かめる",
    guide: null,
  },
  {
    key: "child-allowance",
    match: /児童手当/,
    href: "/articles/child-allowance-eligibility-check",
    label: "児童手当の対象を確かめる",
    second: { href: "/guides/jidou-teate", label: "児童手当の金額と対象を確かめる" },
    guide: "jidou-teate",
  },
  {
    key: "kogaku-ryoyohi",
    match: /高額療養費/,
    href: "/guides/kogaku-ryoyohi",
    label: "高額療養費の上限額を確かめる",
    second: { href: "/guides/iryohi-kojo", label: "医療費控除の対象を確かめる" },
    guide: "kogaku-ryoyohi",
  },
  {
    key: "defense-tax",
    match: /防衛特別所得税/,
    href: "/tools/defense-tax",
    label: "防衛特別所得税の額を計算する",
    guides: ["nencho-how-to", "nenkin-zeikin"],
    articles: ["nencho-2026-changes", "winter-bonus-take-home-pay-calculation"],
  },
  {
    key: "furusato",
    match: /ふるさと納税|ワンストップ特例/,
    href: "/tools/furusato-limit",
    label: "ふるさと納税の上限額を計算する",
  },
  {
    key: "nencho",
    match: /年末調整/,
    href: "/guides/nencho-target",
    label: "年末調整の対象かを確かめる",
  },
];

type ArticleLike = { slug?: string; title: string; seoTitle?: string; tags?: string[] };

/** 記事に当たる行（無ければ undefined）。見出し・短い題名・タグで照合する */
export function moneyTopicFor(article: ArticleLike, rows: MoneyPage[] = MONEY_PAGES): MoneyPage | undefined {
  const text = `${article.title} ${article.seoTitle ?? ""} ${(article.tags ?? []).join(" ")}`;
  return rows.find((row) => row.match.test(text));
}

/** 記事の要点の下に出す「自分は対象か確かめる」の行き先。自分自身は指さない（second か、無ければ undefined） */
export function moneyLinkFor(article: ArticleLike, rows: MoneyPage[] = MONEY_PAGES): MoneyTarget | undefined {
  const row = moneyTopicFor(article, rows);
  if (!row) return undefined;
  const self = article.slug ? `/articles/${article.slug}` : "";
  if (row.href !== self) return { href: row.href, label: row.label };
  return row.second && row.second.href !== self ? row.second : undefined;
}

/** 計算ツールのページ（href は /tools/*）の行（無ければ undefined） */
export function moneyRowsForTool(toolHref: string, rows: MoneyPage[] = MONEY_PAGES): MoneyPage[] {
  return rows.filter((row) => row.href === toolHref);
}

/**
 * 計算ツールのページに出す関連の記事の slug（表の articles → 見出し・タグが同じ話題の記事の新しい順。重複記事は代表だけ）。
 * articles は新しい順の一覧（lib/articles.ts の getAllArticles）を渡す。記事から計算ツールへは calculatorForArticle（lib/calculators.ts）が案内する
 */
export function toolRelatedArticleSlugs(
  toolHref: string,
  articles: (ArticleLike & { slug: string; duplicateOf?: string })[],
  limit = 5,
  rows: MoneyPage[] = MONEY_PAGES,
): string[] {
  const out: string[] = [];
  const known = new Set(articles.map((a) => a.slug));
  for (const row of moneyRowsForTool(toolHref, rows)) {
    for (const slug of row.articles ?? []) if (known.has(slug) && !out.includes(slug)) out.push(slug);
    for (const article of articles) {
      if (article.duplicateOf && article.duplicateOf !== article.slug) continue;
      if (!out.includes(article.slug) && moneyTopicFor(article, [row])) out.push(article.slug);
    }
  }
  return out.slice(0, limit);
}
