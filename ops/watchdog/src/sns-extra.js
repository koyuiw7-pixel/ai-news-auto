/**
 * 朝まとめ・火金の問いかけの起動補助。SNS API にはアクセスしない。
 * 専用 Cron から呼び、速報・地震の実行時間と KV の記録を分離する。
 * KV は分散ロックではない。二重投稿防止の最後の境界は sns-extra の
 * workflow concurrency と morning_digest.py の媒体別記録・Buffer 照合。
 */
import { makeGh } from "./fastlane.js";

export const SNS_EXTRA_PREFIX = "sns_extra:v1:";
export const SNS_EXTRA_LAST_ATTEMPT = `${SNS_EXTRA_PREFIX}last_attempt`;
const MIN_INTERVAL_MS = 20 * 60 * 1000;
const MAX_ATTEMPTS = 3;
const ACCEPTED = new Set(["accepted", "scheduled", "sending", "sent"]);
const CHANNELS = new Set(["threads", "twitter"]);

/** morning_digest.py と同じ当日窓。遅延起動でも翌日の投稿へ置き換えない。 */
export function snsSlots(now) {
  if (!(now instanceof Date) || !Number.isFinite(now.getTime())) return [];
  const jst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  const date = jst.toISOString().slice(0, 10);
  const minutes = jst.getUTCHours() * 60 + jst.getUTCMinutes();
  const slots = [];
  // 昼の枠が始まったら、その期限がある問いかけを先に確認する。
  if ([2, 5].includes(jst.getUTCDay()) && minutes >= 11 * 60 && minutes < 20 * 60) {
    slots.push({ kind: "poll", date });
  }
  if (minutes >= 6 * 60 + 30 && minutes < 18 * 60) slots.push({ kind: "digest", date });
  return slots;
}

