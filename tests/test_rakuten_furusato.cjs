const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 2026-11-10 M4: 楽天ふるさと納税の枠（rakuten-furusato）。楽天アフィリエイト（A8 の s00000011623001）の決まった a8mat・hgc で、
// 楽天ふるさと納税のトップへ飛ぶリンクの形だけを確かめる（リンクは開かない。開くとオーナーのアカウントにクリックが付く）。
const root = path.resolve(__dirname, "..");
process.chdir(root);
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const compiled = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  cache.set(file, mod);
  const original = mod.require.bind(mod);
  mod.require = (name) => {
    if (name === "@/lib/content-fs") return fs;
    if (name === "@/lib/articles") return { getAllArticles: () => [] };
    if (name.startsWith("@/lib/")) return load(path.join(root, "lib", `${name.slice(6)}.ts`));
    if (name.startsWith("./")) return load(path.join(path.dirname(file), `${name}.ts`));
    return original(name);
  };
  mod._compile(compiled, file);
  return mod.exports;
}
const { rakutenPageUrl, rakutenSearchUrl, RAKUTEN_FURUSATO_PAGE } = load(path.join(root, "lib/amazon.ts"));
const { partnerItem, isValidAffiliateUrl } = load(path.join(root, "lib/offers.ts"));
const { programOf } = load(path.join(root, "lib/aff-program.ts"));
const { actionAdForArticle, actionAdRuleFor } = load(path.join(root, "lib/action-ad.ts"));
const { toolAd } = load(path.join(root, "lib/guide-ads.ts"));

const A8 = "https://rpx.a8.net/svt/ejp?a8mat=4BELTP+50ED2Q+2HOM+BWGDT&rakuten=y";
const HGC = "g00q0724.2bo11c45.g00q0724.2bo12179/a26102173090_4BELTP_50ED2Q_2HOM_BWGDT";
const FURUSATO = ["furusato-honpo", "rakuten-furusato", "aupay-furusato"];
const TAX = ["freee", "mf-kakutei", "yayoi-kakutei"];
const offers = JSON.parse(fs.readFileSync(path.join(root, "content/offers.json"), "utf8"));
const links = JSON.parse(fs.readFileSync(path.join(root, "affiliate_links.json"), "utf8"));
const article = (slug) => JSON.parse(fs.readFileSync(path.join(root, `content/articles/${slug}.json`), "utf8"));
const keys = (ad) => (ad?.items ?? []).map(({ item }) => item.key);

test("rakutenPageUrl は A8 の楽天リンクの形で、hb.afl.rakuten.co.jp を通って指定のページへ飛ぶ", () => {
  assert.equal(RAKUTEN_FURUSATO_PAGE, "https://event.rakuten.co.jp/furusato/");
  const url = rakutenPageUrl(RAKUTEN_FURUSATO_PAGE);
  assert.ok(url.startsWith(`${A8}&a8ejpredirect=`), url);
  const inner = decodeURIComponent(url.split("&a8ejpredirect=")[1]);
  assert.equal(inner, `https://hb.afl.rakuten.co.jp/hgc/${HGC}?pc=${encodeURIComponent(RAKUTEN_FURUSATO_PAGE)}&m=${encodeURIComponent(RAKUTEN_FURUSATO_PAGE)}`);
  assert.equal(new URL(inner).searchParams.get("pc"), RAKUTEN_FURUSATO_PAGE);
  assert.ok(decodeURIComponent(inner).includes("furusato"));
  // 検索リンクも同じ組み立て（今までの形のまま）
  assert.ok(rakutenSearchUrl("電気毛布").startsWith(`${A8}&a8ejpredirect=`));
  assert.equal(rakutenSearchUrl("x"), rakutenPageUrl("https://search.rakuten.co.jp/search/mall/x/"));
});

test("offers.json の rakuten-furusato は取込（scripts/a8_import.py）と同じリンクで、link の形の確かめに通る", () => {
  const partner = offers.partners["rakuten-furusato"];
  assert.ok(partner, "rakuten-furusato が無い");
  assert.equal(partner.link, rakutenPageUrl(RAKUTEN_FURUSATO_PAGE));
  assert.equal(partner.programId, "s00000011623001");
  assert.equal(links[partner.program].url, partner.link);
  assert.equal(links[partner.program].aliases.length, 0, "本文中の文字リンクには使わない");
  assert.ok(isValidAffiliateUrl(partner.link));
  const picked = partnerItem("rakuten-furusato");
  assert.ok(picked, "partnerItem で出せない");
  assert.equal(picked.item.url, partner.link);
  assert.equal(picked.item.name, "楽天ふるさと納税");
});

