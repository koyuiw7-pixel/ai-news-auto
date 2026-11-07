import { feedResponse } from "@/lib/feeds";
import { smartnewsFeedXml } from "@/lib/smartnews-feed";

export const dynamic = "force-static";

/**
 * スマートニュース用のフィード（SmartFormat / RSS 2.0）。中身の決まりは lib/smartnews-feed.ts。
 * ビルド時に作り、記事を足すデプロイのたびに入れ替わる（新しい記事が載り続ける）。
 */
export async function GET() {
  const { xml } = await smartnewsFeedXml();
  return feedResponse(xml);
}
