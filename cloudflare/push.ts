/**
 * 速報のプッシュ通知（自前。外部の通知サービスは使わない）。cloudflare/worker.ts が /api/push/* をここに回す。
 *
 *   POST /api/push/subscribe    読者の購読を保存（画面 components/PushOptIn.tsx から）
 *   POST /api/push/unsubscribe  購読を消す
 *   POST /api/push/send         送る（Bearer PUSH_SEND_TOKEN。scripts/push_notify.py が速報の公開後に呼ぶ）
 *   GET  /api/push/stats        購読者数・今日の送信数（Bearer PUSH_SEND_TOKEN）
 *   Cron 毎朝 7:00（日本時間）  夜のあいだ保留した速報を1本だけ送る（flushHeld）
 *
 * 保存先は Workers KV の PUSH_KV（saisoku-push）:
 *   sub:<id>       購読（id = endpoint の SHA-256 先頭32桁）。送信時に一覧だけで読めるよう metadata にも入れる
 *   seen:<slug>    その記事をどう扱ったか（sent / held / limit / gap / stale / morning-drop）。同じ記事は二度と送らない
 *   held:<slug>    夜（22〜7時）に来た速報。朝 7:00 に一番新しい1本だけ送る
 *   day:<日付>     その日（日本時間）に送った回数と最後の時刻
 *   job:<id>       送信中の通知の中身（購読者が多いときに続きから送るため）
 *   last           最後の送信の結果
 *   rl:<IP>:<時>   登録の連投制限（1時間で消える）
 * 決まりごとの数字は lib/push-config.ts。
 */
import { PUSH_RULES, VAPID_PUBLIC_KEY } from "../lib/push-config";
import { b64urlDecode, sendPush, type PushTarget, type Vapid } from "./webpush";

export type KvListKey = { name: string; metadata?: unknown };
export type KvNamespace = {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number; metadata?: unknown }): Promise<void>;
  delete(key: string): Promise<void>;
  list(options: { prefix?: string; cursor?: string; limit?: number }): Promise<{ keys: KvListKey[]; list_complete: boolean; cursor?: string }>;
};

export type PushEnv = {
  PUSH_KV?: KvNamespace;
  VAPID_PRIVATE_KEY?: string;
  PUSH_SEND_TOKEN?: string;
  PUSH_SALT?: string;
  NEXT_PUBLIC_SITE_URL?: string;
};

type Ctx = { waitUntil(promise: Promise<unknown>): void };

/** 通知の中身（Service Worker public/sw.js が受け取る） */
type Payload = { title: string; body: string; url: string; icon: string; badge: string; tag: string; slug: string; generatedAt?: string };
type Sub = { endpoint: string; keys: { p256dh: string; auth: string }; createdAt: string };
type Day = { count: number; slugs: string[]; lastAt?: string };
type Delivery = { total: number; delivered: number; removed: number; failed: number; cursor: string | null };

/** 1回の呼び出しで送る上限（Workers の1回あたりの外部呼び出しの上限より十分少なく） */
const SEND_BUDGET = 4000;
const CONCURRENCY = 50;
/** プッシュサービスとして受け付ける送り先（Chrome・Edge・Firefox・Safari/iPhone） */
const PUSH_HOST =
  /^(fcm\.googleapis\.com|android\.googleapis\.com|([a-z0-9-]+\.)*push\.services\.mozilla\.com|([a-z0-9-]+\.)*push\.apple\.com|([a-z0-9-]+\.)*notify\.windows\.com)$/;

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

export async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const subId = async (endpoint: string) => (await sha256Hex(endpoint)).slice(0, 32);

/** 長さ・内容の違いで時間が変わらない比較 */
export function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function authorized(request: Request, env: PushEnv): boolean {
  const expected = env.PUSH_SEND_TOKEN ?? "";
  const header = request.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  return expected.length >= 16 && safeEqual(token, expected);
}

/** 画面からの呼び出しだけ受け付ける（同じオリジンの Origin ヘッダーが必要） */
export function sameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  return !!origin && origin === new URL(request.url).origin;
}

