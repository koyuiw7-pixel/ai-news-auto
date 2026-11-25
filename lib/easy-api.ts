import { getAllArticles, getArticle } from "@/lib/articles";
import { easyHtmlOf, easyMarkdownOf } from "@/lib/easy-version";
import { isNoir } from "@/lib/noir";

/**
 * /api/easy/<slug>（いつもの見た目）と /api/easy/<slug>/noir（新しい見た目。lib/noir.ts）の中身。
 * components/ReadingMode.tsx が「要約版で読む」を選んだときに読む。
 *
 * 2026-11-26: 実行時に描く作り（force-dynamic）だと、Cloudflare Workers では記事 JSON が読めず（cloudflare/worker.ts が
 * 先読みするのは記事ページ・カバーだけだった）、本番で 404 になっていた。記事ページと同じく、ビルド時に全記事ぶんを静的に作る
 * （OpenNext がビルドの ISR キャッシュに入れ、scripts/cf_content.mjs が静的アセットへ写す。open-next.config.ts の kvOverAssets が読む）。
 * ビルドに無い slug を描くときのために、cloudflare/worker.ts は /api/easy/<slug> でも記事 JSON を先読みする。
 * /api/ は robots.txt で巡回させず（app/robots.ts）、念のため X-Robots-Tag: noindex も付ける。サイトマップには載せない
 */
export const EASY_HEADERS = {
  "Cache-Control": "public, max-age=3600, s-maxage=3600",
  "X-Robots-Tag": "noindex, nofollow",
};

const SLUG = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;

/** ビルド時に作る slug（要約版のある記事。noir は新しい見た目の記事だけ） */
export function easyStaticParams(noir: boolean): { slug: string }[] {
  const out: { slug: string }[] = [];
  for (const summary of getAllArticles()) {
    const article = getArticle(summary.slug);
    if (!article || !easyMarkdownOf(article)) continue;
    if (noir && !isNoir(article)) continue;
    out.push({ slug: article.slug });
  }
  return out;
}

/** 要約版の JSON（{ html }）。無い記事・要約版の無い記事は 404 */
export async function easyResponse(slug: string, noir: boolean): Promise<Response> {
  const article = SLUG.test(slug) ? getArticle(slug) : undefined;
  if (!article) return Response.json({ html: "" }, { status: 404, headers: EASY_HEADERS });
  const html = await easyHtmlOf(article, noir);
  return Response.json({ html }, { status: html ? 200 : 404, headers: EASY_HEADERS });
}
