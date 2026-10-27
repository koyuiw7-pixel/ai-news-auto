/**
 * 速報レーン（2分ごと）: 主要企業の公式ニュースルームだけを見て、新しい重要な発表を見つけたら
 * すぐ記事作り（auto_run.yml の mode=web + fast_url）を起動する。
 *
 * - 判定ルールは scripts/fast_lane_rules.json（Python 側 scripts/fast_lane.py と同じ判定。npm test で突き合わせる）
 * - フィードは ETag / Last-Modified で条件付き取得。見た記事の ID は KV（キー "state"）に残す
 * - 初めて読む発信元は「いまある記事は全部既読」にするだけ（デプロイ直後に昔の記事を流さない）
 * - 起動した記事は、パイプラインが state/fast_lane.json に結果を書くまで KV に残し、
 *   取り消し・失敗・行方不明なら起動し直す（最大 max_dispatches 回）
 * - GitHub は同じ concurrency group の待機を1つしか持てない（新しい方が古い待機を取り消す）ので、
 *   速報レーンの実行が待機中なら新しく起動しない（次の回に回す）
 * - 1日の新規起動は FAST_DAILY_MAX（既定 daily_max）まで。FAST_DRY_RUN=1 なら起動せずログだけ
 */

const UA = "Mozilla/5.0 (compatible; SaisokuFastLane/1.0; +https://ai-tech-express.jp)";
export const RUN_PREFIX = "速報レーン";
const MAX_SEEN = 400;
// 1つのフィードで見るのは新しい順にこの件数まで（OpenAI の RSS は1000件超・800KB 近くある）
const MAX_ITEMS = 60;
const MAX_BLOCKS = 200;
const KEEP_DONE_HOURS = 72;
const TERMINAL = new Set(["created", "updated", "duplicate", "skipped", "failed", "capped"]);
const WAITING = new Set(["queued", "pending", "waiting", "requested"]);

// --------------------------------------------------------------------------- //
// ルール
// --------------------------------------------------------------------------- //

export function compile(rules) {
  const re = (s) => new RegExp(s, "i");
  return {
    ...rules,
    sources: rules.sources.filter((s) => !s.disabled),
    bySlug: Object.fromEntries(rules.sources.map((s) => [s.slug, s])),
    model: re(rules.model_re),
    head: re(rules.head_re),
    launch: re(rules.launch_re),
    exclude: re(rules.exclude_re),
    ai: re(rules.ai_re),
  };
}

/** 速報レーンに乗せるか。理由の文言は scripts/fast_lane.py の relevant() と同じ */
export function relevant(title, slug, R) {
  const src = R.bySlug[slug];
  if (!src) return { ok: false, reason: "対象外の発信元" };
  const t = String(title || "").trim();
  const ex = t.match(R.exclude);
  if (ex) return { ok: false, reason: `除外語（${ex[0]}）` };
  const model = R.model.test(t);
  if (src.ai_only && !model && !R.ai.test(t)) return { ok: false, reason: "AI の話題ではない" };
  const launch = R.launch.test(t);
  if (model && (launch || R.head.test(t))) return { ok: true, reason: "新モデル・新製品" };
  // 対象は各社の公式ニュースルームだけなので、発表の語があれば自社（か提携先と共同）の発表とみなす
  if (launch) return { ok: true, reason: "公式の発表" };
  return { ok: false, reason: "発表の語がない" };
}

// --------------------------------------------------------------------------- //
// 解析（標準のパーサーが無いので正規表現で。RSS 2.0 / Atom / RSS 1.0 と、一覧ページの HTML）
// --------------------------------------------------------------------------- //

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export function decode(s) {
  return String(s).replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
    if (e[0] === "#") {
      const code = e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : m;
    }
    return ENTITIES[e.toLowerCase()] ?? m;
  });
}

