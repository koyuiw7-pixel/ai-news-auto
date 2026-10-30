/** モックDOMとBeaconだけで実クライアントのイベント処理を検証。本番・実ASP・ブラウザへの通信なし。 */
import assert from "node:assert/strict";
import { installFunnelTracking } from "./RevenueFunnelTracker";
import { ARTICLE_PATHS, GUIDE_PATH } from "../lib/revenue-funnel";

type Payload = { stage: string; path: string; articleMeasurement?: number; source: string };
type Handler = (event?: unknown) => void;
let timers = new Map<number, Handler>(), nextTimer = 0;
let attempts: Payload[] = [], queued: Payload[] = [];
let failFirstView = false;
const original = new Map<string, PropertyDescriptor | undefined>();
function replace(name: string, value: unknown) {
  if (!original.has(name)) original.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
  Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
}
class MockDocument {
  visibilityState = "visible";
  listeners = new Map<string, Set<Handler>>();
  addEventListener(type: string, handler: Handler) { const list=this.listeners.get(type)??new Set();list.add(handler);this.listeners.set(type,list); }
  removeEventListener(type: string, handler: Handler) { this.listeners.get(type)?.delete(handler); }
  getElementById() { return null; }
  emit(type: string, event?: unknown) { for(const handler of this.listeners.get(type)??[]) handler(event); }
}
let doc = new MockDocument();
const link = { origin: "https://test.invalid", pathname: GUIDE_PATH, closest: () => null, getAttribute: () => null };
const click = (override = {}) => ({ isTrusted: true, button: 0, target: { closest: () => link }, ...override });
const flush = () => { const pending=[...timers.values()];timers.clear();pending.forEach(fn=>fn()); };
const setup = () => {
  doc=new MockDocument();attempts=[];queued=[];timers.clear();failFirstView=false;
  replace("document",doc);
};
let passed=0;
async function test(name: string, fn: () => void) { setup();fn();passed++;console.log(`ok client ${name}`); }
try {
  replace("setTimeout", (fn: Handler) => { const id=++nextTimer;timers.set(id,fn);return id; });
  replace("clearTimeout", (id: number) => timers.delete(id));
  replace("location", { origin: "https://test.invalid" });
  replace("navigator", { sendBeacon: (url: string, text: string) => {
    assert.equal(url,"/api/aff/event");const event=JSON.parse(text) as Payload;attempts.push(event);
    if(failFirstView && event.stage==="article_view"){failFirstView=false;return false;}queued.push(event);return true;
  } });
  await test("visible article view once across visibility changes", () => {
    const clean=installFunnelTracking(ARTICLE_PATHS[0],"google");assert.equal(queued.length,0);flush();
    assert.equal(queued[0].stage,"article_view");assert.equal(queued[0].articleMeasurement,2);
    doc.visibilityState="hidden";doc.emit("visibilitychange");doc.visibilityState="visible";doc.emit("visibilitychange");flush();assert.equal(queued.length,1);clean();
  });
  await test("subsecond comparison click queues view first and does not double count", () => {
    const clean=installFunnelTracking(ARTICLE_PATHS[1],"bing");doc.emit("click",click());
    assert.deepEqual(queued.map(e=>e.stage),["article_view","guide_click"]);assert(queued.every(e=>e.articleMeasurement===2 && e.path===ARTICLE_PATHS[1]));
    flush();doc.emit("auxclick",click({button:1}));assert.equal(queued.length,2);clean();
  });
  await test("hidden page does not send article view or click", () => {
    doc.visibilityState="hidden";const clean=installFunnelTracking(ARTICLE_PATHS[0],"direct");flush();doc.emit("click",click());assert.equal(queued.length,0);
    doc.visibilityState="visible";doc.emit("visibilitychange");flush();assert.equal(queued.length,1);clean();
  });
  await test("timer rechecks visibility even if hidden event was missed", () => {
    const clean=installFunnelTracking(ARTICLE_PATHS[0],"direct");doc.visibilityState="hidden";flush();assert.equal(queued.length,0);clean();
  });
  await test("failed early view beacon is retried without suppressing click", () => {
    failFirstView=true;const clean=installFunnelTracking(ARTICLE_PATHS[0],"google");doc.emit("click",click());assert.deepEqual(queued.map(e=>e.stage),["guide_click"]);
    flush();assert.deepEqual(queued.map(e=>e.stage),["guide_click","article_view"]);assert.equal(attempts.length,3);clean();
  });
  await test("unrelated pages preserve legacy guide click without v2 marker", () => {
    const clean=installFunnelTracking("/articles/other","google");flush();assert.equal(queued.length,0);doc.emit("click",click());assert.equal(queued[0].stage,"guide_click");assert.equal(queued[0].articleMeasurement,undefined);clean();
  });
  await test("untrusted and right-click actions do not create view or transition", () => {
    const clean=installFunnelTracking(ARTICLE_PATHS[0],"google");doc.emit("click",click({isTrusted:false}));doc.emit("click",click({button:2}));assert.equal(queued.length,0);clean();
  });
  await test("cleanup removes pending timers and handlers", () => {
    const clean=installFunnelTracking(ARTICLE_PATHS[0],"google");clean();flush();doc.emit("click",click());assert.equal(queued.length,0);assert.equal(timers.size,0);
  });
  console.log(`${passed} client measurement checks passed; mock DOM and beacon only.`);
} finally {
  for(const [name,descriptor] of original) {if(descriptor)Object.defineProperty(globalThis,name,descriptor);else Reflect.deleteProperty(globalThis,name);}
}
