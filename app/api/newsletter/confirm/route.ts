import { siteConfig } from "@/site.config";
import { getSubscriber, newsletterEnv, putSubscriber, tokenMatches } from "@/lib/newsletter/store";

export const dynamic = "force-dynamic";

function back(status: string): Response {
  return new Response(null, {
    status: 303,
    headers: { Location: `${siteConfig.url}/newsletter?s=${status}`, "Cache-Control": "no-store" },
  });
}

/** 確認メールのリンク。登録を有効にして /newsletter へ戻す */
export async function GET(request: Request) {
  const env = await newsletterEnv();
  if (!env) return back("error");
  const url = new URL(request.url);
  const id = url.searchParams.get("id") ?? "";
  const kv = env.NEWSLETTER_KV!;
  const sub = await getSubscriber(kv, id);
  if (!sub || !tokenMatches(sub, url.searchParams.get("t"))) return back("invalid");
  if (sub.status !== "active") {
    sub.status = "active";
    sub.confirmedAt = new Date().toISOString();
    delete sub.unsubscribedAt;
    await putSubscriber(kv, id, sub);
  }
  return back("confirmed");
}
