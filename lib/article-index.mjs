// 記事一覧用の軽い索引（content/index.json）を作る処理。
// ビルド前の scripts/build_index.mjs と、開発時の lib/articles.ts の両方から使うので、
// 依存なしの素の JavaScript にしている（TypeScript の型は lib/articles.ts の ArticleSummary）。
//
// 一覧・関連記事・サイトマップ・カードは全記事の本文を必要としない。本文を含む全 JSON を
// すべてのサーバー関数に同梱するとデプロイの容量が膨らむので、必要な項目だけを索引に入れ、
// 本文は記事ページとカバー画像だけが1本ずつ読む。

import fs from "node:fs";
import path from "node:path";

export const INDEX_VERSION = 9;

function distinctHits(re, text) {
  const found = (text || "").match(new RegExp(re.source, re.flags.includes("g") ? re.flags : `${re.flags}g`));
  return found ? new Set(found.map((w) => w.toLowerCase())).size : 0;
}

/**
 * 比較記事の話題（content/offers.json の actionAds の key）を題名・本文から決める。
 * scripts/muse_articles.py の comparison_topic と同じ規則: 題名に当たる話題を優先し、題名で当たった語の数 → 本文で当たった語の数の多い順。
 * 同点は actionAds の順。題名に当たらない話題は本文で3語以上当たったときだけ。除く語（exclude）が題名にある話題は使わない
 */
export function comparisonTopicFromText(rules, title, body) {
  let best;
  for (const rule of rules || []) {
    let re;
    let ex;
    try {
      re = new RegExp(rule.match, "i");
      ex = rule.exclude ? new RegExp(rule.exclude, "i") : undefined;
    } catch {
      continue;
    }
    if (ex && ex.test(title)) continue;
    const t = distinctHits(re, title);
    const b = distinctHits(re, body);
    if (t === 0 && b < 3) continue;
    const score = [t > 0 ? 1 : 0, t, b];
    const better = !best || score[0] > best.score[0] || (score[0] === best.score[0] && (score[1] > best.score[1] || (score[1] === best.score[1] && score[2] > best.score[2])));
    if (better) best = { key: rule.key, score };
  }
  return best?.key;
}

/** 選び方・比較の記事か（公開時の印。印の無い Muse の「比較」の原稿はファイル名で拾う） */
export function isComparisonRecord(a) {
  return a.kind === "comparison" || /^\d{8}-比較-/.test(a.museFile || "");
}

/** 記事 JSON として最低限そろっているか（lib/articles.ts の isArticle と同じ基準） */
export function isArticleLike(value) {
  if (typeof value !== "object" || value === null) return false;
  return (
    typeof value.slug === "string" &&
    typeof value.title === "string" &&
    typeof value.body === "string" &&
    typeof value.videoId === "string"
  );
}

/**
 * 読者のブラウザに直接読ませてよい画像か。自前の配信（/img/・/cover/）と YouTube のサムネイルだけ。
 * ほかのサイトの画像を直リンクすると、相手の参照元チェック・削除・URL 変更で壊れた画像アイコンになる。
 * 公式発表の写真は scripts/images.py が自前の KV（/img/）に保存してから使う決まりなので、
 * まだ保存されていない外部の URL は空にして、独自カバー（/cover/<slug>）・代替表示に回す（2026-11-03）
 */
const SERVABLE_THUMB = /^(?:https:\/\/ai-tech-express\.jp)?\/(?:img|cover)\/|^https:\/\/(?:i\.ytimg\.com|img\.youtube\.com)\//;
export function servableThumb(url) {
  return typeof url === "string" && SERVABLE_THUMB.test(url) ? url : "";
}

/** 欠けている項目の既定値（lib/articles.ts の normalize と同じ） */
/**
 * 本当の「最終更新」日時（SEO A16）。更新履歴（updates）がある記事か、公式の資料で本文を書き直した記事（searchRefreshedAt）の
 * updatedAt だけを使う。更新履歴の無い updatedAt（11/04 に一括で押された43本など、中身が変わっていない日時）は捨てる。
 * ファイルは書きかえない。記事の更新日時を書くのは scripts/updated_at.py の touch_updated だけ。
 */
