/**
 * 提携リンクの「人による」クリックの自前集計。cloudflare/worker.ts が /api/aff/* をここに回す。
 * ASP（A8 など）のクリック数にはクローラーや自動ブラウザが混ざるので、実数と見比べるために数える。
 *
 *   POST /api/aff/click                   1クリックを記録（画面 components/AffClickTracker.tsx から。同じオリジンだけ）
 *   GET  /api/aff/stats?date=YYYY-MM-DD   その日（日本時間）の集計（Bearer AFF_STATS_TOKEN。scripts/aff_stats.py が読む）
 *
 * 保存先は Workers KV の AFF_KV（saisoku-aff）:
 *   c:<日付>:<提携先ID>:<時分秒><乱数>   1クリック = 1キー（同時に押されても数がずれない）。値は空で metadata にパス・置き場所・訪問者の短いハッシュ。400日で消える
 * IP アドレスは保存しない。訪問者のハッシュは「秘密の値 + 日付 + IP + UA」の SHA-256 先頭8桁で、日をまたいで同じ人をたどれない。
 * 連打・機械的な連投は Cache API（そのデータセンターの一時置き場）で間引く。
 */
import { json, readJson, safeEqual, sameOrigin, sha256Hex, type KvNamespace } from "./push";
import { FUNNEL, SOURCES, STAGES, validFunnelEvent } from "../lib/revenue-funnel";

export type AffEnv = {
  AFF_KV?: KvNamespace;
  AFF_STATS_TOKEN?: string;
};

type Ctx = { waitUntil(promise: Promise<unknown>): void };
type Meta = { path?: string; pos?: string; v?: string };
type FunnelMeta = Meta & { stage?: string; source?: string; choice?: string };

/** 画面側（components/AffClickTracker.tsx）と同じ。サーバーでも念のため弾く */
const BOT_UA = /bot|crawl|spider|slurp|headless|lighthouse|pagespeed|preview|phantom|puppeteer|playwright|selenium|python|curl|wget/i;
const PROGRAM = /^[A-Za-z0-9+._-]{1,60}$/;
const PATH = /^\/[A-Za-z0-9\-._~%!$&'()*+,;=:@/]{0,200}$/;
const POS = /^[a-z0-9-]{1,32}$/;
const KEEP_DAYS = 400;
/** 同じ人が同じリンクを押し直したら、この秒数のあいだは1回と数える */
const DEDUPE_SEC = 10;
/** 同じ人の記録はこの回数まで（最後の記録から10分で戻る） */
const BURST_MAX = 20;
const BURST_SEC = 600;

const JST = 9 * 3600_000;
const jstDate = (ms = Date.now()) => new Date(ms + JST).toISOString().slice(0, 10);
const jstTime = (ms = Date.now()) => new Date(ms + JST).toISOString().slice(11, 19).replace(/:/g, "");

const noContent = () => new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });

function authorized(request: Request, env: AffEnv): boolean {
  const expected = env.AFF_STATS_TOKEN ?? "";
  const header = request.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  return expected.length >= 16 && safeEqual(token, expected);
}

/** 押し直し・連投なら true（その場合は記録しない）。Cache API が使えないときは数える */
async function limited(origin: string, visitor: string, link: string): Promise<boolean> {
  try {
    const cache = (caches as unknown as { default: Cache }).default;
    const dedupe = new Request(`${origin}/api/aff/_rl/d/${visitor}/${(await sha256Hex(link)).slice(0, 16)}`);
    if (await cache.match(dedupe)) return true;
    const counter = new Request(`${origin}/api/aff/_rl/n/${visitor}`);
    const hit = await cache.match(counter);
    const n = hit ? Number(await hit.text()) || 0 : 0;
    if (n >= BURST_MAX) return true;
    await Promise.all([
      cache.put(dedupe, new Response("1", { headers: { "Cache-Control": `max-age=${DEDUPE_SEC}` } })),
      cache.put(counter, new Response(String(n + 1), { headers: { "Cache-Control": `max-age=${BURST_SEC}` } })),
    ]);
    return false;
  } catch {
    return false;
  }
}

