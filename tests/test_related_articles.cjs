const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 記事ページの「関連記事」「次に読むならこれ」の選び方（lib/related.ts。台帳 W19・2026-11-03 の点検の6番）を Next.js を起動せずに確かめる。
const root = path.resolve(__dirname, "..");
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
  mod.require = (name) => (name.startsWith("@/lib/") ? load(path.join(root, "lib", `${name.slice(6)}.ts`)) : original(name));
  mod._compile(compiled, file);
  return mod.exports;
}
const { relatedArticles, nextReads, similarity, isDisasterArticle, topicCluster } = load(path.join(root, "lib/related.ts"));
const { companyOf } = load(path.join(root, "lib/companies.ts"));
const company = (a) => companyOf(a).slug;

const base = { title: "", tags: [], keywords: [], genreSlug: "business", channelSlug: "", sourceUrl: "", publishedAt: "2026-11-02T00:00:00Z" };
let n = 0;
const art = (fields) => ({ ...base, slug: `a${n++}`, ...fields });

// 監査で見つかった組み合わせ（Appleの決算・年金月間・フットサル・リフォーム会社）と、同じジャンルの無関係な記事
const apple = art({ slug: "apple-q4", title: "Apple、7〜9月期の売上高が12％増の1145億ドル", genreSlug: "tech-gadget", tags: ["Apple", "決算", "スマートフォン", "業績", "ビジネス"], keywords: ["Apple", "決算", "iPhone Duo", "配当"] });
const appleDuo = art({ slug: "apple-duo", title: "Apple、折りたたみ型「iPhone Duo」向け最適化アプリを発表", genreSlug: "tech-gadget", tags: ["スマートフォン", "Apple", "ガジェット"], keywords: ["iPhone Duo", "Apple", "Netflix"] });
const appleMac = art({ slug: "apple-mac", title: "Appleが「M6」搭載の14インチMacBook Proを発表", genreSlug: "tech-gadget", tags: ["PC", "家電"], keywords: ["MacBook Pro", "M6", "Apple"], publishedAt: "2026-10-20T00:00:00Z" });
const samsung = art({ slug: "samsung-yog", title: "サムスン、ユース五輪ダカール大会に「Galaxy S26 Ultra」を提供", genreSlug: "tech-gadget", tags: ["スマートフォン", "通信", "家電"], keywords: ["サムスン", "Galaxy S26 Ultra"] });
const ipa = art({ slug: "ipa-dx", title: "IPA、DX認定制度で118件を公表", genreSlug: "tech-gadget", tags: ["ビジネス", "セキュリティ", "アプリ", "通信"], keywords: ["IPA", "DX認定"] });
const nenkin = art({ slug: "nenkin", title: "厚労省、11月30日の「年金の日」と11月の「ねんきん月間」で啓発", genreSlug: "public", tags: ["年金", "社会・行政", "ライフプラン"], keywords: ["厚生労働省", "日本年金機構", "ねんきんネット"] });
const izoku = art({ slug: "izoku", title: "厚労省、11月1日から「遺族年金受給者実態調査」を実施", genreSlug: "public", tags: ["年金", "社会保障", "行政"], keywords: ["厚生労働省", "遺族年金", "日本年金機構"] });
const quake = art({ slug: "quake-20261029000759", title: "【地震】千葉県北東部で最大震度5弱、M5.4（気象庁）", genreSlug: "public", channelSlug: "jma", tags: ["地震", "防災"], keywords: ["地震", "千葉県"] });
const tokyo = art({ slug: "tokyo-challenge", title: "東京都、地域企業グループチャレンジ促進事業で4グループを決定", genreSlug: "public", tags: ["社会・行政", "中小企業支援", "東京都"], keywords: ["東京都"] });
const futsal = art({ slug: "futsal", title: "フットサル日本代表、11月6日・8日に大分でモロッコ代表と親善試合", genreSlug: "sports", tags: ["サッカー", "フットサル", "日本代表", "モロッコ"], keywords: ["フットサル日本代表"] });
const bounty = art({ slug: "openai-bounty", title: "OpenAI、セキュリティのバグ報奨金を増額", genreSlug: "ai", tags: ["OpenAI", "サイバーセキュリティ"], keywords: ["OpenAI", "バグバウンティ"] });
const reform = art({ slug: "reform", title: "リフォームテクノロジー、持株会社体制へ移行", genreSlug: "business", tags: ["住宅設備", "DX", "企業再編"], keywords: ["交換できるくん", "持株会社"] });
const beer = art({ slug: "beer", title: "地ビール1-8月出荷量は2年連続増", genreSlug: "business", tags: ["ビジネス", "統計", "小売", "飲食"], keywords: ["地ビール", "東京商工リサーチ"] });
const tobacco = art({ slug: "tobacco", title: "財務省、製造たばこの小売定価の認可情報を随時公開　日付ごとにPDFで確認可能", genreSlug: "business", tags: ["ビジネス", "統計"], keywords: ["PDF", "たばこ"] });
const gemini = art({ slug: "gemini-pdf", title: "Gemini、ファイルを直接編集", genreSlug: "ai", tags: ["Gemini"], keywords: ["PDF", "Google"] });
const dup = art({ slug: "apple-q4-dup", title: "Apple、第4四半期の業績を発表", genreSlug: "tech-gadget", tags: ["Apple", "決算"], keywords: ["Apple", "決算"], duplicateOf: "apple-q4" });
// 文書頻度の母数（多くの記事に付く語を「話題」と数えない）を実データに近づけるための、関係のない記事
const filler = Array.from({ length: 60 }, (_, i) => art({ title: `新サービス${i}を開始`, tags: ["ビジネス", "統計", "社会・行政", "スマートフォン"], keywords: [`語${i}`] }));
const all = [apple, appleDuo, appleMac, samsung, ipa, nenkin, izoku, quake, tokyo, futsal, bounty, reform, beer, tobacco, gemini, dup, ...filler];
const now = Date.parse("2026-11-03T00:00:00Z");
const slugs = (items) => items.map((a) => a.slug);

