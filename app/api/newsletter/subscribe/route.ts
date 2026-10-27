import { siteConfig } from "@/site.config";
import { confirmMail } from "@/lib/newsletter/emails";
import { mailerConfigured, sendMail } from "@/lib/newsletter/mailer";
import {
  getSubscriber,
  newToken,
  newsletterEnv,
  putSubscriber,
  rateLimited,
  subscriberId,
  type Subscriber,
} from "@/lib/newsletter/store";

export const dynamic = "force-dynamic";

const EMAIL_RE = /^[^\s@<>()[\]\\,;:"]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/;
/** 確認メールの再送間隔 */
const RESEND_AFTER_MS = 10 * 60_000;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

/**
 * 登録の受付（ダブルオプトイン）。
 * state: sent=確認メールを送った / queued=受け付けた（送信設定がまだ。設定後にまとめて送る）
 * 登録済みかどうかは返さない（他人のアドレスの登録有無を調べられないように）
 */
export async function POST(request: Request) {
  const env = await newsletterEnv();
  if (!env) return json({ ok: false, error: "unavailable" }, 503);

  let body: { email?: unknown; company?: unknown; ts?: unknown; source?: unknown };
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "bad-request" }, 400);
  }

  // ボット除け: 見えない入力欄に何か入っている／表示から1.5秒未満の送信は、受け付けたふりをして捨てる
  const elapsed = Date.now() - Number(body.ts ?? 0);
  if ((typeof body.company === "string" && body.company !== "") || !(elapsed > 1500)) {
    return json({ ok: true, state: "sent" });
  }

  const email = String(body.email ?? "").trim().toLowerCase();
  if (email.length > 254 || !EMAIL_RE.test(email)) return json({ ok: false, error: "invalid-email" }, 400);

  const ip = request.headers.get("cf-connecting-ip") ?? request.headers.get("x-forwarded-for") ?? "unknown";
  if (await rateLimited(env, ip)) return json({ ok: false, error: "rate-limited" }, 429);

  const kv = env.NEWSLETTER_KV!;
  const id = await subscriberId(email);
  const now = new Date();
  const existing = await getSubscriber(kv, id);
  if (existing?.status === "active") return json({ ok: true, state: "sent" });

  const recentlySent =
    existing?.confirmSentAt && now.getTime() - new Date(existing.confirmSentAt).getTime() < RESEND_AFTER_MS;
  const sub: Subscriber = {
    email,
    status: "pending",
    token: existing?.token ?? newToken(),
    createdAt: existing?.createdAt ?? now.toISOString(),
    confirmSentAt: existing?.confirmSentAt,
    source: String(body.source ?? "").slice(0, 40) || existing?.source,
  };

  if (recentlySent) return json({ ok: true, state: "sent" });

  let state: "sent" | "queued" = "queued";
  if (mailerConfigured(env)) {
    const url = `${siteConfig.url}/api/newsletter/confirm?id=${id}&t=${sub.token}`;
    const result = await sendMail(env, confirmMail(email, url));
    if (result.sent) {
      sub.confirmSentAt = now.toISOString();
      state = "sent";
    } else {
      console.error("[newsletter] confirm mail failed", result.reason);
    }
  }
  await putSubscriber(kv, id, sub);
  return json({ ok: true, state });
}
