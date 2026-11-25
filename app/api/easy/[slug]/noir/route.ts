import { easyResponse, easyStaticParams } from "@/lib/easy-api";

/** 新しい見た目の記事（lib/noir.ts）の要約版。app/api/easy/[slug]/route.ts と同じく、ビルド時に静的に作る */
export const dynamic = "force-static";
export const dynamicParams = true;
export const revalidate = false;

export function generateStaticParams() {
  return easyStaticParams(true);
}

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return easyResponse(slug, true);
}