function object(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** 「受理済み」判定。公開成功の証明ではなく、再作成を止めるための記録。 */
export function snsAccepted(entry) {
  if (!object(entry)) return false;
  const expected = entry.expectedChannels === undefined ? ["threads", "twitter"] : entry.expectedChannels;
  if (!Array.isArray(expected) || !expected.includes("threads") ||
      expected.some((channel) => !CHANNELS.has(channel))) return false;
  if (entry.delivery !== undefined && !object(entry.delivery)) return false;
  return expected.every((channel) => {
    const id = channel === "threads" ? entry.id : entry.channels?.twitter;
    if (typeof id !== "string" || !id.trim()) return false;
    const delivery = entry.delivery?.[channel];
    // 旧形式は受理時にだけ ID を記録していた。不明な新形式は完了にしない。
    return entry.delivery === undefined || (object(delivery) && ACCEPTED.has(delivery.status));
  });
}

function validReservation(value) {
  return object(value) && value.version === 1 &&
    Number.isInteger(value.attempts) && value.attempts >= 1 &&
    typeof value.lastAttemptAt === "string" && Number.isFinite(Date.parse(value.lastAttemptAt));
}

function stateKey(kind, date) {
  // Python の既存履歴は compact date。KV は読みやすい ISO date で別管理。
  return `${kind}-${date.replaceAll("-", "")}`;
}

function otherKindNearSlot(state, slot, now) {
  const otherKind = slot.kind === "digest" ? "poll" : "digest";
  const key = stateKey(otherKind, slot.date);
  const entry = state.posted[key] || state.extraPending?.[key];
  if (!object(entry)) return false;
  return ["postedAt", "dueAt"].some((field) => {
    const stamp = typeof entry[field] === "string" ? Date.parse(entry[field]) : NaN;
    const gap = now.getTime() - stamp;
    // dueAt は直後に予定された別投稿も確認する。受付時刻の未来値は扱わない。
    return Number.isFinite(stamp) && gap < MIN_INTERVAL_MS &&
      (gap >= 0 || (field === "dueAt" && gap > -MIN_INTERVAL_MS));
  });
}

/**
 * env: SNS_EXTRA_ENABLED=1 のときだけ有効。SNS_EXTRA_DRY_RUN=1 は読み取りのみ。
 * deps.gh はテスト用。同じ GH_TOKEN を使うが Contents と Actions のみに限定。
 * 受理不明の dispatch も上限に数えるため、POST 前に専用 KV を保存する。
 */
export async function snsExtra(env, now = new Date(), deps = {}) {
  const dry = env.SNS_EXTRA_DRY_RUN === "1";
  const log = { dry, decisions: [], dispatched: null };
  if (env.SNS_EXTRA_ENABLED !== "1") return { ...log, skip: "disabled" };
  const slots = snsSlots(now);
  if (!slots.length) return { ...log, skip: "outside-window" };
  if (!env.FAST?.get || !env.FAST?.put) return { ...log, error: "kv-unavailable" };

  const gh = deps.gh || makeGh(env, (url, init = {}) => fetch(url, {
    ...init, signal: AbortSignal.timeout(15000),
  }));
  let state;
  try {
    const raw = await gh("/contents/state/threads_posted.json?ref=main", {
      raw: true, headers: { Accept: "application/vnd.github.raw+json" },
    });
    state = typeof raw === "string" ? JSON.parse(raw) : null;
    if (!object(state) || !object(state.posted) ||
        (state.extraPending !== undefined && !object(state.extraPending))) throw new Error("invalid state");
  } catch {
    // 記録が読めないことを「まだ投稿されていない」と解釈しない。
    return { ...log, error: "posting-state-unavailable" };
  }

  const pending = [];
  for (const slot of slots) {
    const key = stateKey(slot.kind, slot.date);
    const kvKey = `${SNS_EXTRA_PREFIX}${slot.kind}-${slot.date}`;
    if (snsAccepted(state.posted[key])) {
      log.decisions.push({ ...slot, skip: "accepted" });
      continue;
    }
    if (otherKindNearSlot(state, slot, now)) {
      log.decisions.push({ ...slot, skip: "other-kind-spacing" });
      continue;
    }
    let reservation;
    try {
      reservation = await env.FAST.get(kvKey, "json");
      if (reservation !== null && reservation !== undefined && !validReservation(reservation)) {
        throw new Error("invalid reservation");
      }
    } catch {
      log.decisions.push({ ...slot, error: "dispatch-state-unavailable" });
      continue;
    }
    if (reservation?.attempts >= MAX_ATTEMPTS) {
      log.decisions.push({ ...slot, skip: "daily-limit", attempts: reservation.attempts });
      continue;
    }
    if (reservation && now.getTime() - Date.parse(reservation.lastAttemptAt) < MIN_INTERVAL_MS) {
      log.decisions.push({ ...slot, skip: "cooldown", attempts: reservation.attempts });
      continue;
    }
    pending.push({ ...slot, kvKey, reservation });
  }
  if (!pending.length) return log;

  try {
    const last = await env.FAST.get(SNS_EXTRA_LAST_ATTEMPT, "json");
    if (last !== null && last !== undefined && !validReservation(last)) throw new Error("invalid last attempt");
    if (last && now.getTime() - Date.parse(last.lastAttemptAt) < MIN_INTERVAL_MS) {
      return { ...log, skip: "global-cooldown" };
    }
  } catch {
    return { ...log, error: "global-dispatch-state-unavailable" };
  }

  try {
    const response = await gh("/actions/workflows/sns_extra.yml/runs?branch=main&per_page=50");
    if (!object(response) || !Array.isArray(response.workflow_runs) ||
        response.workflow_runs.some((run) => !object(run) || typeof run.status !== "string")) {
      throw new Error("invalid runs");
    }
    // queued/in_progress だけでなく waiting/requested 等も起動中として扱う。
    if (response.workflow_runs.some((run) => run.status !== "completed")) {
      return { ...log, skip: "workflow-active" };
    }
  } catch {
    return { ...log, error: "workflow-state-unavailable" };
  }

  // 同じ concurrency group に2つ続けて積まない。次の Cron で不足分を再確認。
  const slot = pending[0];
  const inputs = { kind: slot.kind, date: slot.date, test: "false" };
  if (dry) return { ...log, wouldDispatch: inputs };
  const reservation = {
    version: 1,
    attempts: (slot.reservation?.attempts || 0) + 1,
    lastAttemptAt: now.toISOString(),
    outcome: "dispatch-outcome-unknown",
  };
  try {
    await env.FAST.put(slot.kvKey, JSON.stringify(reservation), { expirationTtl: 7 * 86400 });
    await env.FAST.put(SNS_EXTRA_LAST_ATTEMPT, JSON.stringify({ ...reservation, kind: slot.kind, date: slot.date }), {
      expirationTtl: 7 * 86400,
    });
  } catch {
    return { ...log, error: "dispatch-state-write-failed" };
  }
  try {
    await gh("/actions/workflows/sns_extra.yml/dispatches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main", inputs }),
    });
  } catch {
    // タイムアウト時も受理された可能性がある。記録・回数を戻さない。
    return { ...log, error: "dispatch-outcome-unknown", attempted: inputs, attempts: reservation.attempts };
  }
  return { ...log, dispatched: inputs, attempts: reservation.attempts };
}
