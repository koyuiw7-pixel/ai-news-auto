/**
 * 記事を「どこまで読んだか・どれだけ見ていたか・次にどこを押したか」の自前集計（2026-11-10）。cloudflare/aff.ts が回す。
 * 決まりは lib/reading.ts、送るのは components/ReadingBeacon.tsx、読むのは scripts/reading_report.py。
 *
 *   POST /api/aff/read                      1ページの表示の記録（同じオリジンだけ）
 *   GET  /api/aff/reading?date=YYYY-MM-DD   その日（日本時間）の集計（Bearer AFF_STATS_TOKEN）
 *
 * 保存先は AFF_KV（saisoku-aff）:
 *   r:<日付>:<訪問者>:<記事のハッシュ>   同じ人・同じ記事・同じ日は1キー。送り直し（タブを隠した・次のページへ移った）は最新で上書きする。
 *                                       値は空、metadata に {p, s, d, t, n, a, x}。90日で消える
 * IP アドレスは保存しない。訪問者は「秘密の値 + 日付 + IP + UA」の SHA-256 先頭12桁（cloudflare/inflow.ts と同じ）で、日をまたいでたどれない。
 * Do Not Track / GPC のブラウザ、機械・自動ブラウザ、自社のテスト（X-Saisoku-Internal: 1、?_internal=1 のページ）は記録しない。
 * KV の書き込みは1表示につき1〜3回。今の訪問数（1日数百〜数千）なら月の込みの量（100万回）に収まる。
 */
import { json, readJson, safeEqual, sameOrigin, sha256Hex, type KvNamespace } from "./push";
import { isInternal } from "./inflow";
import { INFLOW_BOT_UA } from "../lib/inflow";
import { parseReading, TIME_BUCKETS, type ReadingEvent } from "../lib/reading";

export type ReadingEnv = { AFF_KV?: KvNamespace; AFF_STATS_TOKEN?: string };
type Ctx = { waitUntil(promise: Promise<unknown>): void };

const KEEP_DAYS = 90;
/** 同じ人の記録はこの回数まで（10分で戻る）。機械的な連投で KV の書き込みを使い切らないため */
const BURST_MAX = 60;
const BURST_SEC = 600;
const MAX_KEYS = 200_000;

const JST = 9 * 3600_000;
const jstDate = (ms = Date.now()) => new Date(ms + JST).toISOString().slice(0, 10);
const noContent = () => new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });

async function burst(origin: string, visitor: string): Promise<boolean> {
  try {
    const cache = (caches as unknown as { default: Cache }).default;
    const counter = new Request(`${origin}/api/aff/_rl/rd/${visitor}`);
    const hit = await cache.match(counter);
    const n = hit ? Number(await hit.text()) || 0 : 0;
    if (n >= BURST_MAX) return true;
    await cache.put(counter, new Response(String(n + 1), { headers: { "Cache-Control": `max-age=${BURST_SEC}` } }));
    return false;
  } catch {
    return false;
  }
}

async function record(request: Request, url: URL, env: ReadingEnv, ctx: Ctx): Promise<Response> {
  if (request.method !== "POST") return json({ error: "method" }, 405);
  const site = request.headers.get("sec-fetch-site");
  if (!sameOrigin(request) || (site && site !== "same-origin")) return json({ error: "origin" }, 403);
  const ua = request.headers.get("user-agent") ?? "";
  if (!ua || INFLOW_BOT_UA.test(ua) || isInternal(request) || request.headers.get("dnt") === "1" || request.headers.get("sec-gpc") === "1" || !env.AFF_KV || !env.AFF_STATS_TOKEN) {
    return noContent();
  }
  const event = parseReading(await readJson<Record<string, unknown>>(request, 1024));
  if (!event) return json({ error: "invalid" }, 400);

  const date = jstDate();
  const visitor = (await sha256Hex(`${env.AFF_STATS_TOKEN}|${date}|${request.headers.get("cf-connecting-ip") ?? ""}|${ua}`)).slice(0, 12);
  if (await burst(url.origin, visitor)) return noContent();
  const page = (await sha256Hex(event.p)).slice(0, 12);
  const meta = { p: event.p, s: event.s, d: event.d, t: event.t, n: event.n ? 1 : 0, a: event.a.join(","), x: event.x };
  ctx.waitUntil(
    env.AFF_KV.put(`r:${date}:${visitor}:${page}`, "", { expirationTtl: KEEP_DAYS * 86400, metadata: meta }).catch((error) =>
      console.error("[reading] put failed", String(error)),
    ),
  );
  return noContent();
}

type Meta = { p?: string; s?: string; d?: number; t?: number; n?: number; a?: string; x?: string };
type Row = { views: number; depth: number[]; time: number[]; nextSeen: number; exits: Record<string, number>; adSeen: Record<string, number> };
const newRow = (): Row => ({ views: 0, depth: Array(11).fill(0), time: TIME_BUCKETS.map(() => 0), nextSeen: 0, exits: {}, adSeen: {} });