async function click(request: Request, url: URL, env: AffEnv, ctx: Ctx): Promise<Response> {
  if (request.method !== "POST") return json({ error: "method" }, 405);
  const site = request.headers.get("sec-fetch-site");
  if (!sameOrigin(request) || (site && site !== "same-origin")) return json({ error: "origin" }, 403);
  const ua = request.headers.get("user-agent") ?? "";
  // 機械のアクセス・設定が無いときは黙って捨てる（画面には何も返さなくてよい）
  if (!ua || BOT_UA.test(ua) || !env.AFF_KV || !env.AFF_STATS_TOKEN) return noContent();

  const body = await readJson<{ p?: unknown; path?: unknown; pos?: unknown }>(request, 1024);
  const program = typeof body?.p === "string" ? body.p : "";
  const path = typeof body?.path === "string" ? body.path : "";
  const pos = typeof body?.pos === "string" ? body.pos : "other";
  if (!PROGRAM.test(program) || !PATH.test(path) || !POS.test(pos)) return json({ error: "invalid" }, 400);

  const now = Date.now();
  const date = jstDate(now);
  const ip = request.headers.get("cf-connecting-ip") ?? "";
  const visitor = (await sha256Hex(`${env.AFF_STATS_TOKEN}|${date}|${ip}|${ua}`)).slice(0, 16);
  if (await limited(url.origin, visitor, `${program}|${path}`)) return noContent();

  const rand = crypto.getRandomValues(new Uint32Array(1))[0].toString(36);
  const meta: Meta = { path, pos, v: visitor.slice(0, 8) };
  ctx.waitUntil(
    env.AFF_KV.put(`c:${date}:${program}:${jstTime(now)}${rand}`, "", { expirationTtl: KEEP_DAYS * 86400, metadata: meta }).catch((error) =>
      console.error("[aff] put failed", String(error)),
    ),
  );
  return noContent();
}

/** 新導線の表示・遷移。旧クリック(c:)と分離し、既存の集計値を変えない。 */
async function funnelEvent(request: Request, url: URL, env: AffEnv, ctx: Ctx): Promise<Response> {
  if (request.method !== "POST") return json({ error: "method" }, 405);
  const site = request.headers.get("sec-fetch-site");
  if (!sameOrigin(request) || (site && site !== "same-origin")) return json({ error: "origin" }, 403);
  const ua = request.headers.get("user-agent") ?? "";
  if (!ua || BOT_UA.test(ua) || request.headers.get("dnt") === "1" || request.headers.get("sec-gpc") === "1" || !env.AFF_KV || !env.AFF_STATS_TOKEN) return noContent();
  const body = await readJson<Record<string, unknown>>(request, 1024);
  const field = (key: string) => typeof body?.[key] === "string" ? body[key] as string : "";
  const stage = field("stage"), path = field("path"), source = field("source"), choice = field("choice"), pos = field("pos") || "other";
  if (field("funnel") !== FUNNEL || !validFunnelEvent(stage, path, choice) || !SOURCES.includes(source as typeof SOURCES[number]) || !POS.test(pos)) return json({ error: "invalid" }, 400);
  const now = Date.now(), date = jstDate(now);
  const visitor = (await sha256Hex(`${env.AFF_STATS_TOKEN}|${date}|${request.headers.get("cf-connecting-ip") ?? ""}|${ua}`)).slice(0, 16);
  // 別カウンターにして、表示イベントが広告クリックの連投制限を消費しないようにする。
  if (await limited(url.origin, `f-${visitor}`, `${stage}|${path}|${choice}`)) return noContent();
  const rand = crypto.getRandomValues(new Uint32Array(1))[0].toString(36);
  ctx.waitUntil(env.AFF_KV.put(`f:${date}:${FUNNEL}:${jstTime(now)}${rand}`, "", {
    expirationTtl: 90 * 86400,
    metadata: { stage, path, source, choice, pos, v: visitor } satisfies FunnelMeta,
  }).catch((error) => console.error("[funnel] put failed", String(error))));
  return noContent();
}

