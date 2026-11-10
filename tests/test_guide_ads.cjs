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
const KIDS = ["digitane", "litalico"];
const ALLOWED = { furusato: FURUSATO, tax: TAX, mobile: ["bb-excite"], kids: KIDS, medical: [] };

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

// 2026-11-10 M3: 児童手当のガイドは、上が子どもの学び、下がふるさと納税のサイトと上限額の計算への案内
test("児童手当のガイド：上は子どもの学び、下はふるさと納税のサイトと /tools/furusato-limit への案内", () => {
  const { top, lower } = guideAds(guide("jidou-teate"));
  assert.equal(top?.key, "kids");
  assert.ok(keys(top).length >= 1 && keys(top).every((key) => KIDS.includes(key)), keys(top).join());
  assert.equal(lower?.key, "furusato");
  assert.ok(keys(lower).length >= 1 && keys(lower).every((key) => FURUSATO.includes(key)), keys(lower).join());
  assert.deepEqual((lower.internal ?? []).map((link) => link.href), ["/tools/furusato-limit"]);
  assert.ok(!top.internal, "上の囲みにはサイト内の案内を出さない");
  // 子育ての広い語（子ども・出産・保育など）では、ほかの手続きのガイドに子どもの学びを出さない
  for (const item of guides.filter((g) => g.slug !== "jidou-teate")) {
    for (const ad of Object.values(guideAds(item))) assert.notEqual(ad?.key, "kids", item.slug);
  }
});

test("高額療養費のガイド：上の位置にサイト内の案内だけ（関係の薄い提携先は出さない）。保険相談の提携先が入れば同じ囲みに並ぶ", () => {
  const { top, lower } = guideAds(guide("kogaku-ryoyohi"));
  assert.equal(top?.key, "medical");
  assert.deepEqual(keys(top), [], "格安SIMなど話題の違う提携先を出さない");
  assert.equal(lower, undefined);
  const hrefs = (top.internal ?? []).map((link) => link.href);
  assert.deepEqual(hrefs, ["/guides/iryohi-kojo", "/articles/kogaku-ryoyohi-2026-tasukai-kaisu"]);
  assert.ok(fs.existsSync(path.join(root, "content/howto/iryohi-kojo.json")));
  assert.ok(fs.existsSync(path.join(root, "content/articles/kogaku-ryoyohi-2026-tasukai-kaisu.json")));
  for (const link of top.internal) assert.doesNotMatch(`${link.label} ${top.title} ${top.lead ?? ""}`, /ざっくり|｜/);
  // 保険相談の提携先（名前か説明に「保険相談」）が offers.json に入ると、ガイドを直さずに同じ囲みに並ぶ
  const fake = { item: { key: "hoken-soudan", kind: "partner", name: "保険相談の窓口", url: "https://px.a8.net/svt/ejp?a8mat=A+B+C+D" } };
  const seen = [];
  const filled = guideAds(guide("kogaku-ryoyohi"), (key) => (key === "hoken-soudan" ? fake : undefined), undefined, (pattern) => {
    seen.push(pattern);
    return pattern.test("保険相談の窓口") ? ["hoken-soudan"] : [];
  });
  assert.ok(seen.length === 1 && !seen[0].test("保険スクエアbang！ 火災保険を見直す"), "火災保険の見積もりは保険相談に数えない");
  assert.deepEqual(keys(filled.top), ["hoken-soudan"]);
  assert.deepEqual((filled.top.internal ?? []).map((link) => link.href), hrefs);
});

