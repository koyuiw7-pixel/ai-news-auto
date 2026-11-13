import type { ArticleSummary } from "@/lib/articles";

/**
 * 記事ページの「関連記事」「次に読むならこれ」（同じ話題の記事・同じ企業の発表）の選び方（2026-11-03 オーナー判断・台帳 W19）。
 *
 * 前の選び方は「同じジャンル」に5点を足していたので、中身と関係のない同じジャンルの新着が並んでいた
 * （Appleの決算 → サムスンのユース五輪・IPAのDX認定、年金月間 → 【地震】、フットサル → OpenAIのバグ報奨金）。
 * 新しい選び方:
 *   1. 話題の重なり: タグ・キーワード・見出しの固有名詞（英字の名前・3字以上のカタカナ・「」の中）のうち、
 *      多くの記事に付く語（ジャンル名・「統計」「ビジネス」など）を除いた語が重なるか。珍しい語ほど重い（IDF）
 *   2. 同じ企業（companies.ts の分類。「その他」は数えない）
 *   3. 同じジャンルは小さな加点だけ（ジャンルだけでは選ばない）
 *   4. 新しい記事を少し上に
 * 基準に届く記事が無ければ何も出さない（関係のない記事で埋めない）。地震・津波の記事とそれ以外は混ぜない。
 * 同じ発表の重複記事（duplicateOf・同じ出典URL）は選ばない。
 */

/** どの記事にも付きやすく、話題の手がかりにならない語（ジャンル名・分野名・発表の種類） */
const GENERIC = new Set(
  [
    "AI", "AIツール", "AIニュース", "生成AI", "人工知能", "テクノロジー", "テック", "AIエージェント", "LLM", "使い方", "料金", "無料",
    "日本語", "とは", "開発", "アップデート", "ニュース", "発表", "調査", "ビジネス", "ビジネス・経済", "経済", "統計", "統計情報", "行政",
    "社会・行政", "社会", "暮らし", "暮らし・生活", "生活", "ライフスタイル", "スポーツ", "エンタメ", "テクノロジー・ガジェット", "ガジェット",
    "投資・マネー", "金融", "IT", "DX", "アプリ", "通信", "セキュリティ", "提携", "業務提携", "連携", "協定", "地域", "イベント",
    "キャンペーン", "セール", "新製品", "新サービス", "デザイン", "トレンド", "環境", "政策", "教育", "日本", "国内", "海外", "企業",
    "サービス", "公式", "発表会", "2026年", "2027年", "令和8年",
    // 業種・製品の大きな分類（2026-11-10: 暖房の電気代の記事に「家電」だけ重なるスマホ・ディスプレイの記事が並んだ）
    "家電", "小売", "飲食", "食品", "流通", "製造業", "家計",
  ].map(norm),
);

export type CompanyOf = (a: ArticleSummary) => string;

export type NextRead = { article: ArticleSummary; reason: string };

type Ctx = { df: Map<string, number>; n: number; cap: number; terms: WeakMap<ArticleSummary, Set<string>>; names: WeakMap<ArticleSummary, Set<string>> };
const contexts = new WeakMap<object, Ctx>();

function norm(word: string): string {
  return (word ?? "").normalize("NFKC").trim().toLowerCase();
}

/** 英字の略語・カタカナの一般語（固有名詞ではない。見出しに出ても同じ話題の手がかりにしない） */
const NAME_STOP = new Set(
  [
    "AI", "IT", "DX", "PDF", "API", "SNS", "CEO", "CFO", "URL", "APP", "PC", "OS", "CPU", "GPU", "NPU", "IOT", "EV", "PHEV", "HEV", "SDK", "UI",
    "WEB", "CVE", "FAQ", "ETF", "LLM", "GX", "SDGS", "PR", "IR", "Q", "Pro", "Max", "Plus", "Ultra", "Mini", "Air", "New",
    "サービス", "システム", "データ", "ネット", "アプリ", "ユーザー", "プラン", "モデル", "ツール", "セキュリティ", "ガイドライン", "プログラム",
    "プロジェクト", "ビジネス", "マッチング", "イベント", "キャンペーン", "オンライン", "デジタル", "テクノロジー", "ソリューション", "プラットフォーム",
    "コンテンツ", "サポート", "アップデート", "リリース", "パートナー", "グループ", "ホールディングス", "センター", "クラウド", "ポイント", "トレンド",
  ].map(norm),
);

