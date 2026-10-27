/**
 * メール購読者の保存先（Cloudflare KV の NEWSLETTER_KV）。
 *
 * キー: sub:<id>（id = メールアドレスの SHA-256 先頭32桁）
 * 値: Subscriber の JSON。一覧で読めるよう、状態・アドレス・解除トークンを metadata にも入れる
 *     （scripts/newsletter.py は KV の一覧 API だけで配信先を集める）。
 * 連投制限: rl:<IP のハッシュ>:<時> を数える（1時間で消える）。
 */
import { getCloudflareContext } from "@opennextjs/cloudflare";

export type SubscriberStatus = "pending" | "active" | "unsubscribed";

export type Subscriber = {
  email: string;
  status: SubscriberStatus;
  token: string;
  createdAt: string;
  confirmSentAt?: string;
  confirmedAt?: string;
  unsubscribedAt?: string;
  source?: string;
};

type KvNamespace = {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number; metadata?: unknown }): Promise<void>;
  delete(key: string): Promise<void>;
};

export type NewsletterEnv = {
  NEWSLETTER_KV?: KvNamespace;
  CF_EMAIL_TOKEN?: string;
  CLOUDFLARE_ACCOUNT_ID?: string;
  RESEND_API_KEY?: string;
  NEWSLETTER_FROM?: string;
  NEWSLETTER_SALT?: string;
};

/** Workers のバインディングと秘密情報。Cloudflare の外（Vercel・素の next dev）では null */
export async function newsletterEnv(): Promise<NewsletterEnv | null> {
  try {
    const { env } = await getCloudflareContext({ async: true });
    const e = env as unknown as NewsletterEnv;
    return e.NEWSLETTER_KV ? e : null;
  } catch {
    return null;
  }
}

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function subscriberId(email: string): Promise<string> {
  return (await sha256(email.trim().toLowerCase())).slice(0, 32);
}

export function newToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(18));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function getSubscriber(kv: KvNamespace, id: string): Promise<Subscriber | null> {
  if (!/^[0-9a-f]{32}$/.test(id)) return null;
  const raw = await kv.get(`sub:${id}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Subscriber;
  } catch {
    return null;
  }
}

export async function putSubscriber(kv: KvNamespace, id: string, sub: Subscriber): Promise<void> {
  await kv.put(`sub:${id}`, JSON.stringify(sub), {
    // c: 確認メールを送ったか（未送信の pending は scripts/newsletter.py が送る）
    metadata: { s: sub.status, e: sub.email, t: sub.token, c: sub.confirmSentAt ? 1 : 0 },
  });
}

/** トークンの照合（長さ・内容の違いで時間が変わらないように） */
export function tokenMatches(sub: Subscriber, token: string | null): boolean {
  if (!token || token.length !== sub.token.length) return false;
  let diff = 0;
  for (let i = 0; i < token.length; i++) diff |= token.charCodeAt(i) ^ sub.token.charCodeAt(i);
  return diff === 0;
}

/** 1時間あたりの上限を超えたら true（KV は結果整合なので厳密ではないが、機械的な連投は止まる） */
export async function rateLimited(env: NewsletterEnv, ip: string, limit = 5): Promise<boolean> {
  const kv = env.NEWSLETTER_KV!;
  const hour = Math.floor(Date.now() / 3_600_000);
  const key = `rl:${(await sha256(`${env.NEWSLETTER_SALT ?? "saisoku"}:${ip}`)).slice(0, 24)}:${hour}`;
  const count = Number((await kv.get(key)) ?? "0");
  if (count >= limit) return true;
  await kv.put(key, String(count + 1), { expirationTtl: 3600 });
  return false;
}
