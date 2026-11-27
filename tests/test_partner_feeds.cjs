const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

// ニュースアプリへ送るフィード（/feeds/smartnews.xml・/feeds/gunosy.xml・/feeds/partner.xml・/feeds/news.xml）。
// 2026-11-28: 暮らしとお金の記事だけ（lib/partner-feed.ts）。広告・紹介リンク・PR・計測の画像・登録への誘導を入れない
// （Yahoo!ニュース・スマートニュース・グノシーの決まり）。各記事に AI 利用の開示を1行。
process.env.NEXT_PUBLIC_SITE_URL = "https://ai-tech-express.jp";
const root = path.resolve(__dirname, "..");
const { createJiti } = require("jiti");
const jiti = createJiti(__filename, { alias: { "@": root }, interopDefault: true });
const load = (rel) => jiti.import(path.join(root, rel));

const AXIS = new Set(["社会・行政", "暮らし・生活", "投資・マネー", "ビジネス・経済", "不動産"]);
const FORBIDDEN = /a8\.net|\/api\/aff\/|afl\.rakuten|moshimo|valuecommerce|accesstrade|rel="[^"]*sponsored|【PR】|>\s*PR\s*<|<script|<iframe|<form|<button/i;
const DISCLOSURE = "この記事は生成AIで下書きを作成し、元の発表と自動で照合してから公開しています。";

const base = {
  slug: "x",
  type: "article",
  sourceType: "web",
  channelSlug: "mhlw",
  genreSlug: "public",
  title: "児童手当の支給日は12月10日　申請の期限に注意",
  tags: [],
  bodyLength: 4000,
  indexable: true,
};

test("載せる記事の選び方: 暮らしとお金だけ、AI・海外・スポーツ・芸能・比較ページ・noindex は外す", async () => {
  const { partnerAxisReason } = await load("lib/partner-feed.ts");
  assert.equal(partnerAxisReason(base), null);
  for (const genreSlug of ["investment", "business", "lifestyle", "real-estate"]) assert.equal(partnerAxisReason({ ...base, genreSlug }), null, genreSlug);
  assert.equal(partnerAxisReason({ ...base, genreSlug: "ai" }), "genre");
  assert.equal(partnerAxisReason({ ...base, genreSlug: "tech-gadget" }), "genre");
  assert.equal(partnerAxisReason({ ...base, genreSlug: "sports" }), "genre");
  assert.equal(partnerAxisReason({ ...base, genreSlug: "entertainment" }), "genre");
  assert.equal(partnerAxisReason({ ...base, genreSlug: "business", title: "生成AIの導入支援を開始　料金は月額5万円" }), "ai-tech");
  assert.equal(partnerAxisReason({ ...base, genreSlug: "investment", title: "NVIDIAの売上高が103％増　1,076億ドル" }), "ai-tech");
  assert.equal(partnerAxisReason({ ...base, genreSlug: "investment", title: "米国の利下げで株価が上昇" }), "overseas");
  assert.equal(partnerAxisReason({ ...base, kind: "comparison" }), "comparison");
  assert.equal(partnerAxisReason({ ...base, type: "roundup" }), "roundup");
  assert.equal(partnerAxisReason({ ...base, duplicateOf: "y" }), "duplicate");
  assert.equal(partnerAxisReason({ ...base, indexable: false }), "noindex");
  assert.equal(partnerAxisReason({ ...base, indexable: undefined, pressOnly: true }), "noindex");
});

test("本文の点検: 広告・紹介リンク・PR の札・計測の画像・スクリプトを見つける", async () => {
  const { feedProblems } = await load("lib/feeds.ts");
  assert.deepEqual(feedProblems("<p>児童手当は月1万円。</p>"), []);
  assert.deepEqual(feedProblems(`<p>PR TIMES で公表された</p>`), [], "出典名の PR TIMES は札ではない");
  assert.ok(feedProblems(`<a href="https://px.a8.net/svt/ejp?a8mat=1">申し込む</a>`).includes("a8"));
  assert.ok(feedProblems(`<img src="https://www10.a8.net/0.gif?a8mat=1" width="1" height="1" />`).includes("pixel"));
  assert.ok(feedProblems(`<a href="https://x.com" rel="sponsored">x</a>`).includes("sponsored"));
  assert.ok(feedProblems(`<span>PR</span>`).includes("pr-badge"));
  assert.ok(feedProblems(`<a href="https://ai-tech-express.jp/api/aff/x">x</a>`).includes("aff-redirect"));
  assert.ok(feedProblems(`<a href="https://www.amazon.co.jp/dp/B0?tag=saisoku-22">x</a>`).includes("amazon-tag"));
  assert.ok(feedProblems(`<script>1</script>`).includes("script"));
});

