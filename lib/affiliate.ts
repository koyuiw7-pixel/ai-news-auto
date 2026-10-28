/**
 * 提携（アフィリエイト）リンクの共通ルール。
 * rel に nofollow を入れて、検索エンジンなどのクローラーが計測リンクをたどらないようにする
 * （たどられると ASP のクリック数が人以外で水増しされる）。href と表示計測の img はいじらない（ASP の規約）。
 */
export const AFFILIATE_REL = "sponsored nofollow noopener noreferrer";

/** 提携リンクの配信元（ASP・楽天・Amazon の短縮URL） */
const AFFILIATE_HOST = /(?:^|\.)(?:a8\.net|moshimo\.com|valuecommerce\.com|accesstrade\.net|afi-b\.com|rakuten\.co\.jp|amzn\.to|felmat\.net)$/i;

/** 提携リンクか（登録済みの URL か、ASP のドメインか、tag 付きの Amazon） */
export function isAffiliateUrl(href: string, affiliateUrls?: Set<string>): boolean {
  if (affiliateUrls?.has(href)) return true;
  try {
    const url = new URL(href);
    return AFFILIATE_HOST.test(url.hostname) || (/amazon\.co\.jp$/i.test(url.hostname) && url.searchParams.has("tag"));
  } catch {
    return false;
  }
}
