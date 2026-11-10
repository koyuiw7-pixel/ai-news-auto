const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// Next.js を起動せず、本体の選択関数と実際のガイド設定をオフラインで検査する。
const root = path.resolve(__dirname, "..");
// 答えの欄の判定（lib/nonanswer.ts。式は lib/index-rules.json の notStated）は本物を使う
const loadTs = (rel, mocks = {}) => {
  const file = path.join(root, rel);
  const out = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true },
  }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  const original = mod.require.bind(mod);
  mod.require = (name) => (name in mocks ? mocks[name] : original(name));
  mod._compile(out, file);
  return mod.exports;
};
const nonanswer = loadTs("lib/nonanswer.ts");
// お金の話題 → ガイドの表（lib/money-pages.ts）も本物を使う（SEO A12。lib/guide-links.ts と同じ答え）
const moneyPages = loadTs("lib/money-pages.ts");
const sourcePath = path.join(root, "lib/howto.ts");
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText;
const loaded = new Module(sourcePath, module);
loaded.filename = sourcePath;
loaded.paths = Module._nodeModulePaths(path.dirname(sourcePath));
const requireOriginal = loaded.require.bind(loaded);
loaded.require = (name) => {
  if (name === "@/lib/content-fs") return fs;
  if (name === "@/lib/articles") return { getAllArticles: () => [] };
  // 文末の言い換え（lib/polite-text.ts）は振り分けに関係しない
  if (name === "@/lib/polite-text") return { politeDeep: (value) => value };
  if (name === "@/lib/nonanswer") return nonanswer;
  if (name === "@/lib/money-pages") return moneyPages;
  return requireOriginal(name);
};
loaded._compile(compiled, sourcePath);
const { howtoForArticle, answerSlots } = loaded.exports;
const readGuide = (slug) => JSON.parse(fs.readFileSync(path.join(root, "content/howto", `${slug}.json`), "utf8"));
const startup = readGuide("dify-1-18-startup-check");
const cost = readGuide("dify-free-api-cost");
const chatgptFree = readGuide("chatgpt-free-plan");
const chatgptHowto = readGuide("chatgpt-how-to-use");
const gemini = readGuide("gemini-free-plan");
const guides = [startup, cost, chatgptFree, chatgptHowto, gemini];
const pick = (title, seoTitle = "", candidates = guides) => howtoForArticle({ title, seoTitle }, candidates)?.slug;

test("Difyの料金・無料枠・APIキーの疑問を料金ガイドへ案内する", () => {
  for (const title of [
    "Dify Cloudの無料クレジットとAPI料金が変更",
    "Dify APIキーの利用条件を確認",
    "Dify Cloud free credits",
    "Dify API cost update",
    "Dify 1.18.0のAPI料金",
  ]) assert.equal(pick(title), cost.slug, title);
});

test("Difyの起動・版数・更新は起動ガイドへ案内する", () => {
  for (const title of ["Dify 1.18.0が起動しない", "Dify self-host upgrade", "Dify version 1.18.0", "Difyのapiコンテナが起動しない"]) {
    assert.equal(pick(title), startup.slug, title);
  }
  // 並び順が入れ替わっても、起動の疑問には起動ガイドを選ぶ。
  assert.equal(pick("Dify startup check", "", [cost, startup]), startup.slug);
});

test("疑問が特定できないDify記事は従来の最初の一致を維持する", () => {
  assert.equal(pick("Difyが新機能を発表"), startup.slug);
  assert.equal(pick("Difyが新機能を発表", "", [cost, startup]), cost.slug);
});

test("SEOタイトルの料金意図も読む", () => {
  assert.equal(pick("Dify Cloudの変更点", "API課金と費用"), cost.slug);
});

test("他ツールの既存案内と無関係な記事を変えない", () => {
  assert.equal(pick("ChatGPTの無料枠"), chatgptFree.slug);
  assert.equal(pick("ChatGPTの使い方"), chatgptFree.slug);
  assert.equal(pick("GeminiのAPI料金"), gemini.slug);
  assert.equal(pick("自治体の無料相談"), undefined);
});

test("不正または空の意図条件は既存fallbackを壊さない", () => {
  for (const match of ["[", ""]) {
    const broken = { ...cost, articleIntent: { match, priority: 100 } };
    assert.equal(pick("Difyの費用", "", [startup, broken]), startup.slug);
  }
  assert.equal(pick("Difyの費用", "", [{ ...startup, match: "[" }, cost]), cost.slug);
});