test("本文の点検に引っかかった記事はフィードに載せない", async () => {
  const { buildItems } = await load("lib/feeds.ts");
  const items = await buildItems([{ slug: "ok" }, { slug: "ad" }], 1_000_000, async (a) =>
    a.slug === "ad" ? `<item><a href="https://px.a8.net/x">x</a></item>` : `<item>${a.slug}</item>`,
  );
  assert.deepEqual(items, ["<item>ok</item>"]);
});

/** item ごとに [分野, 本文, 題名] を取り出す */
function itemsOf(xml) {
  return xml
    .split("<item>")
    .slice(1)
    .map((item) => ({
      title: /<title>([^<]*)<\/title>/.exec(item)?.[1] ?? "",
      category: /<category>([^<]*)<\/category>/.exec(item)?.[1] ?? "",
      link: /<link>([^<]*)<\/link>/.exec(item)?.[1] ?? "",
      body: /<content:encoded><!\[CDATA\[([\s\S]*?)\]\]><\/content:encoded>/.exec(item)?.[1] ?? "",
      raw: item,
    }));
}

test("実際の記事で作ったフィード: 暮らしとお金の記事だけ・広告なし・開示あり（スマートニュース・グノシー・汎用）", async () => {
  const { smartnewsFeedXml } = await load("lib/smartnews-feed.ts");
  const { partnerFeedXml } = await load("lib/partner-xml.ts");
  const { GET } = await load("app/feeds/gunosy.xml/route.ts");
  const { getArticleSummary } = await load("lib/articles.ts");
  const { partnerAxisReason } = await load("lib/partner-feed.ts");
  const smartnews = (await smartnewsFeedXml()).xml;
  const partner = (await partnerFeedXml("/feeds/partner.xml")).xml;
  const gunosyRes = await GET();
  assert.match(gunosyRes.headers.get("content-type"), /^application\/rss\+xml/);
  const gunosy = await gunosyRes.text();
  for (const [name, xml] of [["smartnews", smartnews], ["partner", partner], ["gunosy", gunosy]]) {
    const items = itemsOf(xml);
    assert.ok(items.length >= 5, `${name}: 5本以上（${items.length}本）`);
    assert.ok(!FORBIDDEN.test(xml), `${name}: 広告・紹介リンク・PR・スクリプトなし`);
    for (const item of items) {
      const slug = item.link.replace(/^.*\/articles\//, "") || /saisoku-([^<]+)<\/guid>/.exec(item.raw)?.[1];
      const summary = getArticleSummary(slug);
      assert.ok(summary, `${name}: 記事がある ${slug}`);
      assert.equal(partnerAxisReason(summary), null, `${name}: 暮らしとお金の記事だけ ${item.title}`);
      if (name === "partner") assert.ok(AXIS.has(item.category), `${name}: 分野 ${item.category}`);
      assert.ok(item.body.includes(DISCLOSURE), `${name}: AI 利用の開示 ${item.title}`);
      assert.ok(!/ai-tech-express\.jp\/(?:articles|guides|tools|choose|products|compare|calc)\//.test(item.body.replace(/<img[^>]*>/g, "")), `${name}: 自サイトへの誘導なし ${item.title}`);
      if (name === "gunosy") {
        assert.ok(!/<table/i.test(item.body), "グノシーは表を段落に開く");
        assert.ok((item.body.match(/<a\s/g) ?? []).length <= 1, "グノシーの本文のリンクは出典の1本まで");
      }
    }
  }
});
