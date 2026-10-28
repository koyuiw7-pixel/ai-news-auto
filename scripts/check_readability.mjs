#!/usr/bin/env node
/**
 * 文字の読みやすさを実ページで機械チェックする（ルールは docs/typography.md）。
 *
 * 使い方:
 *   npm run check:readability                         # 本番 https://ai-tech-express.jp
 *   npm run check:readability -- --base http://localhost:3100
 *   npm run check:readability -- --paths /,/products --shots out/readability/shots [--full]
 *   npm run check:readability -- --json out/readability/report.json
 *
 * 375px / 1440px × ライト / ダーク で主要ページを開き、見えている文字を全部調べる。
 *   - 文字サイズ 13px 未満（data-allow-small の中だけ 12px まで可）
 *   - 太さ 400 未満
 *   - コントラスト比 4.5:1 未満（WCAG 2.2 AA。背景は親をたどって合成して求める）
 *   - 段落（本文・説明文）が 16px 未満、またはコントラスト比 7:1 未満
 *   - 記事本文（.prose の段落）が 16px 未満（1440px では 17px 未満）、またはコントラスト比 10:1 未満
 * 違反があれば終了コード 1。依存パッケージなし（Chrome を DevTools プロトコルで直接操作する）。
 */
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join } from "node:path";

// ---------------------------------------------------------------------------
// ルール（docs/typography.md と同じ数字）
// ---------------------------------------------------------------------------
export const RULES = {
  minSize: 13, // どんな文字も 13px 以上
  badgeMinSize: 12, // バッジ（.text-badge / .eyebrow / data-allow-small）だけ 12px まで
  badgeSelector: ".text-badge, .eyebrow, [data-allow-small]",
  minWeight: 400, // 細字（300 以下）は使わない
  minContrast: 4.5, // WCAG 2.2 AA
  // 説明文・リード・段落（40字以上の細字の文章）。注記（.text-note）と密な表（data-dense）は 14px まで
  paragraph: { minChars: 40, minSize: 16, noteMinSize: 14, noteSelector: ".text-note, [data-dense]", minContrast: 7 },
  prose: { minSize: 16, minSizeWide: 17, wideFrom: 768, minContrast: 10 }, // 記事本文
  // 見出し。自信のある見え方＝本文との大きさの差をはっきり付ける
  heading: {
    wideFrom: 1024,
    h1: { minSize: 28, minSizeWide: 36, minWeight: 700, minContrast: 7, ratio: 1.8, ratioWide: 2.5 },
    h2: { minSize: 20, minWeight: 700, minContrast: 7, ratio: 1.35 },
    h3: { minSize: 17, minWeight: 700 }, // 一覧の題名・小見出し
  },
};

const DEFAULT_BASE = "https://ai-tech-express.jp";
const DEFAULT_PATHS = [
  "/",
  "/news",
  "/articles",
  "@article", // /articles の先頭の記事
  "/products",
  "@product", // /products の先頭の製品
  "/usable",
  "/companies/openai",
  "/ai-pricing",
  "/about",
];
const VIEWPORTS = [
  { name: "375", width: 375, height: 812, mobile: true, dpr: 2 },
  { name: "1440", width: 1440, height: 900, mobile: false, dpr: 1 },
];
const THEMES = ["light", "dark"];

// ---------------------------------------------------------------------------
// 引数
// ---------------------------------------------------------------------------
function parseArgs(argv) {
  const args = { base: DEFAULT_BASE, paths: DEFAULT_PATHS, json: "", shots: "", full: false, viewports: "", themes: "", limit: 25 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === "--base") args.base = next().replace(/\/$/, "");
    else if (a === "--paths") args.paths = next().split(",").map((s) => s.trim()).filter(Boolean);
    else if (a === "--json") args.json = next();
    else if (a === "--shots") args.shots = next();
    else if (a === "--full") args.full = true;
    else if (a === "--viewports") args.viewports = next();
    else if (a === "--themes") args.themes = next();
    else if (a === "--limit") args.limit = Number(next());
    else if (a === "-h" || a === "--help") {
      console.log(readFileSync(new URL(import.meta.url), "utf8").split("\n").slice(1, 20).join("\n"));
      process.exit(0);
    }
  }
  return args;
}

