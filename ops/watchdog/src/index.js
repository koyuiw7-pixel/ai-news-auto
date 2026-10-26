/**
 * サイソクの見張り番（Cloudflare Workers の Cron Triggers で10分ごとに動く）
 *
 * 1. GitHub Actions の記事作り（auto_run.yml）が START_GAP_MIN 分以上始まっていなければ、自分で起動する
 *    - 6時間ごとの枠（UTC 0/6/12/18時台の最初）に当たらなければ mode=web（軽い回）
 * 2. 成功した回が ALERT_GAP_MIN 分以上無ければ、GitHub に Issue を立ててオーナーにメールで知らせる
 *    （すでに開いている知らせがあれば重ねて立てない。回復したら自動で閉じる）
 *
 * 必要な秘密情報: GH_TOKEN（このリポジトリの Actions の読み書きと Issues の書き込みだけを許可した細かい権限のトークン）
 */
const ALERT_TITLE = "【自動通知】記事の自動作成が止まっています";

async function gh(env, path, init = {}) {
  const res = await fetch(`https://api.github.com/repos/${env.REPO}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "saisoku-watchdog",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init.headers || {}),
    },
  });
  if (!res.ok && res.status !== 204) throw new Error(`GitHub ${path} -> ${res.status} ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

async function check(env, now = new Date()) {
  const runs = (await gh(env, `/actions/workflows/${env.WORKFLOW}/runs?per_page=20`)).workflow_runs || [];
  const minutesSince = (iso) => (now - new Date(iso)) / 60000;
  const latestStart = runs[0] ? minutesSince(runs[0].created_at) : Infinity;
  const active = runs.some((r) => r.status === "queued" || r.status === "in_progress");
  const lastSuccess = runs.find((r) => r.conclusion === "success");
  const sinceSuccess = lastSuccess ? minutesSince(lastSuccess.updated_at) : Infinity;
  const log = { latestStart: Math.round(latestStart), active, sinceSuccess: Math.round(sinceSuccess) };

  // 1. 起動
  if (!active && latestStart >= Number(env.START_GAP_MIN)) {
    // 6時間ごとの重い回は、UTC 0/6/12/18時台の最初の30分だけ
    const full = now.getUTCHours() % 6 === 0 && now.getUTCMinutes() < 30;
    await gh(env, `/actions/workflows/${env.WORKFLOW}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: "main", inputs: { mode: full ? "full" : "web" } }),
    });
    log.dispatched = full ? "full" : "web";
  }

  // 2. 知らせる／回復したら閉じる
  const open = (await gh(env, `/issues?state=open&labels=watchdog&per_page=5`)) || [];
  if (sinceSuccess >= Number(env.ALERT_GAP_MIN)) {
    if (open.length === 0) {
      await gh(env, `/issues`, {
        method: "POST",
        body: JSON.stringify({
          title: ALERT_TITLE,
          labels: ["watchdog"],
          body:
            `最後に記事作りが成功してから約${Math.round(sinceSuccess)}分たっています。\n\n` +
            `見張り番が自動で起動を試みていますが、成功していません。` +
            `GitHub の Actions 画面で失敗の内容を確認してください。\n\n` +
            `https://github.com/${env.REPO}/actions/workflows/${env.WORKFLOW}`,
        }),
      });
      log.alert = "opened";
    }
  } else {
    for (const issue of open) {
      await gh(env, `/issues/${issue.number}/comments`, {
        method: "POST",
        body: JSON.stringify({ body: "記事作りが再開したので、この知らせを閉じます。" }),
      });
      await gh(env, `/issues/${issue.number}`, { method: "PATCH", body: JSON.stringify({ state: "closed" }) });
      log.alert = "closed";
    }
  }
  return log;
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(check(env).then((l) => console.log(JSON.stringify(l))).catch((e) => console.error(String(e))));
  },
  // 動作確認用（中身は見せない）
  async fetch(_req, env) {
    try {
      const l = await check(env);
      return new Response(JSON.stringify(l), { headers: { "content-type": "application/json" } });
    } catch (e) {
      return new Response("error", { status: 500 });
    }
  },
};