async function funnelStats(date: string, kv: KvNamespace) {
  const stages = new Map<string, Row>();
  const sources = new Map<string, Row>();
  const entries = new Map<string, Row>();
  const choices = new Map<string, Row>();
  let count = 0, cursor: string | undefined;
  do {
    const page = await kv.list({ prefix: `f:${date}:${FUNNEL}:`, cursor, limit: 1000 });
    for (const key of page.keys) {
      const meta = (key.metadata ?? {}) as FunnelMeta;
      if (!meta.stage || !STAGES.includes(meta.stage as typeof STAGES[number])) continue;
      count++;
      bump(stages, meta.stage, meta.v ?? "");
      bump(sources, `${meta.source ?? "other"}:${meta.stage}`, meta.v ?? "");
      if (meta.stage === "guide_click") bump(entries, `${meta.path ?? "?"}|${meta.pos ?? "other"}`, meta.v ?? "");
      if (meta.stage === "choice_click") bump(choices, meta.choice ?? "?", meta.v ?? "");
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor && count < 100_000);
  const events = (map: Map<string, Row>, name: string) => sorted(map, name).map(({ clicks, ...row }) => ({ ...row, events: clicks }));
  return {
    id: FUNNEL, version: 1, enabled: true, retentionDays: 90, truncated: !!cursor,
    definition: "Visible browser events, not confirmed humans, ordered sessions, sales or approvals. Visitors are daily IP/UA hash estimates; do not sum them across days.",
    stages: STAGES.map((stage) => ({ stage, events: stages.get(stage)?.clicks ?? 0, visitors: stages.get(stage)?.visitors.size ?? 0 })),
    bySourceStage: events(sources, "sourceStage"), byEntry: events(entries, "entry"), byChoice: events(choices, "choice"),
  };
}

type Row = { clicks: number; visitors: Set<string> };
const bump = (map: Map<string, Row>, key: string, visitor: string) => {
  const row = map.get(key) ?? { clicks: 0, visitors: new Set<string>() };
  row.clicks++;
  if (visitor) row.visitors.add(visitor);
  map.set(key, row);
};
const sorted = (map: Map<string, Row>, name: string) =>
  [...map.entries()]
    .map(([key, row]) => ({ [name]: key, clicks: row.clicks, visitors: row.visitors.size }))
    .sort((a, b) => b.clicks - a.clicks);

async function stats(request: Request, url: URL, env: AffEnv): Promise<Response> {
  if (request.method !== "GET") return json({ error: "method" }, 405);
  if (!authorized(request, env)) return json({ error: "unauthorized" }, 401);
  if (!env.AFF_KV) return json({ error: "AFF_KV がありません" }, 503);
  const date = url.searchParams.get("date") || jstDate();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return json({ error: "date は YYYY-MM-DD" }, 400);

  const programs = new Map<string, Row>();
  const pages = new Map<string, Row>();
  const positions = new Map<string, Row>();
  const hours = new Map<string, Row>();
  const visitors = new Set<string>();
  let total = 0;
  let cursor: string | undefined;
  do {
    const page = await env.AFF_KV.list({ prefix: `c:${date}:`, cursor, limit: 1000 });
    for (const key of page.keys) {
      const [, , program = "?", rest = ""] = key.name.split(":");
      const meta = (key.metadata ?? {}) as Meta;
      const visitor = meta.v ?? "";
      total++;
      if (visitor) visitors.add(visitor);
      bump(programs, program, visitor);
      bump(pages, meta.path ?? "?", visitor);
      bump(positions, meta.pos ?? "other", visitor);
      bump(hours, rest.slice(0, 2) || "??", visitor);
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor && total < 100_000);

  return json({
    date,
    timezone: "Asia/Tokyo",
    clicks: total,
    visitors: visitors.size,
    byProgram: sorted(programs, "program"),
    byPage: sorted(pages, "path"),
    byPosition: sorted(positions, "pos"),
    byHour: sorted(hours, "hour").sort((a, b) => String(a.hour).localeCompare(String(b.hour))),
    funnel: await funnelStats(date, env.AFF_KV),
  });
}

export async function handleAff(request: Request, url: URL, env: AffEnv, ctx: Ctx): Promise<Response> {
  if (url.pathname === "/api/aff/click") return click(request, url, env, ctx);
  if (url.pathname === "/api/aff/event") return funnelEvent(request, url, env, ctx);
  if (url.pathname === "/api/aff/stats") return stats(request, url, env);
  return json({ error: "not found" }, 404);
}
