/** A8への通信・自己クリックをせず、元URL保持・限定範囲・privacy・履歴遷移を検証する。 */
import assert from "node:assert/strict";
import { a8EntryOf, appendDifyA8Attribution, difyDecisionHref, installDifyA8Attribution } from "./a8-attribution";
import { GUIDE_PATH } from "./revenue-funnel";

const base = "https://px.a8.net/svt/ejp?a8mat=TEST+KEEP+BYTE+EXACT";
const origin = "https://test.invalid";
const nav = { userAgent: "Mozilla/5.0" };
let passed = 0;
function test(name: string, fn: () => void) { fn(); passed++; console.log(`ok attribution ${name}`); }

class Link {
  attrs: Record<string, string>;
  constructor(readonly pos: string, attrs: Record<string, string> = {}) {
    this.attrs = { href: base, "data-a8-dify": "v1", "data-funnel-choice": "xserver-dify", rel: "sponsored nofollow noopener noreferrer", ...attrs };
  }
  getAttribute(key: string) { return this.attrs[key] ?? null; }
  setAttribute(key: string, value: string) { this.attrs[key] = value; }
  closest(selector: string) { assert.equal(selector, "[data-aff-pos]"); return { getAttribute: () => this.pos }; }
}
function documentWith(links: Link[], referrer = "") {
  return {
    referrer,
    querySelectorAll(selector: string) {
      assert.equal(selector, 'a[data-a8-dify="v1"][data-funnel-choice="xserver-dify"][rel~="sponsored"]');
      return links.filter((link) => link.attrs["data-a8-dify"] === "v1" && link.attrs["data-funnel-choice"] === "xserver-dify" && link.attrs.rel.split(/\s+/).includes("sponsored"));
    },
  } as unknown as Document;
}

