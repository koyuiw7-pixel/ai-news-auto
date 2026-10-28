// 追加の発信元の試運転（npm run registry-dry -- 72）: 直近 N 時間に、速報レーンが何を起動したはずかを表にする。
// 話題待ちは、いまのまとめサイト（レーダーの RSS）の見出しで突き合わせる。記事の有無は content/articles の sourceUrl で見る。起動はしない
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { buzzMatch, buzzPatterns, buzzStop, compile, itemId, mergeRegistry, parseFeed, parseHtmlList, relevant, WAIT_REASON } from "../src/fastlane.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const read = (p) => JSON.parse(readFileSync(join(ROOT, p), "utf-8"));
const RULES = mergeRegistry(read("scripts/fast_lane_rules.json"), read("scripts/sources_registry.json"));
const R = compile(RULES);
const HOURS = Number(process.argv[2] || 72);
const now = Date.now();
const UA = "Mozilla/5.0 (compatible; SaisokuFastLane/1.0; +https://ai-tech-express.jp)";

async function get(url) {
  const res = await fetch(url, { headers: { "User-Agent": UA }, signal: AbortSignal.timeout(20000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

const have = new Set();
for (const f of readdirSync(join(ROOT, "content", "articles"))) {
  if (!f.endsWith(".json")) continue;
  try {
    const a = JSON.parse(readFileSync(join(ROOT, "content", "articles", f), "utf-8"));
    for (const u of [a.sourceUrl, ...(a.updates || []).map((x) => x.sourceUrl)]) if (u) have.add(await itemId(u));
  } catch {
    // 壊れたファイルは飛ばす
  }
}

// まとめサイトの見出し（話題の突き合わせ用）
const names = buzzPatterns(RULES);
const buzz = {};
for (const s of RULES.radar.sources.filter((x) => x.type === "rss")) {
  try {
    for (const it of parseFeed(await get(s.url))) {
      for (const [ent, re] of Object.entries(names)) if (re.test(it.title)) (buzz[ent] ||= []).push({ at: it.publishedAt, t: it.title, src: s.name });
    }
  } catch (e) {
    console.error(`radar ${s.slug}: ${e}`);
  }
}

const rows = [];
const broken = [];
await Promise.all(RULES.sources.filter((s) => s.registry).map(async (src) => {
  let items;
  try {
    const body = await get(src.url);
    items = src.type === "html" ? parseHtmlList(body, src) : parseFeed(body);
  } catch (e) {
    broken.push(`${src.slug}（${e}）`);
    return;
  }
  for (const it of items) {
    // 一覧ページは日付が無いので、記事ページの公開日を見ずに「いちばん上の1件」だけ（新着なら起動するかの目安）
    if (it.publishedAt ? now - Date.parse(it.publishedAt) > HOURS * 3600e3 : items.indexOf(it) >= 1) continue;
    const v = relevant(it.title, src.slug, R);
    let verdict = v.ok ? `◎ ${v.reason}` : "";
    if (v.reason === WAIT_REASON) {
      const hit = buzzMatch(it.title, buzz[src.entity], names[src.entity], buzzStop(R));
      verdict = hit ? `◎ 話題（${hit.src}: ${hit.t.slice(0, 40)}）` : "△ 話題待ち（いまは話題なし）";
    }
    if (!verdict) continue;
    rows.push({ at: it.publishedAt || "（一覧）", tier: src.tier, src: src.slug, title: it.title.slice(0, 70), verdict, article: have.has(await itemId(it.url)) ? "あり" : "なし" });
  }
}));
rows.sort((a, b) => String(b.at).localeCompare(String(a.at)));
console.log(`| 公開 | tier | 発信元 | 見出し | 判定 | 記事 |\n|---|---|---|---|---|---|`);
for (const r of rows) console.log(`| ${String(r.at).slice(5, 16)} | ${r.tier} | ${r.src} | ${r.title.replace(/\|/g, "／")} | ${r.verdict.replace(/\|/g, "／")} | ${r.article} |`);
const fire = rows.filter((r) => r.verdict.startsWith("◎"));
console.log(`\n直近${HOURS}時間: 起動したはず ${fire.length} 件（うち記事なし ${fire.filter((r) => r.article === "なし").length}）・話題待ちのまま ${rows.length - fire.length} 件`);
if (broken.length) console.log(`取得できない: ${broken.join("、")}`);
