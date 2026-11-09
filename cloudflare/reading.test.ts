/** 記事の読まれ方の計測（lib/reading.ts の決まり・cloudflare/reading.ts の記録と集計）の回帰テスト。本番 KV には通信しない。node scripts/test_aff.mjs */
import assert from "node:assert/strict";
import { handleAff } from "./aff";
import { depthBucket, normalizeAdPositions, parseReading, timeBucket } from "../lib/reading";

const O = "https://ai-tech-express.jp";
const records = new Map<string, { value: string; metadata?: unknown; expirationTtl?: number }>();
const cache = new Map<string, { response: Response; until: number }>();
Object.defineProperty(globalThis, "caches", { configurable: true, value: { default: {
  match: async (request: Request) => {
    const item = cache.get(request.url);
    return item && item.until > Date.now() ? item.response.clone() : undefined;
  },
  put: async (request: Request, response: Response) => {
    cache.set(request.url, { response: response.clone(), until: Date.now() + Number(response.headers.get("cache-control")?.split("=")[1]) * 1000 });
  },
} } });
const kv = {
  get: async (key: string) => records.get(key)?.value ?? null,
  delete: async (key: string) => { records.delete(key); },
  put: async (key: string, value: string, options?: { metadata?: unknown; expirationTtl?: number }) => { records.set(key, { value, ...options }); },
  list: async ({ prefix = "", cursor = "0" }: { prefix?: string; cursor?: string }) => {
    const keys = [...records].filter(([key]) => key.startsWith(prefix)).map(([name, item]) => ({ name, metadata: item.metadata }));
    const start = Number(cursor), end = start + 3;
    return { keys: keys.slice(start, end), list_complete: end >= keys.length, cursor: String(end) };
  },
};
const env = { AFF_KV: kv, AFF_STATS_TOKEN: "test-only-not-a-production-token" };
const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Barcelona 350.0";
const base = { p: "docomo-data-leak-what-to-do", s: "threads", d: 40, t: 30, n: false, a: ["action-ad"], x: "" };
async function read(body: unknown, headers: Record<string, string> = {}, ip = "198.51.100.7") {
  const req = new Request(`${O}/api/aff/read`, { method: "POST", body: JSON.stringify(body), headers: {
    origin: O, "sec-fetch-site": "same-origin", "user-agent": IPHONE, "cf-connecting-ip": ip, ...headers,
  } });
  const pending: Promise<unknown>[] = [];
  const res = await handleAff(req, new URL(req.url), env, { waitUntil: (p) => pending.push(p) });
  await Promise.all(pending);
  return res;
}
async function reading(token = env.AFF_STATS_TOKEN) {
  const date = new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 10);
  const req = new Request(`${O}/api/aff/reading?date=${date}`, { headers: { authorization: `Bearer ${token}` } });
  return handleAff(req, new URL(req.url), env, { waitUntil: () => {} });
}
const keys = () => [...records.keys()].filter((key) => key.startsWith("r:"));
let passed = 0;
async function test(name: string, run: () => void | Promise<void>) { records.clear(); cache.clear(); await run(); passed++; console.log(`ok reading ${name}`); }

await test("区切りへの丸め", () => {
  assert.equal(timeBucket(0), 0);
  assert.equal(timeBucket(4.9), 0);
  assert.equal(timeBucket(12), 10);
  assert.equal(timeBucket(59), 30);
  assert.equal(timeBucket(10_000), 600);
  assert.equal(timeBucket(Number.NaN), 0);
  assert.equal(depthBucket(0.05), 0);
  assert.equal(depthBucket(0.349), 30);
  assert.equal(depthBucket(0.97), 100);
  assert.equal(depthBucket(3), 100);
  assert.equal(depthBucket(-1), 0);
  assert.deepEqual(normalizeAdPositions(["action-ad-1", "action-ad", "ranking-end", "BAD POS", "ranking-inline-2"]), ["action-ad", "ranking-end", "ranking-inline"]);
});

await test("送信の中身の確かめ", () => {
  assert.deepEqual(parseReading(base), base);
  assert.equal(parseReading({ ...base, p: "_home" }), null);
  assert.equal(parseReading({ ...base, p: "digest-20261109" }), null);
  assert.equal(parseReading({ ...base, p: "../x" }), null);
  assert.equal(parseReading({ ...base, s: "evil" }), null);
  assert.equal(parseReading({ ...base, s: "internal" })?.s, "internal");
  assert.equal(parseReading({ ...base, d: 45 }), null);
  assert.equal(parseReading({ ...base, d: 110 }), null);
  assert.equal(parseReading({ ...base, t: 31 }), null);
  assert.equal(parseReading({ ...base, n: 1 }), null);
  assert.equal(parseReading({ ...base, a: ["x".repeat(40)] }), null);
  assert.equal(parseReading({ ...base, a: Array(9).fill("action-ad") }), null);
  assert.equal(parseReading({ ...base, x: "https://evil.example" }), null);
  assert.equal(parseReading(null), null);
});