test("楽天ふるさと納税の文に、ポイント・還元・縦棒・「ざっくり」を書かない", () => {
  const textOf = (value) => (typeof value === "string" ? value : Array.isArray(value) ? value.map(textOf).join(" ") : value && typeof value === "object" ? Object.entries(value).filter(([k]) => !["image", "link", "pixel", "programId"].includes(k)).map(([, v]) => textOf(v)).join(" ") : "");
  const text = `${textOf(offers.partners["rakuten-furusato"])} ${textOf(links[offers.partners["rakuten-furusato"].program])}`;
  assert.ok(text.includes("楽天ふるさと納税"));
  assert.doesNotMatch(text, /ポイント|還元|｜|ざっくり/);
  for (const rule of offers.actionAds.filter((r) => r.partners.includes("rakuten-furusato"))) {
    assert.doesNotMatch(`${rule.title} ${rule.reason ?? ""} ${rule.lead ?? ""}`, /ポイント|還元|｜|ざっくり/, rule.key);
  }
});

test("クリックは楽天の a8mat で数える（unknown にしない）", () => {
  assert.equal(programOf(rakutenPageUrl(RAKUTEN_FURUSATO_PAGE)), "4BELTP+50ED2Q+2HOM+BWGDT");
  assert.equal(programOf("https://px.a8.net/svt/ejp?a8mat=4BGGBL+BZNACY+5IMU+5YRHE"), "4BGGBL+BZNACY+5IMU+5YRHE");
});

test("年末調整の記事は nencho（上限額の計算への案内とふるさと納税のサイト）。確定申告の記事は tax のまま", () => {
  for (const slug of ["nencho-2026-changes", "kiso-kojo-2026-nencho"]) {
    const ad = actionAdForArticle(article(slug));
    assert.equal(ad?.key, "nencho", slug);
    assert.ok(keys(ad).length >= 1 && keys(ad).every((key) => FURUSATO.includes(key)), `${slug}: ${keys(ad)}`);
    assert.deepEqual((ad.internal ?? []).map((x) => x.href), ["/tools/furusato-limit"], slug);
    assert.doesNotMatch(`${ad.title} ${ad.reason} ${ad.lead}`, /ポイント|還元|｜|ざっくり/);
  }
  const rules = offers.actionAds;
  const fake = (title, tags = []) => ({ slug: "x", title, seoTitle: "", tags, summary: title, description: title, genreSlug: "public", genre: "暮らし" });
  assert.equal(actionAdRuleFor(fake("確定申告の期限と医療費控除の書き方", ["確定申告"]), rules)?.key, "tax");
  assert.equal(actionAdRuleFor(fake("年末調整と確定申告、副業の人はどちら", ["年末調整", "確定申告"]), rules)?.key, "tax");
  assert.notEqual(actionAdRuleFor(fake("相続税の基礎控除は3,000万円＋600万円×人数", ["相続税", "基礎控除"]), rules)?.key, "nencho");
  const order = rules.map((r) => r.key);
  assert.ok(order.indexOf("furusato") < order.indexOf("nencho") && order.indexOf("nencho") < order.indexOf("tax"));
  assert.ok(rules.find((r) => r.key === "nencho").partners.every((key) => !TAX.includes(key)));
});

test("ふるさと納税の記事は furusato（3社をずらして2件）。計算ツールの囲みも同じ3社から", () => {
  const ad = actionAdForArticle(article("furusato-nozei-deadline-2026"));
  assert.equal(ad?.key, "furusato");
  assert.equal(keys(ad).length, 2);
  assert.ok(keys(ad).every((key) => FURUSATO.includes(key)));
  assert.ok(keys(ad).includes("rakuten-furusato") || keys(ad).includes("furusato-honpo"), keys(ad).join());
  assert.deepEqual(offers.actionAds.find((r) => r.key === "furusato").partners, FURUSATO);
  const tool = toolAd("furusato");
  assert.equal(keys(tool).length, 2);
  assert.ok(keys(tool).every((key) => FURUSATO.includes(key)));
});