test("Appleの決算の関連記事は Apple の記事だけ（同じジャンルのサムスン・IPA は出さない。重複記事も出さない）", () => {
  const got = slugs(relatedArticles(apple, all, company, 4, now));
  assert.deepEqual(got.sort(), ["apple-duo", "apple-mac"]);
  assert.ok(!got.includes("apple-q4-dup"));
});

test("年金の記事の関連に地震・同じ分野の別の話題を出さない（同じ年金の記事は出す）", () => {
  const got = slugs(relatedArticles(nenkin, all, company, 4, now));
  assert.deepEqual(got, ["izoku"]);
  const next = nextReads(nenkin, all, company, 3, now);
  assert.ok(next.every((x) => x.article.slug !== "tokyo-challenge" && x.article.slug !== "quake-20261029000759"));
  // 地震の記事の関連にも、ほかの記事を混ぜない
  assert.deepEqual(slugs(relatedArticles(quake, all, company, 4, now)), []);
  assert.ok(isDisasterArticle(quake) && !isDisasterArticle(nenkin));
});

test("関係のある記事が無ければ空（フットサル・リフォーム・たばこに無関係な記事で埋めない）", () => {
  assert.deepEqual(slugs(relatedArticles(futsal, all, company, 4, now)), []);
  assert.deepEqual(slugs(relatedArticles(reform, all, company, 4, now)), []);
  // 「PDF」のような分野の語1つだけでは関連にしない
  assert.deepEqual(slugs(relatedArticles(tobacco, all, company, 4, now)), []);
  assert.equal(similarity(tobacco, gemini, all, company).strong, false);
});

test("記事を作るときに使った過去記事（relatedSlugs）も、話題が重ならなければ出さない", () => {
  const withCtx = { ...nenkin, relatedSlugs: ["quake-20261029000759", "tokyo-challenge", "izoku"] };
  assert.deepEqual(slugs(relatedArticles(withCtx, all, company, 4, now)), ["izoku"]);
});

test("「同じ話題の記事」の札は語が2つ以上重なる記事だけ。名前（企業）だけ重なる記事は「同じ企業の発表」", () => {
  const next = nextReads(apple, all, company, 3, now);
  const reason = Object.fromEntries(next.map((x) => [x.article.slug, x.reason]));
  assert.equal(reason["apple-duo"], "同じ話題の記事");
  assert.equal(reason["apple-mac"], "同じ企業の発表");
  assert.ok(!("samsung-yog" in reason) && !("ipa-dx" in reason));
});

test("実データ: 関連記事は話題の基準を満たすものだけ・地震と混ぜない・自分と重複を出さない", () => {
  const dir = path.join(root, "content/articles");
  const real = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => ({ tags: [], keywords: [], ...JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) }));
  for (const a of real) {
    const got = relatedArticles(a, real, company, 4, now);
    for (const b of got) {
      assert.notEqual(b.slug, a.slug);
      assert.equal(isDisasterArticle(b), isDisasterArticle(a), `${a.slug} → ${b.slug}`);
      assert.ok(similarity(a, b, real, company).strong, `${a.slug} → ${b.slug}`);
      assert.notEqual(b.duplicateOf, a.slug, `${a.slug} → ${b.slug}`);
    }
  }
});