test("関係のないガイドには出さない（AIツール・NISA・年金・マイナンバー・相続など）", () => {
  for (const item of guides.filter((g) => g.kind !== "procedure")) {
    assert.deepEqual(guideAds(item), {}, item.slug);
  }
  for (const slug of ["nisa-start", "nisa-limit", "myna-card-apply", "passport", "sozoku-zei", "zoyo-zei", "kokunen-menjo", "shitsugyo-kyufu", "nenshu-kabe"]) {
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
    const base = rules.find((r) => r.rule.key === ads.top.key).rule.match;
    const pattern = new RegExp(config.only ? config.extra.source : config.extra ? `${base}|${config.extra.source}` : base, "i");
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
      // 提携商品の無い囲みは、サイト内の案内だけ（高額療養費のガイド）
      assert.ok(ad.items.length <= 2 && (ad.items.length >= 1 || (ad.internal ?? []).length >= 1), item.slug);
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

// 2026-11-10 M3: 囲みを実際に描いて、提携リンクと「サイソクの案内」を確かめる（Next.js を起動しない。next/link は a に置き換える）
function loadTsx(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const compiled = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  cache.set(file, mod);
  const original = mod.require.bind(mod);
  mod.require = (name) => {
    if (name === "next/link") {
      const React = require("react");
      return { __esModule: true, default: ({ href, children, ...rest }) => React.createElement("a", { href, ...rest }, children) };
    }
    if (name === "@/lib/content-fs") return fs;
    if (name === "@/lib/articles") return { getAllArticles: () => [] };
    if (name.startsWith("@/lib/")) return load(path.join(root, "lib", `${name.slice(6)}.ts`));
    if (name.startsWith("@/components/")) return loadTsx(path.join(root, "components", `${name.slice(13)}.tsx`));
    if (name.startsWith("./")) {
      const base = path.join(path.dirname(file), name);
      return fs.existsSync(`${base}.tsx`) ? loadTsx(`${base}.tsx`) : load(`${base}.ts`);
    }
    return original(name);
  };
  mod._compile(compiled, file);
  return mod.exports;
}

test("描いた囲み：提携リンクはすべて rel=sponsored で [data-aff-pos] の中、サイト内の案内には sponsored を付けない", () => {
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const ActionAd = loadTsx(path.join(root, "components/ActionAd.tsx")).default;
  const { actionAdForArticle } = load(path.join(root, "lib/action-ad.ts"));
  const article = (slug) => JSON.parse(fs.readFileSync(path.join(root, `content/articles/${slug}.json`), "utf8"));
  const boxes = [];
  for (const slug of ["pension-support-benefit-old-age-eligibility", "kyoukai-kenpo-childbirth-allowance", "child-allowance-third-child-monthly-30000", "kogaku-ryoyohi-2026-tasukai-kaisu", "izoku-nenkin-seikyu-tetsuzuki"]) {
    const ad = actionAdForArticle(article(slug));
    assert.ok(ad, slug);
    boxes.push([slug, ad, "action-ad"]);
  }
  for (const slug of ["jidou-teate", "kogaku-ryoyohi"]) {
    const { top, lower } = guideAds(guide(slug));
    if (top) boxes.push([slug, top, GUIDE_AD_POS.top]);
    if (lower) boxes.push([slug, lower, GUIDE_AD_POS.lower]);
  }
  for (const [slug, ad, pos] of boxes) {
    const html = renderToStaticMarkup(React.createElement(ActionAd, { ad, pos }));
    assert.match(html, new RegExp(`^<aside data-aff-pos="${pos}"`), slug);
    assert.equal((html.match(/<aside/g) ?? []).length, 1, slug);
    const anchors = html.match(/<a [^>]*>/g) ?? [];
    for (const a of anchors) {
      const href = a.match(/href="([^"]+)"/)[1];
      if (href.startsWith("/")) {
        assert.doesNotMatch(a, /sponsored|data-aff-rank/, `${slug}: サイト内の案内に sponsored`);
      } else {
        assert.match(href, /^https:\/\/px\.a8\.net\//, slug);
        assert.match(a, /rel="sponsored[^"]*"/, `${slug}: ${href}`);
      }
    }
    const internal = (ad.internal ?? []).map((x) => x.href);
    for (const href of internal) assert.ok(html.includes(`href="${href}"`), `${slug}: ${href}`);
    if (internal.length) {
      assert.match(html, /サイソクの案内/);
      // 案内は囲みの1行目（提携商品より前）
      const first = html.indexOf(`href="${internal[0]}"`);
      const sponsored = html.indexOf('rel="sponsored');
      assert.ok(sponsored < 0 || first < sponsored, `${slug}: 案内が先`);
    }
    if (ad.items.length === 0) {
      assert.doesNotMatch(html, />PR</, `${slug}: 広告の無い囲みに PR の札を出さない`);
      assert.doesNotMatch(html, /アフィリエイトリンク/, slug);
    } else {
      assert.match(html, />PR</, slug);
    }
  }
  const htmlOf = (slug, which) => renderToStaticMarkup(React.createElement(ActionAd, { ad: guideAds(guide(slug))[which], pos: GUIDE_AD_POS[which] }));
  assert.match(htmlOf("jidou-teate", "lower"), /href="\/tools\/furusato-limit"/);
  assert.match(htmlOf("kogaku-ryoyohi", "top"), /data-aff-pos="guide-top"/);
});

test("手続きガイドの「あわせて読む」は同じ話題のお金のガイド（AIツールのガイドを入れない）", () => {
  const { procedureSiblings } = load(path.join(root, "lib/money-pages.ts"));
  const all = guides;
  for (const slug of ["jidou-teate", "kogaku-ryoyohi", "nencho-how-to", "furusato-how"]) {
    const list = procedureSiblings(guide(slug), all);
    assert.ok(list.length >= 1, slug);
    for (const other of list) {
      assert.equal(other.kind, "procedure", `${slug}: ${other.slug}`);
      assert.notEqual(other.slug, slug);
    }
  }
  assert.equal(procedureSiblings(guide("kogaku-ryoyohi"), all)[0].slug, "iryohi-kojo");
  // 年末調整のガイドは、表で同じ話題の年末調整の対象のガイドが先
  assert.equal(procedureSiblings(guide("nencho-how-to"), all)[0].slug, "nencho-target");
  const view = fs.readFileSync(path.join(root, "components/HowtoGuideView.tsx"), "utf8");
  assert.ok(view.includes("siblingHowtos(guide)"));
  const howto = fs.readFileSync(path.join(root, "lib/howto.ts"), "utf8");
  assert.ok(howto.includes('if (guide.kind === "procedure") return procedureSiblings(guide, getAllHowtos(), limit);'));
});

test("記事の行動欄の PR は「すぐにできること」のすぐ下のまま（本文の下に動かさない）", () => {
  const page = fs.readFileSync(path.join(root, "app/articles/[slug]/page.tsx"), "utf8");
  const today = page.indexOf("<TodayActions actions={todayActions} />");
  const ad = page.indexOf("{actionAd && <ActionAd ad={actionAd}");
  const desk = page.indexOf("{depth.officialDesk.length > 0 && <OfficialDesk");
  const faq = page.indexOf("{articleFaq.length >= 1 && <ArticleFaq");
  assert.ok(today > 0 && today < ad && ad < desk && desk < faq, "今やること → PR → 公式の窓口 → よくある質問");
  const between = page.slice(today, ad);
  assert.equal((between.match(/\n/g) ?? []).length, 2, "今やることと PR のあいだに別の部品を入れない");
});