/** 見出しの固有名詞らしい語（英字の名前・3字以上のカタカナ・「」『』の中） */
function titleTerms(title: string): string[] {
  const t = (title ?? "").normalize("NFKC");
  const out: string[] = [];
  for (const m of t.matchAll(/[「『]([^」』]{2,24})[」』]/g)) out.push(m[1]);
  for (const m of t.matchAll(/[A-Za-z][A-Za-z0-9.+\-]*[A-Za-z0-9+]/g)) out.push(m[0]);
  for (const m of t.matchAll(/[ァ-ヴー]{3,}/g)) out.push(m[0]);
  return out.map(norm).filter((w) => w.length >= 2 && !NAME_STOP.has(w) && !GENERIC.has(w));
}

function rawTerms(a: ArticleSummary): Set<string> {
  const words = [...(a.tags ?? []), ...(a.keywords ?? []), ...titleTerms(a.title)];
  return new Set(words.map(norm).filter((w) => w.length >= 2 && !GENERIC.has(w) && !/^\d+$/.test(w)));
}

function contextOf(candidates: ArticleSummary[]): Ctx {
  let ctx = contexts.get(candidates);
  if (ctx) return ctx;
  const terms = new WeakMap<ArticleSummary, Set<string>>();
  const df = new Map<string, number>();
  for (const a of candidates) {
    const set = rawTerms(a);
    terms.set(a, set);
    for (const w of set) df.set(w, (df.get(w) ?? 0) + 1);
  }
  const n = Math.max(candidates.length, 1);
  // 全記事の4%（最低8本）を超えて付いている語は、話題ではなくジャンル・分野・発表元の名前とみなす
  ctx = { df, n, cap: Math.max(8, Math.round(n * 0.04)), terms, names: new WeakMap() };
  contexts.set(candidates, ctx);
  return ctx;
}

function termsOf(a: ArticleSummary, ctx: Ctx): Set<string> {
  let set = ctx.terms.get(a);
  if (!set) {
    set = rawTerms(a);
    ctx.terms.set(a, set);
  }
  return set;
}

/** 記事の名前（見出しの固有名詞と、英字の名前のタグ）。両方の記事の名前に出る語は、企業・製品・話題が同じ手がかり */
function namesOf(a: ArticleSummary, ctx: Ctx): Set<string> {
  let set = ctx.names.get(a);
  if (!set) {
    const tagNames = (a.tags ?? []).map(norm).filter((w) => /^[a-z][a-z0-9.+\- ]+$/.test(w) && w.length >= 2 && !NAME_STOP.has(w) && !GENERIC.has(w));
    set = new Set([...titleTerms(a.title), ...tagNames]);
    ctx.names.set(a, set);
  }
  return set;
}

/** 地震・津波の速報（気象庁の型の記事）。それ以外の記事の関連に混ぜない（逆も） */
export function isDisasterArticle(a: Pick<ArticleSummary, "slug" | "title" | "channelSlug">): boolean {
  return /^(?:quake|tsunami)-/.test(a.slug) || a.channelSlug === "jma" || /^【(?:地震|津波)/.test(a.title ?? "");
}

