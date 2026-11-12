// 2026-11-12 オーナー承認: AdSense の申し込み直しまでは PR の囲みを1記事1つ・本文の後ろだけ
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const read = (p) => fs.readFileSync(path.join(__dirname, "..", p), "utf8");

test("審査の期間は11/27より前だけ", () => {
  const src = read("lib/ad-review.ts");
  assert.match(src, /2026-11-27T00:00:00\+09:00/);
});

test("記事のページ: 審査の期間は上・途中・右・帯・導線のPRを出さない", () => {
  const page = read("app/articles/[slug]/page.tsx");
  for (const s of [
    "const compareOffers = noPr || adReview ? undefined",
    "const actionAd = compareOffers || noPr || adReview ? undefined",
    "const offer = adReview ? undefined",
    "const shopLink = noPr || adReview ? undefined",
    "const inlineCta = !noPr && !adReview",
    "const primaryCta = !noPr && !adReview",
  ]) assert.ok(page.includes(s), s);
});

test("新しい見た目: 審査の期間は1つだけ・本文の後ろ", () => {
  const noir = read("components/noir/noirArticlePage.tsx");
  assert.ok(noir.includes("adReview ? [null, null, adBlocks[0] ?? null]"));
  assert.ok(noir.includes("const noirInlineCta = !adReview"));
});
