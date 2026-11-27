import { feedResponse } from "@/lib/feeds";
import { partnerFeedXml } from "@/lib/partner-xml";

export const dynamic = "force-static";

/**
 * 配信先向けの汎用フィード（前からある URL。中身は /feeds/partner.xml と同じ。lib/partner-xml.ts）。
 * /feed.xml（要約のみ・全記事）は読者・RSSリーダー向けにそのまま残す。
 */
export async function GET() {
  const { xml } = await partnerFeedXml("/feeds/news.xml");
  return feedResponse(xml);
}