function add(row: Row, meta: Meta) {
  row.views++;
  const d = Math.min(Math.max(Math.round((meta.d ?? 0) / 10), 0), 10);
  row.depth[d]++;
  const t = TIME_BUCKETS.indexOf((meta.t ?? 0) as typeof TIME_BUCKETS[number]);
  row.time[t < 0 ? 0 : t]++;
  if (meta.n) row.nextSeen++;
  if (meta.x) row.exits[meta.x] = (row.exits[meta.x] ?? 0) + 1;
  for (const pos of (meta.a ?? "").split(",").filter(Boolean)) row.adSeen[pos] = (row.adSeen[pos] ?? 0) + 1;
}

/** 深さ「d 以上まで読んだ」人数・時間「t 秒以上」の人数に直す（読みやすい形） */
function shape(row: Row) {
  const atLeast = (list: number[], i: number) => list.slice(i).reduce((s, v) => s + v, 0);
  const median = (() => {
    let seen = 0;
    for (let i = 0; i < row.time.length; i++) { seen += row.time[i]; if (seen * 2 >= row.views) return TIME_BUCKETS[i]; }
    return 0;
  })();
  return {
    views: row.views,
    reached: { d25: atLeast(row.depth, 3), d50: atLeast(row.depth, 5), d75: atLeast(row.depth, 8), d100: row.depth[10] },
    engaged: { s10: atLeast(row.time, 2), s30: atLeast(row.time, 4), s60: atLeast(row.time, 5), s180: atLeast(row.time, 7) },
    medianSecondsBucket: median,
    nextReadSeen: row.nextSeen,
    internalClicks: Object.values(row.exits).reduce((s, v) => s + v, 0),
    exits: row.exits,
    adSeen: row.adSeen,
    depthHistogram: row.depth,
    timeHistogram: Object.fromEntries(TIME_BUCKETS.map((edge, i) => [String(edge), row.time[i]])),
  };
}

export async function summarizeReading(date: string, kv: KvNamespace) {
  const total = newRow();
  const pages = new Map<string, Row>();
  const sources = new Map<string, Row>();
  let count = 0;
  let cursor: string | undefined;
  do {
    const list = await kv.list({ prefix: `r:${date}:`, cursor, limit: 1000 });
    for (const key of list.keys) {
      const meta = (key.metadata ?? {}) as Meta;
      if (!meta.p || !meta.s) continue;
      count++;
      add(total, meta);
      for (const [map, name] of [[pages, meta.p], [sources, meta.s]] as const) {
        let row = map.get(name);
        if (!row) map.set(name, (row = newRow()));
        add(row, meta);
      }
    }
    cursor = list.list_complete ? undefined : list.cursor;
  } while (cursor && count < MAX_KEYS);
  return {
    date,
    timezone: "Asia/Tokyo",
    version: 1,
    definition:
      "One record per estimated visitor x article x JST day (latest snapshot wins). Depth = share of the page above the footer that was on screen (10% steps). Engaged = seconds the tab was visible (bucketed). nextReadSeen = the 'next article' section was at least half on screen. internalClicks = the last same-site link clicked, by zone. adSeen = PR boxes (data-aff-pos) at least half on screen. Excludes bots, automated browsers, DNT/GPC and internal tests. Snapshots can be lost when a browser is closed abruptly, so counts are a lower bound.",
    truncated: !!cursor,
    total: shape(total),
    bySource: [...sources].map(([source, row]) => ({ source, ...shape(row) })).sort((a, b) => b.views - a.views),
    byPage: [...pages].map(([page, row]) => ({ page, ...shape(row) })).sort((a, b) => b.views - a.views),
  };
}

async function stats(request: Request, url: URL, env: ReadingEnv): Promise<Response> {
  if (request.method !== "GET") return json({ error: "method" }, 405);
  const expected = env.AFF_STATS_TOKEN ?? "";
  const header = request.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (expected.length < 16 || !safeEqual(token, expected)) return json({ error: "unauthorized" }, 401);
  if (!env.AFF_KV) return json({ error: "AFF_KV がありません" }, 503);
  const date = url.searchParams.get("date") || jstDate();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return json({ error: "date は YYYY-MM-DD" }, 400);
  return json(await summarizeReading(date, env.AFF_KV));
}

export async function handleReading(request: Request, url: URL, env: ReadingEnv, ctx: Ctx): Promise<Response> {
  if (url.pathname === "/api/aff/read") return record(request, url, env, ctx);
  if (url.pathname === "/api/aff/reading") return stats(request, url, env);
  return json({ error: "not found" }, 404);
}

export type { ReadingEvent };
