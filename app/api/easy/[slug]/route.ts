import { easyResponse, easyStaticParams } from "@/lib/easy-api";

/**
 * 記事の要約版（かんたんに読む版）の HTML を返す（components/ReadingMode.tsx が「要約版で読む」を選んだときに読む）。
 * 2026-11-25 AdSense の点検: 記事ページの HTML に詳細版と要約版の両方を入れると同じ文がくり返されるため、要約版はここから読み込む。
 * ビルド時に全記事ぶんを静的に作る（lib/easy-api.ts の easyHtmlOf(article, noir)。実行時に描く作りでは Cloudflare で記事 JSON が読めず 404 だった）。
 * /api/ は robots.txt で巡回させず、念のため "X-Robots-Tag": "noindex, nofollow" も付ける。新しい見た目の記事（lib/noir.ts）は /api/easy/<slug>/noir
 */
export const dynamic = "force-static";
export const dynamicParams = true;
export const revalidate = false;

export function generateStaticParams() {
  return easyStaticParams(false);
}

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return easyResponse(slug, false);
}
