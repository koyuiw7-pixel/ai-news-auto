/**
 * 地震・津波の速報レーン（2分ごと）: 気象庁の防災情報XML（eqvol.xml）を見て、
 * 震度5弱以上・大津波警報・津波警報が出たら、すぐ記事作り（auto_run.yml の fast_url = 電文の URL）を起動する。
 *
 * - 記事は scripts/quake.py が LLM を使わず決まった書式で作る。同じ地震（EventID）の続報は同じ記事を書き直す
 * - 一度記事にした地震は follow_hours 時間、続報の電文（震源・震度・津波の更新・解除）も起動する
 * - 起動の数は quake.daily_max まで（全体の速報レーンの上限には数えない＝安全のため）
 * - 記録は KV のキー "quake"（速報レーンの "state" とは別。書くのはここだけ）
 * - 訓練・試験の電文（Status が「通常」以外）は使わない
 */
import { decode, jstDate, parseFeed, readAcks, RUN_PREFIX } from "./fastlane.js";

const UA = "Mozilla/5.0 (compatible; SaisokuQuake/1.0; +https://ai-tech-express.jp)";
export const RANK = { 1: 1, 2: 2, 3: 3, 4: 4, "5-": 5, "5+": 6, "6-": 7, "6+": 8, 7: 9 };
const WARN = { 52: "大津波警報", 53: "大津波警報", 51: "津波警報", 62: "津波注意報" };
const MAX_SEEN = 300;
const MAX_FETCH = 6;
const WAITING = new Set(["queued", "pending", "waiting", "requested"]);

const pick = (xml, re) => decode(((xml.match(re) || [])[1] || "").trim());

/** 電文の要点（Python の quake.parse の一部と同じ） */
export function parseQuake(xml) {
  const control = (xml.match(/<Control>([\s\S]*?)<\/Control>/) || [])[1] || "";
  const head = (xml.match(/<Head\b[\s\S]*?<\/Head>/) || [])[0] || "";
  const body = (xml.match(/<Body\b[\s\S]*?<\/Body>/) || [])[0] || "";
  const obs = (body.match(/<Observation>([\s\S]*?)<\/Observation>/) || [])[1] || "";
  const forecast = (body.match(/<Tsunami>[\s\S]*?<Forecast>([\s\S]*?)<\/Forecast>/) || [])[1] || "";
  const codes = [...forecast.matchAll(/<Category>\s*<Kind>\s*<Name>[^<]*<\/Name>\s*<Code>(\d+)<\/Code>/g)].map((m) => m[1]);
  const kinds = new Set(codes.map((c) => WARN[c]).filter(Boolean));
  return {
    title: pick(control, /<Title>([^<]*)<\/Title>/),
    status: pick(control, /<Status>([^<]*)<\/Status>/),
    eventId: pick(head, /<EventID>([^<]*)<\/EventID>/),
    infoType: pick(head, /<InfoType>([^<]*)<\/InfoType>/),
    reportAt: pick(head, /<ReportDateTime>([^<]*)<\/ReportDateTime>/),
    maxInt: pick(obs, /<MaxInt>([^<]*)<\/MaxInt>/),
    warn: ["大津波警報", "津波警報", "津波注意報"].find((k) => kinds.has(k)) || "",
  };
}

/** 新しく記事にする電文か（震度 min_int 以上・大津波警報・津波警報） */
export function triggers(b, Q) {
  if (b.status !== "通常" || b.infoType === "取消") return false;
  if ((RANK[b.maxInt] || 0) >= RANK[Q.min_int || "5-"]) return true;
  return b.warn === "大津波警報" || b.warn === "津波警報";
}

/**
 * @param env  KV（FAST）・GH_TOKEN・REPO・WORKFLOW・FAST_DRY_RUN
 * @param deps { rules, fetch, gh }
 */