/** CDATA を外し、タグを除いてから実体参照を戻す（Python の feeds.strip_html と同じ順） */
export function textOf(s) {
  const raw = String(s || "").replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1");
  return decode(raw.replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}

function tag(block, name) {
  // 自己終了タグ（<link .../>）は拾わない
  const m = block.match(new RegExp(`<${name}(?:\\s[^>]*)?(?<!/)>([\\s\\S]*?)</${name}>`, "i"));
  return m ? m[1] : "";
}

function firstBlocks(xml, name, limit) {
  const re = new RegExp(`<${name}\\b[\\s\\S]*?</${name}>`, "gi");
  const out = [];
  for (let m = re.exec(xml); m && out.length < limit; m = re.exec(xml)) out.push(m[0]);
  return out;
}

/** 新しい順に MAX_ITEMS 件（日付が全部あれば日付順、無ければ載っている順） */
export function newest(items) {
  const sorted = items.every((i) => i.publishedAt) ? [...items].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt)) : items;
  return sorted.slice(0, MAX_ITEMS);
}

export function parseFeed(xml) {
  let blocks = firstBlocks(xml, "item", MAX_BLOCKS);
  if (!blocks.length) blocks = firstBlocks(xml, "entry", MAX_BLOCKS);
  const items = [];
  for (const b of blocks) {
    const title = textOf(tag(b, "title"));
    let link = textOf(tag(b, "link"));
    if (!link) {
      // Atom: rel が無いか alternate の link
      for (const m of b.matchAll(/<link\b([^>]*)>/gi)) {
        const attrs = m[1];
        const rel = (attrs.match(/\brel=["']([^"']*)["']/i) || [])[1] || "alternate";
        const href = (attrs.match(/\bhref=["']([^"']*)["']/i) || [])[1];
        if (rel === "alternate" && href) {
          link = decode(href).trim();
          break;
        }
      }
    }
    if (!title || !/^https?:\/\//i.test(link)) continue;
    const date = textOf(tag(b, "pubDate") || tag(b, "dc:date") || tag(b, "published") || tag(b, "updated"));
    const ts = Date.parse(date);
    items.push({ title, url: link, publishedAt: Number.isFinite(ts) ? new Date(ts).toISOString() : null });
  }
  return items;
}

/** RSS の無い一覧ページ（Anthropic /news など）: 見出し（h1〜h4）を含むリンクだけを記事とみなす */
export function parseHtmlList(html, src) {
  const base = new URL(src.url);
  const linkRe = new RegExp(src.link_re || ".", "i");
  const seen = new Set();
  const items = [];
  for (const m of html.matchAll(/<a\b[^>]*?\bhref=["']([^"'#?]+)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    let url;
    try {
      url = new URL(decode(m[1]), base);
    } catch {
      continue;
    }
    if (url.host !== base.host || !linkRe.test(url.pathname)) continue;
    const h = m[2].match(/<h[1-4]\b[^>]*>([\s\S]*?)<\/h[1-4]>/i);
    if (!h) continue;
    const title = textOf(h[1]);
    const key = url.origin + url.pathname.replace(/\/+$/, "");
    if (title.length < 8 || seen.has(key)) continue;
    seen.add(key);
    items.push({ title, url: key, publishedAt: null });
  }
  return items;
}

// --------------------------------------------------------------------------- //
// 記事本文（GitHub Actions からは openai.com などが 403 で読めないので、起動するときにこちらで読んで渡す）
// --------------------------------------------------------------------------- //

const TEXT_CAP = 12000;
const plainLen = (s) => textOf(s).length;

export function metaContent(html, key) {
  const k = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const m =
    html.match(new RegExp(`<meta\\b[^>]*(?:property|name)=["']${k}["'][^>]*\\bcontent=["']([^"']*)["']`, "i")) ||
    html.match(new RegExp(`<meta\\b[^>]*\\bcontent=["']([^"']*)["'][^>]*(?:property|name)=["']${k}["']`, "i"));
  return m ? decode(m[1]).trim() : "";
}

/** 簡易リーダビリティ（article → main → body の順に、本文らしい部分のテキスト） */
export function htmlToText(html) {
  const h = String(html).replace(/<(script|style|noscript|svg|template|iframe)\b[\s\S]*?<\/\1>/gi, " ");
  const inner = (name) => (h.match(new RegExp(`<${name}\\b[^>]*>([\\s\\S]*)</${name}>`, "i")) || [])[1] || "";
  let body = inner("article");
  if (plainLen(body) < 500) body = inner("main");
  if (plainLen(body) < 500) body = inner("body") || h;
  body = body
    .replace(/<(nav|footer|aside|form|button)\b[\s\S]*?<\/\1>/gi, " ")
    .replace(/<\/?(p|div|section|li|h[1-6]|br|tr|blockquote|pre|figure|figcaption|dd|dt|ul|ol|table)\b[^>]*>/gi, "\n");
  return decode(body.replace(/<[^>]+>/g, " "))
    .split("\n")
    .map((l) => l.replace(/[ \t ]+/g, " ").trim())
    .filter((l) => l.length >= 2)
    .join("\n")
    .slice(0, TEXT_CAP);
}

/** {text, image, published}。直接読めない・薄いときは読み取りサービス（r.jina.ai）で取り直す。失敗しても例外にしない */
export async function fetchArticle(url, fetchImpl) {
  const out = { text: "", image: "", published: "" };
  try {
    const res = await fetchImpl(url, {
      headers: { "User-Agent": UA, Accept: "text/html,application/xhtml+xml", "Accept-Language": "en,ja;q=0.8" },
      signal: AbortSignal.timeout(12000),
    });
    if (res.ok) {
      const html = await res.text();
      out.text = htmlToText(html);
      out.image = metaContent(html, "og:image") || metaContent(html, "twitter:image");
      out.published = metaContent(html, "article:published_time");
    }
  } catch {
    // 読み取りサービスで取り直す
  }
  if (out.text.length >= 600) return out;
  try {
    const res = await fetchImpl(`https://r.jina.ai/${url}`, { headers: { Accept: "text/plain" }, signal: AbortSignal.timeout(20000) });
    if (res.ok) {
      const body = await res.text();
      const at = body.indexOf("Markdown Content:");
      const md = (at >= 0 ? body.slice(at + 17) : body)
        .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
        .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
      const text = md.split("\n").map((l) => l.trim()).filter((l) => l.length >= 2).join("\n").slice(0, TEXT_CAP);
      if (text.length > out.text.length) out.text = text;
      out.published ||= ((body.match(/^Published Time:\s*(.+)$/m) || [])[1] || "").trim();
    }
  } catch {
    // 取れなければパイプライン側の取得に任せる
  }
  return out;
}

/** Python の feeds.item_id と同じ正規化（utm_* と末尾スラッシュを無視） */
export function normalizeUrl(u) {
  const x = new URL(String(u).trim());
  const params = [...x.searchParams].filter(([k]) => !k.toLowerCase().startsWith("utm_"));
  const q = new URLSearchParams(params).toString();
  return `${x.protocol}//${x.host.toLowerCase()}${x.pathname.replace(/\/+$/, "")}${q ? `?${q}` : ""}`;
}

export async function itemId(u) {
  const data = new TextEncoder().encode(normalizeUrl(u));
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-1", data));
  return [...hash].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

/** 日本時間の日付（1日の上限の数え方） */
export function jstDate(now) {
  return new Date(now.getTime() + 9 * 3600e3).toISOString().slice(0, 10);
}

// --------------------------------------------------------------------------- //
// 取得
// --------------------------------------------------------------------------- //

async function poll(src, st, fetchImpl) {
  const headers = {
    "User-Agent": UA,
    Accept: src.type === "html" ? "text/html,application/xhtml+xml" : "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en,ja;q=0.8",
  };
  if (st?.etag) headers["If-None-Match"] = st.etag;
  if (st?.lm) headers["If-Modified-Since"] = st.lm;
  const res = await fetchImpl(src.url, { headers, signal: AbortSignal.timeout(12000), cache: "no-store" });
  if (res.status === 304) return { status: 304, items: null };
  if (!res.ok) return { status: res.status, items: null };
  const body = await res.text();
  const items = newest(src.type === "html" ? parseHtmlList(body, src) : parseFeed(body));
  return { status: res.status, items, etag: res.headers.get("etag") || "", lm: res.headers.get("last-modified") || "" };
}

/**
 * 新着の判定（KV の state.sources を書き換える）。戻り値: { fresh: [...], changed: bool }
 * - 初回は既読にするだけ / 0件（解析失敗）なら既読の記録を触らない
 */
export async function detect(srcState, src, result, now) {
  if (!result.items) return { fresh: [], changed: false };
  if (result.items.length === 0) return { fresh: [], changed: false, empty: true };
  const ids = await Promise.all(result.items.map((it) => itemId(it.url)));
  const withIds = result.items.map((it, k) => ({ ...it, id: ids[k] }));
  const meta = { etag: result.etag || "", lm: result.lm || "" };
  if (!srcState) {
    return { fresh: [], changed: true, baseline: true, next: { ...meta, seen: [...new Set(ids)].slice(0, MAX_SEEN), since: now.toISOString() } };
  }
  const seen = new Set(srcState.seen || []);
  const fresh = withIds.filter((it) => !seen.has(it.id));
  const next = { ...srcState, ...meta };
  if (fresh.length) next.seen = [...new Set([...ids, ...(srcState.seen || [])])].slice(0, MAX_SEEN);
  const changed = fresh.length > 0 || meta.etag !== (srcState.etag || "") || meta.lm !== (srcState.lm || "");
  return { fresh, changed, next };
}

// --------------------------------------------------------------------------- //
// GitHub
// --------------------------------------------------------------------------- //

export function makeGh(env, fetchImpl = fetch) {
  return async function gh(path, init = {}) {
    const res = await fetchImpl(`https://api.github.com/repos/${env.REPO}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${env.GH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "saisoku-watchdog",
        "X-GitHub-Api-Version": "2022-11-28",
        ...(init.headers || {}),
      },
    });
    if (res.status === 404 && init.allow404) return null;
    if (!res.ok && res.status !== 204) throw new Error(`GitHub ${path} -> ${res.status} ${(await res.text()).slice(0, 200)}`);
    if (res.status === 204) return null;
    return init.raw ? res.text() : res.json();
  };
}

/** パイプラインの処理結果（state/fast_lane.json の items）。API で読めなければ公開の raw（最大5分古い）で読む */
async function readAcks(gh, env, fetchImpl, now) {
  let text;
  try {
    text = await gh(`/contents/state/fast_lane.json?ref=main`, {
      headers: { Accept: "application/vnd.github.raw+json" },
      raw: true,
      allow404: true,
    });
  } catch {
    const res = await fetchImpl(`https://raw.githubusercontent.com/${env.REPO}/main/state/fast_lane.json?t=${now.getTime()}`, {
      cache: "no-store",
    });
    text = res.ok ? await res.text() : "";
  }
  if (!text) return {};
  try {
    return JSON.parse(text).items || {};
  } catch {
    return {};
  }
}

// --------------------------------------------------------------------------- //
// 1回分
// --------------------------------------------------------------------------- //

/**
 * @param env  KV（FAST）・GH_TOKEN・REPO・WORKFLOW・FAST_DRY_RUN・FAST_DAILY_MAX
 * @param deps テスト用の差し替え { rules, fetch, gh }
 */
export async function fastLane(env, now, deps = {}) {
  const R = compile(deps.rules);
  const fetchImpl = deps.fetch || fetch;
  const gh = deps.gh || makeGh(env, fetchImpl);
  const dry = String(env.FAST_DRY_RUN || "") === "1";
  const state = (await env.FAST.get("state", "json")) || {};
  state.sources ||= {};
  state.queue ||= {};
  state.daily ||= {};
  const log = { dry, polled: 0, notModified: 0, errors: {}, baseline: [], new: [], queued: [] };
  let dirty = false;

  // 1. 取得と新着の判定
  const results = await Promise.all(
    R.sources.map((src) => poll(src, state.sources[src.slug], fetchImpl).catch((e) => ({ error: String(e).slice(0, 120) }))),
  );
  const candidates = [];
  for (const [k, src] of R.sources.entries()) {
    const r = results[k];
    log.polled += 1;
    if (r.error || (!r.items && r.status !== 304)) {
      log.errors[src.slug] = r.error || r.status;
      continue;
    }
    if (r.status === 304) {
      log.notModified += 1;
      continue;
    }
    const d = await detect(state.sources[src.slug], src, r, now);
    if (d.empty) {
      log.errors[src.slug] = "0件（解析できず）";
      continue;
    }
    if (d.changed) {
      state.sources[src.slug] = d.next;
      dirty = true;
    }
    if (d.baseline) log.baseline.push(`${src.slug}:${r.items.length}`);
    for (const it of d.fresh) {
      const rel = relevant(it.title, src.slug, R);
      const ageH = it.publishedAt ? (now - Date.parse(it.publishedAt)) / 3600e3 : 0;
      let verdict = rel.ok ? "対象" : rel.reason;
      if (rel.ok && ageH > R.max_age_hours) verdict = `古い（${Math.round(ageH)}時間前）`;
      if (rel.ok && state.queue[it.id]) verdict = "処理待ちに登録済み";
      log.new.push(`${src.slug}: ${it.title.slice(0, 70)} → ${verdict}`);
      if (verdict === "対象") candidates.push({ ...it, source: src.slug, entity: src.entity, reason: rel.reason, order: k });
    }
  }

  // 同じ回に同じ会社の発表が複数あれば1本だけ（大きな発表は Google の複数のブログに同時に載るため）。
  // 新モデル・新製品を優先し、同じならルールの並び順（本家のブログが先）
  const best = new Map();
  for (const c of candidates) {
    const cur = best.get(c.entity);
    const rank = (x) => (x.reason === "新モデル・新製品" ? 0 : 1) * 100 + x.order;
    if (!cur || rank(c) < rank(cur)) best.set(c.entity, c);
  }
  for (const c of candidates) {
    const picked = best.get(c.entity) === c;
    state.queue[c.id] = {
      id: c.id, url: c.url, title: c.title, source: c.source, reason: c.reason,
      publishedAt: c.publishedAt, detectedAt: now.toISOString(),
      status: picked ? "new" : "merged", dispatches: 0,
    };
    dirty = true;
    log.queued.push(`${picked ? "登録" : "同じ会社の発表と重複（見送り）"}: ${c.title.slice(0, 60)}`);
  }

  // 2. 起動済みの記事の確認と、新規・再起動
  if (await manageQueue(env, state, now, log, R, gh, dry, fetchImpl)) dirty = true;

  // 3. 古い記録を消す
  for (const [id, e] of Object.entries(state.queue)) {
    const at = Date.parse(e.doneAt || e.detectedAt);
    if (!["new", "dispatched"].includes(e.status) && now - at > KEEP_DONE_HOURS * 3600e3) {
      delete state.queue[id];
      dirty = true;
    }
  }
  for (const day of Object.keys(state.daily)) {
    if (day < jstDate(new Date(now.getTime() - 7 * 86400e3))) {
      delete state.daily[day];
      dirty = true;
    }
  }
  if (dirty) await env.FAST.put("state", JSON.stringify(state));
  log.open = Object.values(state.queue).filter((e) => ["new", "dispatched"].includes(e.status)).length;
  return log;
}

async function manageQueue(env, state, now, log, R, gh, dry, fetchImpl) {
  const open = Object.values(state.queue).filter((e) => e.status === "new" || e.status === "dispatched");
  if (!open.length) return false;
  let dirty = false;
  let runs = null;
  const getRuns = async () => (runs ??= (await gh(`/actions/workflows/${env.WORKFLOW}/runs?per_page=30`)).workflow_runs || []);
  const minutes = (iso) => (now - Date.parse(iso)) / 60000;

  // 起動済み: パイプラインの結果を見る
  const redo = [];
  const dispatched = open.filter((e) => e.status === "dispatched");
  if (dispatched.length) {
    const acks = await readAcks(gh, env, fetchImpl, now);
    for (const e of dispatched) {
      const ack = acks[e.id];
      if (ack && TERMINAL.has(ack.outcome)) {
        Object.assign(e, { status: "done", outcome: ack.outcome, slug: ack.slug || "", doneAt: now.toISOString() });
        log.done = [...(log.done || []), `${ack.outcome}: ${e.title.slice(0, 50)}${ack.slug ? ` → ${ack.slug}` : ""}`];
        dirty = true;
        continue;
      }
      const run = (await getRuns()).find(
        (r) => (r.display_title || "").includes(e.runKey || e.url) && Date.parse(r.created_at) >= Date.parse(e.dispatchedAt) - 60000,
      );
      const since = minutes(e.dispatchedAt);
      let again = false;
      let why = "";
      if (ack?.outcome === "retry" && (!run || run.status === "completed")) [again, why] = [true, "作れなかった（再挑戦）"];
      else if (run?.status === "completed") [again, why] = [since >= 3, `実行が ${run.conclusion} で結果の記録なし`];
      else if (!run) [again, why] = [since >= 10, "実行が見つからない"];
      else [again, why] = [since >= 60, "60分たっても終わらない"];
      if (!again) continue;
      if ((e.dispatches || 0) >= R.max_dispatches) {
        Object.assign(e, { status: "gave_up", outcome: why, doneAt: now.toISOString() });
        log.gaveUp = [...(log.gaveUp || []), `${e.title.slice(0, 50)}（${why}）`];
        dirty = true;
        continue;
      }
      e.redoReason = why;
      redo.push(e);
    }
  }

  // 新規（1日の上限を超えた分は capped）
  const day = jstDate(now);
  const cap = Number(env.FAST_DAILY_MAX || R.daily_max);
  const fresh = open.filter((e) => e.status === "new").sort((a, b) => a.detectedAt.localeCompare(b.detectedAt));
  const allowance = Math.max(0, cap - (state.daily[day] || 0));
  for (const e of fresh.slice(allowance)) {
    Object.assign(e, { status: "capped", doneAt: now.toISOString() });
    log.capped = [...(log.capped || []), e.title.slice(0, 50)];
    dirty = true;
  }
  const batch = [...redo, ...fresh.filter((e) => e.status === "new")].slice(0, R.max_per_run);
  if (!batch.length) return dirty;

  // 本文・画像はこちらで読んで渡す（パイプラインからは読めないサイトがあるため）
  const pages = await Promise.all(batch.map((e) => fetchArticle(e.url, fetchImpl)));
  const meta = batch.map((e, k) => ({
    id: e.id, url: e.url, title: e.title, source: e.source,
    publishedAt: e.publishedAt || pages[k].published || null, detectedAt: e.detectedAt,
    image: pages[k].image || "", text: pages[k].text || "",
  }));
  const summary = meta.map((x) => ({ url: x.url, title: x.title.slice(0, 60), textChars: x.text.length, image: Boolean(x.image) }));

  if (dry) {
    for (const e of batch) Object.assign(e, { status: "dry", doneAt: now.toISOString() });
    log.wouldDispatch = summary.map((x, k) => ({ ...x, reason: batch[k].redoReason || batch[k].reason }));
    return true;
  }

  // 速報レーンの実行が待機中なら、取り消してしまわないよう次の回に回す（通常の回の待機は取り消してよい）
  const waiting = (await getRuns()).find((r) => WAITING.has(r.status) && (r.display_title || "").startsWith(RUN_PREFIX));
  if (waiting) {
    log.waiting = `速報レーンの実行が待機中（#${waiting.run_number}）`;
    return dirty;
  }
  await gh(`/actions/workflows/${env.WORKFLOW}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: "main", inputs: { mode: "web", fast_url: batch[0].url, fast_meta: JSON.stringify(meta) } }),
  });
  for (const e of batch) {
    if (e.status === "new") state.daily[day] = (state.daily[day] || 0) + 1;
    Object.assign(e, { status: "dispatched", dispatchedAt: now.toISOString(), dispatches: (e.dispatches || 0) + 1, runKey: batch[0].url });
  }
  log.dispatched = summary.map((x, k) => ({ ...x, redo: batch[k].redoReason || "" }));
  return true;
}
