/**
 * Cloudflare 用: 実行時に読むファイルを静的アセット（.open-next/assets/_content）へ書き出す。
 * opennextjs-cloudflare build の後に実行する。読み手は cloudflare/worker.ts。
 *
 *   base.json         一覧用の索引（content/index.json）・設定・ガイド類 { files: {相対パス: 中身}, dirs: {相対パス: [名前]} }
 *   articles/<slug>.json  記事の本文入り JSON（そのままコピー）
 *   fonts/*           カバー画像用フォント
 *   retired.json      取り下げた記事（content/retired.json）
 */
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

const OUT = path.join(".open-next", "assets", "_content");
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(path.join(OUT, "articles"), { recursive: true });
fs.mkdirSync(path.join(OUT, "fonts"), { recursive: true });

const files = {};
const dirs = {};
const addFile = (rel) => {
  if (fs.existsSync(rel)) files[rel] = fs.readFileSync(rel, "utf8");
};
const addDir = (rel, filter = (name) => name.endsWith(".json")) => {
  if (!fs.existsSync(rel)) return;
  const names = fs.readdirSync(rel).filter(filter).sort();
  dirs[rel] = names;
  return names;
};

for (const dir of ["content/guides", "content/howto", "content/buying-guides", "content/products", "content/digests"]) {
  for (const name of addDir(dir) ?? []) addFile(`${dir}/${name}`);
}
for (const rel of ["content/index.json", "content/offers.json", "content/products.json", "affiliate_links.json", "monetization.json"]) {
  addFile(rel);
}
// content/state.json（約1MB の記事づくりの記録）は、サイトでは /api/v1/stats が processed・failed を数えるだけ。
// 冷えた isolate が毎回まるごと読み込んで遅くならないよう、使う2つの欄だけ載せる（2026-11-07 表示速度の改善）
if (fs.existsSync("content/state.json")) {
  try {
    const state = JSON.parse(fs.readFileSync("content/state.json", "utf8"));
    files["content/state.json"] = JSON.stringify({ processed: state.processed ?? {}, failed: state.failed ?? {} });
  } catch {
    files["content/state.json"] = "{}";
  }
}
dirs["assets/fonts"] = addDir("assets/fonts", (name) => /\.(otf|ttf)$/.test(name));
for (const name of dirs["assets/fonts"]) fs.copyFileSync(path.join("assets/fonts", name), path.join(OUT, "fonts", name));
fs.writeFileSync(path.join(OUT, "base.json"), JSON.stringify({ files, dirs }));
// 取り下げた記事（cloudflare/worker.ts が 301・410 を返す。scripts/retire_articles.py）
fs.writeFileSync(path.join(OUT, "retired.json"), fs.existsSync("content/retired.json") ? fs.readFileSync("content/retired.json", "utf8") : "{}");

// 編集部の記事確認ページ（cloudflare/review.ts）の一覧: 新しい順に 400 本。速報・SNS に出した記事に印を付ける
{
  let posted = {};
  try {
    posted = JSON.parse(fs.readFileSync("state/threads_posted.json", "utf8")).posted ?? {};
  } catch {}
  const rows = [];
  for (const name of fs.readdirSync("content/articles").filter((n) => n.endsWith(".json"))) {
    try {
      const a = JSON.parse(fs.readFileSync(path.join("content/articles", name), "utf8"));
      rows.push({ slug: a.slug, title: a.title, genre: a.genre ?? "", generatedAt: a.generatedAt || a.publishedAt || "", breaking: Boolean(a.breaking) || undefined, sns: Boolean(posted[a.slug]) || undefined });
    } catch {}
  }
  rows.sort((x, y) => String(y.generatedAt).localeCompare(String(x.generatedAt)));
  fs.writeFileSync(path.join(OUT, "review.json"), JSON.stringify({ articles: rows.slice(0, 400) }));
}

let count = 0;
// 載せた・直したばかりの記事（48時間以内）の一覧。cloudflare/worker.ts が、前の版の写しを返さずその場で今の版を出す記事を決めるのに使う
// （cloudflare/edge-cache.ts の isRecentArticlePath・articleTouchedAt と同じ決まり）
const RECENT_MS = 48 * 3_600_000;
const buildNow = Date.now();
const recent = {};
for (const name of fs.readdirSync("content/articles").filter((n) => n.endsWith(".json"))) {
  fs.copyFileSync(path.join("content/articles", name), path.join(OUT, "articles", name));
  count++;
  try {
    const a = JSON.parse(fs.readFileSync(path.join("content/articles", name), "utf8"));
    const times = [a.generatedAt || a.publishedAt, a.updatedAt].map((iso) => Date.parse(iso ?? "")).filter((t) => !Number.isNaN(t));
    const at = times.length ? Math.min(Math.max(...times), buildNow) : 0;
    if (a.slug && buildNow - at <= RECENT_MS) recent[a.slug] = at;
  } catch {}
}
fs.writeFileSync(path.join(OUT, "recent.json"), JSON.stringify({ builtAt: buildNow, articles: recent }));
console.log(`[cf_content] ${Object.keys(recent).length} recent articles -> recent.json`);
console.log(`[cf_content] ${count} articles, ${Object.keys(files).length} files -> ${OUT}`);

// ビルド時に作った ISR のキャッシュを静的アセットへ（open-next.config.ts の kvOverAssets が読む）
const CACHE_OUT = path.join(".open-next", "assets", "cdn-cgi", "_next_cache");
fs.rmSync(CACHE_OUT, { recursive: true, force: true });
fs.cpSync(path.join(".open-next", "cache"), CACHE_OUT, { recursive: true });
console.log(`[cf_content] build cache -> ${CACHE_OUT}`);

// エッジキャッシュのキー（cloudflare/worker.ts）。JS・CSS・フォントのファイル名（中身のハッシュ入り）の組。
// 記事だけ増えたデプロイでは変わらないので、前の版の HTML を返しながら裏で作り直せる
const STATIC = path.join(".open-next", "assets", "_next", "static");
const staticNames = [];
const walk = (dir) => {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else staticNames.push(path.relative(STATIC, full));
  }
};
walk(path.join(STATIC, "chunks"));
walk(path.join(STATIC, "media"));
const codeHash = staticNames.length
  ? createHash("sha256").update(staticNames.sort().join("\n")).digest("hex").slice(0, 16)
  : "";
fs.writeFileSync(path.join(".open-next", "saisoku-code.json"), JSON.stringify({ hash: codeHash }));
console.log(`[cf_content] code hash ${codeHash || "(none)"} (${staticNames.length} static files)`);