test("記事ページは lib/related.ts の選び方を使う（同じジャンルに点数を足す古い選び方に戻さない）", () => {
  const src = fs.readFileSync(path.join(root, "lib/articles.ts"), "utf8");
  assert.match(src, /relatedArticles\(article, getAllArticles\(\)/);
  assert.match(src, /nextReads\(article, getAllArticles\(\)/);
  assert.ok(!/genreSlug === article\.genreSlug \? 5/.test(src));
});

test("情報流出の記事の関連は、名前（ドコモ）だけ重なる記事より、同じ困りごと（情報流出）の記事を先に（2026-11-10）", () => {
  const leak = art({ slug: "docomo-leak", title: "ドコモ情報流出、最大30万件　今日やるのは明細の確認", tags: ["情報流出", "ドコモ", "セキュリティ"], keywords: ["ドコモ 情報流出"] });
  const other = art({ slug: "other-leak", title: "アララのメール配信で7,700万件流出の恐れ", tags: ["情報流出", "メール"], keywords: ["不審メール"] });
  const pass = art({ slug: "d-pass", title: "ドコモ「dバリューパス」にUberとLUUPの特典", tags: ["ドコモ", "ポイント"], keywords: ["dバリューパス"] });
  const pen = art({ slug: "d-pen", title: "ドコモ、再生材のタッチペンを発売", tags: ["ドコモ", "環境"], keywords: ["タッチペン"] });
  const pool = [leak, other, pass, pen, ...filler];
  const got = slugs(relatedArticles(leak, pool, company, 4, now));
  assert.equal(got[0], "other-leak");
  // 名前だけ重なる記事は、全部で2本に満たないときだけ（関係の薄い記事で埋めない）
  assert.ok(got.length <= 2, got.join(","));
});

test("[A10] 出典 URL の比べ方は索引（article-index.mjs）と同じ（?period=・#entry- を残す）", async () => {
  const { urlKey } = load(path.join(root, "lib/related.ts"));
  const index = await import(path.join(root, "lib/article-index.mjs"));
  for (const url of [
    "https://www.stat.go.jp/data/kakei/sokuhou/tsuki/pdf/fies_mr.pdf?period=2026-09",
    "https://platform.claude.com/docs/en/release-notes/overview.md#entry-2026-11-03",
    "https://example.com/news/a/?utm_source=x",
    "https://www.jma.go.jp/bosai/map.html#contents=earthquake_map",
  ]) assert.equal(urlKey(url), index.urlKey(url), url);
  assert.notEqual(urlKey("https://x.jp/a.pdf?period=2026-08"), urlKey("https://x.jp/a.pdf?period=2026-09"));
});

// 同じ話題の束（lib/related.ts の topicCluster。2026-11-13 オーナー「Googleからの流入対策」）
test("束: 紅白の3本は互いに結ぶ。「紅白」だけ重なる別の商品の記事は入れない", () => {
  const at = "2026-11-13T05:00:00Z";
  const list = art({ slug: "kohaku-list", title: "紅白歌合戦2026 出場歌手41組の一覧　初出場は7組", genreSlug: "lifestyle", tags: ["年末年始", "テレビ"], keywords: ["紅白歌合戦2026", "紅白 出場歌手"], generatedAt: at });
  const debut = art({ slug: "kohaku-debut", title: "紅白歌合戦2026、初出場7組の一覧と代表曲", genreSlug: "lifestyle", tags: ["テレビ", "年末年始", "音楽"], keywords: ["紅白歌合戦2026", "紅白 初出場"], generatedAt: at });
  const changes = art({ slug: "kohaku-changes", title: "紅白の出場41組、去年から20組が入れ替わる", genreSlug: "entertainment", tags: ["テレビ", "大みそか", "音楽"], keywords: ["紅白 出場歌手", "紅白歌合戦2026"], generatedAt: at });
  const drink = art({ slug: "horoyoi", title: "ほろよい「紅白スパークリング」1月5日発売", genreSlug: "lifestyle", tags: ["食品", "飲料"], keywords: ["ほろよい"], generatedAt: at });
  const pool = [list, debut, changes, drink, ...filler];
  assert.deepEqual(slugs(topicCluster(list, pool, 3, company)).sort(), ["kohaku-changes", "kohaku-debut"]);
  assert.deepEqual(slugs(topicCluster(debut, pool, 3, company)).sort(), ["kohaku-changes", "kohaku-list"]);
  assert.deepEqual(slugs(topicCluster(changes, pool, 3, company)).sort(), ["kohaku-debut", "kohaku-list"]);
  assert.deepEqual(slugs(topicCluster(drink, pool, 3, company)), []);
  // 「次に読むならこれ」の先頭に「同じ話題の記事」として出る
  const next = nextReads(list, pool, company, 3, now);
  assert.deepEqual(next.slice(0, 2).map((x) => x.article.slug).sort(), ["kohaku-changes", "kohaku-debut"]);
  assert.ok(next.slice(0, 2).every((x) => x.reason === "同じ話題の記事"));
});

test("束: 出典 URL が同じでも別の記事（NVIDIA の CEO 退任と決算）は結ぶ。同じ会社の別の発表・14日より古い記事・重複の印のある記事は入れない", () => {
  const url = "https://nvidianews.nvidia.com/news/nvidia-announces-ceo-transition";
  const ceo = art({ slug: "nv-ceo", title: "NVIDIAのフアンCEOが即日退任　決算は17日予定どおり", genreSlug: "ai", tags: ["NVIDIA", "人事", "決算"], keywords: ["NVIDIA CEO"], sourceUrl: url, generatedAt: "2026-11-12T13:00:00Z" });
  const earn = art({ slug: "nv-earn", title: "NVIDIA決算は11月18日朝　CEO交代後の初決算", genreSlug: "investment", tags: ["投資信託", "決算", "NVIDIA"], keywords: ["NVIDIA 決算"], sourceUrl: url, generatedAt: "2026-11-13T05:00:00Z" });
  const robot = art({ slug: "nv-robot", title: "NVIDIA、ロボット向けAI「GR00T 2」を公開", genreSlug: "ai", tags: ["NVIDIA", "ロボティクス"], keywords: ["GR00T 2"], generatedAt: "2026-11-09T05:00:00Z" });
  const old = art({ slug: "nv-old", title: "NVIDIAのフアンCEOが基調講演", genreSlug: "ai", tags: ["NVIDIA"], keywords: ["NVIDIA CEO"], generatedAt: "2026-10-20T05:00:00Z" });
  const copy = art({ slug: "nv-dup", title: "NVIDIAのCEOが退任", genreSlug: "ai", tags: ["NVIDIA"], keywords: ["NVIDIA CEO"], duplicateOf: "nv-ceo", generatedAt: "2026-11-12T14:00:00Z" });
  const others = Array.from({ length: 12 }, (_, i) => art({ title: `NVIDIA、新しい開発ツール${i}を公開`, genreSlug: "ai", tags: ["NVIDIA"], keywords: [`ツール${i}`], generatedAt: "2026-09-01T00:00:00Z" }));
  const pool = [ceo, earn, robot, old, copy, ...others, ...filler];
  assert.deepEqual(slugs(topicCluster(earn, pool, 3, company)), ["nv-ceo"]);
  assert.deepEqual(slugs(topicCluster(ceo, pool, 3, company)), ["nv-earn"]);
  assert.deepEqual(slugs(topicCluster(robot, pool, 3, company)), []);
  assert.equal(nextReads(earn, pool, company, 3, now)[0].article.slug, "nv-ceo");
});

test("束: 記事ページの「この話の続き」は、次にやることが何本あっても束の記事が入る位置に置く（今までの見た目・ノワールの両方）", () => {
  for (const file of ["app/articles/[slug]/page.tsx", "components/noir/noirArticlePage.tsx"]) {
    const src = fs.readFileSync(path.join(root, file), "utf8");
    assert.match(src, /\.slice\(0, 1\), clusterReads, topicReads\.slice\(2\)/, file);
  }
  assert.match(fs.readFileSync(path.join(root, "lib/articles.ts"), "utf8"), /topicCluster\(article, getAllArticles\(\), limit, companySlugOf\)/);
});

test("束: 実データで紅白の3本と NVIDIA の2本が互いに出る", () => {
  const dir = path.join(root, "content/articles");
  const need = [
    ["nhk-kohaku-2026-41-performers", "kouhaku-2026-debut-7-groups", "kohaku-2026-singers-changes-list"],
    ["nvidia-earnings-ceo-transition-orukan", "nvidia-ceo-transition-huang-resigns"],
  ];
  if (!need.flat().every((slug) => fs.existsSync(path.join(dir, `${slug}.json`)))) return;
  const real = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => ({ tags: [], keywords: [], ...JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) }));
  for (const group of need) {
    // あとで重複の印が付いた記事は束から外れるので、その組は確かめない
    if (group.some((slug) => real.find((x) => x.slug === slug).duplicateOf)) continue;
    for (const slug of group) {
      const a = real.find((x) => x.slug === slug);
      const got = slugs(topicCluster(a, real, 3, company));
      for (const other of group) if (other !== slug) assert.ok(got.includes(other), `${slug} → ${other}（${got.join(",")}）`);
    }
  }
});