// ---------------------------------------------------------------------------
// Chrome を起動して DevTools プロトコルでつなぐ
// ---------------------------------------------------------------------------
// 広告・提携リンクの計測先には一切つながない（本番を開くと ASP の表示回数・クリック数が機械で水増しされる）。
// ブラウザ全体で名前解決させないので、新しいタブ・ポップアップでも届かない。ルールは docs/automation.md
const BLOCKED_HOSTS = [
  "a8.net",
  "*.a8.net",
  "*.afl.rakuten.co.jp",
  "*.amazon-adsystem.com",
  "*.googlesyndication.com",
  "*.doubleclick.net",
  "*.googleadservices.com",
  "adservice.google.com",
  "*.adtrafficquality.google",
];
const BLOCK_FLAG = `--host-resolver-rules=${BLOCKED_HOSTS.map((h) => `MAP ${h} ~NOTFOUND`).join(", ")}`;
// 1枚のタブの中でも念のため止める（Network.setBlockedURLs のパターン）
const BLOCKED_URLS = BLOCKED_HOSTS.map((h) => `*://${h}/*`);

function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const candidates = [
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ];
  // puppeteer が入れた headless shell（ローカル開発機）
  const cache = join(homedir(), ".cache/puppeteer/chrome-headless-shell");
  if (existsSync(cache)) {
    for (const v of readdirSafe(cache).sort().reverse()) {
      for (const arch of readdirSafe(join(cache, v))) {
        candidates.unshift(join(cache, v, arch, "chrome-headless-shell"));
      }
    }
  }
  const found = candidates.find((p) => existsSync(p));
  if (!found) throw new Error("Chrome が見つかりません。CHROME_PATH で指定してください");
  return found;
}

function readdirSafe(dir) {
  try {
    return readdirSync(dir);
  } catch {
    return [];
  }
}

