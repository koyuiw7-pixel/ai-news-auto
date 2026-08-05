export const dynamic = "force-static";

/**
 * AdSense の所有権確認と、なりすまし広告在庫の防止に使われるファイル。
 * ルート直下（/ads.txt）に置く必要があるため、静的ルートとして配信する。
 *
 * NEXT_PUBLIC_ADSENSE_CLIENT（ca-pub-XXXXXXXXXXXXXXXX）を設定すると自動で有効になる。
 * 未設定のときは空ファイルを返す（誤った publisher ID を晒さないため）。
 */
export function GET() {
  const client = process.env.NEXT_PUBLIC_ADSENSE_CLIENT ?? "";
  const publisherId = client.replace(/^ca-/, ""); // ads.txt では "pub-..." 表記

  const lines = publisherId.startsWith("pub-")
    ? [
        "# Google AdSense",
        `google.com, ${publisherId}, DIRECT, f08c47fec0942fa0`,
      ]
    : ["# NEXT_PUBLIC_ADSENSE_CLIENT が未設定のため、掲載中の広告配信事業者はありません"];

  return new Response(lines.join("\n") + "\n", {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