export async function quakeLane(env, now, deps) {
  const Q = deps.rules.quake;
  if (!Q?.feed) return null;
  const fetchImpl = deps.fetch || fetch;
  const gh = deps.gh;
  const dry = String(env.FAST_DRY_RUN || "") === "1";
  const st = (await env.FAST.get("quake", "json")) || {};
  st.seen ||= [];
  st.events ||= {};
  st.daily ||= {};
  const log = { dry, fresh: 0, read: [], dispatched: [] };
  let dirty = false;

  // 1. feed（Last-Modified で条件付き取得）
  const headers = { "User-Agent": UA, Accept: "application/atom+xml, application/xml;q=0.9" };
  if (st.lm) headers["If-Modified-Since"] = st.lm;
  const res = await fetchImpl(Q.feed, { headers, signal: AbortSignal.timeout(10000), cache: "no-store" });
  if (res.status !== 304) {
    if (!res.ok) {
      log.error = `feed ${res.status}`;
    } else {
      const items = parseFeed(await res.text());
      const ids = items.map((i) => i.url);
      const baseline = !st.lm && !st.seen.length;
      st.lm = res.headers.get("last-modified") || st.lm || now.toUTCString();
      dirty = true;
      const seen = new Set(st.seen);
      const fresh = baseline ? [] : items.filter((i) => !seen.has(i.url) && (Q.titles || []).includes(i.title));
      st.seen = [...new Set([...ids, ...st.seen])].slice(0, MAX_SEEN);
      log.fresh = fresh.length;
      if (baseline) log.baseline = items.length;
      // 古い順に読む（同じ地震の震度速報 → 震源・震度の順に積む）
      for (const it of fresh.reverse().slice(0, MAX_FETCH)) {
        let b;
        try {
          const r = await fetchImpl(it.url, { headers: { "User-Agent": UA }, signal: AbortSignal.timeout(10000) });
          if (!r.ok) throw new Error(String(r.status));
          b = parseQuake(await r.text());
        } catch (e) {
          // 読めなければ次の回に読み直す
          st.seen = st.seen.filter((u) => u !== it.url);
          log.read.push(`読めない: ${it.title}（${String(e).slice(0, 40)}）`);
          continue;
        }
        const ev = st.events[b.eventId];
        const follow = ev && now - Date.parse(ev.firstAt) < (Q.follow_hours || 24) * 3600e3;
        const hit = triggers(b, Q);
        log.read.push(`${b.title} ${b.eventId} 震度${b.maxInt || "-"} ${b.warn || ""} → ${hit ? "対象" : follow ? "続報" : "対象外"}`);
        if (!b.eventId || (!hit && !follow)) continue;
        const e = ev || { firstAt: now.toISOString(), urls: [], dispatches: 0 };
        e.urls = [...e.urls.filter((u) => u !== it.url), it.url].slice(-12);
        e.pending = true;
        e.maxInt = (RANK[b.maxInt] || 0) > (RANK[e.maxInt] || 0) ? b.maxInt : e.maxInt || b.maxInt;
        e.warn = b.warn || e.warn || "";
        e.lastAt = b.reportAt;
        e.publishedAt ||= b.reportAt;
        e.detectedAt ||= now.toISOString();
        st.events[b.eventId] = e;
      }
    }
  }

  // 起動したのに結果（state/fast_lane.json）が無いまま12分たったら、起動し直す（最大3回。安全の情報なので取りこぼさない）
  const waitingAck = Object.entries(st.events).filter(([, e]) => e.dispatchedAt && !e.pending && !e.acked);
  if (waitingAck.length && !dry) {
    try {
      const acks = await readAcks(gh, env, fetchImpl, now);
      for (const [id, e] of waitingAck) {
        const a = acks[`quake-${id}`];
        if (a && Date.parse(a.finishedAt || 0) >= Date.parse(e.dispatchedAt) - 60000 && a.outcome !== "retry") {
          e.acked = true;
        } else if (now - Date.parse(e.dispatchedAt) >= 12 * 60000) {
          if ((e.dispatches || 0) < 3) e.pending = true;
          else e.acked = true; // 諦める（朝の見逃しチェックで知らせる）
        } else continue;
        dirty = true;
      }
    } catch (err) {
      log.ackError = String(err).slice(0, 80);
    }
  }

  // 2. 起動（1回に1件。GitHub は同じ concurrency group の待機を1つしか持てないため）
  const pending = Object.entries(st.events).filter(([, e]) => e.pending);
  if (pending.length) {
    const day = jstDate(now);
    const [eventId, e] = pending.sort((a, b) => (RANK[b[1].maxInt] || 0) - (RANK[a[1].maxInt] || 0))[0];
    let skip = "";
    if ((st.daily[day] || 0) >= (Q.daily_max || 20)) skip = `1日の上限 ${Q.daily_max}`;
    if (!skip && !dry) {
      // 同じ地震の実行が待機中なら、その実行が始まるときに feed を読み直すので重ねない
      const runs = (await gh(`/actions/workflows/${env.WORKFLOW}/runs?per_page=20`)).workflow_runs || [];
      const waiting = runs.find((r) => WAITING.has(r.status) && (r.display_title || "").startsWith(RUN_PREFIX) && (r.display_title || "").includes("data.jma.go.jp"));
      if (waiting) skip = `地震の実行が待機中（#${waiting.run_number}）`;
    }
    if (skip) {
      log.skip = skip;
      if (skip.startsWith("1日")) e.pending = false;
    } else {
      const url = e.urls[e.urls.length - 1];
      const meta = [{
        id: `quake-${eventId}`, url, urls: e.urls, eventId, source: "jma-quake", genre: "disaster",
        title: `地震・津波の情報（EventID ${eventId}）`, publishedAt: e.publishedAt, detectedAt: e.detectedAt,
      }];
      if (!dry) {
        await gh(`/actions/workflows/${env.WORKFLOW}/dispatches`, {
          method: "POST",
          body: JSON.stringify({ ref: "main", inputs: { mode: "web", fast_url: url, fast_meta: JSON.stringify(meta) } }),
        });
        st.daily[day] = (st.daily[day] || 0) + 1;
      }
      Object.assign(e, { pending: false, acked: false, dispatchedAt: now.toISOString(), dispatches: (e.dispatches || 0) + 1 });
      log.dispatched.push(`${eventId} 震度${e.maxInt || "-"} ${e.warn}`);
    }
    dirty = true;
  }

  // 3. 古い記録を消す
  for (const [id, e] of Object.entries(st.events)) {
    if (now - Date.parse(e.firstAt) > 72 * 3600e3) {
      delete st.events[id];
      dirty = true;
    }
  }
  for (const d of Object.keys(st.daily)) {
    if (d < jstDate(new Date(now.getTime() - 7 * 86400e3))) delete st.daily[d];
  }
  if (dirty) await env.FAST.put("quake", JSON.stringify(st));
  return log;
}
