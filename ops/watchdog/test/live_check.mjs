// 本物のフィードを Worker と同じコードで読んで、件数と判定を表示する（npm run live）。KV・GitHub には触らない
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { compile, newest, parseFeed, parseHtmlList, relevant } from "../src/fastlane.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const R = compile(JSON.parse(readFileSync(join(ROOT, "scripts", "fast_lane_rules.json"), "utf-8")));
const days = Number(process.argv[2] || 7);
const since = Date.now() - days * 86400e3;

let failed = 0;
for (const src of R.sources) {
  const started = Date.now();
  try {
    const res = await fetch(src.url, {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; SaisokuFastLane/1.0; +https://ai-tech-express.jp)", "Accept-Language": "en,ja;q=0.8" },
      signal: AbortSignal.timeout(15000),
    });
    const body = await res.text();
    const items = newest(src.type === "html" ? parseHtmlList(body, src) : parseFeed(body));
    const etag = res.headers.get("etag") ? "ETag" : res.headers.get("last-modified") ? "Last-Modified" : "条件付き取得なし";
    console.log(`\n■ ${src.slug}: HTTP ${res.status} / ${items.length}件 / ${Math.round(body.length / 1024)}KB / ${Date.now() - started}ms / ${etag}`);
    if (!res.ok || items.length === 0) failed += 1;
    for (const it of items.filter((i) => !i.publishedAt || Date.parse(i.publishedAt) >= since).slice(0, 12)) {
      const r = relevant(it.title, src.slug, R);
      console.log(`  ${r.ok ? "◎" : "  "} ${it.publishedAt ? it.publishedAt.slice(5, 16) : "日付なし   "} ${it.title.slice(0, 80)}  (${r.reason})`);
    }
  } catch (e) {
    failed += 1;
    console.log(`\n■ ${src.slug}: 失敗 ${e}`);
  }
}
console.log(failed ? `\n取得・解析できなかった発信元: ${failed}` : "\nすべての発信元を取得・解析できました");
process.exit(failed ? 1 : 0);