async function launchChrome() {
  const userDataDir = mkdtempSync(join(tmpdir(), "readability-"));
  const bin = findChrome();
  const proc = spawn(
    bin,
    [
      "--headless=new",
      "--remote-debugging-port=0",
      `--user-data-dir=${userDataDir}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-gpu",
      "--hide-scrollbars",
      // 裏のタブ扱いでタイマーが間引かれると、スクロール待ちが何分も止まる（CI の Chrome で起きた）
      "--disable-background-timer-throttling",
      "--disable-renderer-backgrounding",
      "--disable-backgrounding-occluded-windows",
      "--font-render-hinting=none",
      BLOCK_FLAG,
      ...(process.env.CI ? ["--no-sandbox"] : []),
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  // DevToolsActivePort にポートが書かれるのを待つ
  const portFile = join(userDataDir, "DevToolsActivePort");
  for (let i = 0; i < 200 && !existsSync(portFile); i++) await sleep(50);
  if (!existsSync(portFile)) throw new Error(`Chrome を起動できませんでした: ${bin}`);
  const [port] = readFileSync(portFile, "utf8").split("\n");
  const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
  const cdp = await connect(version.webSocketDebuggerUrl);
  const close = async () => {
    try {
      await cdp.send("Browser.close");
    } catch {}
    proc.kill();
    await sleep(200);
    rmSync(userDataDir, { recursive: true, force: true });
  };
  return { cdp, close };
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    let id = 0;
    const pending = new Map();
    const listeners = new Set();
    ws.onopen = () =>
      resolve({
        send(method, params = {}, sessionId) {
          const msg = { id: ++id, method, params };
          if (sessionId) msg.sessionId = sessionId;
          ws.send(JSON.stringify(msg));
          // 応答の無いコマンドで止まらないよう 90 秒で打ち切る（そのページは ERR として記録）
          return new Promise((res, rej) => {
            const timer = setTimeout(() => {
              pending.delete(msg.id);
              rej(new Error(`${method}: 90 秒で応答なし`));
            }, 90_000);
            pending.set(msg.id, {
              res: (v) => (clearTimeout(timer), res(v)),
              rej: (e) => (clearTimeout(timer), rej(e)),
              method,
            });
          });
        },
        on(fn) {
          listeners.add(fn);
          return () => listeners.delete(fn);
        },
      });
    ws.onerror = (e) => reject(e);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) {
        const p = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) p.rej(new Error(`${p.method}: ${msg.error.message}`));
        else p.res(msg.result);
      } else {
        for (const fn of listeners) fn(msg);
      }
    };
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function openPage(cdp, { viewport, theme }) {
  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  const send = (m, p) => cdp.send(m, p, sessionId);
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Network.enable");
  await send("Network.setBlockedURLs", { urls: BLOCKED_URLS }).catch(() => {});
  await send("Page.bringToFront");
  await send("Emulation.setFocusEmulationEnabled", { enabled: true });
  await send("Emulation.setDeviceMetricsOverride", {
    width: viewport.width,
    height: viewport.height,
    deviceScaleFactor: viewport.dpr,
    mobile: viewport.mobile,
  });
  // テーマは右上のボタン（localStorage）で決まる。OS 設定も合わせておく
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
  await send("Page.addScriptToEvaluateOnNewDocument", {
    source: `try{localStorage.setItem("theme",${JSON.stringify(theme)})}catch(e){}`,
  });
  const waitLoad = () =>
    new Promise((resolve) => {
      const off = cdp.on((msg) => {
        if (msg.sessionId === sessionId && msg.method === "Page.loadEventFired") {
          off();
          resolve();
        }
      });
      setTimeout(() => {
        off();
        resolve();
      }, 30000);
    });
  return {
    async goto(url) {
      const loaded = waitLoad();
      const res = await send("Page.navigate", { url });
      if (res.errorText) throw new Error(`${url}: ${res.errorText}`);
      await loaded;
      // 遅延読み込みとウェブフォントを待つ
      await this.eval(`(async () => {
        const h = document.documentElement.scrollHeight;
        for (let y = 0; y < h; y += innerHeight) { scrollTo({ top: y, behavior: "instant" }); await new Promise(r => setTimeout(r, 40)); }
        scrollTo({ top: 0, behavior: "instant" });
        await document.fonts.ready;
        await new Promise(r => setTimeout(r, 300));
      })()`);
    },
    async eval(expression) {
      const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
      return r.result.value;
    },
    async screenshot(path, full = false) {
      // full: 画面の高さをページ全体に広げて撮る（長いページは 6000px で切る）
      if (full) {
        const h = Math.min(6000, await this.eval("document.documentElement.scrollHeight"));
        await send("Emulation.setDeviceMetricsOverride", {
          width: viewport.width,
          height: h,
          deviceScaleFactor: viewport.dpr,
          mobile: viewport.mobile,
        });
        await sleep(300);
        await this.eval(`scrollTo({ top: 0, behavior: "instant" })`);
        await sleep(100);
      }
      const { data } = await send("Page.captureScreenshot", { format: "png" });
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, Buffer.from(data, "base64"));
    },
    async close() {
      await cdp.send("Target.closeTarget", { targetId });
    },
  };
}

// ---------------------------------------------------------------------------
// ページ内で走らせる検査（ブラウザ側のコード）
// ---------------------------------------------------------------------------
function inPageAudit(RULES, viewportWidth) {
  const parse = (s) => {
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (fg, bg) => {
    const a = fg.a + bg.a * (1 - fg.a);
    if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
    const mix = (c) => (fg[c] * fg.a + bg[c] * bg.a * (1 - fg.a)) / a;
    return { r: mix("r"), g: mix("g"), b: mix("b"), a };
  };
  const lum = (c) => {
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => {
    const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (l1 + 0.05) / (l2 + 0.05);
  };
  const hex = (c) => "#" + [c.r, c.g, c.b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");

  // 画像・動画の位置（画像の上に載った文字はコントラストを測れないので目視に回す）
  const media = [...document.querySelectorAll("img, picture, video, canvas")]
    .map((el) => ({ el, r: el.getBoundingClientRect() }))
    .filter((m) => m.r.width > 4 && m.r.height > 4);

  // 背景色の候補（親をたどり、不透明な色に当たるまで重ねる。グラデーションは各色を候補にする）
  function backgrounds(el) {
    const layers = [];
    let n = el;
    let reachedOpaque = false;
    while (n && n.nodeType === 1) {
      const cs = getComputedStyle(n);
      const bgc = parse(cs.backgroundColor) ?? { r: 0, g: 0, b: 0, a: 0 };
      const bgi = cs.backgroundImage;
      if (bgi && bgi !== "none") {
        if (/url\(/.test(bgi)) return { image: true };
        const stops = [...bgi.matchAll(/rgba?\([^)]+\)/g)].map((m) => parse(m[0]));
        layers.push({ solid: bgc, stops });
      } else if (bgc.a > 0) {
        layers.push({ solid: bgc, stops: [] });
        if (bgc.a >= 1) {
          reachedOpaque = true;
          break;
        }
      }
      n = n.parentElement;
    }
    let cands = [reachedOpaque ? { r: 0, g: 0, b: 0, a: 0 } : { r: 255, g: 255, b: 255, a: 1 }];
    for (let i = layers.length - 1; i >= 0; i--) {
      const L = layers[i];
      cands = cands.map((c) => over(L.solid, c.a ? c : { r: 255, g: 255, b: 255, a: 1 }));
      if (L.stops.length) {
        const next = [];
        for (const c of cands) for (const s of L.stops) next.push(over(s, c));
        cands = next.slice(0, 12);
      }
    }
    return { colors: cands };
  }

  function describe(el) {
    const parts = [];
    let n = el;
    for (let i = 0; i < 3 && n && n !== document.body; i++) {
      let s = n.tagName.toLowerCase();
      const cls = (n.getAttribute("class") || "").split(/\s+/).filter(Boolean).slice(0, 4);
      if (cls.length) s += "." + cls.join(".");
      parts.unshift(s);
      n = n.parentElement;
    }
    return parts.join(" > ");
  }

  // 段落＝本文の中で、文字を含むいちばん近いブロック。40 字以上あり、いちばん多くの字が細字のもの
  // （見出し・太字の題名は除く）。大きさと色は、そのブロックでいちばん字数の多い書式で判定する
  const blockOf = (el) => {
    if (!el.closest("main") || el.closest("nav, header, footer, h1, h2, h3, h4, h5, h6, table")) return null;
    let b = el;
    while (b && b !== document.body && /^(inline|contents)/.test(getComputedStyle(b).display)) b = b.parentElement;
    return b && b !== document.body ? b : null;
  };
  const blocks = new Map();

  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const findings = [];
  let checked = 0;
  let overImage = 0;
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const el = node.parentElement;
    if (!el || seen.has(el)) continue;
    if (!/[\p{L}\p{N}]/u.test(node.nodeValue)) continue;
    if (el.closest("script, style, noscript, template, svg, ins.adsbygoogle, [data-decorative], [role='img']")) continue;
    if (el.closest("button:disabled, input:disabled, [aria-disabled='true']")) continue;
    seen.add(el);
    if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const rect = range.getBoundingClientRect();
    if (rect.width <= 1 || rect.height <= 1) continue;
    const cs = getComputedStyle(el);
    // 画面外に追いやった読み上げ専用の文字（sr-only）は対象外
    if (cs.clip === "rect(0px, 0px, 0px, 0px)" || (cs.position === "absolute" && rect.width <= 1)) continue;
    checked++;

    const size = parseFloat(cs.fontSize);
    const weight = Number(cs.fontWeight) || 400;
    const text = (el.innerText || node.nodeValue).replace(/\s+/g, " ").trim().slice(0, 40);
    const base = { text, size, weight, where: describe(el) };
    const issues = [];

    const allowSmall = !!el.closest(RULES.badgeSelector);
    const minSize = allowSmall ? RULES.badgeMinSize : RULES.minSize;
    if (size < minSize - 0.01) issues.push({ rule: "size", need: minSize });
    if (weight < RULES.minWeight) issues.push({ rule: "weight", need: RULES.minWeight });

    // コントラスト
    let fg = parse(cs.webkitTextFillColor && cs.webkitTextFillColor !== cs.color ? cs.webkitTextFillColor : cs.color);
    let contrast = null;
    let bgHex = "";
    const onImage = media.some(
      (m) =>
        !el.contains(m.el) &&
        m.r.left < rect.right && m.r.right > rect.left && m.r.top < rect.bottom && m.r.bottom > rect.top,
    );
    const bgs = onImage ? { image: true } : backgrounds(el);
    if (bgs.image) {
      overImage++;
    } else if (fg && fg.a > 0) {
      // 親の opacity は文字色の透明度として扱う
      let op = 1;
      for (let n = el; n && n.nodeType === 1; n = n.parentElement) op *= Number(getComputedStyle(n).opacity);
      fg = { ...fg, a: fg.a * op };
      let worst = Infinity;
      for (const bg of bgs.colors) {
        const r = ratio(over(fg, bg), bg);
        if (r < worst) {
          worst = r;
          bgHex = hex(bg);
        }
      }
      contrast = Math.round(worst * 100) / 100;
      if (contrast < RULES.minContrast) issues.push({ rule: "contrast", need: RULES.minContrast });
    }

    for (const i of issues) {
      findings.push({ ...base, ...i, contrast, color: fg ? hex(fg) : "", bg: bgHex });
    }

    // 段落の集計（この要素の直下の字数で重み付け）
    const blk = blockOf(el);
    if (blk) {
      const chars = [...el.childNodes]
        .filter((n) => n.nodeType === 3)
        .reduce((a, n) => a + n.nodeValue.replace(/\s+/g, "").length, 0);
      const link = el.closest("a");
      // 文中のリンク（段落の中の a）は色の判定から外す。カード全体がリンクの場合は外さない
      const inlineLink = !!link && link !== blk && blk.contains(link);
      const key = `${size}|${weight}|${contrast}|${inlineLink}`;
      const entry = blocks.get(blk) ?? { total: 0, keys: new Map() };
      entry.total += chars;
      const k = entry.keys.get(key) ?? { chars: 0, size, weight, contrast, inlineLink, color: fg ? hex(fg) : "", bg: bgHex };
      k.chars += chars;
      entry.keys.set(key, k);
      blocks.set(blk, entry);
    }
  }

  // 段落（説明文・記事本文）
  for (const [blk, entry] of blocks) {
    if (entry.total < RULES.paragraph.minChars) continue;
    const dom = [...entry.keys.values()].sort((a, b) => b.chars - a.chars)[0];
    if (dom.weight >= 600) continue;
    const base = {
      text: (blk.innerText || "").replace(/\s+/g, " ").trim().slice(0, 40),
      size: dom.size,
      weight: dom.weight,
      where: describe(blk),
      contrast: dom.contrast,
      color: dom.color,
      bg: dom.bg,
    };
    const prose = !!blk.closest(".prose") && !!blk.closest("p, li, dd, blockquote");
    if (prose) {
      const need = viewportWidth >= RULES.prose.wideFrom ? RULES.prose.minSizeWide : RULES.prose.minSize;
      if (dom.size < need - 0.01) findings.push({ ...base, rule: "prose-size", need });
      if (dom.contrast !== null && !dom.inlineLink && dom.contrast < RULES.prose.minContrast)
        findings.push({ ...base, rule: "prose-contrast", need: RULES.prose.minContrast });
    } else {
      const need = blk.closest(RULES.paragraph.noteSelector) ? RULES.paragraph.noteMinSize : RULES.paragraph.minSize;
      if (dom.size < need - 0.01) findings.push({ ...base, rule: "para-size", need });
      if (dom.contrast !== null && !dom.inlineLink && dom.contrast < RULES.paragraph.minContrast)
        findings.push({ ...base, rule: "para-contrast", need: RULES.paragraph.minContrast });
    }
  }

  // 見出し（本文の大きさ＝記事本文があればその段落、なければ説明文の 16px と比べる）
  const H = RULES.heading;
  const wide = viewportWidth >= H.wideFrom;
  // 記事本文の段落でいちばん多い大きさ（冒頭のリード段落など例外の大きさに引っ張られない）
  const proseSizes = [...document.querySelectorAll(".prose p")].map((p) => parseFloat(getComputedStyle(p).fontSize));
  const bodyP = proseSizes.length > 0;
  const bodySize = bodyP
    ? Number(
        Object.entries(proseSizes.reduce((m, v) => ((m[v] = (m[v] ?? 0) + 1), m), {})).sort((a, b) => b[1] - a[1])[0][0],
      )
    : 16;
  const headingBg = (el) => {
    const b = backgrounds(el);
    return b.image ? null : b.colors;
  };
  for (const h of document.querySelectorAll("main h1, main h2, main h3")) {
    if (!h.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue;
    if (h.closest("aside, nav, footer, [data-decorative]")) continue;
    const r = h.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    const cs = getComputedStyle(h);
    const size = parseFloat(cs.fontSize);
    const weight = Number(cs.fontWeight) || 400;
    const tag = h.tagName.toLowerCase();
    const R = H[tag];
    const base = { text: (h.innerText || "").replace(/\s+/g, " ").trim().slice(0, 40), size, weight, where: describe(h) };
    const issues = [];
    const minSize = tag === "h1" && wide ? R.minSizeWide : R.minSize;
    if (size < minSize - 0.01) issues.push({ rule: `${tag}-size`, need: minSize });
    if (weight < R.minWeight) issues.push({ rule: `${tag}-weight`, need: R.minWeight });
    if (R.ratio) {
      const need = tag === "h1" && wide ? R.ratioWide : R.ratio;
      const ratioNow = Math.round((size / bodySize) * 100) / 100;
      // h2 の比は記事本文の中の見出しだけ（枠の見出しは大きさの下限だけ見る）
      if (ratioNow < need - 0.005 && (tag === "h1" || (bodyP && h.closest(".prose"))))
        issues.push({ rule: `${tag}-ratio`, need: `${need}倍（今 ${ratioNow}倍・本文 ${bodySize}px）` });
    }
    let contrast = null;
    let bgHex = "";
    const fg = parse(cs.color);
    const colors = R.minContrast && fg ? headingBg(h) : null;
    if (colors) {
      contrast = Math.min(...colors.map((bg) => ratio(over(fg, bg), bg)));
      contrast = Math.round(contrast * 100) / 100;
      bgHex = hex(colors[0]);
      if (contrast < R.minContrast) issues.push({ rule: `${tag}-contrast`, need: R.minContrast });
    }
    for (const i of issues) findings.push({ ...base, ...i, contrast, color: fg ? hex(fg) : "", bg: bgHex });
  }

  // 本文の段落が実際にどの書体で描かれているか（参考）
  const sample = document.querySelector(".prose p") || document.querySelector("main p");
  const family = sample ? getComputedStyle(sample).fontFamily : "";
  return { findings, checked, overImage, family };
}

// ---------------------------------------------------------------------------
// 実行
// ---------------------------------------------------------------------------
async function discover(base, kind) {
  const listPath = kind === "@article" ? "/articles" : "/products";
  const re = kind === "@article" ? /href="(\/articles\/(?!page\/)[^"#?/]+)"/ : /href="(\/products\/[^"#?/]+)"/;
  const html = await (await fetch(base + listPath)).text();
  const m = html.match(re);
  return m ? m[1] : null;
}

function pad(s, n) {
  s = String(s);
  // 全角は2桁として数える
  const w = [...s].reduce((acc, ch) => acc + (/[^\x00-\xff]/.test(ch) ? 2 : 1), 0);
  return s + " ".repeat(Math.max(0, n - w));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const viewports = args.viewports ? VIEWPORTS.filter((v) => args.viewports.split(",").includes(v.name)) : VIEWPORTS;
  const themes = args.themes ? THEMES.filter((t) => args.themes.split(",").includes(t)) : THEMES;

  const paths = [];
  for (const p of args.paths) {
    if (p.startsWith("@")) {
      const found = await discover(args.base, p).catch(() => null);
      if (found) paths.push(found);
      else console.warn(`! ${p} を見つけられませんでした`);
    } else paths.push(p);
  }

  const { cdp, close } = await launchChrome();
  const results = [];
  try {
    for (const path of paths) {
      for (const viewport of viewports) {
        for (const theme of themes) {
          const started = Date.now();
          // Chrome が稀にページ移動へ応答しなくなるので、新しいタブで 1 回だけやり直す
          let result;
          for (let attempt = 1; attempt <= 2 && (!result || result.error); attempt++) {
            let page;
            try {
              page = await openPage(cdp, { viewport, theme });
              await page.goto(args.base + path);
              const r = await page.eval(`(${inPageAudit.toString()})(${JSON.stringify(RULES)}, ${viewport.width})`);
              result = { path, viewport: viewport.name, theme, ...r };
              if (args.shots) {
                const name = `${path === "/" ? "home" : path.replace(/^\//, "").replace(/\//g, "_")}-${viewport.name}-${theme}.png`;
                await page.screenshot(join(args.shots, name), args.full);
              }
            } catch (e) {
              result = { path, viewport: viewport.name, theme, error: String(e.message || e), findings: [], checked: 0 };
            } finally {
              await page?.close().catch(() => {});
            }
          }
          results.push(result);
          // 途中経過（CI のログで止まった場所がわかるように標準エラーへ）
          console.error(
            `  ${path} ${viewport.name}/${theme}: ${result.error ? "ERR" : `${result.findings.length}件`} (${((Date.now() - started) / 1000).toFixed(1)}s)`,
          );
        }
      }
    }
  } finally {
    await close();
  }

  // 集計表
  const combos = viewports.flatMap((v) => themes.map((t) => `${v.name}/${t}`));
  console.log(`\n文字の読みやすさチェック  ${args.base}`);
  console.log(
    `ルール: ${RULES.minSize}px以上（バッジ${RULES.badgeMinSize}px）・太さ${RULES.minWeight}以上・コントラスト${RULES.minContrast}:1以上／` +
      `段落${RULES.paragraph.minSize}px（注記${RULES.paragraph.noteMinSize}px）・${RULES.paragraph.minContrast}:1／記事本文${RULES.prose.minSize}px（PC ${RULES.prose.minSizeWide}px）・${RULES.prose.minContrast}:1／` +
      `h1 ${RULES.heading.h1.minSize}px（PC ${RULES.heading.h1.minSizeWide}px）・本文の${RULES.heading.h1.ratio}倍（PC ${RULES.heading.h1.ratioWide}倍）／h2 ${RULES.heading.h2.minSize}px・${RULES.heading.h2.ratio}倍／h3 ${RULES.heading.h3.minSize}px\n`,
  );
  console.log(pad("ページ", 34) + combos.map((c) => pad(c, 12)).join(""));
  let total = 0;
  const byRule = {};
  for (const path of paths) {
    const row = combos.map((c) => {
      const [v, t] = c.split("/");
      const r = results.find((x) => x.path === path && x.viewport === v && x.theme === t);
      if (!r) return "-";
      if (r.error) return "ERR";
      total += r.findings.length;
      for (const f of r.findings) byRule[f.rule] = (byRule[f.rule] ?? 0) + 1;
      return `${r.findings.length}/${r.checked}`;
    });
    console.log(pad(path.length > 32 ? path.slice(0, 31) + "…" : path, 34) + row.map((c) => pad(c, 12)).join(""));
  }
  console.log("\n（違反数/調べた要素数）");
  const ruleNames = {
    size: "文字が小さい",
    weight: "文字が細い",
    contrast: "コントラスト不足",
    "para-size": "段落が小さい",
    "para-contrast": "段落が薄い",
    "prose-size": "記事本文が小さい",
    "prose-contrast": "記事本文が薄い",
    "h1-size": "h1が小さい",
    "h1-weight": "h1が細い",
    "h1-ratio": "h1と本文の差が小さい",
    "h1-contrast": "h1が薄い",
    "h2-size": "h2が小さい",
    "h2-weight": "h2が細い",
    "h2-ratio": "h2と本文の差が小さい",
    "h2-contrast": "h2が薄い",
    "h3-size": "h3が小さい",
    "h3-weight": "h3が細い",
  };
  console.log(
    "ルール別: " +
      (Object.entries(byRule)
        .map(([k, v]) => `${ruleNames[k] ?? k} ${v}`)
        .join("・") || "なし"),
  );
  const fonts = [...new Set(results.map((r) => r.family).filter(Boolean))];
  if (fonts.length) console.log(`本文の書体: ${fonts.join(" | ")}`);
  const images = results.reduce((a, r) => a + (r.overImage ?? 0), 0);
  if (images) console.log(`画像の上の文字（コントラストは目視）: ${images}`);
  for (const r of results.filter((x) => x.error)) console.log(`ERR ${r.path} ${r.viewport}/${r.theme}: ${r.error}`);

  // 同じ違反はまとめて上位だけ出す
  if (total) {
    const groups = new Map();
    for (const r of results) {
      for (const f of r.findings) {
        const key = `${f.rule}|${f.where}|${f.size}|${f.color}|${f.bg}`;
        const g = groups.get(key) ?? { ...f, count: 0, pages: new Set(), combos: new Set() };
        g.count++;
        g.pages.add(r.path);
        g.combos.add(`${r.viewport}/${r.theme}`);
        groups.set(key, g);
      }
    }
    const top = [...groups.values()].sort((a, b) => b.count - a.count).slice(0, args.limit);
    console.log(`\n主な違反（${groups.size}種類中 上位${top.length}）`);
    for (const g of top) {
      const c = g.contrast !== null ? ` ${g.contrast}:1 (${g.color} on ${g.bg})` : "";
      console.log(
        `  ${pad(ruleNames[g.rule] ?? g.rule, 16)} ×${g.count}  ${g.size}px/${g.weight}${c}  要${g.need}  「${g.text}」\n` +
          `      ${g.where}  [${[...g.pages].slice(0, 3).join(" ")}${g.pages.size > 3 ? " …" : ""}] [${[...g.combos].join(" ")}]`,
      );
    }
  }

  if (args.json) {
    mkdirSync(dirname(args.json), { recursive: true });
    writeFileSync(args.json, JSON.stringify({ base: args.base, rules: RULES, total, byRule, results }, null, 2));
  }
  console.log(`\n合計 ${total} 件の違反${total ? "" : "（すべてルールを満たしています）"}`);
  process.exit(total || results.some((r) => r.error) ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(2);
});