test("同点は従来順を保ち、候補配列を変更しない", () => {
  const candidates = [startup, { ...cost, articleIntent: { match: "起動", priority: 10 } }];
  const before = candidates.map((guide) => guide.slug);
  assert.equal(pick("Difyの起動", "", candidates), startup.slug);
  assert.deepEqual(candidates.map((guide) => guide.slug), before);
});

// 2026-11-10 LLMO-A4: 答えの欄に「このページには載っていません」を出さない（見える欄・FAQPage・結論・説明文）
test("答えが「載っていません」の質問は、よくある質問（見える欄と FAQPage）から外す", () => {
  const passport = {
    slug: "passport", conclusion: ["申請は住民登録のある都道府県の窓口で行います。", "手数料の金額は、このページには載っていません。"],
    description: "パスポートの申請の流れをまとめました。手数料の金額は、このページには載っていません。",
    faq: [
      { q: "パスポートの手数料はいくら？", a: "金額は、このページには載っていません。外務省は「手数料改定関連情報」を令和8年3月26日付で掲載しています。申請前に、最新の金額をそのページで確認します。" },
      { q: "どこで申請する？", a: "住民登録をしている都道府県のパスポート申請窓口で申請します。" },
      { q: "受け取りは代理でできる？", a: "受け取りは本人が窓口に行く必要があります。代理の受け取りの条件は案内されていません。" },
    ],
  };
  const out = answerSlots(passport);
  assert.deepEqual(out.faq.map((f) => f.q), ["どこで申請する？", "受け取りは代理でできる？"]);
  assert.equal(out.faq[0].a, passport.faq[1].a); // 答えている質問はそのまま
  assert.equal(out.faq[1].a, "受け取りは本人が窓口に行く必要があります。"); // 2文目の「案内されていません」は外す
  assert.deepEqual(out.conclusion, ["申請は住民登録のある都道府県の窓口で行います。"]);
  assert.equal(out.description, "パスポートの申請の流れをまとめました。");
  assert.equal(answerSlots({ ...passport, description: "手数料はこのページには載っていません。" }).description, out.conclusion[0]);
});

test("本物の passport ガイドでも、FAQ に「載っていません」の答えが出ない", () => {
  const out = answerSlots(readGuide("passport"));
  assert.ok(out.faq.every((f) => !nonanswer.isNotStated(f.a)), JSON.stringify(out.faq));
  assert.ok(!out.faq.some((f) => f.q === "パスポートの手数料はいくら？"));
});

test("答えになっていない文の式は、普通の答えを外さない", () => {
  assert.equal(nonanswer.answerOrNull("無料プランでも使えます。上限は1日10回です。"), "無料プランでも使えます。上限は1日10回です。");
  assert.equal(nonanswer.answerOrNull("料金は公式ページに記載がありません。"), null);
  assert.equal(nonanswer.answerOrNull("この記事では説明を控えます。"), null);
  assert.equal(nonanswer.answerOrNull("提供時期はまだ発表されていません。"), null);
});

// 2026-11-10 SEO A12: お金の話題は lib/money-pages.ts の表で決めたガイドだけ（lib/guide-links.ts と同じ1つの決まり）
test("[A12] 年金生活者支援給付金の記事に、「年金」の1語で当たる別のガイド（年金の確定申告）を出さない", () => {
  const all = require("node:fs").readdirSync(path.join(root, "content/howto")).filter((f) => f.endsWith(".json")).map((f) => readGuide(f.replace(/\.json$/, "")));
  for (const slug of ["pension-support-benefit-old-age-eligibility", "pension-support-benefit-old-age-check"]) {
    const a = JSON.parse(fs.readFileSync(path.join(root, "content/articles", `${slug}.json`), "utf8"));
    assert.equal(howtoForArticle(a, all), undefined, slug);
  }
  // 表でガイドを決めた話題はそのガイド。表に無い話題（年金の税金）は今までどおり match で選ぶ
  assert.equal(howtoForArticle({ title: "高額療養費の上限が変わる", tags: [] }, all)?.slug, "kogaku-ryoyohi");
  assert.equal(howtoForArticle({ title: "児童手当の支給日", tags: [] }, all)?.slug, "jidou-teate");
  assert.ok(howtoForArticle({ title: "年金の源泉徴収はいくら", tags: [] }, all));
});
