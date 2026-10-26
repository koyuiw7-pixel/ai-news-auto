import { renderUrlset, sitemapChunkCount, sitemapEntries, SITEMAP_CHUNK, XML_HEADERS } from "@/lib/sitemap";

export const dynamic = "force-static";
export const dynamicParams = false;

/** 分割したサイトマップ（/sitemaps/0.xml …）。1枚に収まる間は 0.xml だけ（中身は /sitemap.xml と同じ） */
export function generateStaticParams() {
  return Array.from({ length: sitemapChunkCount() }, (_, i) => ({ id: `${i}.xml` }));
}

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const match = /^(\d+)\.xml$/.exec(id);
  const index = match ? Number(match[1]) : -1;
  const entries = sitemapEntries().slice(index * SITEMAP_CHUNK, (index + 1) * SITEMAP_CHUNK);
  if (index < 0 || entries.length === 0) return new Response("Not found", { status: 404 });
  return new Response(renderUrlset(entries), { headers: XML_HEADERS });
}
