const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

// スマートニュース（SmartFormat）のフィード（/feeds/smartnews.xml。lib/smartnews-feed.ts・lib/smartformat.ts）。
// 2026-11-07 オーナー承認: 申請前チェックリストと仕様書（publishers.smartnews.com/hc/ja）に合わせる。
// 全文・画像・絶対URL・出典リンクだけ・広告や自サイトへの誘導なし・AI のイメージには札・未来の日時なし・5本以上。
process.env.NEXT_PUBLIC_SITE_URL = "https://ai-tech-express.jp";
const root = path.resolve(__dirname, "..");
const { createJiti } = require("jiti");
const jiti = createJiti(__filename, { alias: { "@": root }, interopDefault: true });
const load = (rel) => jiti.import(path.join(root, rel));

const IMG = "https://ai-tech-express.jp/img/";

test("本文: 自サイトへのリンク・広告は文字だけ、外部の出典リンクは段落に1本・全体で3本まで", async () => {
  const { smartnewsBody, BODY_LINK_LIMIT } = await load("lib/smartformat.ts");
  const html = [
    `<p>詳しくは<a href="/articles/other">別の記事</a>と<a href="https://ai-tech-express.jp/guides/x">ガイド</a>。</p>`,
    `<p><a href="https://openai.com/a" target="_blank" rel="noopener">公式</a>と<a href="https://openai.com/b">もう1本</a></p>`,
    `<p><a href="https://px.a8.net/svt/ejp?a8mat=1">申し込む</a></p>`,
    `<ul><li><a href="https://example.com/1">1</a></li><li><a href="https://example.com/2">2</a></li><li><a href="https://example.com/3">3</a></li></ul>`,
    `<h1>見出し</h1><script>alert(1)</script><button>押す</button>`,
    `<img src="/img/x.jpg" class="a" loading="lazy" />`,
  ].join("\n");
  const out = smartnewsBody(html, (href) => href.includes("a8.net"));
  assert.ok(!out.includes("/articles/other") && out.includes("別の記事"));
  assert.ok(!out.includes("guides/x") && out.includes("ガイド"));
  assert.ok(out.includes(`<a href="https://openai.com/a">公式</a>`));
  assert.ok(!out.includes("openai.com/b") && out.includes("もう1本"), "1つの段落に外部リンクは1本まで");
  assert.ok(!out.includes("a8.net") && out.includes("申し込む"));
  assert.equal((out.match(/<a\s/g) ?? []).length, BODY_LINK_LIMIT);
  assert.ok(!/<h1|<script|<button|target=|rel=|class=|loading=/.test(out));
  assert.ok(out.includes("<h2>見出し</h2>"));
  assert.ok(out.includes(`src="https://ai-tech-express.jp/img/x.jpg"`));
});

test("写真: 公式の写真は出典、AI のイメージは「画像はイメージ（AI生成）」、写真が無ければ本文に置かない", async () => {
  const { feedPhoto, photoFigure } = await load("lib/smartformat.ts");
  const official = feedPhoto({ slug: "a", thumbnail: `${IMG}a-1111aaaa.jpg`, imageCredit: { kind: "official", org: "OpenAI" } });
  assert.deepEqual(official, { url: `${IMG}a-1111aaaa.jpg`, caption: "画像：OpenAI（公式発表より）", ai: false });
  const ai = feedPhoto({ slug: "b", thumbnail: "", imageCredit: { kind: "card" }, coverImage: `${IMG}b-cover-2222bbbb.jpg`, coverCredit: { kind: "ai" } });
  assert.equal(ai.caption, "画像はイメージ（AI生成）");
  assert.ok(photoFigure(ai, "題名").includes("<figcaption>画像はイメージ（AI生成）</figcaption>"));
  const launch = feedPhoto({ slug: "c", thumbnail: `${IMG}c-3333cccc.jpg`, imageCredit: { kind: "ai", launch: true } });
  assert.equal(launch.caption, "公式画像がないためイメージ（AI生成）");
  assert.equal(feedPhoto({ slug: "d", thumbnail: "", imageCredit: { kind: "card" } }), null);
  assert.equal(feedPhoto({ slug: "e", thumbnail: "https://i.ytimg.com/vi/x/maxresdefault.jpg" }), null);
  assert.equal(feedPhoto({ slug: "f", thumbnail: `${IMG}f-4444dddd.jpg`, imageCredit: { kind: "official", org: "X" }, noPhoto: true }), null);
});