export async function readJson<T>(request: Request, max = 4096): Promise<T | null> {
  const text = await request.text();
  if (text.length > max) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

function validKeys(keys: unknown): keys is Sub["keys"] {
  if (!keys || typeof keys !== "object") return false;
  const { p256dh, auth } = keys as Record<string, unknown>;
  if (typeof p256dh !== "string" || typeof auth !== "string" || p256dh.length > 120 || auth.length > 40) return false;
  try {
    const pub = b64urlDecode(p256dh);
    return pub.length === 65 && pub[0] === 4 && b64urlDecode(auth).length === 16;
  } catch {
    return false;
  }
}

function validEndpoint(endpoint: unknown): endpoint is string {
  if (typeof endpoint !== "string" || endpoint.length > 1024) return false;
  try {
    const url = new URL(endpoint);
    return url.protocol === "https:" && !url.port && PUSH_HOST.test(url.hostname);
  } catch {
    return false;
  }
}

/** 1時間あたりの上限を超えたら true（KV は結果整合なので厳密ではないが、機械的な連投は止まる） */
async function rateLimited(env: PushEnv, request: Request, limit = 10): Promise<boolean> {
  const kv = env.PUSH_KV!;
  const ip = request.headers.get("cf-connecting-ip") ?? "unknown";
  const hour = Math.floor(Date.now() / 3_600_000);
  const key = `rl:${(await sha256Hex(`${env.PUSH_SALT ?? "saisoku-push"}:${ip}`)).slice(0, 24)}:${hour}`;
  const count = Number((await kv.get(key)) ?? "0");
  if (count >= limit) return true;
  await kv.put(key, String(count + 1), { expirationTtl: 3600 });
  return false;
}

async function putSub(kv: KvNamespace, id: string, sub: Sub): Promise<void> {
  const meta = { e: sub.endpoint, p: sub.keys.p256dh, a: sub.keys.auth };
  // metadata は 1024 バイトまで。長すぎる送り先（まれ）は本体だけに入れ、送信時に読み直す
  await kv.put(`sub:${id}`, JSON.stringify(sub), JSON.stringify(meta).length <= 1000 ? { metadata: meta } : {});
}

// ---------------------------------------------------------------------------
// 登録・解除（読者の画面から）
// ---------------------------------------------------------------------------

async function subscribe(request: Request, env: PushEnv): Promise<Response> {
  if (!sameOrigin(request)) return json({ ok: false, error: "forbidden" }, 403);
  const body = await readJson<{ subscription?: { endpoint?: unknown; keys?: unknown }; ts?: unknown }>(request);
  const sub = body?.subscription;
  if (!sub || !validEndpoint(sub.endpoint) || !validKeys(sub.keys)) return json({ ok: false, error: "invalid" }, 400);
  // ボット除け: 表示から0.8秒未満の送信は受け付けたふりをして捨てる（人はボタンを押して許可するまでに数秒かかる）
  if (!(Date.now() - Number(body?.ts ?? 0) > 800)) return json({ ok: true });
  if (await rateLimited(env, request)) return json({ ok: false, error: "rate-limited" }, 429);

  const kv = env.PUSH_KV!;
  const id = await subId(sub.endpoint);
  const existing = await kv.get(`sub:${id}`);
  const createdAt = existing ? ((JSON.parse(existing) as Sub).createdAt ?? new Date().toISOString()) : new Date().toISOString();
  const keys = sub.keys as Sub["keys"];
  await putSub(kv, id, { endpoint: sub.endpoint, keys: { p256dh: keys.p256dh, auth: keys.auth }, createdAt });
  return json({ ok: true });
}

async function unsubscribe(request: Request, env: PushEnv): Promise<Response> {
  if (!sameOrigin(request)) return json({ ok: false, error: "forbidden" }, 403);
  const body = await readJson<{ endpoint?: unknown; auth?: unknown }>(request);
  if (!body || !validEndpoint(body.endpoint)) return json({ ok: false, error: "invalid" }, 400);
  const kv = env.PUSH_KV!;
  const id = await subId(body.endpoint);
  const raw = await kv.get(`sub:${id}`);
  // 本人の端末だけが知っている auth の鍵が合うときだけ消す（他人の購読を消させない）。結果はいつも同じに見せる
  if (raw && typeof body.auth === "string" && safeEqual((JSON.parse(raw) as Sub).keys.auth, body.auth)) {
    await kv.delete(`sub:${id}`);
  }
  return json({ ok: true });
}

// ---------------------------------------------------------------------------
// 送信
// ---------------------------------------------------------------------------

function jstParts(date = new Date()): { day: string; hour: number } {
  const jst = new Date(date.getTime() + 9 * 3_600_000);
  return { day: jst.toISOString().slice(0, 10), hour: jst.getUTCHours() };
}

function isQuiet(date = new Date()): boolean {
  const { hour } = jstParts(date);
  return hour >= PUSH_RULES.quietFrom || hour < PUSH_RULES.quietUntil;
}

function vapidOf(env: PushEnv): Vapid | null {
  if (!env.VAPID_PRIVATE_KEY) return null;
  return { publicKey: VAPID_PUBLIC_KEY, privateKey: env.VAPID_PRIVATE_KEY, subject: "https://ai-tech-express.jp" };
}

function siteUrl(env: PushEnv): string {
  return (env.NEXT_PUBLIC_SITE_URL ?? "https://ai-tech-express.jp").replace(/\/$/, "");
}

const SLUG = /^[A-Za-z0-9][A-Za-z0-9_-]{0,160}$/;

function clip(text: unknown, max: number): string {
  const s = String(text ?? "").replace(/\s+/g, " ").trim();
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/** 呼び出し側の値から通知の中身を作る。リンクは必ずこのサイトの記事にする */
function buildPayload(input: Record<string, unknown>, env: PushEnv): Payload | null {
  const slug = String(input.slug ?? "");
  if (!SLUG.test(slug)) return null;
  const title = clip(input.title, 80);
  if (!title) return null;
  const site = siteUrl(env);
  return {
    title,
    body: clip(input.body, 120),
    url: `${site}/articles/${slug}?utm_source=push&utm_medium=web-push`,
    icon: `${site}/apple-icon`,
    badge: `${site}/icon`,
    tag: slug,
    slug,
    generatedAt: typeof input.generatedAt === "string" ? input.generatedAt : undefined,
  };
}

async function getJson<T>(kv: KvNamespace, key: string): Promise<T | null> {
  const raw = await kv.get(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function targetOf(key: KvListKey): PushTarget | null {
  const m = key.metadata as { e?: string; p?: string; a?: string } | undefined;
  return m?.e && m.p && m.a ? { endpoint: m.e, keys: { p256dh: m.p, auth: m.a } } : null;
}

/** 購読者に順に送る（cursor から。SEND_BUDGET 件で区切り、続きの cursor を返す）。消えた購読（404/410）は消す */
async function deliver(env: PushEnv, payload: Payload, cursor: string | null): Promise<Delivery> {
  const kv = env.PUSH_KV!;
  const vapid = vapidOf(env)!;
  const result: Delivery = { total: 0, delivered: 0, removed: 0, failed: 0, cursor: null };
  let next: string | undefined = cursor ?? undefined;
  do {
    const page = await kv.list({ prefix: "sub:", cursor: next, limit: 1000 });
    for (let i = 0; i < page.keys.length; i += CONCURRENCY) {
      await Promise.all(
        page.keys.slice(i, i + CONCURRENCY).map(async (key) => {
          result.total++;
          let target = targetOf(key);
          if (!target) {
            const sub = await getJson<Sub>(kv, key.name);
            target = sub ? { endpoint: sub.endpoint, keys: sub.keys } : null;
          }
          if (!target) return;
          try {
            const res = await sendPush(target, payload, vapid, { topic: payload.tag });
            if (res.ok) result.delivered++;
            else if (res.gone) {
              await kv.delete(key.name);
              result.removed++;
            } else {
              result.failed++;
              console.warn("[push] send failed", res.status, new URL(target.endpoint).hostname);
            }
          } catch (error) {
            result.failed++;
            console.warn("[push] send error", String(error));
          }
        }),
      );
    }
    next = page.list_complete ? undefined : page.cursor;
  } while (next && result.total < SEND_BUDGET);
  result.cursor = next ?? null;
  return result;
}

async function recordLast(kv: KvNamespace, slug: string, d: Delivery, append: boolean): Promise<void> {
  const prev = append ? await getJson<Delivery & { slug: string }>(kv, "last") : null;
  const base = prev && prev.slug === slug ? prev : { total: 0, delivered: 0, removed: 0, failed: 0 };
  await kv.put(
    "last",
    JSON.stringify({
      slug,
      at: new Date().toISOString(),
      total: base.total + d.total,
      delivered: base.delivered + d.delivered,
      removed: base.removed + d.removed,
      failed: base.failed + d.failed,
      done: !d.cursor,
    }),
  );
}

/** 送ると決めた通知を、日の回数に数えてから送る */
async function startJob(env: PushEnv, payload: Payload, reason: string): Promise<Record<string, unknown>> {
  const kv = env.PUSH_KV!;
  const { day } = jstParts();
  const record = (await getJson<Day>(kv, `day:${day}`)) ?? { count: 0, slugs: [] };
  record.count++;
  record.slugs.push(payload.slug);
  record.lastAt = new Date().toISOString();
  await kv.put(`day:${day}`, JSON.stringify(record), { expirationTtl: 3 * 86400 });
  await kv.put(`seen:${payload.slug}`, JSON.stringify({ status: "sent", reason, at: record.lastAt }), { expirationTtl: 90 * 86400 });
  const job = crypto.randomUUID();
  await kv.put(`job:${job}`, JSON.stringify(payload), { expirationTtl: 86400 });
  const d = await deliver(env, payload, null);
  await recordLast(kv, payload.slug, d, false);
  console.log("[push] sent", payload.slug, JSON.stringify(d));
  return { status: "sent", job, ...d };
}

/** その記事を送るか決める（同じ記事は二度と送らない・夜は保留・1日の上限・間隔） */
async function decide(env: PushEnv, payload: Payload, dryRun: boolean, urgent = false): Promise<Record<string, unknown>> {
  const kv = env.PUSH_KV!;
  const seen = await getJson<{ status: string }>(kv, `seen:${payload.slug}`);
  // urgent（大津波警報・津波警報・震度6弱以上）: 夜間・1日の上限・間隔を超えて送る。まだ送っていなければ続報でも送る
  if (seen && !(urgent && seen.status !== "sent")) return { status: "duplicate", previous: seen.status };
  if (urgent) {
    if (dryRun) return { status: "would-send", urgent, dryRun };
    await kv.delete(`held:${payload.slug}`);
    return startJob(env, payload, "safety");
  }
  const mark = async (status: string) => {
    if (!dryRun) await kv.put(`seen:${payload.slug}`, JSON.stringify({ status, at: new Date().toISOString() }), { expirationTtl: 90 * 86400 });
    return { status, dryRun };
  };

  const generated = payload.generatedAt ? Date.parse(payload.generatedAt) : NaN;
  if (Number.isFinite(generated) && Date.now() - generated > PUSH_RULES.maxAgeMin * 60_000) return mark("stale");
  if (isQuiet()) {
    if (!dryRun) await kv.put(`held:${payload.slug}`, JSON.stringify(payload), { expirationTtl: 12 * 3600 });
    return mark("held");
  }
  const record = await getJson<Day>(kv, `day:${jstParts().day}`);
  if (record && record.count >= PUSH_RULES.perDay) return mark("limit");
  if (record?.lastAt && Date.now() - Date.parse(record.lastAt) < PUSH_RULES.minGapMin * 60_000) return mark("gap");
  if (dryRun) return { status: "would-send", dryRun };
  return startJob(env, payload, "breaking");
}

/** 朝 7:00（日本時間）: 夜のあいだ保留した速報のうち、一番新しい1本だけ送る（朝に何度も鳴らさない） */
export async function flushHeld(env: PushEnv): Promise<Record<string, unknown>> {
  const kv = env.PUSH_KV;
  if (!kv || !vapidOf(env)) return { status: "unavailable" };
  const held: Payload[] = [];
  let cursor: string | undefined;
  do {
    const page = await kv.list({ prefix: "held:", cursor });
    for (const key of page.keys) {
      const p = await getJson<Payload>(kv, key.name);
      if (p) held.push(p);
      await kv.delete(key.name);
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  if (!held.length) return { status: "none" };
  held.sort((a, b) => (b.generatedAt ?? "").localeCompare(a.generatedAt ?? ""));
  const [pick, ...rest] = held;
  for (const p of rest) {
    await kv.put(`seen:${p.slug}`, JSON.stringify({ status: "morning-drop", at: new Date().toISOString() }), { expirationTtl: 90 * 86400 });
  }
  const record = await getJson<Day>(kv, `day:${jstParts().day}`);
  if (record && record.count >= PUSH_RULES.perDay) return { status: "limit", slug: pick.slug };
  const result = await startJob(env, pick, "morning");
  // 朝のうちに送り切れなかった分（購読者が非常に多いとき）は続きから送る
  let next = result.cursor as string | null;
  while (next) {
    const d = await deliver(env, pick, next);
    await recordLast(kv, pick.slug, d, true);
    next = d.cursor;
  }
  return { ...result, dropped: rest.map((p) => p.slug) };
}

async function send(request: Request, env: PushEnv): Promise<Response> {
  if (!authorized(request, env)) return json({ ok: false, error: "unauthorized" }, 401);
  if (!vapidOf(env)) return json({ ok: false, error: "vapid-missing" }, 503);
  const body = await readJson<Record<string, unknown>>(request, 16_384);
  if (!body) return json({ ok: false, error: "bad-request" }, 400);
  const kv = env.PUSH_KV!;

  // 続きから送る（購読者が SEND_BUDGET を超えるとき、呼び出し側が cursor を渡して繰り返す）
  if (typeof body.job === "string" && typeof body.cursor === "string") {
    const payload = await getJson<Payload>(kv, `job:${body.job.replace(/[^0-9a-f-]/g, "")}`);
    if (!payload) return json({ ok: false, error: "job-not-found" }, 404);
    const d = await deliver(env, payload, body.cursor);
    await recordLast(kv, payload.slug, d, true);
    return json({ ok: true, status: "sent", job: body.job, ...d });
  }

  // 動作確認: 指定した1件の購読にだけ送る（ほかの読者には届かない。回数にも数えない）
  if (body.test === true) {
    if (!validEndpoint(body.endpoint)) return json({ ok: false, error: "invalid-endpoint" }, 400);
    const sub = await getJson<Sub>(kv, `sub:${await subId(body.endpoint)}`);
    if (!sub) return json({ ok: false, error: "not-subscribed" }, 404);
    const payload = buildPayload({ slug: "test", title: "テスト通知", body: "プッシュ通知の動作確認です。", ...body }, env)!;
    const res = await sendPush({ endpoint: sub.endpoint, keys: sub.keys }, payload, vapidOf(env)!, { ttl: 600 });
    if (res.gone) await kv.delete(`sub:${await subId(sub.endpoint)}`);
    return json({ ok: res.ok, status: "test", pushStatus: res.status });
  }

  const payload = buildPayload(body, env);
  if (!payload) return json({ ok: false, error: "invalid-payload" }, 400);
  return json({ ok: true, ...(await decide(env, payload, body.dryRun === true, body.urgent === true)) });
}

async function stats(request: Request, env: PushEnv): Promise<Response> {
  if (!authorized(request, env)) return json({ ok: false, error: "unauthorized" }, 401);
  const kv = env.PUSH_KV!;
  let subscribers = 0;
  let cursor: string | undefined;
  do {
    const page = await kv.list({ prefix: "sub:", cursor });
    subscribers += page.keys.length;
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  const held = (await kv.list({ prefix: "held:" })).keys.map((k) => k.name.slice(5));
  const { day } = jstParts();
  return json({
    ok: true,
    subscribers,
    today: (await getJson<Day>(kv, `day:${day}`)) ?? { count: 0, slugs: [] },
    held,
    last: await getJson(kv, "last"),
    rules: PUSH_RULES,
  });
}

export async function handlePush(request: Request, url: URL, env: PushEnv, _ctx: Ctx): Promise<Response> {
  if (!env.PUSH_KV) return json({ ok: false, error: "unavailable" }, 503);
  const route = url.pathname.replace(/\/$/, "");
  try {
    if (request.method === "POST" && route === "/api/push/subscribe") return await subscribe(request, env);
    if (request.method === "POST" && route === "/api/push/unsubscribe") return await unsubscribe(request, env);
    if (request.method === "POST" && route === "/api/push/send") return await send(request, env);
    if (request.method === "GET" && route === "/api/push/stats") return await stats(request, env);
  } catch (error) {
    console.error("[push] error", String(error));
    return json({ ok: false, error: "server-error" }, 500);
  }
  return json({ ok: false, error: "not-found" }, 404);
}
