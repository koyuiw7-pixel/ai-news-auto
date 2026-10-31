import test from 'node:test';
import assert from 'node:assert/strict';
import { bufferMonitorWatchdog, BUFFER_MONITOR_LAST_ATTEMPT } from '../src/buffer-monitor.js';

const NOW = new Date('2026-10-31T03:00:00Z');
function harness(options = {}) {
  const calls = { reads: [], writes: [], gh: [] };
  const state = { runs: options.runs ?? [{ status: 'completed', created_at: '2026-10-31T02:00:00Z' }], last: options.last ?? null };
  const env = {
    BUFFER_MONITOR_WATCHDOG_ENABLED: '1', BUFFER_MONITOR_WATCHDOG_DRY_RUN: options.dry ? '1' : '0',
    FAST: {
      async get(key) { calls.reads.push(key); if (options.badGet) throw new Error('private'); return state.last; },
      async put(key, value, opts) { calls.writes.push({key, value:JSON.parse(value), opts}); if (options.badPut) throw new Error('private'); state.last=JSON.parse(value); },
    },
  };
  const gh = async (path, init = {}) => {
    calls.gh.push({path, method:init.method || 'GET', body:init.body});
    if (options.badGh || (options.badDispatch && init.method === 'POST')) throw new Error('private diagnostic');
    if (init.method === 'POST') return null;
    return { workflow_runs: state.runs };
  };
  return { calls, state, env, run: (now = NOW, extra={}) => bufferMonitorWatchdog({...env,...extra}, now, {gh}) };
}

test('disabled leaves all services untouched', async () => {
  const h=harness(); assert.equal((await h.run(NOW,{BUFFER_MONITOR_WATCHDOG_ENABLED:'0'})).skip,'disabled');
  assert.deepEqual(h.calls,{reads:[],writes:[],gh:[]});
});
test('recent, active and exact time boundary', async () => {
  const h=harness({runs:[{status:'completed',created_at:'2026-10-31T02:26:00Z'}]});
  assert.equal((await h.run()).skip,'recent-run');
  h.state.runs=[{status:'in_progress',created_at:'2026-10-31T02:59:00Z'}];
  assert.equal((await h.run()).skip,'workflow-active');
  h.state.runs=[{status:'queued',created_at:'2026-10-31T02:39:00Z'}];
  assert.equal((await h.run()).error,'workflow-stuck');
  assert.equal(h.calls.gh.filter(x=>x.method==='POST').length,0);
  h.state.runs=[{status:'completed',created_at:'2026-10-31T02:25:00Z'}];
  assert.equal((await h.run()).dispatched,true);
});
test('dry mode makes no writes or dispatch', async () => {
  const h=harness({dry:true}); const r=await h.run();
  assert.equal(r.wouldDispatch,true); assert.equal(h.calls.writes.length,0);
  assert.equal(h.calls.gh.filter(x=>x.method==='POST').length,0);
});
test('stale monitor dispatch only, no SNS or Buffer mutations, cooldown', async () => {
  const h=harness(); const r=await h.run(); assert.equal(r.dispatched,true);
  assert.equal(h.calls.writes.length,1); assert.equal(h.calls.writes[0].key, BUFFER_MONITOR_LAST_ATTEMPT);
  assert.equal(h.calls.gh.length,2); assert.equal(h.calls.gh[1].path,'/actions/workflows/buffer_delivery_monitor.yml/dispatches');
  assert.deepEqual(JSON.parse(h.calls.gh[1].body), {ref:'main'});
  assert.equal((await h.run(new Date(NOW.getTime()+10*60000))).skip,'attempt-cooldown');
  assert.equal(h.calls.gh.filter(x=>x.method==='POST').length,1);
});
test('unknown dispatch retains reservation and prevents rapid retry', async () => {
  const h=harness({badDispatch:true}); assert.equal((await h.run()).error,'dispatch-outcome-unknown');
  assert.equal((await h.run(new Date(NOW.getTime()+10*60000))).skip,'attempt-cooldown');
  assert.equal(h.calls.gh.filter(x=>x.method==='POST').length,1);
});
test('unavailable run list, malformed history and future clock fail closed', async () => {
  for (const opts of [{badGh:true},{runs:[]},{runs:[{status:'completed',created_at:'invalid'}]}, {runs:[{status:'completed',created_at:'2026-10-31T03:03:00Z'}]}]) {
    const h=harness(opts); assert.equal((await h.run()).error,'run-state-unavailable');
    assert.equal(h.calls.writes.length,0); assert.equal(h.calls.gh.filter(x=>x.method==='POST').length,0);
  }
});
test('KV read or write failures and malformed state do not dispatch', async () => {
  for(const opts of [{badGet:true},{badPut:true},{last:{version:1,at:'invalid'}}]) {
    const h=harness(opts); const r=await h.run(); assert.ok(r.error);
    assert.equal(h.calls.gh.filter(x=>x.method==='POST').length,0);
  }
});
test('invalid clock or missing KV fails before operations', async () => {
  const h=harness(); assert.equal((await h.run(new Date('invalid'))).error,'invalid-clock');
  assert.equal((await h.run(NOW,{FAST:null})).error,'kv-unavailable');
  assert.deepEqual(h.calls,{reads:[],writes:[],gh:[]});
});
