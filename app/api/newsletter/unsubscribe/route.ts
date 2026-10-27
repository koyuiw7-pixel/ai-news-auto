import { getSubscriber, newsletterEnv, putSubscriber, tokenMatches } from "@/lib/newsletter/store";

export const dynamic = "force-dynamic";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

/**
 * 配信停止。POST のみ（メールのリンク先を自動で開くセキュリティ製品に、勝手に解除されないように）。
 * id と t はクエリでも本文でもよい。クエリで来るのはメールソフトの「ワンクリック解除」（RFC 8058）
 */
export async function POST(request: Request) {
  const env = await newsletterEnv();
  if (!env) return json({ ok: false, error: "unavailable" }, 503);
  const url = new URL(request.url);
  let id = url.searchParams.get("id");
  let token = url.searchParams.get("t");
  if (!id || !token) {
    try {
      const body = (await request.json()) as { id?: string; t?: string };
      id = body.id ?? null;
      token = body.t ?? null;
    } catch {
      return json({ ok: false, error: "bad-request" }, 400);
    }
  }
  const kv = env.NEWSLETTER_KV!;
  const sub = await getSubscriber(kv, id ?? "");
  if (!sub || !tokenMatches(sub, token)) return json({ ok: false, error: "invalid" }, 400);
  if (sub.status !== "unsubscribed") {
    sub.status = "unsubscribed";
    sub.unsubscribedAt = new Date().toISOString();
    await putSubscriber(kv, id!, sub);
  }
  return json({ ok: true });
}
