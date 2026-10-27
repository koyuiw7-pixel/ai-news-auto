/**
 * Cloudflare 用: 実行時に読むファイルを静的アセット（.open-next/assets/_content）へ書き出す。
 * opennextjs-cloudflare build の後に実行する。読み手は cloudflare/worker.ts。
 *
 *   base.json         小さい設定・ガイド類 { files: {相対パス: 中身}, dirs: {相対パス: [名前]} }
 *   articles.ndjson   記事の索引（1行1本「slug<TAB>JSON」。本文など記事ページでしか使わない欄は空）
 *   articles/<slug>.json  記事の本文入り JSON（そのままコピー）
 *   fonts/*           カバー画像用フォント
 */
import fs from "node:fs";
import path from "node:path";

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

for (const dir of ["content/guides", "content/buying-guides"]) {
  for (const name of addDir(dir) ?? []) addFile(`${dir}/${name}`);
}
for (const rel of ["content/offers.json", "content/products.json", "content/state.json", "affiliate_links.json", "monetization.json"]) {
  addFile(rel);
}
dirs["assets/fonts"] = addDir("assets/fonts", (name) => /\.(otf|ttf)$/.test(name));
for (const name of dirs["assets/fonts"]) fs.copyFileSync(path.join("assets/fonts", name), path.join(OUT, "fonts", name));
fs.writeFileSync(path.join(OUT, "base.json"), JSON.stringify({ files, dirs }));

const lines = [];
for (const name of fs.readdirSync("content/articles").filter((n) => n.endsWith(".json"))) {
  const raw = fs.readFileSync(path.join("content/articles", name), "utf8");
  let article;
  try {
    article = JSON.parse(raw);
  } catch {
    console.warn(`[cf_content] skip (invalid JSON): ${name}`);
    continue;
  }
  const slug = name.slice(0, -5);
  fs.writeFileSync(path.join(OUT, "articles", name), raw);
  lines.push(`${slug}\t${JSON.stringify({ ...article, body: "", timetable: [], disclaimer: "" })}`);
}
fs.writeFileSync(path.join(OUT, "articles.ndjson"), lines.join("\n"));
console.log(`[cf_content] ${lines.length} articles, ${Object.keys(files).length} files -> ${OUT}`);
