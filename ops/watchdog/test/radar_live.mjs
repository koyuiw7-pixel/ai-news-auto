// レーダーの試運転（npm run radar-live [時間]）。本物の情報源を Worker と同じコードで読み、いま起動するとしたら何を速報レーンに回すかを表示する。
// KV・GitHub には触らない（KV は手元の仮のもの・RADAR_DRY_RUN=1）。記事の索引は手元の state/coverage.json（無ければ GitHub の main）
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { radar } from "../src/radar.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const RULES = JSON.parse(readFileSync(join(ROOT, "scripts", "fast_lane_rules.json"), "utf-8"));
const hours = Number(process.argv[2] || 36);
const now = new Date();
const local = join(ROOT, "state", "coverage.json");
const store = new Map([["radar", JSON.stringify({ since: new Date(now - hours * 3600e3).toISOString(), handled: {}, outbox: {}, daily: {}, notified: {} })]]);
const env = {
  REPO: "koyuiw7-pixel/ai-news-auto",
  RADAR_DRY_RUN: "1",
  FAST: { async get(k, t) { const v = store.get(k); return v == null ? null : t === "json" ? JSON.parse(v) : v; }, async put(k, v) { store.set(k, v); } },
};
const fetchImpl = async (url, init) => {
  if (url.includes("/state/coverage.json") && existsSync(local)) return new Response(readFileSync(local, "utf-8"), { status: 200 });
  return fetch(url, init);
};
// 試運転では1回の上限を外して、候補をすべて表示する
const rules = { ...RULES, radar: { ...RULES.radar, max_per_run: 50, max_age_hours: hours } };
const log = await radar(env, now, { rules, fetch: fetchImpl });
console.log(`■ 読んだ件数: ${JSON.stringify(log.read)}${Object.keys(log.errors).length ? ` / 取得失敗: ${JSON.stringify(log.errors)}` : ""}`);
console.log(`\n■ 候補（会社・製品＋強い発表の語）: ${log.candidates.length} 件`);
for (const c of log.candidates) console.log(`  - ${c}`);
console.log(`\n■ 記事あり・起動済み（回さない）: ${log.covered.length} 件`);
for (const c of log.covered) console.log(`  - ${c}`);
console.log(`\n■ 出典が見つからない（30分後に再挑戦・4回で諦めて朝の見逃しチェックへ）: ${log.noPrimary.length} 件`);
for (const c of log.noPrimary) console.log(`  - ${c}`);
console.log(`\n■ 速報レーンに回す（RADAR_DRY_RUN=1 なので実際には回さない）: ${log.dispatched.length} 件`);
for (const d of log.dispatched) {
  console.log(`  ◎ ${d.title}\n     出典: ${d.sourceName}${d.secondary ? "（報道・一次情報なし）" : "（一次情報）"} ${d.url}\n     見つけた場所: ${d.via}${d.also ? ` ほか同じ話題 ${d.also} 件` : ""}`);
}
