import { articleTitle } from "@/lib/headline";
import { getAllArticles, getAllGenres, getArticlesByGenre } from "@/lib/articles";
import { CALCULATORS } from "@/lib/calculators";
import { getAllGuides, isThinGuide } from "@/lib/guides";
import { getAllHowtos } from "@/lib/howto";
import { isIndexable, isListingIndexable } from "@/lib/indexing";
import { listedProducts, productHeading, supersedesGuide } from "@/lib/products";
import { isBroadGenre } from "@/lib/sections";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

/** 縦棒（全角）は出さない（2026-11-07 オーナー決定）。改行や連続した空白は1つにまとめる */
function llmsClean(text: string): string {
  return text.replace(/｜/g, "　").replace(/\s+/g, " ").trim();
}

const line = (title: string, url: string, note?: string) => {
  const cleanNote = note ? llmsClean(note) : "";
  return `- [${llmsClean(title)}](${url})${cleanNote ? `: ${cleanNote}` : ""}`;
};

/** 中身の無い見出しは出さない（見出しのすぐ下に見出しが来ないようにする） */
const section = (heading: string, lines: string[]) => (lines.length > 0 ? `## ${heading}\n\n${lines.join("\n")}\n` : "");

/**
 * AI検索・AIアシスタント向けのサイト案内（llms.txt）。
 * 今のサイト（暮らしとお金の「自分ごと」ニュース）の中身を短い Markdown で伝え、AIの回答で引用されやすくする（2026-11-10 LLMO-A14）。
 * 載せるのは検索に出すページだけ。記事の題名は articleTitle()（題名は1つだけ。台帳 A29）。AIの製品ページは最後の「Optional」に回す。
 */
export function GET() {
  const base = siteConfig.url;
  const howtos = getAllHowtos();
  const moneyGuides = howtos.filter((g) => g.kind === "procedure");
  const aiHowtos = howtos.filter((g) => g.kind !== "procedure");
  const genres = getAllGenres().filter((genre) => (genre.slug === "ai" || isBroadGenre(genre.slug)) && isListingIndexable(getArticlesByGenre(genre.slug)));
  const latest = getAllArticles().filter((a) => a.type !== "roundup" && isIndexable(a)).slice(0, 40);
  // まとめページへ移した製品ガイドは転送しているので載せない。関連記事の無いガイドは検索に出さないので載せない（台帳 W28）
  const productGuides = getAllGuides().filter((g) => !supersedesGuide(g.slug) && !isThinGuide(g));
  const products = listedProducts();

  const about = [
    line("運営者情報・編集方針", `${base}/about`),
    line("編集方針・AI利用と事実確認について", `${base}/editorial-policy`),
    line("訂正履歴・訂正の方針", `${base}/corrections`),
    line("トップ（新着の時系列）", `${base}/`),
    line("記事一覧", `${base}/articles`),
    line("RSS", `${base}/feed.xml`),
  ];

  const optional = [
    ...products.map((p) => line(productHeading(p), `${base}/products/${p.slug}`, p.overview.text)),
    ...productGuides.map((g) => line(g.title, `${base}/guides/${g.slug}`, g.description)),
    ...aiHowtos.map((g) => line(g.title, `${base}/guides/${g.slug}`, g.description)),
    ...(products.length > 0 ? [line("AIの料金・日本対応 早見表", `${base}/ai-pricing`)] : []),
  ];

  const text = [
    `# ${siteConfig.name}\n`,
    `> ${siteConfig.description}\n`,
    `${siteConfig.name}は、企業・官公庁の公式ブログ・ニュースリリース・発表を常時監視し、日本語の記事にする速報メディアです。公式の資料が無い話題は報道機関の記事を出典にし、その旨を記事に明記しています。運営：${siteConfig.operator.name}（${siteConfig.operator.email}）\n`,
    section("このサイトについて", about),
    section("手続きとお金のガイド", moneyGuides.map((g) => line(g.title, `${base}/guides/${g.slug}`, g.description))),
    section("計算ツール", Object.values(CALCULATORS).map((c) => line(c.title, `${base}${c.href}`, c.description))),
    section("ジャンル", genres.map((g) => line(`${g.label}のニュース`, `${base}/genres/${g.slug}`))),
    section("最新の記事", latest.map((a) => line(articleTitle(a), `${base}/articles/${a.slug}`, a.description))),
    section("Optional", optional),
  ]
    .filter(Boolean)
    .join("\n");

  return new Response(text, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