await test("記録は同じ人・同じ記事で1キー、最新で上書き", async () => {
  assert.equal((await read(base)).status, 204);
  assert.equal((await read({ ...base, d: 90, t: 120, n: true, a: ["action-ad", "ranking-end"], x: "nextread" })).status, 204);
  assert.equal(keys().length, 1);
  const meta = records.get(keys()[0])!.metadata as Record<string, unknown>;
  assert.deepEqual(meta, { p: base.p, s: "threads", d: 90, t: 120, n: 1, a: "action-ad,ranking-end", x: "nextread" });
  assert.equal(records.get(keys()[0])!.expirationTtl, 90 * 86400);
  assert.ok(!JSON.stringify([...records]).includes("198.51.100.7"), "IP を保存しない");
  // 別の人・別の記事は別のキー
  await read(base, {}, "198.51.100.8");
  await read({ ...base, p: "heater-power-cost-per-hour" });
  assert.equal(keys().length, 3);
});

await test("記録しないもの", async () => {
  assert.equal((await read(base, { "user-agent": "Mozilla/5.0 HeadlessChrome/120" })).status, 204);
  assert.equal((await read(base, { "user-agent": "facebookexternalhit/1.1" })).status, 204);
  assert.equal((await read(base, { "x-saisoku-internal": "1" })).status, 204);
  assert.equal((await read(base, { referer: `${O}/articles/x?_internal=1` })).status, 204);
  assert.equal((await read(base, { dnt: "1" })).status, 204);
  assert.equal((await read(base, { "sec-gpc": "1" })).status, 204);
  assert.equal(keys().length, 0);
  assert.equal((await read(base, { origin: "https://evil.example" })).status, 403);
  assert.equal((await read(base, { "sec-fetch-site": "cross-site" })).status, 403);
  assert.equal((await read({ ...base, d: 33 })).status, 400);
  const get = new Request(`${O}/api/aff/read`);
  assert.equal((await handleAff(get, new URL(get.url), env, { waitUntil: () => {} })).status, 405);
  assert.equal(keys().length, 0);
});

await test("連投は間引く", async () => {
  for (let i = 0; i < 70; i++) await read({ ...base, p: `article-${i}` });
  assert.equal(keys().length, 60);
});

await test("集計（深さ・時間・次の記事・押した場所・PR 枠）", async () => {
  await read({ ...base, d: 20, t: 5, a: [] }, {}, "203.0.113.1");
  await read({ ...base, d: 60, t: 30, a: ["action-ad"] }, {}, "203.0.113.2");
  await read({ ...base, d: 100, t: 180, n: true, a: ["action-ad", "ranking-end"], x: "nextread" }, {}, "203.0.113.3");
  await read({ ...base, s: "internal", p: "heater-power-cost-per-hour", d: 80, t: 60, x: "body" }, {}, "203.0.113.3");
  assert.equal((await reading("wrong-token-wrong-token")).status, 401);
  const res = await reading();
  assert.equal(res.status, 200);
  const body = await res.json() as {
    total: { views: number; reached: Record<string, number>; engaged: Record<string, number>; nextReadSeen: number; internalClicks: number; exits: Record<string, number>; adSeen: Record<string, number>; medianSecondsBucket: number };
    byPage: { page: string; views: number }[]; bySource: { source: string; views: number }[]; truncated: boolean;
  };
  assert.equal(body.truncated, false);
  assert.equal(body.total.views, 4);
  assert.deepEqual(body.total.reached, { d25: 3, d50: 3, d75: 2, d100: 1 });
  assert.deepEqual(body.total.engaged, { s10: 3, s30: 3, s60: 2, s180: 1 });
  assert.equal(body.total.medianSecondsBucket, 30);
  assert.equal(body.total.nextReadSeen, 1);
  assert.equal(body.total.internalClicks, 2);
  assert.deepEqual(body.total.exits, { nextread: 1, body: 1 });
  assert.deepEqual(body.total.adSeen, { "action-ad": 3, "ranking-end": 1 });
  assert.deepEqual(body.byPage.map((r) => [r.page, r.views]), [[base.p, 3], ["heater-power-cost-per-hour", 1]]);
  assert.deepEqual(body.bySource.map((r) => [r.source, r.views]), [["threads", 3], ["internal", 1]]);
});

console.log(`reading tests: ${passed} passed`);