test("two fixed article links survive Next Link navigation without changing other guides", () => {
  assert.equal(difyDecisionHref("/guides/dify-free-api-cost", GUIDE_PATH), `${GUIDE_PATH}?sa_from=difyfree`);
  assert.equal(difyDecisionHref("/guides/dify-1-18-startup-check", GUIDE_PATH), `${GUIDE_PATH}?sa_from=difystartup`);
  assert.equal(difyDecisionHref("/guides/other", GUIDE_PATH), GUIDE_PATH);
  assert.equal(difyDecisionHref("__proto__", GUIDE_PATH), GUIDE_PATH);
  assert.equal(difyDecisionHref("/guides/dify-free-api-cost", "/choose/other"), "/choose/other");
});
test("valid query wins but arbitrary, repeated and empty markers do not become an article", () => {
  assert.equal(a8EntryOf("?sa_from=difyfree", "", origin), "difyfree");
  assert.equal(a8EntryOf("?sa_from=difystartup&utm_source=google", "", origin), "difystartup");
  for (const search of ["?sa_from=user@example.com", "?sa_from=direct", "?sa_from=", "?sa_from=difyfree&sa_from=difystartup", "?sa_from=%2Fguides%2Fdify-free-api-cost"]) {
    assert.equal(a8EntryOf(search, `${origin}/guides/dify-free-api-cost`, origin), "unknown");
  }
});
test("an old SPA referrer never attributes an article without an explicit link code", () => {
  assert.equal(a8EntryOf("", `${origin}/guides/dify-free-api-cost?private=value`, origin), "internal");
  assert.equal(a8EntryOf("", `${origin}/guides/dify-1-18-startup-check`, origin), "internal");
  assert.equal(a8EntryOf("", `${origin}/articles/other`, origin), "internal");
  assert.equal(a8EntryOf("", "https://google.com/search?q=private", origin), "direct");
  assert.equal(a8EntryOf("", "", origin), "direct");
  assert.equal(a8EntryOf("", "not a URL", origin), "unknown");
});
test("original a8mat, percent encoding, redirect, query order and fragment remain byte-exact", () => {
  const original = `${base}&a8ejpredirect=https%3a%2f%2fexample.invalid%2f%3fx%3dA%2BB#keep%2fHash`;
  const result = appendDifyA8Attribution(original, "difyfree", "cards");
  assert.equal(result, original.replace("#", "&id1=difyfree&id2=difyhost&id3=cards#"));
  const before = new URL(original), after = new URL(result);
  assert.equal(after.searchParams.get("a8mat"), before.searchParams.get("a8mat"));
  assert.equal(after.searchParams.get("a8ejpredirect"), before.searchParams.get("a8ejpredirect"));
});
test("all existing id1-id5 variants fail closed and never overwrite advertiser data", () => {
  for (const key of ["id1", "id2", "id3", "id4", "id5", "ID1", "i%64%31"]) {
    const url = `${base}&${key}=existing`;
    assert.equal(appendDifyA8Attribution(url, "direct", "table"), url);
  }
});
test("unsupported hosts, formats, keys and ambiguous material IDs are unchanged", () => {
  for (const url of ["https://amazon.co.jp/?tag=test", "https://afl.rakuten.co.jp/test", base.replace("px.a8.net", "px.a8.net.evil.invalid"), base.replace("https:", "http:"), base.replace("/svt/ejp", "/other"), base.replace("/svt/ejp", "/svt/../svt/ejp"), base.replace("/svt/ejp", "\\svt\\ejp"), base.replace("px.a8.net", "name@px.a8.net"), base.replace("px.a8.net", "px.a8.net:8443"), `${base}&a8mat=second`, `${base}&id9=value`, "https://px.a8.net/svt/ejp?a8mat=", `${base} `, "not a URL"]) {
    assert.equal(appendDifyA8Attribution(url, "direct", "table"), url);
  }
});
test("runtime values outside the types cannot leak free text", () => {
  assert.equal(appendDifyA8Attribution(base, "email@example.com" as never, "table"), base);
  assert.equal(appendDifyA8Attribution(base, "direct", "unsafe&x=1" as never), base);
});
test("a trailing separator is preserved and repeat installation is idempotent", () => {
  const result = appendDifyA8Attribution(`${base}&`, "internal", "table");
  assert.equal(result, `${base}&id1=internal&id2=difyhost&id3=table`);
  assert.equal(appendDifyA8Attribution(result, "difyfree", "table"), result);
});
test("only marked sponsored XServer Dify table and card links change; free and other ads remain", () => {
  const table = new Link("choose-table"), cards = new Link("choose-cards");
  const untouched = [new Link("choose-table", { "data-a8-dify": "" }), new Link("choose-table", { "data-funnel-choice": "dify-cloud", rel: "nofollow noopener" }), new Link("choose-table", { "data-funnel-choice": "another-paid" }), new Link("other"), new Link("choose-cards", { href: "https://amazon.co.jp/?tag=test" })];
  const originals = untouched.map(link => link.attrs.href);
  const clean = installDifyA8Attribution(GUIDE_PATH, "?sa_from=difyfree", documentWith([table, cards, ...untouched]), nav, origin);
  assert.equal(table.attrs.href, `${base}&id1=difyfree&id2=difyhost&id3=table`);
  assert.equal(cards.attrs.href, `${base}&id1=difyfree&id2=difyhost&id3=cards`);
  assert.deepEqual(untouched.map(link => link.attrs.href), originals);
  assert.equal(table.attrs.rel, "sponsored nofollow noopener noreferrer");
  clean(); assert.equal(table.attrs.href, base); assert.equal(cards.attrs.href, base);
});
test("DNT, GPC, webdriver and bots do not add A8 classification", () => {
  for (const signals of [{ doNotTrack: "1" }, { globalPrivacyControl: true }, { webdriver: true }, { userAgent: "Google-InspectionTool" }, { userAgent: "HeadlessChrome" }]) {
    const link = new Link("choose-table");
    const clean = installDifyA8Attribution(GUIDE_PATH, "?sa_from=difyfree", documentWith([link]), { ...nav, ...signals }, origin);
    assert.equal(link.attrs.href, base); clean(); assert.equal(link.attrs.href, base);
  }
});
test("other routes do not change even a marked link", () => {
  const link = new Link("choose-table");
  const clean = installDifyA8Attribution("/choose/other", "?sa_from=difyfree", documentWith([link]), nav, origin);
  assert.equal(link.attrs.href, base); clean();
});
test("cleanup plus query/back changes recompute from the original link, without stale origin", () => {
  const link = new Link("choose-table"), doc = documentWith([link]);
  let clean = installDifyA8Attribution(GUIDE_PATH, "?sa_from=difyfree", doc, nav, origin);
  assert(link.attrs.href.includes("id1=difyfree")); clean();
  clean = installDifyA8Attribution(GUIDE_PATH, "?sa_from=difystartup", doc, nav, origin);
  assert(link.attrs.href.includes("id1=difystartup")); assert(!link.attrs.href.includes("id1=difyfree")); clean();
  clean = installDifyA8Attribution(GUIDE_PATH, "", doc, nav, origin);
  assert(link.attrs.href.includes("id1=direct")); clean(); assert.equal(link.attrs.href, base);
});
test("cleanup does not overwrite a link subsequently changed by another owner", () => {
  const link = new Link("choose-table");
  const clean = installDifyA8Attribution(GUIDE_PATH, "", documentWith([link]), nav, origin);
  link.setAttribute("href", "https://replacement.invalid/"); clean();
  assert.equal(link.attrs.href, "https://replacement.invalid/");
});
console.log(`${passed} attribution checks passed; mock DOM only, no ASP requests.`);
