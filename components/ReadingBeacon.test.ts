/** モックDOMとBeaconだけで、読まれ方の計測（components/ReadingBeacon.tsx）の送信を確かめる。本番・ブラウザへの通信なし。node scripts/test_aff.mjs */
import assert from "node:assert/strict";
import { installReading } from "./ReadingBeacon";

type Handler = (event?: unknown) => void;
class Target {
  listeners = new Map<string, Set<Handler>>();
  addEventListener(type: string, handler: Handler) { const list = this.listeners.get(type) ?? new Set(); list.add(handler); this.listeners.set(type, list); }
  removeEventListener(type: string, handler: Handler) { this.listeners.get(type)?.delete(handler); }
  emit(type: string, event?: unknown) { for (const handler of this.listeners.get(type) ?? []) handler(event); }
  count() { return [...this.listeners.values()].reduce((s, l) => s + l.size, 0); }
}
class MockDocument extends Target {
  visibilityState = "visible";
  documentElement = { scrollHeight: 10_000 };
  observed: Element[] = [];
  querySelector(sel: string) { return sel === "main" ? { getBoundingClientRect: () => ({ bottom: 8000 - win.scrollY }) } : null; }
  querySelectorAll() { return [adEl, nextEl]; }
}
class MockWindow extends Target { scrollY = 0; innerHeight = 800; }
const adEl = { getAttribute: (n: string) => (n === "data-aff-pos" ? "action-ad" : null) };
const nextEl = { getAttribute: () => null };
let doc = new MockDocument(), win = new MockWindow(), now = 0, sent: Record<string, unknown>[] = [];
let ioCallback: ((entries: { isIntersecting: boolean; target: unknown }[]) => void) | null = null;
const original = new Map<string, PropertyDescriptor | undefined>();
const replace = (name: string, value: unknown) => {
  if (!original.has(name)) original.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
  Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
};
const send = (body: string) => { sent.push(JSON.parse(body)); return true; };
const linkClick = (pathname: string, zone: string, extra: Partial<{ origin: string; rel: string }> = {}) => ({
  isTrusted: true, button: 0,
  target: { closest: () => ({ origin: "https://ai-tech-express.jp", pathname, rel: "", ...extra, closest: (sel: string) => (sel.includes(zone) ? {} : null) }) },
});
function setup() {
  doc = new MockDocument(); win = new MockWindow(); now = 0; sent = []; ioCallback = null;
  replace("document", doc);
  replace("window", win);
  replace("location", { origin: "https://ai-tech-express.jp", pathname: "/articles/a" });
  replace("performance", { now: () => now });
  replace("requestAnimationFrame", (fn: () => void) => { fn(); return 1; });
  replace("cancelAnimationFrame", () => {});
  // 測り始めの待ち（600ms）と遅れて出る枠の拾い直しは、すぐ動かす
  replace("setTimeout", (fn: () => void) => { fn(); return 1; });
  replace("clearTimeout", () => {});
  replace("IntersectionObserver", class { constructor(cb: typeof ioCallback) { ioCallback = cb; } observe() {} unobserve() {} disconnect() {} });
}
let passed = 0;
function test(name: string, fn: () => void) { setup(); fn(); passed++; console.log(`ok reading-client ${name}`); }

test("タブを隠したときに深さ・時間・PR 枠・次の記事を1件送る", () => {
  const clean = installReading("a", "threads", send);
  win.scrollY = 3200; win.emit("scroll"); // (3200+800)/8000 = 50%
  ioCallback!([{ isIntersecting: true, target: adEl }]);
  now = 42_000;
  doc.visibilityState = "hidden"; doc.emit("visibilitychange");
  assert.deepEqual(sent, [{ p: "a", s: "threads", d: 50, t: 30, n: false, a: ["action-ad"], x: "" }]);
  // 中身が変わらなければ送り直さない
  win.emit("pagehide");
  assert.equal(sent.length, 1);
  // 戻って読み進めたら、最新の状態を送り直す（Worker で上書き）。隠れていた時間は数えない
  now = 100_000; doc.visibilityState = "visible"; doc.emit("visibilitychange");
  win.scrollY = 7400; win.emit("scroll");
  ioCallback!([{ isIntersecting: true, target: nextEl }]);
  now = 130_000; win.emit("pagehide");
  assert.deepEqual(sent[1], { p: "a", s: "threads", d: 100, t: 60, n: true, a: ["action-ad"], x: "" });
  clean();
  assert.equal(doc.count() + win.count(), 0, "後片付けでリスナーを外す");
});

test("サイト内リンクを押した場所を記録して、その場で送る", () => {
  const clean = installReading("a", "internal", send);
  now = 12_000;
  doc.emit("click", linkClick("/articles/b", "next-read-heading"));
  assert.equal(sent.at(-1)!.x, "nextread");
  assert.equal(sent.at(-1)!.t, 10);
  doc.emit("click", linkClick("/", "header"));
  assert.equal(sent.at(-1)!.x, "header");
  const before = sent.length;
  // 提携リンク・外部リンク・同じページ内の移動・機械のクリックは数えない
  doc.emit("click", linkClick("/articles/c", "aside", { rel: "sponsored noopener" }));
  doc.emit("click", linkClick("/articles/c", "aside", { origin: "https://px.a8.net" }));
  doc.emit("click", linkClick("/articles/a", "aside"));
  doc.emit("click", { ...linkClick("/articles/c", "aside"), isTrusted: false });
  assert.equal(sent.length, before);
  clean();
});

test("画面切り替えの後片付けでは次のページを測らない", () => {
  const clean = installReading("a", "threads", send);
  now = 6_000;
  win.scrollY = 9000; // もう次のページが描かれている想定
  clean();
  assert.equal(sent.at(-1)!.d, 10);
  assert.equal(sent.at(-1)!.t, 5);
});

test("サイト内の移動の直後（600ms 以内）は前のページのスクロール位置で測らない", () => {
  replace("setTimeout", () => 1); // 待ちがまだ終わっていない
  win.scrollY = 9000;
  const clean = installReading("b", "internal", send);
  win.emit("scroll");
  ioCallback?.([{ isIntersecting: true, target: nextEl }]);
  now = 400; clean();
  assert.equal(sent.at(-1)!.d, 0);
});

test("隠れたまま開いたページは時間を数えない", () => {
  doc.visibilityState = "hidden";
  const clean = installReading("a", "threads", send);
  now = 50_000; win.emit("pagehide");
  assert.equal(sent.at(-1)!.t, 0);
  ioCallback!([{ isIntersecting: true, target: adEl }]);
  clean();
  assert.deepEqual(sent.at(-1)!.a, []);
});

test("送信が失敗しても止まらない", () => {
  const clean = installReading("a", "threads", () => { throw new Error("blocked"); });
  doc.visibilityState = "hidden"; doc.emit("visibilitychange");
  clean();
});

// 後に続くテストのために、置き換えた globalThis を元に戻す
for (const [name, descriptor] of original) {
  if (descriptor) Object.defineProperty(globalThis, name, descriptor);
  else delete (globalThis as Record<string, unknown>)[name];
}
console.log(`reading client tests: ${passed} passed`);
