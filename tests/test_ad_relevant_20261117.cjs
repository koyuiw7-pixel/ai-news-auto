// 2026-11-17 オーナー決定「2、だね。広告がないのはやめてほしいかな」（台帳 W47）:
// 新しい見た目（ノワール）の記事は、話題が当たらない既定の広告（fallback-*）を出さない決まり（2026-11-10。年金の記事に証券会社が出ていた）のまま、
// 記事の品物・場面に合う話題（content/offers.json の shop-*・watch-*・net-price・water-server・yutai・leak-other）を足して、PR の無い記事を減らす。
// 通販は楽天市場（A8 の楽天アフィリエイト）と Amazon（アソシエイト）の検索結果だけ（価格・宣伝文句なし）。提携先は今ある A8 の案件だけ。
// 化粧品・健康食品・ギャンブル（宝くじを含む）・成人向け・値動きの大きい投資・借入・連鎖販売は出さない。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

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
const { offerPlanForArticle, afterBodyOffer, isValidAffiliateUrl } = load(path.join(root, "lib/offers.ts"));
const offers = JSON.parse(fs.readFileSync(path.join(root, "content/offers.json"), "utf8"));
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");
const articleJson = (slug) => {
  const file = path.join(root, "content/articles", `${slug}.json`);
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : undefined;
};
const base = { slug: "t", title: "", seoTitle: "", lede: "", description: "", highlights: [], tags: [], keywords: [], genreSlug: "lifestyle", channelSlug: "", sourceName: "" };
const article = (fields) => ({ ...base, ...fields });
const keys = (offer) => (offer?.items ?? []).map((item) => item.key);
/** ノワールの記事で本文の後ろに出る囲み（審査の期間。components/noir/noirArticlePage.tsx の matched と同じ判定） */
const noirBox = (a) => {
  const shown = afterBodyOffer(offerPlanForArticle(a, [], []), true);
  return shown && !String(shown.topic ?? "").startsWith("fallback-") ? shown : undefined;
};
const decoded = (url) => decodeURIComponent(decodeURIComponent(decodeURIComponent(url)));
const SECURITIES = ["matsui", "dmm-kabu"];

test("実データ: ナゲットの記事（ノワール）に、同じ種類の食品の検索の囲みが出る", (t) => {
  const a = articleJson("mcdonalds-mcnugget-15pc-490yen");
  if (!a) return t.skip("記事が無い");
  assert.equal(a.layout, "noir");
  const box = noirBox(a);
  assert.ok(box, "囲みが出る");
  assert.equal(box.topic, "shop-food");
  assert.equal(box.headline, "同じ種類の食品や飲み物を、通販でも探す");
  const [rakuten, amazon] = box.items;
  assert.equal(rakuten.name, "「冷凍 チキンナゲット」を楽天市場で探す");
  assert.ok(decoded(rakuten.url).includes("search.rakuten.co.jp/search/mall/冷凍 チキンナゲット/"), rakuten.url);
  assert.equal(amazon.url, `https://www.amazon.co.jp/s?k=${encodeURIComponent("冷凍 チキンナゲット")}&tag=saisokuai-22`);
  assert.ok(box.items.every((item) => item.price == null && !item.priceText && isValidAffiliateUrl(item.url)));
});

// 2026-11-21 オーナー「無関係な広告で埋めない」: 回収の記事に同じ種類の品物の広告を出さない決まりに変更
test("実データ: イヤホン回収の記事（ノワール）に、イヤホンの専門店や同じ種類の検索の囲みを出さない", (t) => {
  const a = articleJson("shinken-zemi-earphone-recall-pth077b");
  if (!a) return t.skip("記事が無い");
  assert.equal(noirBox(a), undefined);
});

