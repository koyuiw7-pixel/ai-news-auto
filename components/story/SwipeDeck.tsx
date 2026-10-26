"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { StoryItem } from "@/components/story/StoryDeck";

export type Bundle = { key: string; label: string; items: StoryItem[] };
type Mode = "easy" | "expert";

const FONTS =
  "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap";
const SAVED_KEY = "saisoku:saved";

function ago(iso: string): string {
  const min = Math.max(1, Math.round((Date.now() - Date.parse(iso)) / 60000));
  if (min < 60) return `${min}分前`;
  const h = Math.round(min / 60);
  return h < 24 ? `${h}時間前` : `${Math.round(h / 24)}日前`;
}

function readSaved(): string[] {
  try {
    return JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function writeSaved(slugs: string[]) {
  try {
    localStorage.setItem(SAVED_KEY, JSON.stringify(slugs.slice(-50)));
  } catch {}
}

/**
 * トップ上段の「ストーリーの丸」と、タップで開く振り分けデッキ。
 * 右スワイプ＝気になる（取っておく）、左＝スキップ、ボタンで今すぐ読む。
 * 束を見終えたら「気になった記事」をまとめて出し、次の束へ進める。
 */
export default function StoryRail({ bundles }: { bundles: Bundle[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const [seen, setSeen] = useState<Record<string, boolean>>({});

  useEffect(() => {
    document.body.style.overflow = open === null ? "" : "hidden";
  }, [open]);

  // 丸ごとに違う写真を使う（同じ記事が先頭に来ても見分けられるように）
  const used = new Set<string>();
  const covers = bundles.map((b) => {
    const pick = b.items.find((s) => !used.has(s.slug)) ?? b.items[0];
    if (pick) used.add(pick.slug);
    return pick?.image.replace("maxresdefault", "hqdefault") ?? "";
  });

  return (
    <>
      <link rel="stylesheet" href={FONTS} precedence="default" />
      <style>{CSS}</style>
      <div className="sr" role="list" aria-label="ストーリー">
        {bundles.map((b, i) => (
          <button key={b.key} type="button" role="listitem" className={`sr-ring ${seen[b.key] ? "seen" : ""}`} onClick={() => setOpen(i)}>
            <span className="sr-img">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={covers[i]} alt="" />
            </span>
            <span className="sr-label">{b.label}</span>
            <span className="sr-n">{b.items.length}本</span>
          </button>
        ))}
      </div>
      {open !== null && (
        <Deck
          key={bundles[open].key}
          bundle={bundles[open]}
          next={bundles[open + 1]}
          onNext={() => {
            setSeen((s) => ({ ...s, [bundles[open].key]: true }));
            setOpen(open + 1 < bundles.length ? open + 1 : null);
          }}
          onClose={() => {
            setSeen((s) => ({ ...s, [bundles[open].key]: true }));
            setOpen(null);
          }}
        />
      )}
    </>
  );
}

function Deck({ bundle, next, onNext, onClose }: { bundle: Bundle; next?: Bundle; onNext: () => void; onClose: () => void }) {
  const { items } = bundle;
  const [index, setIndex] = useState(0);
  const [kept, setKept] = useState<StoryItem[]>([]);
  const [mode, setMode] = useState<Mode>("easy");
  const [grid, setGrid] = useState(false);
  const [drag, setDrag] = useState(0);
  const [fly, setFly] = useState<0 | 1 | -1>(0);
  const start = useRef<{ x: number; y: number } | null>(null);
  const done = index >= items.length;

  const decide = useCallback(
    (dir: 1 | -1) => {
      if (done || fly) return;
      const it = items[index];
      setFly(dir);
      if (dir === 1) {
        setKept((k) => [...k, it]);
        writeSaved([...readSaved().filter((s) => s !== it.slug), it.slug]);
      }
      window.setTimeout(() => {
        setFly(0);
        setDrag(0);
        setIndex((i) => i + 1);
      }, 260);
    },
    [done, fly, index, items],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") decide(1);
      if (e.key === "ArrowLeft") decide(-1);
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide, onClose]);

  const onDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest("button,a")) return;
    start.current = { x: e.clientX, y: e.clientY };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    if (!start.current) return;
    setDrag(e.clientX - start.current.x);
  };
  const onUp = () => {
    if (!start.current) return;
    start.current = null;
    if (drag > 90) decide(1);
    else if (drag < -90) decide(-1);
    else setDrag(0);
  };

  const it = items[index];
  const peek = items[index + 1];
  const x = fly ? fly * 520 : drag;
  const like = Math.max(0, Math.min(1, x / 90));
  const nope = Math.max(0, Math.min(1, -x / 90));

  return (
    <div className="dk" role="dialog" aria-modal="true" aria-label={bundle.label}>
      <div className="dk-top">
        <div className="dk-progress" aria-hidden>
          {items.map((s, i) => (
            <span key={s.slug} className={i < index ? "done" : i === index ? "now" : ""} />
          ))}
        </div>
        <div className="dk-bar">
          <button type="button" className="dk-close" onClick={onClose} aria-label="閉じる">
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          </button>
          <span className="dk-title">{bundle.label}</span>
          <span className="dk-count">{Math.min(index + 1, items.length)}/{items.length}</span>
          <div className="dk-mode" role="group" aria-label="読み方">
            <button type="button" aria-pressed={mode === "easy"} onClick={() => setMode("easy")}>かんたん</button>
            <button type="button" aria-pressed={mode === "expert"} onClick={() => setMode("expert")}>専門家</button>
          </div>
          <button type="button" className="dk-gridbtn" aria-pressed={grid} onClick={() => setGrid((g) => !g)} aria-label="一覧で選ぶ">
            <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden><path d="M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z" fill="none" stroke="currentColor" strokeWidth="1.7" /></svg>
          </button>
        </div>
      </div>

      {!done && (
        <div className="dk-stage">
          {peek && (
            <div className="dk-card is-peek" aria-hidden>
              <Card it={peek} mode={mode} />
            </div>
          )}
          <div
            className="dk-card"
            style={{ transform: `translateX(${x}px) rotate(${x / 22}deg)`, transition: start.current ? "none" : "transform .26s cubic-bezier(.2,.7,.2,1)" }}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
          >
            <Card it={it} mode={mode} />
            <span className="dk-stamp keep" style={{ opacity: like }}>気になる</span>
            <span className="dk-stamp skip" style={{ opacity: nope }}>スキップ</span>
          </div>
        </div>
      )}

      {!done && (
        <div className="dk-actions">
          <button type="button" className="dk-act skip" onClick={() => decide(-1)}>
            <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>
            <span>スキップ</span>
          </button>
          <Link href={`/articles/${it.slug}`} className="dk-read">今すぐ読む</Link>
          <button type="button" className="dk-act keep" onClick={() => decide(1)}>
            <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden><path d="M6 3h8v14l-4-3-4 3z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg>
            <span>気になる</span>
          </button>
        </div>
      )}

      {done && <Summary kept={kept} next={next} onNext={onNext} onClose={onClose} />}

      {grid && (
        <div className="dk-grid" onClick={() => setGrid(false)}>
          <div className="dk-grid-in" onClick={(e) => e.stopPropagation()}>
            <p className="dk-grid-h">{bundle.label}から選ぶ（{items.length}本）</p>
            <ul>
              {items.map((s) => (
                <li key={s.slug}>
                  <Link href={`/articles/${s.slug}`}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={s.image.replace("maxresdefault", "hqdefault")} alt="" />
                    <span className="g-t">{s.title}</span>
                    {s.usableLabel && <span className={`g-v ${s.usable}`}>{s.usableLabel}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function Summary({ kept, next, onNext, onClose }: { kept: StoryItem[]; next?: Bundle; onNext: () => void; onClose: () => void }) {
  return (
    <div className="dk-sum">
      <p className="dk-sum-k">{kept.length ? `気になった${kept.length}本` : "今回はピンとくるものがなかったようです"}</p>
      {kept.length > 0 && (
        <ul className="dk-sum-list">
          {kept.map((s) => (
            <li key={s.slug}>
              <Link href={`/articles/${s.slug}`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.image.replace("maxresdefault", "hqdefault")} alt="" />
                <span>{s.title}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {next ? (
        <button type="button" className="dk-next" onClick={onNext}>
          次は「{next.label}」<span aria-hidden> →</span>
        </button>
      ) : (
        <button type="button" className="dk-next" onClick={onClose}>一覧に戻る</button>
      )}
      <button type="button" className="dk-back" onClick={onClose}>記事一覧から選ぶ</button>
    </div>
  );
}

function Card({ it, mode }: { it: StoryItem; mode: Mode }) {
  return (
    <div className="c">
      <div className="c-photo">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={it.image} alt="" draggable={false} onError={(e) => (e.currentTarget.src = it.image.replace("maxresdefault", "hqdefault"))} />
        <div className="c-shade" />
        <div className="c-head">
          <p className="c-meta">
            <i style={{ background: it.color }} />
            {it.company}
            <time suppressHydrationWarning>{ago(it.at)}</time>
          </p>
          <h2 className="c-title">{it.title}</h2>
        </div>
      </div>
      <div className="c-info">
        {it.usable && (
          <div className="c-verdict">
            <span className={`c-chip ${it.usable}`}>{it.usableLabel}</span>
            <dl>
              <div><dt>日本</dt><dd>{it.japan}</dd></div>
              <div><dt>料金</dt><dd>{it.free === "無料で試せる" ? "無料で試せる" : it.price}</dd></div>
            </dl>
          </div>
        )}
        {mode === "easy" ? (
          <p className="c-gist">{it.gist}</p>
        ) : (
          <ul className="c-points">{it.highlights.map((h) => <li key={h}>{h}</li>)}</ul>
        )}
      </div>
    </div>
  );
}

const CSS = `
.sr{display:flex;gap:14px;overflow-x:auto;padding:14px 16px 10px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.sr::-webkit-scrollbar{display:none}
.sr-ring{flex:none;display:flex;flex-direction:column;align-items:center;gap:5px;width:70px}
.sr-img{width:64px;height:64px;border-radius:50%;padding:2.5px;background:conic-gradient(from 210deg,#2fd27f,#0a6fa0,#2fd27f)}
.sr-ring.seen .sr-img{background:var(--line-strong,#cfcfc7)}
.sr-img img{width:100%;height:100%;border-radius:50%;object-fit:cover;border:2.5px solid var(--paper,#fff)}
.sr-label{font-size:11.5px;font-weight:700;line-height:1.2;text-align:center;color:var(--ink,#111)}
.sr-n{font-family:var(--font-martian),monospace;font-size:9.5px;color:var(--muted,#62625d);margin-top:-3px}

.dk{position:fixed;inset:0;z-index:90;background:#0b0d10;color:#f4f5f7;font-family:"Noto Sans JP",system-ui,sans-serif;-webkit-font-smoothing:antialiased;display:flex;flex-direction:column;overscroll-behavior:contain;touch-action:pan-y}
.dk-top{padding:10px 14px 6px}
.dk-progress{display:flex;gap:4px}
.dk-progress span{flex:1;height:2.5px;border-radius:2px;background:rgba(255,255,255,.22)}
.dk-progress span.done,.dk-progress span.now{background:#f4f5f7}
.dk-bar{display:flex;align-items:center;gap:8px;margin-top:9px}
.dk-close,.dk-gridbtn{width:34px;height:34px;display:grid;place-items:center;border-radius:50%;color:#f4f5f7}
.dk-gridbtn[aria-pressed=true]{background:#f4f5f7;color:#0b0d10}
.dk-title{font-weight:900;font-size:14px}
.dk-count{font-family:var(--font-martian),monospace;font-size:11px;color:#9aa1ab}
.dk-mode{margin-left:auto;display:flex;border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:2px}
.dk-mode button{font-size:11px;font-weight:700;padding:5px 9px;border-radius:999px;color:#b9bfc8}
.dk-mode button[aria-pressed=true]{background:#f4f5f7;color:#0b0d10}

.dk-stage{position:relative;flex:1;min-height:0;margin:4px 12px 0}
.dk-card{position:absolute;inset:0;border-radius:20px;overflow:hidden;background:#15181d;box-shadow:0 18px 40px rgba(0,0,0,.45);touch-action:none;user-select:none;cursor:grab}
.dk-card.is-peek{transform:scale(.95) translateY(10px);opacity:.55;pointer-events:none}
.dk-stamp{position:absolute;top:22px;padding:6px 14px;border:3px solid;border-radius:10px;font-weight:900;font-size:22px;letter-spacing:.06em;pointer-events:none}
.dk-stamp.keep{left:18px;color:#2fd27f;transform:rotate(-12deg)}
.dk-stamp.skip{right:18px;color:#c9ced6;transform:rotate(12deg)}

.c{height:100%;display:grid;grid-template-rows:54% 1fr}
.c-photo{position:relative;overflow:hidden}
.c-photo img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;pointer-events:none}
.c-shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(21,24,29,0) 35%,rgba(21,24,29,.78) 74%,#15181d 100%)}
.c-head{position:absolute;left:16px;right:16px;bottom:6px}
.c-meta{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700;letter-spacing:.04em;color:#e6e8eb}
.c-meta i{width:4px;height:14px;border-radius:1px}
.c-meta time{font-family:var(--font-martian),monospace;font-weight:400;font-size:11px;color:#aeb4bc;margin-left:4px}
.c-title{margin-top:7px;font-weight:900;font-size:clamp(19px,5.6vw,24px);line-height:1.42;text-wrap:balance;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;text-shadow:0 1px 12px rgba(0,0,0,.4)}
.c-info{display:flex;flex-direction:column;gap:13px;padding:12px 16px 16px;min-height:0;overflow:hidden}
.c-verdict{display:flex;align-items:center;gap:12px}
.c-chip{font-weight:900;font-size:14px;padding:6px 13px;border-radius:999px;white-space:nowrap}
.c-chip.go{background:#2fd27f;color:#04170c}
.c-chip.partial{border:1.5px solid #9fb3c8;color:#9fb3c8}
.c-chip.wait{border:1.5px solid #8a919b;color:#8a919b}
.c-verdict dl{display:grid;gap:2px;font-size:12px;min-width:0}
.c-verdict dl div{display:flex;gap:8px;min-width:0}
.c-verdict dt{color:#7d8590;flex:none}
.c-verdict dd{color:#b9bfc8;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.c-gist{font-size:14.5px;line-height:1.8;color:#b9bfc8;display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden}
.c-points{display:grid;gap:8px;font-size:13px;line-height:1.6;color:#b9bfc8;counter-reset:p}
.c-points li{display:grid;grid-template-columns:18px 1fr;gap:6px;counter-increment:p}
.c-points li::before{content:counter(p);font-family:var(--font-martian),monospace;font-size:11px;color:#7d8590;padding-top:2px}

.dk-actions{display:grid;grid-template-columns:64px 1fr 64px;align-items:center;gap:14px;padding:14px 20px calc(14px + env(safe-area-inset-bottom))}
.dk-act{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:10.5px;font-weight:700;color:#9aa1ab}
.dk-act svg{width:48px;height:48px;padding:13px;border-radius:50%;border:1.5px solid rgba(255,255,255,.2)}
.dk-act.keep{color:#2fd27f}
.dk-act.keep svg{border-color:#2fd27f}
.dk-read{height:50px;display:flex;align-items:center;justify-content:center;border-radius:999px;background:#f4f5f7;color:#0b0d10;font-weight:700;font-size:15px}

.dk-sum{flex:1;display:flex;flex-direction:column;gap:14px;padding:18px 20px 28px;overflow-y:auto}
.dk-sum-k{font-weight:900;font-size:22px}
.dk-sum-list{display:grid;gap:10px}
.dk-sum-list a{display:grid;grid-template-columns:88px 1fr;gap:12px;align-items:center;font-size:13.5px;font-weight:700;line-height:1.5}
.dk-sum-list img{width:88px;aspect-ratio:16/9;object-fit:cover;border-radius:8px}
.dk-next{margin-top:auto;height:52px;border-radius:999px;background:#f4f5f7;color:#0b0d10;font-weight:900;font-size:15px}
.dk-back{font-size:13.5px;font-weight:700;color:#9aa1ab;padding:6px}

.dk-grid{position:absolute;inset:0;z-index:2;background:rgba(0,0,0,.55);display:flex;align-items:flex-end}
.dk-grid-in{width:100%;max-height:78%;overflow-y:auto;background:#15181d;border-radius:20px 20px 0 0;padding:18px 16px 24px}
.dk-grid-h{font-weight:900;font-size:15px;margin-bottom:12px}
.dk-grid ul{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.dk-grid a{display:flex;flex-direction:column;gap:6px;position:relative}
.dk-grid img{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:8px}
.g-t{font-size:12px;font-weight:700;line-height:1.45;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.g-v{position:absolute;top:6px;left:6px;font-size:10px;font-weight:900;padding:2px 7px;border-radius:999px;background:rgba(0,0,0,.6);color:#c9ced6}
.g-v.go{background:#2fd27f;color:#04170c}
@media (prefers-reduced-motion:reduce){.dk *{transition:none!important}}
`;
