import { renderIndex, renderUrlset, sitemapEntries, SITEMAP_CHUNK, XML_HEADERS } from "@/lib/sitemap";

export const dynamic = "force-static";

/**
 * サイトマップ。URL が上限以内なら従来どおり1枚（urlset）、
 * 超えたら /sitemaps/0.xml, 1.xml … に分けてインデックスを返す（URL は変えない）
 */
export function GET() {
  const entries = sitemapEntries();
  const body =
    entries.length <= SITEMAP_CHUNK ? renderUrlset(entries) : renderIndex(Math.ceil(entries.length / SITEMAP_CHUNK));
  return new Response(body, { headers: XML_HEADERS });
}
