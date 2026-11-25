import { getArticle } from "@/lib/articles";
import { easyHtmlOf } from "@/lib/easy-version";

/**
 * 記事の要約版（かんたんに読む版）の HTML を返す（components/ReadingMode.tsx が「要約版で読む」を選んだときに読む）。
 * 2026-11-25 AdSense の点検: 記事ページの HTML に詳細版と要約版の両方を入れると同じ文がくり返されるため、要約版はここから読み込む。
 * /api/ は robots.txt で巡回させず、念のため X-Robots-Tag: noindex も付ける。?v=noir は新しい見た目の記事（lib/noir.ts）
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HEADERS = {
  "Cache-Control": "public, max-age=3600, s-maxage=3600",
  "X-Robots-Tag": "noindex, nofollow",
};

export async function GET(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = /^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(slug) ? getArticle(slug) : undefined;
  if (!article) return Response.json({ html: "" }, { status: 404, headers: HEADERS });
  const noir = new URL(request.url).searchParams.get("v") === "noir";
  const html = await easyHtmlOf(article, noir);
  return Response.json({ html }, { status: html ? 200 : 404, headers: HEADERS });
}
