/** 実ASP・本番KVへ通信しない回帰テスト。node scripts/test_aff.mjs */
import assert from "node:assert/strict";
import { handleAff } from "./aff";
import { ARTICLE_MEASUREMENT_VERSION, ARTICLE_PATHS, sourceOf, GUIDE_PATH, FUNNEL, validFunnelEvent } from "../lib/revenue-funnel";

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
const articleEvent = { ...event, stage: "article_view", path: ARTICLE_PATHS[0], articleMeasurement: ARTICLE_MEASUREMENT_VERSION };
await test("article measurement requires the exact pages and client version", async () => {
  reset();
  for (const change of [{ path: "/guides/unrelated" }, { path: GUIDE_PATH }, { path: ARTICLE_PATHS[0] + "?private=1" }, { articleMeasurement: undefined }, { articleMeasurement: 1 }, { articleMeasurement: "2" }]) {
    assert.equal((await call("/api/aff/event", { ...articleEvent, ...change })).status, 400);
  }
  assert.equal((await call("/api/aff/event", { ...event, articleMeasurement: 2 })).status, 400);
  assert.equal(records.size, 0);
});
await test("new article events keep bot and privacy exclusions", async () => {
  for (const h of [{ "user-agent": "Google-InspectionTool" }, { "user-agent": "HeadlessChrome" }, { dnt: "1" }, { "sec-gpc": "1" }]) await call("/api/aff/event", articleEvent, h);
  assert.equal(records.size, 0);
});
await test("both article pages and sources keep separate matched denominators", async () => {
  reset();
  await call("/api/aff/event", articleEvent);
  await call("/api/aff/event", { ...articleEvent, stage: "guide_click" });
  await call("/api/aff/event", { ...articleEvent, path: ARTICLE_PATHS[1], source: "bing" });
  await call("/api/aff/event", { ...articleEvent, source: "threads" }, { "cf-connecting-ip": "192.0.2.2" });
  const result = await stats();
  const [a, b] = result.funnel.articleMeasurement.byArticle;
  assert.equal(a.viewEvents, 2); assert.equal(a.viewVisitors, 2); assert.equal(a.comparisonClickEvents, 1); assert.equal(a.matchedReaderClickVisitors, 1); assert.equal(a.observedReaderClickRate, .5);
  assert.equal(b.viewVisitors, 1); assert.equal(b.comparisonClickEvents, 0); assert.equal(b.observedReaderClickRate, 0);
  assert.equal(result.funnel.articleMeasurement.byArticleSource.length, 3);
  assert.equal(result.funnel.articleMeasurement.byArticleSource.find((r: { source: string }) => r.source === "google").observedReaderClickRate, 1);
  assert.equal(result.funnel.byEntry[0].events, 1);
  assert.equal(result.clicks, 0);
});
await test("legacy guide clicks remain counted but do not create a v2 denominator", async () => {
  reset();
  await call("/api/aff/event", { ...event, stage: "guide_click", path: ARTICLE_PATHS[0] });
  await call("/api/aff/event", articleEvent, { "cf-connecting-ip": "192.0.2.2" });
  await call("/api/aff/event", { ...articleEvent, stage: "guide_click" }, { "cf-connecting-ip": "192.0.2.2" });
  const result = await stats(); const a = result.funnel.articleMeasurement.byArticle[0];
  assert.equal(result.funnel.byEntry[0].events, 2); assert.equal(a.legacyClickEventsExcluded, 1); assert.equal(a.viewVisitors, 1); assert.equal(a.comparisonClickVisitors, 1); assert.equal(a.observedReaderClickRate, 1);
});
await test("click arriving before view reports missing view then matches after arrival", async () => {
  reset();
  await call("/api/aff/event", { ...articleEvent, stage: "guide_click" });
  let a = (await stats()).funnel.articleMeasurement.byArticle[0];
  assert.equal(a.clickVisitorsWithoutObservedView, 1); assert.equal(a.observedReaderClickRate, null); assert.equal(a.matchedReaderClickVisitors, 0);
  await call("/api/aff/event", articleEvent);
  a = (await stats()).funnel.articleMeasurement.byArticle[0];
  assert.equal(a.clickVisitorsWithoutObservedView, 0); assert.equal(a.observedReaderClickRate, 1); assert.equal(a.matchedReaderClickVisitors, 1);
});
await test("view and click from different sources do not invent source-level matching", async () => {
  reset();
  await call("/api/aff/event", articleEvent);
  await call("/api/aff/event", { ...articleEvent, stage: "guide_click", source: "direct" });
  const result = await stats();
  const direct = result.funnel.articleMeasurement.byArticleSource.find((r: { source: string }) => r.source === "direct");
  assert.equal(direct.viewVisitors, 0); assert.equal(direct.clickVisitorsWithoutObservedView, 1); assert.equal(direct.observedReaderClickRate, null);
  assert.equal(result.funnel.articleMeasurement.byArticle[0].matchedReaderClickVisitors, 1);
});
await test("article deduplication, legacy advertisement and retention are preserved", async () => {
  reset();
  for (let i = 0; i < 2; i++) { await call("/api/aff/event", articleEvent); await call("/api/aff/event", { ...articleEvent, stage: "guide_click" }); }
  await call("/api/aff/click", { p: "A+B+C", path: ARTICLE_PATHS[0], pos: "existing" });
  const result = await stats(); const a = result.funnel.articleMeasurement.byArticle[0];
  assert.equal(a.viewEvents, 1); assert.equal(a.comparisonClickEvents, 1); assert.equal(result.clicks, 1); assert.equal(result.byProgram[0].program, "A+B+C");
  for (const [key, item] of records) assert.equal(item.expirationTtl, (key.startsWith("f:") ? 90 : 400) * 86400);
});
await test("dates do not join previous-day article readers to today's clicks", async () => {
  reset();
  await call("/api/aff/event", articleEvent);
  const [key, value] = [...records][0]; records.delete(key); records.set(key.replace(/^f:\d{4}-\d{2}-\d{2}:/, "f:2001-01-01:"), value);
  await call("/api/aff/event", { ...articleEvent, stage: "guide_click" });
  const a = (await stats()).funnel.articleMeasurement.byArticle[0];
  assert.equal(a.viewVisitors, 0); assert.equal(a.clickVisitorsWithoutObservedView, 1); assert.equal(a.observedReaderClickRate, null);
});
console.log(`${passed} measurement checks passed; no external requests.`);
