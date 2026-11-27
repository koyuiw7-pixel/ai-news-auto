import { feedResponse } from "@/lib/feeds";
import { partnerFeedXml } from "@/lib/partner-xml";

export const dynamic = "force-static";

/** 配信先向けの汎用フィード（RSS 2.0・全文・暮らしとお金の記事だけ）。中身は lib/partner-xml.ts */
export async function GET() {
  const { xml } = await partnerFeedXml("/feeds/partner.xml");
  return feedResponse(xml);
}
