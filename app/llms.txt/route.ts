import { getAllArticles } from "@/lib/articles";
import { COMPANIES, companyCounts } from "@/lib/companies";
import { getAllGuides } from "@/lib/guides";
import { STATUS_LABEL, verdictOf } from "@/lib/verdict";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

/**
 * AI検索・AIアシスタント向けのサイト案内（llms.txt）。
 * どんなサイトで、どのページに何があるかを短い Markdown で伝え、AIの回答で引用されやすくする。
 */
export function GET() {
  const base = siteConfig.url;
  const ai = getAllArticles().filter((a) => a.genreSlug === "ai");
  const latest = ai.filter((a) => a.type !== "roundup").slice(0, 40);
  const roundups = ai.filter((a) => a.type === "roundup").slice(0, 10);
  const companies = companyCounts(ai).filter(({ company }) => COMPANIES.some((c) => c.slug === company.slug));

  const line = (title: string, url: string, note?: string) => `- [${title}](${url})${note ? `: ${note}` : ""}`;

  const text = `# ${siteConfig.name}（${siteConfig.tagline}）

> ${siteConfig.description}

${siteConfig.name}は、AI企業の公式発表動画とAI専門の解説動画を常時監視し、映像と音声を解析して日本語の記事にする速報メディアです。
各記事には「使えるか」の判定（提供状況・日本から使えるか・料金・無料で試せるか・向いている人）を付けています。
判定は発表時点の情報にもとづき、記事内に判定日を明記しています。運営：${siteConfig.operator.name}（${siteConfig.operator.email}）

## 主なページ

${line("トップ（新着の時系列）", `${base}/`)}
${line("記事一覧", `${base}/articles`)}
${line("製品ガイド一覧", `${base}/guides`, "主要AI製品の「とは・できること・料金・使い方・FAQ」")}
${line("RSS", `${base}/feed.xml`)}

## 製品ガイド

${getAllGuides().map((g) => line(g.title, `${base}/guides/${g.slug}`, g.description)).join("\n")}

## 企業別の最新発表

${companies.map(({ company, count }) => line(`${company.name}の最新AIニュース`, `${base}/companies/${company.slug}`, `${count}本`)).join("\n")}

## 話題まとめ（複数の発表を1本に統合）

${roundups.map((a) => line(a.title, `${base}/articles/${a.slug}`, a.description)).join("\n")}

## 最新記事

${latest
  .map((a) => {
    const verdict = verdictOf(a);
    const note = verdict ? `【${STATUS_LABEL[verdict.status]}・${verdict.price}】${a.description}` : a.description;
    return line(a.title, `${base}/articles/${a.slug}`, note);
  })
  .join("\n")}
`;

  return new Response(text, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