test("年金の記事には証券会社を出さない（2026-11-10 の決まりのまま）", () => {
  for (const slug of ["pension-payment-december-2026-two-months", "pension-dec-payment-child-allowance", "kokumin-nenkin-premium-deadline-nov30"]) {
    const a = articleJson(slug);
    if (!a || a.layout !== "noir") continue;
    // 本文の後ろに出る囲み（ジャンルの既定の広告の候補に証券会社があっても、ノワールの記事では出ない）
    const shown = noirBox(a);
    assert.ok(!keys(shown).some((k) => SECURITIES.includes(k)), slug);
  }
  for (const title of ["年金生活者支援給付金、12月15日に振り込み", "年金は12月15日に2か月分まとめて振り込み　10月分と11月分が対象"]) {
    for (const genreSlug of ["public", "lifestyle"]) {
      const a = article({ title, genreSlug });
      assert.ok(!keys(noirBox(a)).some((k) => SECURITIES.includes(k)), title);
      assert.ok(!String(offerPlanForArticle(a).offer?.topic ?? "").startsWith("shop-"), title);
    }
  }
});

test("話題が当たらない既定の広告は、ノワールの記事に今までどおり出さない（タグだけで決まる製品カテゴリも）", () => {
  assert.ok(read("components/noir/noirArticlePage.tsx").includes('startsWith("fallback-") ? o : undefined'));
  // 北朝鮮の国旗の記事: 合う品物が無いので囲みは出ない
  assert.equal(noirBox(article({ title: "北朝鮮国旗の縦横比を変更と報道", genreSlug: "public" })), undefined);
  // 見出しに品物の無い記事は、タグに「スマホ」があっても製品の検索を出さない（ポケモンの記事にスマホが出ていた）
  const pokemon = article({ title: "ポケモン30周年、CEOが語る未来", genreSlug: "tech-gadget", tags: ["スマートフォン"] });
  assert.equal(offerPlanForArticle(pokemon).offer.topic, "fallback-product");
  assert.equal(noirBox(pokemon), undefined);
  // 見出しの語で決まる製品カテゴリは記事の品物そのものなので出す
  assert.equal(noirBox(article({ title: "GTA6の事前ダウンロード開始　PS5版は容量212GB", genreSlug: "entertainment" })).topic, "product-search");
  // スポーツの記事はタグの競技でよい
  const basket = noirBox(article({ title: "富山グラウジーズ、三河に70対111で敗れる", genreSlug: "sports", tags: ["バスケットボール"] }));
  assert.equal(basket.topic, "product-search");
});

test("記事の場面ごとの囲み（楽天のセールは楽天だけ・配信は記事にある配信サービスだけ・回収の食品には出さない）", () => {
  const rakuten = noirBox(article({ title: "楽天ブラックフライデー2026は11月19日20時開始　エントリー必須" }));
  assert.equal(rakuten.topic, "shop-sale");
  assert.deepEqual(keys(rakuten), ["rakuten-search:ブラックフライデー"]);
  const amazon = noirBox(article({ title: "Amazonブラックフライデー2026、日程は11月19日午前に公開" }));
  assert.deepEqual(keys(amazon), ["amazon-search:ブラックフライデー"]);
  const prime = noirBox(article({ title: "侍ジャパン決勝は11月15日19時、TBSとPrime Videoで見られる", genreSlug: "sports" }));
  assert.equal(prime.topic, "watch-prime");
  assert.deepEqual(keys(prime), ["amazon-prime"]);
  assert.equal(prime.items[0].url, "https://www.amazon.co.jp/amazonprime?tag=saisokuai-22");
  const abema = noirBox(article({ title: "U-21日本代表の遠征2試合をABEMAで無料配信", genreSlug: "sports" }));
  assert.deepEqual(keys(abema), ["abema-premium"]);
  // U-NEXT で見る試合に、ほかの配信サービスを出さない（サッカーの記事なのでサッカー用品の検索）
  const unext = noirBox(article({ title: "日本代表対ブラジル、19時15分キックオフ　テレビ朝日系とU-NEXTで無料視聴", genreSlug: "sports", tags: ["サッカー日本代表"] }));
  assert.equal(unext.topic, "product-search");
  // 食品の回収の記事は「同じ種類の食品」を出さない
  assert.equal(noirBox(article({ title: "モンテールのシュークリーム3品を回収　消費期限11月11日" })), undefined);
  assert.equal(noirBox(article({ title: "神戸物産の「砂糖不使用デーツバー」にかびの恐れ　返金と回収" })), undefined);
  // 暖房器具の回収の記事には暖房器具を出さない（2026-11-10 の決まり。lib/amazon.ts と同じ）
  assert.equal(noirBox(article({ title: "丸隆の電気ストーブ、端子の発火のおそれで点検交換", genreSlug: "business" })), undefined);
  // 流出の記事（スポーツ）はセキュリティ対策
  assert.equal(noirBox(article({ title: "JFA STOREの利用者11人のメールアドレスが漏えい", genreSlug: "sports" })).topic, "leak-other");
});