test("載せる記事: まとめ・重複・検索に出さない記事は載せない", async () => {
  const { smartnewsEligible } = await load("lib/smartnews-feed.ts");
  const base = { slug: "x", type: "article", sourceType: "web", channelSlug: "openai", bodyLength: 4000, indexable: true };
  assert.equal(smartnewsEligible(base), true);
  assert.equal(smartnewsEligible({ ...base, type: "roundup" }), false);
  assert.equal(smartnewsEligible({ ...base, duplicateOf: "y" }), false);
  assert.equal(smartnewsEligible({ ...base, duplicate: true, indexable: undefined }), false);
  assert.equal(smartnewsEligible({ ...base, indexable: false }), false);
});

test("実際の記事で作ったフィード: 必須の要素・5本以上・未来の日時なし・絶対URL・二重エスケープなし", async () => {
  const { smartnewsFeedXml } = await load("lib/smartnews-feed.ts");
  const now = Date.now();
  const { xml, count } = await smartnewsFeedXml(now);
  assert.ok(count >= 5, `記事は5本以上（${count}本）`);
  assert.ok(Buffer.byteLength(xml) < 1_000_000, "1MB 以下（仕様の推奨）");
  for (const ns of ["xmlns:content=", "xmlns:dc=", "xmlns:media=", "xmlns:snf="]) assert.ok(xml.includes(ns), ns);
  assert.ok(xml.includes("<title>サイソクニュース</title>"));
  assert.ok(xml.includes("<link>https://ai-tech-express.jp</link>"));
  assert.match(xml, /<snf:logo><url>https:\/\/ai-tech-express\.jp\/feeds\/smartnews-logo\.png<\/url><\/snf:logo>/);
  const items = xml.split("<item>").slice(1);
  assert.equal(items.length, count);
  for (const item of items) {
    const title = /<title>([^<]*)<\/title>/.exec(item)?.[1] ?? "";
    assert.ok(title && !/&amp;(?:amp|lt|gt|quot|apos|#\d+);/.test(title), `二重エスケープなし: ${title}`);
    const link = /<link>([^<]*)<\/link>/.exec(item)?.[1] ?? "";
    assert.match(link, /^https:\/\/ai-tech-express\.jp\/articles\/[A-Za-z0-9_-]+$/, "記事の URL は正規の URL（パラメータなし）");
    const pub = Date.parse(/<pubDate>([^<]*)<\/pubDate>/.exec(item)?.[1] ?? "");
    assert.ok(Number.isFinite(pub) && pub <= now, `未来の日時は載せない: ${title}`);
    assert.match(item, /<pubDate>\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} \+0000<\/pubDate>/);
    assert.match(item, /<media:thumbnail url="https:\/\/ai-tech-express\.jp\/[^"]+" \/>/);
    assert.ok(item.includes("<media:status>active</media:status>"));
    const body = /<content:encoded><!\[CDATA\[([\s\S]*?)\]\]><\/content:encoded>/.exec(item)?.[1] ?? "";
    assert.ok(body.length > 500, `本文は全文: ${title}`);
    assert.ok(!/(?:src|href)="(?!https?:\/\/)/.test(body), `相対 URL なし: ${title}`);
    assert.ok(!/<(?:script|iframe|button|form|h1)\b/i.test(body), `スクリプト・ボタンなし: ${title}`);
    assert.ok(!/a8\.net|\/api\/aff\/|ai-tech-express\.jp\/(?:articles|guides|tools|choose|products)\//.test(body.replace(/<img[^>]*>/g, "")), `広告・自サイトへの誘導リンクなし: ${title}`);
    assert.ok((body.match(/<a\s/g) ?? []).length <= 5, `リンクは本文3本＋出典＋編集方針まで: ${title}`);
    if (body.includes("<img")) assert.ok(body.includes("<figcaption>"), `写真には出典か AI の札: ${title}`);
  }
});
