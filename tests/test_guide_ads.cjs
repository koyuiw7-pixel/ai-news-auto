const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 手続きガイド（/guides/*）と計算ツールの PR（lib/guide-ads.ts）を、実データ（content/howto・content/offers.json）で検査する。
// ガイドの話題と同じ提携商品だけが出ること、関係のないガイドには出ないこと、広告の文に書いてはいけない言葉が無いことを確かめる。
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
const { guideAds, guideAdRulesFor, toolAd, GUIDE_AD_RULES, GUIDE_AD_POS } = load(path.join(root, "lib/guide-ads.ts"));
const { AFFILIATE_REL } = load(path.join(root, "lib/affiliate.ts"));

const guides = fs
  .readdirSync(path.join(root, "content/howto"))
  .filter((name) => name.endsWith(".json"))
  .map((name) => JSON.parse(fs.readFileSync(path.join(root, "content/howto", name), "utf8")));
const bySlug = new Map(guides.map((guide) => [guide.slug, guide]));
const guide = (slug) => {
  assert.ok(bySlug.has(slug), `ガイドが無い: ${slug}`);
  return bySlug.get(slug);
};
const keys = (ad) => (ad?.items ?? []).map(({ item }) => item.key);

const FURUSATO = ["furusato-honpo", "aupay-furusato"];
const TAX = ["freee", "mf-kakutei", "yayoi-kakutei"];
const ALLOWED = { furusato: FURUSATO, tax: TAX, mobile: ["bb-excite"] };

test("ふるさと納税のガイドは、上も下もふるさと納税のサイト（確定申告のガイドだけ、下は確定申告ソフト）", () => {
  for (const slug of ["furusato-how", "furusato-limit", "furusato-onestop"]) {
    const { top, lower } = guideAds(guide(slug));
    assert.equal(top?.key, "furusato", slug);
    assert.equal(lower?.key, "furusato", slug);
    assert.deepEqual([...keys(top)].sort(), [...FURUSATO].sort(), slug);
    assert.deepEqual([...keys(lower)].sort(), [...FURUSATO].sort(), slug);
    // 下の囲みは、上で先頭でなかった商品を先頭にする
    assert.notEqual(keys(top)[0], keys(lower)[0], slug);
  }
  const kakutei = guideAds(guide("furusato-kakutei"));
  assert.equal(kakutei.top?.key, "furusato");
  assert.equal(kakutei.lower?.key, "tax");
  assert.ok(keys(kakutei.lower).every((key) => TAX.includes(key)));
});

test("年末調整・確定申告のガイドは確定申告ソフト", () => {
  for (const slug of ["nencho-how-to", "nencho-mid-career", "nencho-spouse", "nencho-target", "two-jobs-nencho", "fukugyo-20man", "iryohi-kojo", "nenkin-kakutei", "kanpu-shinkoku", "jigyo-shotoku", "zatsu-shotoku"]) {
    const { top, lower } = guideAds(guide(slug));
    assert.equal(top?.key, "tax", slug);
    assert.equal(lower?.key, "tax", slug);
    assert.ok(keys(top).length >= 1 && keys(top).every((key) => TAX.includes(key)), slug);
    assert.ok(keys(lower).every((key) => TAX.includes(key)), slug);
    assert.notEqual(keys(top)[0], keys(lower)[0], slug);
  }
  // 年末のお金の手続き（年末調整・ふるさと納税）は、見出しで先に出る話題が上、もう1つが下
  const calendar = guideAds(guide("nenmatsu-money-calendar"));
  assert.deepEqual([calendar.top?.key, calendar.lower?.key], ["tax", "furusato"]);
});

test("スマホの乗り換えのガイドは格安SIMだけ（光回線は出さない）", () => {
  const { top } = guideAds(guide("sumaho-norikae"));
  assert.equal(top?.key, "mobile");
  assert.deepEqual(keys(top), ["bb-excite"]);
});

test("関係のないガイドには出さない（AIツール・NISA・年金・子育て・マイナンバー・相続など）", () => {
  for (const item of guides.filter((g) => g.kind !== "procedure")) {
    assert.deepEqual(guideAds(item), {}, item.slug);
  }
  for (const slug of ["nisa-start", "nisa-limit", "jidou-teate", "myna-card-apply", "passport", "sozoku-zei", "zoyo-zei", "kokunen-menjo", "shitsugyo-kyufu", "nenshu-kabe", "kogaku-ryoyohi"]) {
    assert.deepEqual(guideAds(guide(slug)), {}, slug);
  }
  // 見出しや検索語に話題の語が無いガイドは、どれも出ない
  for (const item of guides) {
    const ads = guideAds(item);
    if (!ads.top) continue;
    const rules = guideAdRulesFor(item);
    assert.ok(rules.length > 0, item.slug);
    const text = `${item.title} ${item.seoTitle ?? ""} ${item.keyword ?? ""}`;
    const config = GUIDE_AD_RULES.find((c) => c.key === ads.top.key);
    const pattern = new RegExp(config.extra ? `${rules.find((r) => r.rule.key === ads.top.key).rule.match}|${config.extra.source}` : rules.find((r) => r.rule.key === ads.top.key).rule.match, "i");
    assert.ok(pattern.test(text), `${item.slug}: ${ads.top.key}`);
  }
});

test("出る商品は、話題ごとに決めた提携先だけ。リンクは計測IDつきで、置き場所の名前は受け口に通る", () => {
  const excluded = /化粧|コスメ|美容液|サプリ|健康食品|カジノ|ギャンブル|競馬|競輪|パチンコ|アダルト|FX|暗号資産|仮想通貨|信用取引|カードローン|キャッシング|消費者金融|マルチ商法|ネットワークビジネス/;
  let shown = 0;
  for (const item of guides) {
    const { top, lower } = guideAds(item);
    assert.ok(!lower || top, item.slug);
    for (const ad of [top, lower]) {
      if (!ad) continue;
      assert.ok(ad.items.length >= 1 && ad.items.length <= 2, item.slug);
      for (const { item: offer } of ad.items) {
        shown += 1;
        assert.ok(ALLOWED[ad.key]?.includes(offer.key), `${item.slug}: ${ad.key} に ${offer.key}`);
        assert.match(offer.url, /^https:\/\/px\.a8\.net\/svt\/ejp\?a8mat=[A-Z0-9+]+$/, offer.key);
        assert.doesNotMatch(offer.url, /YOUR_ID/);
        assert.doesNotMatch(`${offer.name} ${offer.label ?? ""} ${offer.note ?? ""}`, excluded, offer.key);
      }
    }
    // 同じ商品の表示の計測（pixel）は1ページで1回だけ
    const pixels = [top, lower].flatMap((ad) => (ad?.items ?? []).map(({ pixel }) => pixel).filter(Boolean));
    assert.equal(new Set(pixels).size, pixels.length, item.slug);
  }
  assert.ok(shown >= 40, `PR の出るガイドが少なすぎる（${shown}）`);
  // 置き場所の名前（data-aff-pos）: 受け口（cloudflare/aff.ts）に通り、末尾が数字でない（数字は順番として外される）。報告の呼び名もある
  const aff = fs.readFileSync(path.join(root, "cloudflare/aff.ts"), "utf8");
  const pos = new RegExp(aff.match(/const POS = \/(.+)\/;/)[1]);
  const stats = fs.readFileSync(path.join(root, "scripts/aff_stats.py"), "utf8");
  for (const name of Object.values(GUIDE_AD_POS)) {
    assert.match(name, pos);
    assert.doesNotMatch(name, /-\d+$/);
    assert.ok(stats.includes(`"${name}":`), name);
  }
});

test("提携リンクの無い商品は出さない（未設定なら囲みごと出ない）", () => {
  assert.deepEqual(guideAds(guide("furusato-how"), () => undefined), {});
  const onlyOne = (key) => (key === "aupay-furusato" ? { item: { key, kind: "partner", name: "x", url: "https://px.a8.net/svt/ejp?a8mat=A+B+C+D" } } : undefined);
  const ads = guideAds(guide("furusato-how"), onlyOne);
  assert.deepEqual(keys(ads.top), ["aupay-furusato"]);
  assert.deepEqual(keys(ads.lower), ["aupay-furusato"]);
  assert.equal(toolAd("furusato", () => undefined), undefined);
  // 一覧に無い話題（化粧品・投資など）は、計算ツールにも出せない
  assert.equal(toolAd("nisa"), undefined);
  assert.equal(toolAd("beauty"), undefined);
});

test("広告の文：ふるさと納税のサイトにポイントの約束を書かない。「ざっくり」と縦棒を使わない", () => {
  const offers = JSON.parse(fs.readFileSync(path.join(root, "content/offers.json"), "utf8"));
  const textOf = (value) => (typeof value === "string" ? value : Array.isArray(value) ? value.map(textOf).join(" ") : value && typeof value === "object" ? Object.entries(value).filter(([k]) => !["image", "link", "pixel", "programId", "page"].includes(k)).map(([, v]) => textOf(v)).join(" ") : "");
  const used = new Set(Object.values(ALLOWED).flat());
  for (const key of used) {
    const text = textOf(offers.partners[key]);
    assert.ok(text.length > 0, key);
    assert.doesNotMatch(text, /ざっくり|｜|\|/, key);
  }
  // ふるさと納税サイトのポイント付与は2025年10月から禁止。ポイント・還元の約束は書かない
  for (const key of FURUSATO) {
    assert.doesNotMatch(textOf(offers.partners[key]), /ポイント|還元|Ponta/i, key);
  }
  for (const rule of offers.actionAds.filter((r) => GUIDE_AD_RULES.some((c) => c.key === r.key))) {
    const text = `${rule.title} ${rule.reason ?? ""} ${rule.lead ?? ""}`;
    assert.doesNotMatch(text, /ざっくり|｜|\|/, rule.key);
    if (rule.key === "furusato") assert.doesNotMatch(text, /ポイント|還元/, rule.key);
  }
  const importer = fs.readFileSync(path.join(root, "scripts/a8_import.py"), "utf8");
  for (const line of importer.split("\n").filter((l) => /^\s*"(aupay-furusato|furusato-honpo)":/.test(l))) {
    assert.doesNotMatch(line.split("#")[0], /ポイント|還元|Ponta/i, line.trim().slice(0, 40));
  }
});

test("置き場所：ガイドは導入のすぐ下とよくある質問の前、計算ツールは結果のすぐ下。PR の札と rel=sponsored は共通の部品から付く", () => {
  const view = fs.readFileSync(path.join(root, "components/HowtoGuideView.tsx"), "utf8");
  const intro = view.indexOf("{guide.intro}</p>");
  const topAt = view.indexOf("<ActionAd ad={ads.top} pos={GUIDE_AD_POS.top}");
  const lowerAt = view.indexOf("<ActionAd ad={ads.lower} pos={GUIDE_AD_POS.lower}");
  const steps = view.indexOf('<Section id="steps"');
  const faq = view.indexOf('<Section id="faq"');
  assert.ok(intro > 0 && intro < topAt && topAt < steps, "上の囲みは導入のすぐ下・手順の前");
  assert.ok(steps < lowerAt && lowerAt < faq, "下の囲みは手順のあと・よくある質問の前");
  const tool = fs.readFileSync(path.join(root, "app/tools/furusato-limit/page.tsx"), "utf8");
  assert.ok(tool.includes('toolAd("furusato")') && tool.includes("pos={GUIDE_AD_POS.tool}") && tool.includes("afterCalc="));
  assert.doesNotMatch(tool, /ざっくり|｜/);
  assert.doesNotMatch(tool, /ポイント/);
  const shell = fs.readFileSync(path.join(root, "components/calc/ToolPage.tsx"), "utf8");
  assert.ok(shell.indexOf("<Calculator calc={{ kind }} />") < shell.indexOf("{afterCalc}") && shell.indexOf("{afterCalc}") < shell.indexOf("{children ?"));
  const block = fs.readFileSync(path.join(root, "components/ActionAd.tsx"), "utf8");
  assert.ok(block.includes("data-aff-pos={pos}") && block.includes("<PrTag />") && block.includes("PrFeature") && block.includes("PrRow"));
  const parts = fs.readFileSync(path.join(root, "components/rail/parts.tsx"), "utf8");
  assert.ok(parts.includes("rel={AFFILIATE_REL}"));
  assert.match(AFFILIATE_REL, /^sponsored /);
  // 計算ツールの PR はふるさと納税のサイトだけ
  assert.deepEqual([...keys(toolAd("furusato"))].sort(), [...FURUSATO].sort());
});
