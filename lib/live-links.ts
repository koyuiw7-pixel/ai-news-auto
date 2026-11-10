/**
 * 取り下げた記事（content/retired.json）や、無い記事へのリンクを画面に出さない（台帳 A9）。
 * scripts/retire_articles.py --resweep がデータを直すが、記事を戻したとき（2026-11-08 の 132本の復元）などに
 * 直し忘れても、410 のページへのリンクを読者に見せないための最後の守り。
 * 判定（isLive）は呼び出し側が渡す（lib/retired.ts の isLiveArticleSlug）。この中では何も読まない。
 */

export type IsLiveArticle = (slug: string) => boolean;

// サイト内の記事へのリンク（相対・絶対のどちらも）。marked の出力の <a href="..."> の形
const ARTICLE_LINK_RE =
  /<a\s+href="(?:https:\/\/ai-tech-express\.jp)?\/articles\/([A-Za-z0-9_-]+)\/?(?:#[^"]*)?"[^>]*>([\s\S]*?)<\/a>/g;

/**
 * 本文の HTML から、生きていない記事へのリンクを外す。リンクの文字は残す。
 * ただしリンクの文字が slug そのもの・「関連記事」（lib/article-sections.ts の titleSlugLinks の代わりの文字）のときは、
 * 読者に意味の無い文字なので、まわりの（）ごと外す。
 */
export function dropDeadArticleLinks(html: string, isLive: IsLiveArticle): string {
  if (!html || !html.includes("/articles/")) return html;
  const DROP = "\u0000";
  const out = html.replace(ARTICLE_LINK_RE, (all, slug: string, text: string) => {
    if (isLive(slug)) return all;
    const plain = text.replace(/<[^>]+>/g, "").trim();
    return plain === slug || plain === "関連記事" || plain === "" ? DROP : text;
  });
  return out.replace(/[（(]\u0000[）)]|\u0000/g, "");
}

/** まとめ記事への案内（roundupSlug）は、まとめが生きているときだけ残す。生きていなければ roundupSlug・roundupTitle を外した写しを返す */
export function withLiveRoundup<T extends { roundupSlug?: string; roundupTitle?: string }>(article: T, isLive: IsLiveArticle): T {
  if (!article.roundupSlug || isLive(article.roundupSlug)) return article;
  const { roundupSlug: _slug, roundupTitle: _title, ...rest } = article;
  void _slug;
  void _title;
  return rest as T;
}