test("ほかの話題が当たる記事では、最後の手段の話題（lastResort）を使わない", () => {
  const plan = offerPlanForArticle(article({ title: "停電に備えるポータブル電源、台風の前に確認", genreSlug: "lifestyle", tags: ["停電", "防災"] }));
  assert.ok(plan.offer.items.every((item) => !String(item.topic).startsWith("shop-")));
  assert.equal(plan.offer.topic, "life-disaster");
});

test("出さない種類（化粧品・健康食品・ギャンブル・宝くじ・成人向け・値動きの大きい投資・借入・連鎖販売）は、新しい話題の検索語・提携先にも、当たる記事にも無い", () => {
  const NG = /化粧|コスメ|スキンケア|美容|サプリ|健康食品|青汁|プロテイン|宝くじ|ロト|競馬|競輪|競艇|パチンコ|カジノ|成人|アダルト|FX|仮想通貨|暗号資産|ローン|借入|キャッシング|リボ|ネットワークビジネス/;
  const added = offers.topics.filter((t) => t.lastResort || /^(shop|watch)-|^(net-price|water-server|yutai|leak-other)$/.test(t.key));
  assert.ok(added.length >= 15);
  for (const topic of added) {
    for (const s of topic.shop ?? []) assert.doesNotMatch(s.query, NG, topic.key);
    for (const key of topic.partners) {
      const p = offers.partners[key];
      assert.ok(p, `${topic.key}: ${key} は今ある提携先`);
      assert.doesNotMatch(`${p.name} ${p.label}`, NG, key);
    }
    // 見出しに「｜」「ざっくり」を使わない
    assert.doesNotMatch(`${topic.headline}${topic.lead}`, /｜|ざっくり/, topic.key);
    assert.equal(topic.titleOnly, true, topic.key);
  }
  for (const title of ["年末ジャンボ宝くじ、11月24日発売", "ロト6で1等1億1000万円超が出現", "よーじやハッピーバッグ2027、1人1点まで", "特茶初のサプリ「特茶W」11月20日発売", "ドンキの「焼き芋」がコスメや雑貨に"]) {
    assert.equal(noirBox(article({ title })), undefined, title);
  }
  // 化粧品の製品カテゴリ（スキンケア）は通販の検索にも出さない
  assert.ok(!/スキンケア|化粧水/.test(read("lib/keyword-products.ts").replace(/\/\/.*$/gm, "")));
});

test("実データ: 新しい話題の囲みは、どの記事でも提携リンクの形が正しく、価格を出さない", () => {
  const dir = path.join(root, "content/articles");
  let count = 0;
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    let a;
    try { a = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")); } catch { continue; }
    const shown = afterBodyOffer(offerPlanForArticle(a, [], []), true);
    if (!shown || !/^(shop|watch)-|^product-search$/.test(String(shown.topic))) continue;
    count += 1;
    for (const item of shown.items) {
      assert.ok(isValidAffiliateUrl(item.url), `${a.slug}: ${item.url}`);
      if (/-search:/.test(item.key)) assert.ok(item.price == null && !item.priceText, a.slug);
    }
  }
  assert.ok(count >= 50, `新しい話題の囲みの記事 ${count}`);
});
