/**
 * Buffer監視を見張る独立した補助経路。SNS・Bufferへの投稿や予約は一切操作しない。
 * 既存の10分Cronから別waitUntilで起動し、監視runが35分以上始まっていなければ
 * 読み取り専用workflowを起動する。KVは分散ロックではないため最終防御はworkflow concurrency。
 */
import { makeGh } from './fastlane.js';

export const BUFFER_MONITOR_LAST_ATTEMPT = 'buffer_monitor_watchdog:v1:last_attempt';
const INTERVAL_MS = 35 * 60 * 1000;
const FUTURE_TOLERANCE_MS = 2 * 60 * 1000;
const WORKFLOW = 'buffer_delivery_monitor.yml';

export async function bufferMonitorWatchdog(env, now = new Date(), deps = {}) {
  const dry = env.BUFFER_MONITOR_WATCHDOG_DRY_RUN === '1';
  if (env.BUFFER_MONITOR_WATCHDOG_ENABLED !== '1') return { dry, skip: 'disabled' };
  if (!(now instanceof Date) || !Number.isFinite(now.getTime())) return { dry, error: 'invalid-clock' };
  if (!env.FAST?.get || !env.FAST?.put) return { dry, error: 'kv-unavailable' };
  // 一度限りの本番復旧試験。期限を過ぎれば自動的に通常の35分へ戻る。
  const probeUntil = Date.parse(env.BUFFER_MONITOR_PROBE_UNTIL || '');
  const remaining = probeUntil - now.getTime();
  const probe = Number.isFinite(probeUntil) && remaining >= 0 && remaining <= 15 * 60 * 1000;
  const interval = probe ? 60 * 1000 : INTERVAL_MS;
  const gh = deps.gh || makeGh(env, (url, init = {}) => fetch(url, {
    ...init, signal: AbortSignal.timeout(15000),
  }));
  let runs;
  try {
    const result = await gh(`/actions/workflows/${WORKFLOW}/runs?branch=main&per_page=20`);
    if (!result || !Array.isArray(result.workflow_runs) || !result.workflow_runs.length) throw new Error('invalid runs');
    runs = result.workflow_runs;
    if (runs.some(run => !run || typeof run.status !== 'string' ||
      !Number.isFinite(Date.parse(run.created_at)) || Date.parse(run.created_at) > now.getTime() + FUTURE_TOLERANCE_MS)) {
      throw new Error('invalid run data');
    }
  } catch {
    return { dry, error: 'run-state-unavailable' };
  }
  const active = runs.filter(run => run.status !== 'completed');
  if (active.length) {
    const oldest = Math.min(...active.map(run => Date.parse(run.created_at)));
    const activeMinutes = Math.max(0, Math.floor((now.getTime() - oldest) / 60000));
    if (activeMinutes >= 20) return { dry, error: 'workflow-stuck', activeMinutes };
    return { dry, skip: 'workflow-active', activeMinutes };
  }
  const lastStart = Math.max(...runs.map(run => Date.parse(run.created_at)));
  const minutesSince = Math.max(0, Math.floor((now.getTime() - lastStart) / 60000));
  if (now.getTime() - lastStart < interval) return { dry, skip: 'recent-run', minutesSince };
  let last;
  try {
    last = await env.FAST.get(BUFFER_MONITOR_LAST_ATTEMPT, 'json');
    if (last !== null && last !== undefined &&
      (last.version !== 1 || typeof last.at !== 'string' || !Number.isFinite(Date.parse(last.at)))) throw new Error('invalid kv');
    if (last && now.getTime() - Date.parse(last.at) < interval) return { dry, skip: 'attempt-cooldown', minutesSince };
  } catch {
    return { dry, error: 'dispatch-state-unavailable' };
  }
  if (dry) return { dry, wouldDispatch: true, minutesSince };
  try {
    await env.FAST.put(BUFFER_MONITOR_LAST_ATTEMPT, JSON.stringify({ version: 1, at: now.toISOString() }), {
      expirationTtl: 2 * 60 * 60,
    });
  } catch {
    return { dry, error: 'dispatch-state-write-failed' };
  }
  try {
    await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ref: 'main' }),
    });
  } catch {
    // HTTPタイムアウトでも起動済みの可能性があるため、KVを消さず次の期間まで待つ。
    return { dry, error: 'dispatch-outcome-unknown', minutesSince };
  }
  return { dry, dispatched: true, minutesSince, probe };
}
