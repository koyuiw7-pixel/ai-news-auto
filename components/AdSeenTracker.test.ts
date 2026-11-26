/** モックDOMとBeaconだけで、広告を見た記録（components/AdSeenTracker.tsx）を確かめる。本番・ブラウザへの通信なし。node scripts/test_aff.mjs */
import assert from "node:assert/strict";
import { installAdSeen } from "./AdSeenTracker";

type Handler = () => void;
class MockDocument {
  visibilityState = "visible";
  listeners = new Map<string, Set<Handler>>();
  attrs: Record<string, string> = { "data-adv": "b", "data-abc": "1" };
  documentElement = { getAttribute: (n: string) => this.attrs[n] ?? null };
  els: unknown[] = [];
  addEventListener(type: string, h: Handler) { const l = this.listeners.get(type) ?? new Set(); l.add(h); this.listeners.set(type, l); }
  removeEventListener(type: string, h: Handler) { this.listeners.get(type)?.delete(h); }
  emit(type: string) { for (const h of this.listeners.get(type) ?? []) h(); }
  querySelectorAll() { return this.els; }
  count() { return [...this.listeners.values()].reduce((s, l) => s + l.size, 0); }
}
const box = (pos: string, opts: { ab?: boolean; arms?: boolean } = {}) => ({
  getAttribute: (n: string) => (n === "data-aff-pos" ? pos : null),
  hasAttribute: (n: string) => n === "data-ad-ab" && Boolean(opts.ab),
  querySelector: (sel: string) => (sel === "[data-ab-arm]" && opts.arms ? {} : null),
});

let doc = new MockDocument();
let sent: Record<string, unknown>[] = [];
let ioCallback: ((entries: { isIntersecting: boolean; intersectionRatio: number; target: unknown }[]) => void) | null = null;
let observed: unknown[] = [];
let timers: { fn: () => void; id: number; done: boolean }[] = [];
let nextId = 1;
const replace = (name: string, value: unknown) => Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
const send = (body: string) => { sent.push(JSON.parse(body)); return true; };
/** 1秒たった（待っているタイマーをすべて動かす。3秒後の拾い直しも含む） */
const tick = () => { for (const t of [...timers]) if (!t.done) { t.done = true; t.fn(); } };
const see = (target: unknown, ratio = 0.6) => ioCallback!([{ isIntersecting: ratio > 0, intersectionRatio: ratio, target }]);

function setup() {
  doc = new MockDocument(); sent = []; ioCallback = null; observed = []; timers = []; nextId = 1;
  replace("document", doc);
  replace("setTimeout", (fn: () => void) => { const t = { fn, id: nextId++, done: false }; timers.push(t); return t.id; });
  replace("clearTimeout", (id: number) => { const t = timers.find((x) => x.id === id); if (t) t.done = true; });
  replace("IntersectionObserver", class { constructor(cb: typeof ioCallback) { ioCallback = cb; } observe(el: unknown) { observed.push(el); } unobserve() {} disconnect() {} });
}
let passed = 0;
function test(name: string, fn: () => void) { setup(); fn(); passed++; console.log(`ok ad-seen-client ${name}`); }

test("半分以上が1秒続いたら、枠ごとに1回だけ送る（パス・置き場所・A/B の組だけ）", () => {
  const tool = box("tool-result", { ab: true, arms: true });
  doc.els = [tool];
  const clean = installAdSeen("/tools/child-allowance", send);
  see(tool);
  assert.equal(sent.length, 0, "1秒たつまでは送らない");
  tick();
  assert.deepEqual(sent, [{ path: "/tools/child-allowance", pos: "tool-result", ab: "b", arm: "1" }]);
  see(tool, 0); see(tool); tick();
  assert.equal(sent.length, 1, "同じページの表示では1回だけ");
  clean();
  assert.equal(doc.count(), 0, "後片付けでリスナーを外す");
});

test("1秒たつ前に画面から外れたら送らない。半分未満も送らない", () => {
  const ad = box("action-ad");
  doc.els = [ad];
  installAdSeen("/articles/a", send);
  see(ad); see(ad, 0); tick();
  see(ad, 0.3); tick();
  assert.equal(sent.length, 0);
});

test("タブを隠したら待ちを止め、戻ったら数え直す", () => {
  const ad = box("guide-top", { ab: true });
  doc.els = [ad];
  installAdSeen("/guides/x", send);
  see(ad);
  doc.visibilityState = "hidden"; doc.emit("visibilitychange"); tick();
  assert.equal(sent.length, 0);
  doc.visibilityState = "visible"; doc.emit("visibilitychange"); tick();
  assert.deepEqual(sent, [{ path: "/guides/x", pos: "guide-top", ab: "b" }], "A/B の印の無い枠は arm を送らない");
});

test("A/B の印の無い枠は組を送らない。おかしな値・クエリ付きのパスは送らない", () => {
  doc.attrs = { "data-adv": "zzz" };
  const a = box("rail", { ab: true });
  const b = box("BAD POS");
  doc.els = [a, b];
  installAdSeen("/articles/a", send);
  see(a); see(b); tick();
  assert.deepEqual(sent, [], "data-adv がおかしいときは送らない");
  setup();
  const c = box("rail");
  doc.els = [c];
  installAdSeen("/articles/a?x=1", send);
  see(c); tick();
  assert.deepEqual(sent, []);
});

test("後から描かれた枠も拾う（同じ枠を2回見張らない）", () => {
  const first = box("action-ad");
  doc.els = [first];
  installAdSeen("/articles/a", send);
  const late = box("tool-result");
  doc.els = [first, late];
  tick();
  assert.deepEqual(observed, [first, late]);
});

console.log(`ad-seen client tests: ${passed} passed`);
