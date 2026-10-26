"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

export type StoryItem = {
  slug: string;
  title: string;
  gist: string;
  highlights: string[];
  image: string;
  company: string;
  color: string;
  at: string;
  usable: "go" | "partial" | "wait" | null;
  usableLabel: string | null;
  japan: string | null;
  free: string | null;
  price: string | null;
};

type Variant = "a" | "b";
type Mode = "easy" | "expert";

const FONTS =
  "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&family=Noto+Serif+JP:wght@600;700&display=swap";

function ago(iso: string): string {
  const min = Math.max(1, Math.round((Date.now() - Date.parse(iso)) / 60000));
  if (min < 60) return `${min}分前`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h}時間前`;
  return `${Math.round(h / 24)}日前`;
}

function hq(src: string) {
  return src.replace("maxresdefault", "hqdefault");
}

/**
 * スマホ用「今日の7本」。1ニュース1画面で縦にめくる。
 * A: 報道テロップ型（写真全面・暗い地）／B: 雑誌型（白地・明朝見出し）
 */
export default function StoryDeck({ items }: { items: StoryItem[] }) {
  const [variant, setVariant] = useState<Variant>("a");
  const [mode, setMode] = useState<Mode>("easy");
  const [index, setIndex] = useState(0);
  const [now, setNow] = useState<number | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const total = items.length;

  useEffect(() => setNow(Date.now()), []);

  useEffect(() => {
    const root = scroller.current;
    if (!root) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) setIndex(Number((e.target as HTMLElement).dataset.i));
        }
      },
      { root, threshold: 0.6 },
    );
    root.querySelectorAll("[data-i]").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [variant]);

  const go = (i: number) => {
    const el = scroller.current?.querySelector<HTMLElement>(`[data-i="${i}"]`);
    el?.scrollIntoView({ behavior: "smooth" });
  };

  const dark = variant === "a";

  return (
    <div className={`sd sd-${variant}`}>
      <link rel="stylesheet" href={FONTS} precedence="default" />
      <style>{CSS}</style>

      <div className="sd-top">
        <div className="sd-progress" aria-hidden>
          {items.map((it, i) => (
            <span key={it.slug} className={i < index ? "done" : i === index ? "now" : ""} />
          ))}
        </div>
        <div className="sd-bar">
          <Link href="/" className="sd-logo">サイソク</Link>
          <span className="sd-count">
            {index < total ? (
              <>今日の{total}本 <b>{index + 1}</b>/{total}</>
            ) : (
              <>読了</>
            )}
          </span>
          <div className="sd-mode" role="group" aria-label="読み方">
            <button type="button" aria-pressed={mode === "easy"} onClick={() => setMode("easy")}>かんたん</button>
            <button type="button" aria-pressed={mode === "expert"} onClick={() => setMode("expert")}>専門家</button>
          </div>
        </div>
      </div>

      <div ref={scroller} className="sd-scroll">
        {items.map((it, i) => (
          <section key={it.slug} data-i={i} className={`sd-slide ${i === index ? "is-active" : ""}`}>
            {dark ? (
              <SlideA it={it} mode={mode} now={now} />
            ) : (
              <SlideB it={it} mode={mode} now={now} n={i + 1} total={total} />
            )}
            {i === 0 && <p className="sd-hint">上にスワイプで次のニュース</p>}
          </section>
        ))}
        <section data-i={total} className="sd-slide sd-end">
          <div className="sd-end-in">
            <p className="sd-end-k">今日の{total}本はここまで</p>
            <p className="sd-end-t">続きは、使えるAIだけに絞って見られます。</p>
            <Link href="/usable" className="sd-btn">今日から使えるAIを見る</Link>
            <Link href="/articles" className="sd-link">すべての新着 →</Link>
            <button type="button" className="sd-link" onClick={() => go(0)}>最初から見る ↑</button>
          </div>
        </section>
      </div>

      <div className="sd-variant" role="group" aria-label="試作の切り替え">
        <span>試作</span>
        <button type="button" aria-pressed={variant === "a"} onClick={() => setVariant("a")}>A テロップ</button>
        <button type="button" aria-pressed={variant === "b"} onClick={() => setVariant("b")}>B 雑誌</button>
      </div>
    </div>
  );
}

function Verdict({ it }: { it: StoryItem }) {
  if (!it.usable) return null;
  return (
    <div className="sd-verdict">
      <span className={`sd-chip ${it.usable}`}>
        <VIcon u={it.usable} />
        {it.usableLabel}
      </span>
      <dl>
        <div><dt>日本</dt><dd>{it.japan}</dd></div>
        <div><dt>料金</dt><dd>{it.free === "無料で試せる" ? "無料で試せる" : it.price}</dd></div>
      </dl>
    </div>
  );
}

function VIcon({ u }: { u: "go" | "partial" | "wait" }) {
  if (u === "go")
    return (
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden>
        <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  if (u === "partial")
    return (
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden>
        <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M8 2.5a5.5 5.5 0 0 1 0 11z" fill="currentColor" />
      </svg>
    );
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden>
      <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8 5v3.2l2 1.3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function Body({ it, mode }: { it: StoryItem; mode: Mode }) {
  return mode === "easy" ? (
    <p className="sd-gist">{it.gist}</p>
  ) : (
    <ul className="sd-points">
      {it.highlights.map((h) => (
        <li key={h}>{h}</li>
      ))}
    </ul>
  );
}

function SlideA({ it, mode, now }: { it: StoryItem; mode: Mode; now: number | null }) {
  return (
    <div className="a-wrap">
      <div className="a-photo">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={it.image} alt="" onError={(e) => (e.currentTarget.src = hq(it.image))} />
        <div className="a-shade" />
        <div className="a-head">
          <p className="a-meta">
            <i style={{ background: it.color }} />
            {it.company}
            {now && <time>{ago(it.at)}</time>}
          </p>
          <h2 className="a-title">{it.title}</h2>
        </div>
      </div>
      <div className="a-info">
        <Verdict it={it} />
        <Body it={it} mode={mode} />
        <Link href={`/articles/${it.slug}`} className="sd-btn">記事を読む</Link>
      </div>
    </div>
  );
}

function SlideB({ it, mode, now, n, total }: { it: StoryItem; mode: Mode; now: number | null; n: number; total: number }) {
  return (
    <div className="b-wrap">
      <p className="b-issue">
        <span>No.{String(n).padStart(2, "0")}</span>
        <span>/{String(total).padStart(2, "0")}</span>
        {now && <time>{ago(it.at)}</time>}
      </p>
      <div className="b-photo">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={it.image} alt="" onError={(e) => (e.currentTarget.src = hq(it.image))} />
      </div>
      <p className="b-co" style={{ color: it.color }}>{it.company}</p>
      <h2 className="b-title">{it.title}</h2>
      <Verdict it={it} />
      <Body it={it} mode={mode} />
      <Link href={`/articles/${it.slug}`} className="b-read">全文を読む <span aria-hidden>→</span></Link>
    </div>
  );
}

const CSS = `
.sd{position:fixed;inset:0;z-index:80;font-family:"Noto Sans JP",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.sd-a{--bg:#0b0d10;--fg:#f4f5f7;--sub:#b9bfc8;--dim:#7d8590;--rule:rgba(255,255,255,.12);--go:#2fd27f;--part:#9fb3c8;--wait:#8a919b;--btn-bg:#f4f5f7;--btn-fg:#0b0d10;background:var(--bg);color:var(--fg)}
.sd-b{--bg:#f3f4f2;--fg:#121416;--sub:#3d4247;--dim:#7a8087;--rule:#d9dcd8;--go:#0b7a43;--part:#4d6880;--wait:#6b7178;--btn-bg:#121416;--btn-fg:#f3f4f2;background:var(--bg);color:var(--fg)}

.sd-top{position:absolute;inset:0 0 auto 0;z-index:3;padding:10px 16px 8px;pointer-events:none}
.sd-a .sd-top{background:linear-gradient(rgba(0,0,0,.55),rgba(0,0,0,0))}
.sd-b .sd-top{background:var(--bg)}
.sd-progress{display:flex;gap:4px}
.sd-progress span{flex:1;height:2.5px;border-radius:2px;background:var(--rule);position:relative;overflow:hidden}
.sd-a .sd-progress span{background:rgba(255,255,255,.28)}
.sd-progress span.done,.sd-progress span.now{background:var(--fg)}
.sd-bar{display:flex;align-items:center;gap:10px;margin-top:10px;pointer-events:auto}
.sd-logo{font-family:var(--font-dela),sans-serif;font-size:17px;letter-spacing:.02em;color:var(--fg)}
.sd-count{font-family:var(--font-martian),monospace;font-size:11px;color:var(--sub);letter-spacing:.04em}
.sd-count b{color:var(--fg);font-weight:600}
.sd-mode{margin-left:auto;display:flex;border:1px solid var(--rule);border-radius:999px;padding:2px}
.sd-a .sd-mode{border-color:rgba(255,255,255,.3);background:rgba(0,0,0,.25);backdrop-filter:blur(8px)}
.sd-mode button{font-size:11.5px;font-weight:700;padding:5px 10px;border-radius:999px;color:var(--sub)}
.sd-mode button[aria-pressed=true]{background:var(--fg);color:var(--bg)}

.sd-scroll{height:100dvh;overflow-y:scroll;scroll-snap-type:y mandatory;overscroll-behavior:contain;scrollbar-width:none}
.sd-scroll::-webkit-scrollbar{display:none}
.sd-slide{height:100dvh;scroll-snap-align:start;scroll-snap-stop:always;position:relative;overflow:hidden}
.sd-hint{position:absolute;left:0;right:0;bottom:14px;text-align:center;font-size:11px;color:var(--dim);letter-spacing:.08em;animation:sdHint 2.4s ease-in-out infinite}
@keyframes sdHint{0%,100%{transform:translateY(0);opacity:.6}50%{transform:translateY(-4px);opacity:1}}

.sd-verdict{display:flex;align-items:center;gap:14px}
.sd-chip{display:inline-flex;align-items:center;gap:6px;font-weight:900;font-size:15px;padding:7px 13px 7px 11px;border-radius:999px;white-space:nowrap}
.sd-chip.go{background:var(--go);color:#fff}
.sd-a .sd-chip.go{color:#04170c}
.sd-chip.partial{border:1.5px solid var(--part);color:var(--part)}
.sd-chip.wait{border:1.5px solid var(--wait);color:var(--wait)}
.sd-verdict dl{display:grid;gap:3px;font-size:12px;min-width:0}
.sd-verdict dl div{display:flex;gap:8px;min-width:0}
.sd-verdict dt{color:var(--dim);flex:none}
.sd-verdict dd{color:var(--sub);font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sd-gist{font-size:15px;line-height:1.85;color:var(--sub);display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden}
.sd-points{display:grid;gap:9px;font-size:13.5px;line-height:1.65;color:var(--sub);counter-reset:p}
.sd-points li{display:grid;grid-template-columns:20px 1fr;gap:6px;counter-increment:p}
.sd-points li::before{content:counter(p);font-family:var(--font-martian),monospace;font-size:11px;color:var(--dim);padding-top:3px}
.sd-btn{display:flex;align-items:center;justify-content:center;height:48px;border-radius:999px;background:var(--btn-bg);color:var(--btn-fg);font-weight:700;font-size:15px}

/* A: 報道テロップ */
.a-wrap{height:100%;display:grid;grid-template-rows:56% 1fr}
.a-photo{position:relative;overflow:hidden}
.a-photo img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.a-shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(11,13,16,0) 35%,rgba(11,13,16,.75) 72%,#0b0d10 100%)}
.a-head{position:absolute;left:16px;right:16px;bottom:8px}
.a-meta{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700;letter-spacing:.04em;color:#e6e8eb}
.a-meta i{width:4px;height:14px;border-radius:1px}
.a-meta time{font-family:var(--font-martian),monospace;font-weight:400;font-size:11px;color:#aeb4bc;margin-left:4px}
.a-title{margin-top:8px;font-weight:900;font-size:clamp(21px,6vw,26px);line-height:1.42;letter-spacing:.01em;text-wrap:balance;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;text-shadow:0 1px 12px rgba(0,0,0,.4)}
.a-info{display:flex;flex-direction:column;gap:16px;padding:14px 16px 40px;min-height:0}
.a-info .sd-btn{margin-top:auto}

/* B: 雑誌 */
.b-wrap{height:100%;display:flex;flex-direction:column;gap:14px;padding:76px 20px 40px}
.b-issue{display:flex;align-items:baseline;gap:2px;font-family:var(--font-martian),monospace;font-size:12px;color:var(--dim);border-bottom:1px solid var(--fg);padding-bottom:8px}
.b-issue span:first-child{color:var(--fg);font-weight:600;font-size:15px}
.b-issue time{margin-left:auto;font-size:11px}
.b-photo{position:relative;aspect-ratio:16/9;overflow:hidden;background:#e4e6e3;flex:none}
.b-photo img{width:100%;height:100%;object-fit:cover}
.b-co{font-size:11.5px;font-weight:700;letter-spacing:.14em}
.b-title{font-family:"Noto Serif JP",serif;font-weight:700;font-size:clamp(21px,6vw,25px);line-height:1.5;margin-top:-8px;text-wrap:balance;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.sd-b .sd-verdict{border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:10px 0}
.sd-b .sd-gist{-webkit-line-clamp:4;font-size:14.5px}
.b-read{margin-top:auto;display:flex;justify-content:space-between;align-items:center;height:50px;border-top:1.5px solid var(--fg);font-weight:700;font-size:15px}

/* 入場の動き */
.sd-slide .a-head,.sd-slide .a-info>*,.sd-slide .b-title,.sd-slide .sd-verdict{transition:opacity .5s ease,transform .5s cubic-bezier(.2,.7,.2,1)}
.sd-slide:not(.is-active) .a-head,.sd-slide:not(.is-active) .a-info>*,.sd-slide:not(.is-active) .b-title,.sd-slide:not(.is-active) .sd-verdict{opacity:.35;transform:translateY(10px)}
@media (prefers-reduced-motion:reduce){.sd *{transition:none!important;animation:none!important}}

/* 最後 */
.sd-end{display:grid;place-items:center;padding:0 24px}
.sd-end-in{display:flex;flex-direction:column;gap:14px;width:100%;max-width:360px;text-align:center}
.sd-end-k{font-weight:900;font-size:24px}
.sd-end-t{color:var(--sub);font-size:14px;margin-bottom:10px}
.sd-link{font-size:14px;font-weight:700;color:var(--sub);padding:6px}

/* 試作の切り替え（本番では出さない） */
.sd-variant{position:absolute;right:12px;top:62px;z-index:4;display:flex;align-items:center;gap:4px;padding:4px;border-radius:12px;background:rgba(127,127,127,.18);backdrop-filter:blur(10px);font-size:11px}
.sd-variant span{padding:0 6px;color:var(--dim);font-weight:700}
.sd-variant button{padding:6px 9px;border-radius:9px;font-weight:700;color:var(--sub)}
.sd-variant button[aria-pressed=true]{background:var(--fg);color:var(--bg)}
`;
