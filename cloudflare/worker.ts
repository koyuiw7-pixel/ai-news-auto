/**
 * Cloudflare Workers の入口。OpenNext が作った worker を包む。
 *
 * Workers ではリポジトリのファイル（記事 JSON・設定・フォント）を fs で読めないので、
 * ビルド時に静的アセット（/_content/*、scripts/cf_content.mjs が作る）へ置いたものを
 * リクエストの前に先読みし、lib/content-fs.ts が読む仮想 fs（globalThis.__SAISOKU_VFS__）に入れる。
 * デプロイごとに中身は固定なので、isolate の寿命の間は使い回す。
 */
// @ts-ignore ビルド時に生成される
import { default as handler } from "../.open-next/worker.js";

type Env = { ASSETS: { fetch: (input: string | Request) => Promise<Response> } } & Record<string, unknown>;

type VirtualFs = {
  files: Map<string, string | Uint8Array>;
  dirs: Map<string, string[]>;
  roots: string[];
};

type Base = { files: Record<string, string>; dirs: Record<string, string[]> };

const g = globalThis as { __SAISOKU_VFS__?: VirtualFs };
const ORIGIN = "https://assets.local";
const FULL_LIMIT = 200;

let baseLoading: Promise<void> | null = null;
let fontsLoading: Promise<void> | null = null;
/** 本文まで読み込んだ記事（古いものから捨てる） */
const fullSlugs: string[] = [];

async function asset(env: Env, pathname: string): Promise<Response> {
  return env.ASSETS.fetch(new Request(`${ORIGIN}${pathname}`));
}

function loadBase(env: Env): Promise<void> {
  baseLoading ??= (async () => {
    const res = await asset(env, "/_content/base.json");
    if (!res.ok) throw new Error(`content assets missing: ${res.status}`);
    const base = (await res.json()) as Base;
    g.__SAISOKU_VFS__ = {
      files: new Map(Object.entries(base.files)),
      dirs: new Map(Object.entries(base.dirs)),
      roots: ["content", "affiliate_links.json", "monetization.json", "assets/fonts"],
    };
  })().catch((error) => {
    baseLoading = null;
    throw error;
  });
  return baseLoading;
}

function loadFonts(env: Env): Promise<void> {
  fontsLoading ??= (async () => {
    const list = g.__SAISOKU_VFS__!.dirs.get("assets/fonts") ?? [];
    await Promise.all(
      list.map(async (name) => {
        const res = await asset(env, `/_content/fonts/${name}`);
        if (!res.ok) throw new Error(`font missing: ${name}`);
        g.__SAISOKU_VFS__!.files.set(`assets/fonts/${name}`, new Uint8Array(await res.arrayBuffer()));
      }),
    );
  })().catch((error) => {
    fontsLoading = null;
    throw error;
  });
  return fontsLoading;
}

/** 記事ページ・カバーを描く前に、その記事の本文入り JSON を読み込む（無い記事は 404 のまま） */
async function loadArticle(env: Env, slug: string): Promise<void> {
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(slug) || fullSlugs.includes(slug)) return;
  const res = await asset(env, `/_content/articles/${slug}.json`);
  if (res.status === 404) return;
  if (!res.ok) throw new Error(`article asset failed: ${slug} ${res.status}`);
  const vfs = g.__SAISOKU_VFS__!;
  vfs.files.set(`content/articles/${slug}.json`, await res.text());
  fullSlugs.push(slug);
  while (fullSlugs.length > FULL_LIMIT) vfs.files.delete(`content/articles/${fullSlugs.shift()}.json`);
}

const ARTICLE = /^\/(?:articles|cover)\/([^/]+?)(?:\.rsc)?\/?$/;

type Ctx = { waitUntil(promise: Promise<unknown>): void };

/**
 * 出来上がったページを Cloudflare のエッジ（Cache API）に置き、次からは描画もキャッシュ読み出しもせずに返す。
 * キーにデプロイの版を入れるので、デプロイ後に古い HTML（消えた JS を参照）が返ることはない。
 * 画面遷移用の RSC リクエストは対象外。workers.dev では Cache API が効かない（独自ドメインでだけ効く）
 */
function edgeCacheKey(request: Request, url: URL, env: Env): Request | null {
  if (request.method !== "GET" || request.headers.has("rsc") || url.searchParams.has("_rsc")) return null;
  if (url.pathname.startsWith("/_next/") || url.pathname.startsWith("/api/")) return null;
  const version = (env.CF_VERSION_METADATA as { id?: string } | undefined)?.id ?? "dev";
  const key = new URL(url);
  key.searchParams.set("__v", version);
  return new Request(key.toString(), { method: "GET" });
}

/** ISR・静的化されたものだけ（初回の描画中の no-store や、動的なものは置かない） */
function edgeCacheable(response: Response): boolean {
  const cc = response.headers.get("cache-control") ?? "";
  if (response.status !== 200 || /private|no-store/.test(cc) || response.headers.has("set-cookie")) return false;
  return /s-maxage=\d+/.test(cc) || response.headers.has("x-nextjs-cache");
}

/** エッジには1日置く（デプロイで版が変われば自然に使われなくなる）。ブラウザには毎回確かめさせる */
function forEdge(response: Response): Response {
  const copy = new Response(response.body, response);
  const image = (copy.headers.get("content-type") ?? "").startsWith("image/");
  copy.headers.set("cache-control", image ? "public, max-age=604800, s-maxage=86400" : "public, max-age=0, s-maxage=86400");
  return copy;
}

export default {
  async fetch(request: Request, env: Env, ctx: Ctx): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/_content/")) return new Response("Not Found", { status: 404 });

    const cacheKey = edgeCacheKey(request, url, env);
    const edge = cacheKey ? (caches as unknown as { default: Cache }).default : null;
    if (edge && cacheKey) {
      const hit = await edge.match(cacheKey);
      if (hit) return hit;
    }

    // 静的ファイルは OpenNext/アセットに任せる（先読み不要）
    if (!url.pathname.startsWith("/_next/static/")) {
      try {
        await loadBase(env);
        const match = ARTICLE.exec(url.pathname);
        if (match) await loadArticle(env, decodeURIComponent(match[1]));
        if (url.pathname.startsWith("/cover/")) await loadFonts(env);
      } catch (error) {
        console.error("[worker] content preload failed", error);
        return new Response("Service Unavailable", { status: 503, headers: { "Retry-After": "5" } });
      }
    }
    const response: Response = await handler.fetch(request, env, ctx);
    if (edge && cacheKey && edgeCacheable(response)) {
      const cached = forEdge(response);
      ctx.waitUntil(edge.put(cacheKey, cached.clone()));
      return cached;
    }
    return response;
  },
};

// @ts-ignore ビルド時に生成される
export { DOQueueHandler } from "../.open-next/worker.js";
