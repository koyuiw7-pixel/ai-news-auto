/** 実ASP・本番KVへ通信しない回帰テスト。node scripts/test_aff.mjs */
import assert from "node:assert/strict";
import { handleAff } from "./aff";
import { sourceOf, GUIDE_PATH, FUNNEL, validFunnelEvent } from "../lib/revenue-funnel";

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
    const start = Number(cursor), end = start + 2;
    return { keys: keys.slice(start, end), list_complete: end >= keys.length, cursor: String(end) };
  },
};
const env = { AFF_KV: kv, AFF_STATS_TOKEN: "test-only-not-a-production-token" };
const headers = { origin: "https://test.invalid", "sec-fetch-site": "same-origin", "user-agent": "Mozilla/5.0 Safari/605.1", "cf-connecting-ip": "192.0.2.1" };
const event = { funnel: FUNNEL, stage: "guide_view", path: GUIDE_PATH, source: "google", pos: "other", choice: "" };
async function call(path: string, body?: unknown, overrides = {}, method = "POST", bindings = env) {
  const req = new Request(`https://test.invalid${path}`, { method, headers: { ...headers, ...overrides }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const pending: Promise<unknown>[] = [];
  const res = await handleAff(req, new URL(req.url), bindings, { waitUntil: (p) => pending.push(p) });
  await Promise.all(pending);
  return res;
}
let passed = 0;
async function test(name: string, run: () => void | Promise<void>) { await run(); passed++; console.log(`ok ${name}`); }
const reset = () => { records.clear(); cache.clear(); };
const stats = async () => (await call("/api/aff/stats", undefined, { authorization: `Bearer ${env.AFF_STATS_TOKEN}` }, "GET")).json();

await test("unauthorized stats reveal nothing", async () => assert.equal((await call("/api/aff/stats", undefined, {}, "GET")).status, 401));
await test("cross-origin event rejected", async () => { assert.equal((await call("/api/aff/event", event, { origin: "https://evil.invalid" })).status, 403); assert.equal(records.size, 0); });
await test("GET cannot record events", async () => assert.equal((await call("/api/aff/event", undefined, {}, "GET")).status, 405));
await test("bots, inspection tool, DNT and GPC excluded", async () => { for (const h of [{ "user-agent": "Googlebot" }, { "user-agent": "Mozilla/5.0 (compatible; Google-InspectionTool/1.0)" }, { "user-agent": "GoogleOther" }, { "user-agent": "HeadlessChrome" }, { dnt: "1" }, { "sec-gpc": "1" }]) await call("/api/aff/event", event, h); assert.equal(records.size, 0); });
await test("missing KV fails closed", async () => { await call("/api/aff/event", event, {}, "POST", { ...env, AFF_KV: undefined } as unknown as typeof env); assert.equal(records.size, 0); });
await test("unknown funnel, query strings, raw sources and choices rejected", async () => {
  for (const change of [{ funnel: "other" }, { path: GUIDE_PATH + "?email=private" }, { source: "https://private.invalid" }, { stage: "sale" }, { choice: "wrong" }, { pos: "bad space" }]) assert.equal((await call("/api/aff/event", { ...event, ...change })).status, 400);
  assert.equal(records.size, 0);
});
await test("visible event writes only bounded metadata and expires in 90 days", async () => {
  assert.equal((await call("/api/aff/event", event)).status, 204);
  const item = [...records.values()][0]; assert.equal(item.expirationTtl, 90 * 86400);
  const saved = JSON.stringify(item); assert(!saved.includes("192.0.2.1")); assert(!saved.includes("Mozilla")); assert(!saved.includes(env.AFF_STATS_TOKEN));
  assert.match((item.metadata as { v: string }).v, /^[a-f0-9]{16}$/);
});
await test("repeat event deduped; different stages remain", async () => {
  await call("/api/aff/event", event); assert.equal(records.size, 1);
  await call("/api/aff/event", { ...event, stage: "comparison_view" }); assert.equal(records.size, 2);
});
await test("free and sponsored choices counted separately", async () => {
  for (const choice of ["dify-cloud", "local-pc", "xserver-dify"]) await call("/api/aff/event", { ...event, stage: "choice_click", choice });
  const result = await stats(); assert.equal(result.clicks, 0); assert.equal(result.funnel.byChoice.length, 3); assert.equal(result.funnel.stages.find((r: { stage: string }) => r.stage === "choice_click").visitors, 1);
});
await test("legacy affiliate counts, positions and A8 plus codes unchanged", async () => {
  await call("/api/aff/click", { p: "A+B+C", path: GUIDE_PATH, pos: "choose-table" });
  await call("/api/aff/click", { p: "A+B+C", path: GUIDE_PATH, pos: "choose-table" });
  const result = await stats(); assert.equal(result.clicks, 1); assert.equal(result.byProgram[0].program, "A+B+C"); assert.equal(result.byPosition[0].pos, "choose-table");
  assert.equal(result.funnel.stages.find((r: { stage: string }) => r.stage === "guide_view").events, 1);
});
await test("new events cannot exhaust old click burst allowance", async () => {
  reset();
  for (let i = 0; i < 21; i++) await call("/api/aff/event", { ...event, stage: "guide_click", path: `/articles/article-${i}` });
  assert.equal(records.size, 20);
  await call("/api/aff/click", { p: "legacy", path: GUIDE_PATH });
  assert.equal((await stats()).clicks, 1);
});
await test("pagination aggregates entries and source stages", async () => {
  const result = await stats(); assert.equal(result.funnel.byEntry.length, 20); assert.equal(result.funnel.bySourceStage[0].events, 20); assert.equal(result.funnel.truncated, false);
});
await test("source classification retains no query or referrer text", () => {
  assert.equal(sourceOf("?utm_source=twitter&utm_term=secret", "", "https://test.invalid"), "x");
  assert.equal(sourceOf("", "https://www.google.co.jp/search?q=secret", "https://test.invalid"), "google");
  assert.equal(sourceOf("", "https://google.com.evil.invalid", "https://test.invalid"), "other");
  assert.equal(sourceOf("", "https://test.invalid/private", "https://test.invalid"), "internal");
  assert.equal(sourceOf("?utm_source=private-person", "", "https://test.invalid"), "other");
});
await test("stage cannot be attached to unrelated pages", () => {
  assert.equal(validFunnelEvent("guide_view", "/", ""), false);
  assert.equal(validFunnelEvent("entry_view", "/guides", ""), true);
  assert.equal(validFunnelEvent("choice_click", GUIDE_PATH, "dify-cloud"), true);
});
console.log(`${passed} measurement checks passed; no external requests.`);