export function trustedUpdatedAt(parsed) {
  const at = parsed?.updatedAt;
  if (!at) return undefined;
  const hasNote = Array.isArray(parsed.updates) && parsed.updates.length > 0;
  return hasNote || parsed.searchRefreshedAt ? at : undefined;
}

export function withDefaults(parsed) {
  return {
    ...parsed,
    updatedAt: trustedUpdatedAt(parsed),
    thumbnail: servableThumb(parsed.thumbnail),
    keywords: parsed.keywords ?? [],
    tags: parsed.tags ?? [],
    highlights: parsed.highlights ?? [],
    timetable: parsed.timetable ?? [],
    affiliates: parsed.affiliates ?? [],
    sources: parsed.sources ?? [],
    lede: parsed.lede ?? "",
    genre: parsed.genre ?? "AI・テクノロジー",
    genreSlug: parsed.genreSlug ?? "ai",
    disclaimer: parsed.disclaimer ?? "",
  };
}

/** 「かんたん」版の「ひとことで言うと」（または「概要」）段落（無ければ空。表示側 lib/general.ts の easyGist がリード文に戻す） */
export function easyGistOf(easy) {
  const match = (easy ?? "").match(/##\s*(?:ひとことで言うと|概要)\s*\n+([\s\S]*?)(?=\n##\s|$)/);
  return (match?.[1] ?? "").trim().replace(/\s*\n+\s*/g, "");
}

/** 公式のロゴ・サイト共通の画像（記事の写真として出さない。scripts/muse_images.py の photo_state と同じ。台帳 S49） */
const NOT_PHOTO_KINDS = ["logo", "generic"];
/** 文字の多い告知のバナー・図（切り抜くと文字が切れるので、枠に丸ごと収める） */
const TEXT_HEAVY_KINDS = ["banner", "dense"];
/** 話題と関係の無い「誰もいない会場」の AI の絵（2026-11-07 オーナー。scripts/muse_images.py の filler と同じ） */
const FILLER_PROMPT = /empty exhibition hall|no exhibits/i;

/** 自前の画像（/img/<名前>）の名前が、この記事の slug で始まらない（ほかの記事のために保存した画像）か（lib/sns-photo.ts の borrowedImage と同じ） */
function borrowedPhoto(url, slug) {
  const m = /\/img\/([^/?#]+)$/.exec(String(url ?? "").split("?")[0]);
  if (!m || !slug) return false;
  return !m[1].startsWith(String(slug).slice(0, 120));
}

/**
 * 一覧・トップに出す記事の写真（2026-11-10 オーナー「画像またでてない記事あるよ」「画像が見切れている記事があるのはダサい」）。
 * 順: ①表紙用の AI のイメージ（coverImage。Muse・Workers AI が描き、見出しとのつながりを確かめたもの）を、記事の写真が
 * AI の絵・文字のカード・ロゴのときに優先 ②記事の写真（公式・素材・YouTube。ロゴ・サイト共通・ほかの記事の画像・関係の無い会場の絵は除く）
 * ③無ければ undefined（トップの大きな枠には出さない。小さい枠は代わりの図版）。
 * pos は主役の位置（scripts/image_focus.py の imageFocus。object-position）、fit: "contain" は文字の多いバナー・図（切り抜かない）。
 * ai: AI が描いた絵（「AI生成」の札を出す）。launch: 公式画像が無い新製品の発表で製品の種類を描いた絵
 */
export function photoOf(article) {
  if (article.noPhoto) return undefined;
  const credit = article.imageCredit ?? {};
  const kind = credit.kind;
  const thumb = String(article.thumbnail ?? "").trim();
  const cover = String(article.coverImage ?? "").trim();
  const coverOk = Boolean(cover) && article.coverCredit?.kind === "ai" && Boolean(servableThumb(cover));
  const thumbOk =
    Boolean(thumb) &&
    kind !== "card" &&
    !(kind === "official" && NOT_PHOTO_KINDS.includes(credit.imageKind ?? "")) &&
    !(kind === "ai" && FILLER_PROMPT.test(String(credit.prompt ?? ""))) &&
    !borrowedPhoto(thumb, article.slug);
  // 図の表紙（imageCredit.kind figure・imageKind cover。台帳 I9）は写真ではないので、表紙用の AI のイメージ（Muse など）が届けばそちら
  const figureCover = kind === "figure" && credit.imageKind === "cover";
  if (coverOk && (!thumbOk || kind === "ai" || figureCover)) {
    return { src: cover, ai: true, ...(article.coverCredit?.launch ? { launch: true } : {}) };
  }
  if (!thumbOk) return undefined;
  const focus = article.imageFocus;
  const pos =
    focus && focus.src === thumb && Number.isFinite(focus.x) && Number.isFinite(focus.y)
      ? `${Math.round(Math.min(Math.max(focus.x, 0), 1) * 100)}% ${Math.round(Math.min(Math.max(focus.y, 0), 1) * 100)}%`
      : undefined;
  const contain = kind === "figure" || (kind === "official" && TEXT_HEAVY_KINDS.includes(credit.imageKind ?? ""));
  // 写真の縦横比（主役の枠の ar か、保存した公式の写真の幅・高さ）。縦長・正方形の写真を 16:9 の枠で大きく切らないために使う
  const rawAr =
    focus && focus.src === thumb && Number(focus.ar) > 0
      ? Number(focus.ar)
      : Number(credit.width) > 0 && Number(credit.height) > 0
        ? Number(credit.width) / Number(credit.height)
        : undefined;
  return {
    src: thumb,
    ...(kind === "ai" ? { ai: true, ...(credit.launch ? { launch: true } : {}) } : {}),
    ...(pos ? { pos } : {}),
    ...(contain ? { fit: "contain" } : {}),
    ...(rawAr ? { ar: Math.round(rawAr * 100) / 100 } : {}),
  };
}

/** 本文から計算する、一覧で使う値 */
export function derivedOf(article) {
  return {
    photo: photoOf(article),
    bodyLength: article.body.length,
    hasEasy: Boolean(article.easy && article.easy.trim()),
    // 「日本で使える？無料？料金・使い方」の見出しがあるか（検索に出す条件。indexnow.py と同じ）
    hasJapanValue: Boolean(article.scheduledRelease) || /^#{2,3}.*(日本|無料|使い方|料金|始め方|使える)/m.test(article.body),
    easyGist: easyGistOf(article.easy),
    sourceCount: Array.isArray(article.sources) ? article.sources.length : 0,
    affiliateNames: Array.isArray(article.affiliates) ? article.affiliates.map((a) => a.name).filter(Boolean) : [],
  };
}

/** 一覧で使う項目だけを抜き出す（ArticleSummary） */
export function summarize(article, actionAds = []) {
  const a = withDefaults(article);
  const comparison = isComparisonRecord(a);
  return {
    slug: a.slug,
    type: a.type,
    roundupSlug: a.roundupSlug,
    roundupTitle: a.roundupTitle,
    title: a.title,
    seoTitle: a.seoTitle,
    lede: a.lede,
    description: a.description,
    keywords: a.keywords,
    tags: a.tags,
    // 一覧（ストーリー）では先頭3つまでしか使わない
    highlights: a.highlights.slice(0, 3),
    verdict: a.verdict ?? null,
    channel: a.channel,
    channelId: a.channelId,
    channelSlug: a.channelSlug,
    genre: a.genre,
    genreSlug: a.genreSlug,
    // 企業の札の上書き（lib/companies.ts の companyOf が最優先で使う。台帳 A30）
    companySlug: a.companySlug || undefined,
    sourceType: a.sourceType,
    sourceUrl: a.sourceUrl,
    sourceName: a.sourceName,
    sourcePublishedAt: a.sourcePublishedAt,
    indexable: a.indexable,
    duplicateOf: a.duplicateOf,
    angleOf: a.angleOf,
    late: a.late,
    // 話題のレーンの記事（急上昇の言葉。lib/indexing.ts の trendTopic が見る。2026-11-13）
    trendKeyword: a.trendKeyword || undefined,
    // Muse に頼んで書いた記事（トップの「話題の記事」の枠の判定。lib/home-lead.ts の isTrendingFresh。2026-11-13）
    writer: a.writer || (a.museFile ? "muse" : undefined),
    videoId: a.videoId,
    videoUrl: a.videoUrl,
    publishedAt: a.publishedAt,
    generatedAt: a.generatedAt,
    updatedAt: a.updatedAt,
    relatedSlugs: a.relatedSlugs,
    thumbnail: a.thumbnail,
    // 公式発表の写真の出典（トップの大きな写真の下に出す）。ほかの写真の出典は記事ページだけで出す。
    // AI 生成の画像は「AI生成」の札をトップ・朝のまとめでも出すため、種類だけ残す（2026-11-03 の画面の点検で、トップと朝のまとめに札が出ていなかった）
    imageCredit:
      a.imageCredit?.kind === "official"
        ? { kind: "official", org: a.imageCredit.org, via: a.imageCredit.via, provider: a.imageCredit.provider, imageKind: a.imageCredit.imageKind }
        : a.imageCredit?.kind === "figure"
          ? { kind: "figure", org: a.imageCredit.org }
          : a.imageCredit?.kind === "ai"
            ? { kind: "ai" }
            : undefined,
    speedMinutes: a.speedMinutes,
    // 赤い「速報」（画像・ヘッダー下の帯）の判定に使う（lib/cover-path.ts の isFastNews）
    breaking: a.breaking || undefined,
    // ニュースの種類（scripts/news_types.py）。判定カードを出してよい種類かを lib/verdict.ts が見る
    newsType: a.newsType || undefined,
    // 選び方・比較の記事（ニュース記事の「次に読む」の受け皿。lib/comparison.ts）。印の無い Muse の「比較」の原稿もファイル名で拾う
    kind: comparison ? "comparison" : undefined,
    // 公開時に話題が付いていない比較記事は、本文まで見て同じ規則で決める（索引には本文を入れないため、ここで決めて残す）
    comparisonTopic: comparison
      ? a.comparisonTopic || comparisonTopicFromText(actionAds, `${a.title} ${a.seoTitle || ""}`, `${a.lede || ""} ${a.description || ""} ${a.body || ""}`) || undefined
      : undefined,
    ...derivedOf(a),
  };
}

/** サイソクに載った順（新しい順） */
export function byNewest(a, b) {
  return (
    new Date(b.generatedAt || b.publishedAt).getTime() - new Date(a.generatedAt || a.publishedAt).getTime()
  );
}

/** content/articles/*.json を全部読んで索引を作る。壊れた JSON は1本ずつ飛ばす */
export function buildIndex(articlesDir) {
  if (!fs.existsSync(/* turbopackIgnore: true */ articlesDir)) return [];
  const items = [];
  // 比較記事の話題の規則（content/offers.json の actionAds。articlesDir の隣）
  let actionAds = [];
  try {
    actionAds = JSON.parse(fs.readFileSync(/* turbopackIgnore: true */ path.join(articlesDir, "..", "offers.json"), "utf8")).actionAds || [];
  } catch {
    actionAds = [];
  }
  for (const file of fs.readdirSync(/* turbopackIgnore: true */ articlesDir)) {
    if (!file.endsWith(".json")) continue;
    try {
      const parsed = JSON.parse(fs.readFileSync(/* turbopackIgnore: true */ path.join(articlesDir, file), "utf8"));
      if (!isArticleLike(parsed)) {
        console.warn(`[articles] skip (schema mismatch): ${file}`);
        continue;
      }
      items.push(summarize(parsed, actionAds));
    } catch (error) {
      console.warn(`[articles] skip (invalid JSON): ${file}`, error);
    }
  }
  markDuplicates(items);
  return items.sort(byNewest);
}

/** 重複の判定に使う題名（記号・空白を除く。scripts/indexnow.py と同じ） */
function titleKey(title) {
  return String(title || "").replace(/[\s「」『』【】()（）・、。！？!?:：|｜\-—〜~"'“”]/g, "").toLowerCase();
}

/**
 * 出典 URL の比較用（クエリ・末尾の / を落とす。scripts/indexnow.py の _url_key・scripts/story.py の url_keys と同じ）。
 * ただし、毎月同じ URL に上書きされる資料の ?period=（家計調査など）と、リリースノートの1項目の #entry-… は残す
 * （別の月・別の項目の記事が「重複」として検索から隠れていた。SEO A10）
 */
export function urlKey(url) {
  const raw = String(url || "").trim().toLowerCase();
  const period = /[?&]period=([^&#]+)/.exec(raw)?.[1];
  const entry = /#(entry-[^?#]+)/.exec(raw)?.[1];
  const base = raw.replace(/[?#].*$/, "").replace(/\/+$/, "");
  return base + (period ? `?period=${period}` : "") + (entry ? `#${entry}` : "");
}

/** 地震・津波の速報（気象庁の同じ地図のページが出典。出来事ごとに別の記事なので、出典 URL では重複にしない） */
export function isDisasterSlug(slug) {
  return /^(?:quake|tsunami)-/.test(String(slug || ""));
}

/**
 * 予備の判定で、出典 URL が同じ2本を「同じ切り口」とみなす題名の類似度（文字バイグラムの重なり。scripts/indexnow.py の
 * SAME_URL_TITLE_SIM・scripts/story.py の SAME_URL_SIM と同じ）。2026-11-13: 同じ公式のページから別のことを書いた記事
 * （NVIDIA の「CEO退任」と「決算は11月18日」、医療費控除の「明細書」と「10万円の壁」）を重複にしない
 */
export const SAME_URL_TITLE_SIM = 0.3;

function titleBigrams(key) {
  const out = new Set();
  if (key.length === 1) out.add(key);
  for (let i = 0; i < key.length - 1; i++) out.add(key.slice(i, i + 2));
  return out;
}

function bigramSim(a, b) {
  if (a.size === 0 || b.size === 0) return 0;
  let both = 0;
  for (const g of a) if (b.has(g)) both++;
  return both / (a.size + b.size - both);
}

/**
 * 重複の印（duplicate）を付ける。
 * 1. 記事 JSON の duplicateOf（scripts/story.py が同じ発表の記事を見分けて付ける。主な判定はこちら）
 * 2. 予備: 同じ題名の記事と、出典URLが同じで題名も似ている記事（SAME_URL_TITLE_SIM 以上）のうち代表以外
 *    （本文の長い方、同じなら先に載った方が代表）。
 *    duplicateOf のある記事・意図して角度を変えた解説（angleOf）は予備の判定に入れない
 */
export function markDuplicates(items) {
  for (const a of items) if (a.duplicateOf && a.duplicateOf !== a.slug) a.duplicate = true;
  const keep = new Set();
  const ordered = items
    .filter((a) => a.type !== "roundup" && !a.duplicate && !a.angleOf)
    .sort((a, b) => b.bodyLength - a.bodyLength || String(a.generatedAt).localeCompare(String(b.generatedAt)));
  const byUrl = new Map();
  for (const a of ordered) {
    const title = titleKey(a.title);
    const grams = titleBigrams(title);
    const url = a.sourceUrl && !isDisasterSlug(a.slug) ? urlKey(a.sourceUrl) : "";
    if (keep.has(`t:${title}`) || (byUrl.get(url) ?? []).some((g) => bigramSim(grams, g) >= SAME_URL_TITLE_SIM)) {
      a.duplicate = true;
      continue;
    }
    keep.add(`t:${title}`);
    if (url) byUrl.set(url, [...(byUrl.get(url) ?? []), grams]);
  }
}