// 出典 URL の比べ方は索引（lib/article-index.mjs の urlKey）と同じ。?period=・#entry-… は残す。地震・津波は URL で比べない（SEO A10）。
// lib/article-index.mjs は ESM でテストから読みにくいので写しを持つ（同じ結果になることは tests/test_related_articles.cjs で確かめる）
export function urlKey(url?: string): string {
  const raw = String(url ?? "").trim().toLowerCase();
  const period = /[?&]period=([^&#]+)/.exec(raw)?.[1];
  const entry = /#(entry-[^?#]+)/.exec(raw)?.[1];
  const base = raw.replace(/[?#].*$/, "").replace(/\/+$/, "");
  return base + (period ? `?period=${period}` : "") + (entry ? `#${entry}` : "");
}
const isDisasterSlug = (slug?: string) => /^(?:quake|tsunami)-/.test(String(slug ?? ""));

/** 同じ発表の重複記事（どちらかがもう一方の duplicateOf / angleOf か、同じ出典URL） */
function isSameStory(a: ArticleSummary, b: ArticleSummary): boolean {
  // 同じ発表で別の疑問に答える記事（とは・料金・比較・使い方。angleOf。scripts/story.py の link_siblings）は互いに関連として出す（台帳 A68）
  if ((a.angleOf && (a.angleOf === b.slug || a.angleOf === b.angleOf)) || (b.angleOf && b.angleOf === a.slug)) return false;
  if (a.duplicateOf && (a.duplicateOf === b.slug || a.duplicateOf === b.duplicateOf)) return true;
  if (b.duplicateOf && b.duplicateOf === a.slug) return true;
  if (isDisasterSlug(a.slug) || isDisasterSlug(b.slug)) return false;
  const ua = urlKey(a.sourceUrl);
  return Boolean(ua) && ua === urlKey(b.sourceUrl);
}

export type Similarity = { score: number; shared: string[]; sameCompany: boolean; sameName: boolean; strong: boolean; need: boolean };

/**
 * 2つの記事の話題の重なり。shared は重なった具体的な語、score は語の珍しさ（IDF）の合計。
 * strong（同じ話題と言える）: 具体的な語が2つ以上重なる、または両方の名前（見出しの固有名詞・英字のタグ）に同じ名前が出る、
 * または同じ企業（companies.ts）で語が1つ以上重なる。分野の語1つ（「売上高」「PDF」「ネット」）だけでは同じ話題としない。
 * need（同じ困りごと）: どちらかの記事のタグにある珍しい語（「情報流出」「年金」など。多くの記事に付く語・企業や製品の名前は除く）が両方に出る。
 * 2026-11-10: ドコモの情報流出の記事の関連に、名前（ドコモ）だけ重なる dバリューパス・iPad mini が並び、
 * ほかの情報流出の記事（確かめ方・今やること）が出ていなかった。タグの話題が同じ記事も同じ話題として扱う
 */
export function similarity(a: ArticleSummary, b: ArticleSummary, candidates: ArticleSummary[], companySlugOf?: CompanyOf): Similarity {
  const ctx = contextOf(candidates);
  const ta = termsOf(a, ctx);
  const tb = termsOf(b, ctx);
  const na = namesOf(a, ctx);
  const nb = namesOf(b, ctx);
  const shared: string[] = [];
  let score = 0;
  let sameName = false;
  for (const w of ta) {
    if (!tb.has(w)) continue;
    const df = Math.max(ctx.df.get(w) ?? 1, 1);
    const name = na.has(w) && nb.has(w);
    // 多くの記事に付く語は数えない。ただし両方の見出しに出る名前（OpenAI など記事の多い会社）は数える
    if (df > ctx.cap && !name) continue;
    shared.push(w);
    score += Math.log(ctx.n / df);
    if (name) sameName = true;
  }
  const ca = companySlugOf?.(a);
  const sameCompany = Boolean(ca && ca !== "other" && ca === companySlugOf?.(b));
  const tagsA = new Set((a.tags ?? []).map(norm));
  const tagsB = new Set((b.tags ?? []).map(norm));
  // 名前（ドコモ・Apple など）は「同じ困りごと」ではない（名前だけの重なりは sameName で扱い、関連では後ろに回す）
  // 語が1つだけのときは同じ分野（ジャンル）の記事に限る（分野をまたぐと、同じ語でも別の話のことが多い）
  const need =
    (shared.length >= 2 || a.genreSlug === b.genreSlug) &&
    shared.some((w) => (tagsA.has(w) || tagsB.has(w)) && !na.has(w) && !nb.has(w) && !/^[a-z0-9 .+\-]+$/.test(w));
  const strong = shared.length >= 2 || sameName || (shared.length >= 1 && sameCompany) || need;
  return { score, shared, sameCompany, sameName, strong, need };
}

function candidateOk(article: ArticleSummary, item: ArticleSummary): boolean {
  if (item.slug === article.slug) return false;
  if (isDisasterArticle(item) !== isDisasterArticle(article)) return false;
  return !isSameStory(article, item);
}

const DAY = 86_400_000;

/** 新しい記事を少し上に（同じくらい関係があるときの順番。関係の薄い新着を上げるほどは効かない） */
function freshness(item: ArticleSummary, now: number): number {
  const t = Date.parse(item.publishedAt || item.generatedAt || "");
  if (!Number.isFinite(t)) return 0.7;
  const days = Math.max(0, (now - t) / DAY);
  return 0.7 + 0.3 / (1 + days / 30);
}

/** 名前（企業・製品の名前）だけが重なる記事を関連に入れてよい本数の上限（2026-11-10。同じ話題・同じ困りごとの記事を先に） */
const NAME_ONLY_FILL = 2;

/**
 * 関連記事（記事末の一覧）。話題の重なりが基準に届く記事だけを、重なりの大きい順・新しい順に最大 limit 本。
 * 記事を作るときに文脈として使った過去記事（relatedSlugs）も、同じ基準を満たすときだけ先に出す。
 * 並びは ①同じ話題（語が2つ以上重なる） ②同じ困りごと（タグの話題が同じ） ③名前だけが重なる記事（全部で NAME_ONLY_FILL 本に満たないときだけ）
 */
export function relatedArticles(
  article: ArticleSummary,
  candidates: ArticleSummary[],
  companySlugOf?: CompanyOf,
  limit = 4,
  now = Date.now(),
): ArticleSummary[] {
  const bySlug = new Map(candidates.map((a) => [a.slug, a]));
  const picked: ArticleSummary[] = [];
  for (const slug of article.relatedSlugs ?? []) {
    const item = bySlug.get(slug);
    if (!item || picked.includes(item) || !candidateOk(article, item)) continue;
    if (!similarity(article, item, candidates, companySlugOf).strong) continue;
    picked.push(item);
    if (picked.length >= limit) return picked;
  }
  const tierOf = (sim: Similarity) => (sim.shared.length >= 2 ? 0 : sim.need ? 1 : 2);
  const scored = candidates
    .filter((item) => !picked.includes(item) && candidateOk(article, item))
    .map((item) => ({ item, sim: similarity(article, item, candidates, companySlugOf) }))
    .filter((x) => x.sim.strong)
    .map((x) => ({
      item: x.item,
      tier: tierOf(x.sim),
      rank: (x.sim.score + (x.sim.sameCompany || x.sim.sameName ? 1.5 : 0) + (x.item.genreSlug === article.genreSlug ? 0.5 : 0)) * freshness(x.item, now),
    }))
    .sort((a, b) => a.tier - b.tier || b.rank - a.rank || Date.parse(b.item.publishedAt) - Date.parse(a.item.publishedAt));
  for (const { item, tier } of scored) {
    if (picked.length >= limit) break;
    if (tier === 2 && picked.length >= NAME_ONLY_FILL) break;
    picked.push(item);
  }
  return picked;
}

/** 同じ話題の束にする記事どうしの、載せた日の差の上限（日） */
export const CLUSTER_WINDOW_DAYS = 14;

/** 題名に出ても話題の手がかりにならない漢字2字（発表の種類・時期・程度の語） */
const CLUSTER_STOP = new Set(
  (
    "発表 公開 開始 提供 発売 対応 搭載 実施 開催 導入 予定 決定 更新 追加 強化 拡大 連携 提携 協業 日本 国内 世界 海外 最大 最新 無料 対象 " +
    "今年 去年 来年 今回 以上 以下 以降 以内 可能 確認 方法 必要 利用 使用 活用 一覧 理由 影響 注意 今後 現在 時点 午前 午後 日時 期間 期限 月額 年間 " +
    "企業 会社 事業 製品 商品 情報 機能 向上 改善 新型 新作 新製 初回 一部 全国 各社 結果 報告 調査 開発 支援 推進 取組 関連 解説 報道 公式 公表 変更 終了 開設 設立 受付 販売 比較 "
  )
    .split(/\s+/)
    .filter(Boolean),
);

type ClusterKeys = { names: Set<string>; runs: string[]; pairs: Set<string> };
const clusterContexts = new WeakMap<object, { df: Map<string, number>; cap: number; strict: number; keys: WeakMap<ArticleSummary, ClusterKeys> }>();

/** 英字の略語（CEO・EV など。名前ではないが、名前と一緒に重なれば同じ話の手がかり） */
function acronyms(text: string): string[] {
  return [...text.matchAll(/[A-Za-z]{2,}/g)].map((m) => norm(m[0])).filter((w) => NAME_STOP.has(w) && !GENERIC.has(w));
}

function clusterKeys(a: ArticleSummary): ClusterKeys {
  // 検索用の題名（seoTitle）にだけ出る名前も手がかりにする（題名は言い回しを変えていることがある）
  const text = `${a.title ?? ""} ${a.seoTitle ?? ""}`.normalize("NFKC");
  // 漢字の続き（「紅白歌合戦」「出場歌手」）。2字ずつの組（紅白・白歌・歌合・合戦）で比べる。カタカナ・英字の名前は titleTerms で拾う
  const runs = [...new Set([...text.matchAll(/[一-龠々]{2,}/g)].map((m) => m[0]))];
  const pairs = new Set<string>();
  for (const run of runs) for (let i = 0; i < run.length - 1; i++) pairs.add(run.slice(i, i + 2));
  for (const w of acronyms(text)) pairs.add(w);
  return { names: new Set(titleTerms(text)), runs: [...runs, ...new Set(acronyms(text))], pairs };
}

function clusterContext(candidates: ArticleSummary[]) {
  let ctx = clusterContexts.get(candidates);
  if (ctx) return ctx;
  const df = new Map<string, number>();
  const keys = new WeakMap<ArticleSummary, ClusterKeys>();
  for (const a of candidates) {
    const k = clusterKeys(a);
    keys.set(a, k);
    for (const w of k.pairs) df.set(w, (df.get(w) ?? 0) + 1);
    for (const w of k.names) df.set(`n:${w}`, (df.get(`n:${w}`) ?? 0) + 1);
  }
  // 珍しい語: 題名の1%（最低6本）以下にしか出ない。名前の無い束（漢字の語だけ）は、さらに珍しい語（0.5%・最低6本）に限る
  ctx = { df, cap: Math.max(6, Math.round(candidates.length * 0.01)), strict: Math.max(6, Math.round(candidates.length * 0.005)), keys };
  clusterContexts.set(candidates, ctx);
  return ctx;
}

const clusterTime = (a: ArticleSummary) => Date.parse(a.generatedAt || a.publishedAt || "");

/** 重なった漢字の語（続いた組は1語に数える。「手数料」は 手数・数料 の2組でも1語）。返すのは各語のいちばん珍しい組の出現数 */
function sharedWords(mine: ClusterKeys, theirs: ClusterKeys, df: Map<string, number>): number[] {
  const out: number[] = [];
  for (const run of mine.runs) {
    if (!/[一-龠々]/.test(run)) {
      if (theirs.pairs.has(run)) out.push(df.get(run) ?? 1);
      continue;
    }
    let best = 0;
    for (let i = 0; i < run.length - 1; i++) {
      const pair = run.slice(i, i + 2);
      if (theirs.pairs.has(pair) && !CLUSTER_STOP.has(pair)) {
        const n = df.get(pair) ?? 1;
        best = best === 0 ? n : Math.min(best, n);
      } else if (best) {
        out.push(best);
        best = 0;
      }
    }
    if (best) out.push(best);
  }
  return out;
}

/**
 * 同じ話題の束（2026-11-13 オーナー「Googleからの流入対策」）。載せた日が CLUSTER_WINDOW_DAYS 日以内で、題名に同じ強い手がかりがある記事。
 * 紅白の出場歌手の一覧・初出場・入れ替わりの3本、NVIDIA の CEO 退任と決算の2本のように、同じ話題を別の疑問で書いた記事を必ず互いに結ぶ
 * （検索のロボットが1本を見つけたら残りにも届く。読者も続きを読める）。束の条件はどれか:
 *   1. 記事の多い名前（NVIDIA・Microsoft など）が同じで、さらに珍しい名前か珍しい語がもう1つ重なる（NVIDIA＋CEO、NVIDIA＋フアン、Microsoft＋障害）
 *   2. 珍しい名前（英字の名前・3字以上のカタカナ・「」の中）が2つ重なる、または珍しい名前1つと、とても珍しい語1つが重なる
 *   3. 名前が無くても、とても珍しい漢字の語が2つ以上重なる（紅白＋出場）
 * どの場合も、タグ・キーワード・名前で同じ話題と言える（similarity の strong）ことが条件。
 * 名前1つだけ（同じ会社の別の発表）・ありふれた語だけ（値上げ＋平均、中間＋純利益）では束にしない。重複の印のある記事・まとめ記事・地震は入れない。
 * 出典 URL が同じでも別の記事として載せているものは入れる（clusterOk）。
 * 並びは重なりの多い順 → 載せた日が近い順
 */
/** 束に入れてよい相手か。出典 URL が同じでも、別の記事として載せているもの（重複の印が無い）は入れる（NVIDIA の CEO 退任と決算は同じ発表から書いた別の記事） */
function clusterOk(article: ArticleSummary, item: ArticleSummary): boolean {
  if (item.slug === article.slug || item.duplicate || item.type === "roundup") return false;
  if (isDisasterArticle(item) || isDisasterArticle(article)) return false;
  if (item.duplicateOf || (article.duplicateOf && article.duplicateOf === item.slug)) return false;
  return true;
}

export function topicCluster(article: ArticleSummary, candidates: ArticleSummary[], limit = 3, companySlugOf?: CompanyOf): ArticleSummary[] {
  const at = clusterTime(article);
  if (!Number.isFinite(at)) return [];
  const ctx = clusterContext(candidates);
  const mine = ctx.keys.get(article) ?? clusterKeys(article);
  if (mine.names.size === 0 && mine.runs.length < 2) return [];
  const out: { item: ArticleSummary; hits: number; gap: number }[] = [];
  for (const item of candidates) {
    if (!clusterOk(article, item)) continue;
    const t = clusterTime(item);
    if (!Number.isFinite(t)) continue;
    const gap = Math.abs(at - t);
    if (gap > CLUSTER_WINDOW_DAYS * DAY) continue;
    const theirs = ctx.keys.get(item) ?? clusterKeys(item);
    let commonNames = 0;
    let rareNames = 0;
    for (const w of mine.names) {
      if (!theirs.names.has(w)) continue;
      if ((ctx.df.get(`n:${w}`) ?? 1) <= ctx.cap) rareNames += 1;
      else commonNames += 1;
    }
    const words = sharedWords(mine, theirs, ctx.df);
    const rareWords = words.filter((n) => n <= ctx.cap).length;
    const veryRareWords = words.filter((n) => n <= ctx.strict).length;
    const same =
      (commonNames >= 1 && rareNames + rareWords >= 1) || rareNames >= 2 || (rareNames >= 1 && veryRareWords >= 1) || veryRareWords >= 2;
    if (!same) continue;
    // 題名の語がたまたま重なっただけの記事を入れない: タグ・キーワード・名前でも同じ話題と言える記事だけ（similarity の strong）
    if (!similarity(article, item, candidates, companySlugOf).strong) continue;
    out.push({ item, hits: rareNames * 3 + rareWords * 2 + commonNames, gap });
  }
  return out
    .sort((x, y) => y.hits - x.hits || x.gap - y.gap || clusterTime(y.item) - clusterTime(x.item))
    .slice(0, limit)
    .map((x) => x.item);
}

/**
 * 「次に読むならこれ」。1. 同じ話題のまとめ記事（全体像） 2. 同じ話題の記事（具体的な語が2つ以上重なる） 3. 同じ企業の発表（同じ企業・同じ名前） の順。
 * 「同じ話題の記事」の札は、同じ企業か同じ製品・話題の語が重なる記事にだけ付ける（ジャンルや「社会・行政」のような分野の語だけでは付けない）。
 */
export function nextReads(article: ArticleSummary, candidates: ArticleSummary[], companySlugOf: CompanyOf, limit = 3, now = Date.now()): NextRead[] {
  const picked: NextRead[] = [];
  const used = new Set<string>([article.slug]);
  const add = (item: ArticleSummary | undefined, reason: string) => {
    if (!item || used.has(item.slug) || picked.length >= limit || !candidateOk(article, item)) return;
    used.add(item.slug);
    picked.push({ article: item, reason });
  };
  if (article.roundupSlug) add(candidates.find((a) => a.slug === article.roundupSlug), "この話題の全体像");
  // 同じ話題の束（14日以内・題名に同じ強い手がかり）を先に。紅白の3本・NVIDIA の CEO 退任と決算を必ず互いに結ぶ（2026-11-13）
  // 出典 URL が同じ別の記事（candidateOk では外れる）も、束なら入れる
  for (const item of topicCluster(article, candidates, 2, companySlugOf)) {
    if (used.has(item.slug) || picked.length >= limit) continue;
    used.add(item.slug);
    picked.push({ article: item, reason: "同じ話題の記事" });
  }
  const sims = candidates
    .filter((item) => candidateOk(article, item))
    .map((item) => ({ item, sim: similarity(article, item, candidates, companySlugOf) }));
  // 「同じ話題の記事」: 具体的な語が2つ以上重なる記事。名前（企業）だけが重なる記事は「同じ企業の発表」
  const topical = sims
    .filter((x) => x.sim.shared.length >= 2)
    .sort((a, b) => b.sim.score * freshness(b.item, now) - a.sim.score * freshness(a.item, now));
  for (const { item } of topical) add(item, "同じ話題の記事");
  const sameCompany = sims
    .filter((x) => x.sim.strong && (x.sim.sameCompany || x.sim.sameName))
    .sort((a, b) => Date.parse(b.item.publishedAt) - Date.parse(a.item.publishedAt));
  for (const { item } of sameCompany) add(item, "同じ企業の発表");
  return picked;
}

/**
 * 「この話題のページ」（SEO A17・2026-11-10）。元の記事には、同じ話題で別の疑問に答える角度の記事（angleOf）の一覧。
 * 角度の記事には、元の記事とほかの角度の記事。別の登録簿は作らず angleOf だけで結ぶ（角度の記事はニュースのサイトマップに載らないので、元の記事から必ず結ぶ）
 */
export function topicPages(article: ArticleSummary, all: ArticleSummary[]): { parent?: ArticleSummary; pages: ArticleSummary[] } {
  const parentSlug = article.angleOf || article.slug;
  const parent = article.angleOf ? all.find((a) => a.slug === parentSlug) : undefined;
  const pages = all.filter((a) => a.angleOf === parentSlug && a.slug !== article.slug);
  return { parent, pages };
}
