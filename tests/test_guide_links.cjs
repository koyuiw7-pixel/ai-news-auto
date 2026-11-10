const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// ニュース記事 → 同じ製品の料金・使い方ガイドへの固定の案内（lib/guide-links.ts）。Next.js を起動せずに実際のガイド設定で検査する。
const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "lib/guide-links.ts");
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText;
const readGuide = (slug) => JSON.parse(fs.readFileSync(path.join(root, "content/howto", `${slug}.json`), "utf8"));
const howtos = fs
  .readdirSync(path.join(root, "content/howto"))
  .filter((file) => file.endsWith(".json"))
  .map((file) => readGuide(file.replace(/\.json$/, "")));
// 使い方ガイドの振り分け（lib/howto.ts の moneyGuideFor と、表 lib/money-pages.ts）は本物を使う（SEO A12）
const loadTs = (rel, mocks) => {
  const file = path.join(root, rel);
  const out = ts.transpileModule(fs.readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  const original = mod.require.bind(mod);
  mod.require = (name) => (name in mocks ? mocks[name] : original(name));
  mod._compile(out, file);
  return mod.exports;
};
const moneyPages = loadTs("lib/money-pages.ts", {});
const howtoLib = loadTs("lib/howto.ts", {
  "@/lib/content-fs": fs,
  "@/lib/articles": { getAllArticles: () => [] },
  "@/lib/polite-text": { politeDeep: (value) => value },
  "@/lib/nonanswer": { answeredOnly: (x) => x, answerOrNull: (x) => x, stripNotStated: (x) => x },
  "@/lib/money-pages": moneyPages,
});
const loaded = new Module(sourcePath, module);
loaded.filename = sourcePath;
loaded.paths = Module._nodeModulePaths(path.dirname(sourcePath));
const requireOriginal = loaded.require.bind(loaded);
loaded.require = (name) => {
  if (name === "@/lib/howto") return { getAllHowtos: () => howtos, moneyGuideFor: howtoLib.moneyGuideFor };
  if (name === "@/lib/guides") return { getAllGuides: () => [], guideHref: (slug) => `/guides/${slug}` };
  if (name === "@/lib/choose") return { chooseGuideForArticle: () => undefined };
  return requireOriginal(name);
};
loaded._compile(compiled, sourcePath);
const { guideLinksForArticle, insertAfterPricingSection } = loaded.exports;
const article = (title, seoTitle = "") => ({ title, seoTitle, tags: [], genreSlug: "ai" });

test("Claude Ultra の記事は Claude の料金ガイドを先に、使い方ガイドを次に出す", () => {
  const links = guideLinksForArticle(article("対話AI「Claude」の最上位プランが「Ultra」に 月200ドル", "Claude Ultraプランとは？料金と日本での使い方"));
  assert.deepEqual(links.map((l) => [l.kind, l.href]), [["pricing", "/guides/claude-pricing"], ["howto", "/guides/claude-how-to-use"]]);
});

test("Claude Code の記事には Claude（チャット）のガイドを混ぜない", () => {
  const links = guideLinksForArticle(article("Claude Codeに新機能"));
  assert.ok(links.length > 0);
  for (const link of links) assert.match(link.href, /claude-code/);
});

test("ガイドの無い製品・まとめ記事には何も出さない", () => {
  assert.deepEqual(guideLinksForArticle(article("Windows 11の右クリックメニューが整理可能に")), []);
  assert.deepEqual(guideLinksForArticle({ ...article("ChatGPTの料金"), type: "roundup" }), []);
});

test("料金の章の終わりに料金ガイドへの1行を差し込む", () => {
  const body = "## 概要\nA\n\n## 料金は？\n- 月200ドル\n\n## 日本で使える？\n使えます。";
  const out = insertAfterPricingSection(body, { kind: "pricing", href: "/guides/claude-pricing", label: "Claudeの料金" });
  const pricing = out.indexOf("## 料金は？");
  const note = out.indexOf('<p class="guide-link-note">');
  const japan = out.indexOf("## 日本で使える？");
  assert.ok(pricing < note && note < japan, out);
  assert.ok(out.includes('<a href="/guides/claude-pricing">Claudeの料金</a>'));
  // 料金の章が無い・料金ガイドでない案内なら本文は変えない
  assert.equal(insertAfterPricingSection("## 概要\nA", { kind: "pricing", href: "/x", label: "x" }), "## 概要\nA");
  assert.equal(insertAfterPricingSection(body, { kind: "howto", href: "/x", label: "x" }), body);
});

// 2026-11-10 SEO A12: 見える「使い方ガイド」（lib/howto.ts の howtoForArticle）と、この案内の欄は同じ1つの決まりで選ぶ
test("[A12] お金の話題の記事は、使い方ガイドの1行と案内の欄が同じガイドを指す（年金生活者支援給付金には出さない）", () => {
  const read = (slug) => JSON.parse(fs.readFileSync(path.join(root, "content/articles", `${slug}.json`), "utf8"));
  for (const slug of ["pension-support-benefit-old-age-eligibility", "pension-support-benefit-old-age-check", "kogaku-ryoyohi-2026-tasukai-kaisu", "child-allowance-third-child-monthly-30000", "kyoukai-kenpo-childbirth-allowance", "mynumber-insurance-card-guide"]) {
    const a = read(slug);
    const howto = howtoLib.howtoForArticle(a, howtos);
    const links = guideLinksForArticle(a, howtos).filter((l) => l.kind === "howto" || l.kind === "pricing").map((l) => l.href);
    assert.deepEqual(links, howto ? [`/guides/${howto.slug}`] : [], slug);
  }
  assert.deepEqual(guideLinksForArticle(read("pension-support-benefit-old-age-eligibility"), howtos), []);
  assert.deepEqual(guideLinksForArticle(read("kogaku-ryoyohi-2026-tasukai-kaisu"), howtos).map((l) => l.href), ["/guides/kogaku-ryoyohi"]);
});
