"use client";

import { useEffect, useState } from "react";
import Panel from "./Panel";
import { DIRECTIONS, PRESETS, type DirKey, type Mode, type PreviewData, type Usage } from "./data";
import s from "./preview.module.css";

type View = "split" | "single";

/**
 * 3案の切り替え。広い画面は「3案を並べる／1案ずつ大きく」、スマホは常に1案ずつ。
 * 状態は URL（?d=a&mode=dark&view=single）にも残すので、そのまま共有・撮影できる。
 */
export default function DesignPreview({ data }: { data: PreviewData }) {
  const [dir, setDir] = useState<DirKey>("a");
  const [mode, setMode] = useState<Mode>("light");
  const [view, setView] = useState<View>("split");
  // 使い方は3案で共通（同じ条件で見比べる）
  const [usage, setUsage] = useState<Usage>(PRESETS[1].usage);

  // URL → 状態（無ければサイトのテーマに合わせる）
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const d = q.get("d");
    if (d === "a" || d === "b" || d === "c") setDir(d);
    const m = q.get("mode");
    if (m === "light" || m === "dark") setMode(m);
    else if (document.documentElement.dataset.theme === "dark") setMode("dark");
    const v = q.get("view");
    if (v === "split" || v === "single") setView(v);
  }, []);

  // 状態 → URL
  function update(next: Partial<{ d: DirKey; mode: Mode; view: View }>) {
    const q = new URLSearchParams(window.location.search);
    for (const [k, v] of Object.entries(next)) q.set(k, v);
    window.history.replaceState(null, "", `?${q.toString()}`);
    if (next.d) setDir(next.d);
    if (next.mode) setMode(next.mode);
    if (next.view) setView(next.view);
  }

  return (
    <div className={s.root} data-mode={mode} data-view={view}>
      <div className={s.toolbar}>
        <p className={s.tbTitle}>
          配色デザイン案の比較
          <span>確認用・検索には出ません。3案とも同じ実データです</span>
        </p>
        <div className={`${s.seg} ${s.viewSeg}`} role="group" aria-label="表示のしかた">
          <button type="button" className={s.segBtn} aria-pressed={view === "split"} onClick={() => update({ view: "split" })}>
            3案を並べる
          </button>
          <button type="button" className={s.segBtn} aria-pressed={view === "single"} onClick={() => update({ view: "single" })}>
            1案ずつ大きく
          </button>
        </div>
        <div className={`${s.seg} ${s.dirSeg}`} role="group" aria-label="デザイン案">
          {DIRECTIONS.map((d) => (
            <button key={d.key} type="button" className={s.segBtn} aria-pressed={dir === d.key} onClick={() => update({ d: d.key })}>
              {d.label} <span className={s.long}>{d.name}</span>
              <span className={s.short}>{d.short}</span>
            </button>
          ))}
        </div>
        <div className={s.seg} role="group" aria-label="明るさ">
          <button type="button" className={s.segBtn} aria-pressed={mode === "light"} onClick={() => update({ mode: "light" })}>
            ライト
          </button>
          <button type="button" className={s.segBtn} aria-pressed={mode === "dark"} onClick={() => update({ mode: "dark" })}>
            ダーク
          </button>
        </div>
      </div>

      <div className={s.stage} data-view={view}>
        {DIRECTIONS.map((d) => (
          <section key={d.key} className={s.col} data-active={dir === d.key} aria-label={`${d.label}案 ${d.name}`}>
            <div className={s.caption}>
              <span className={s.capLabel}>{d.label}</span>
              <span className={s.capName}>{d.name}</span>
              <span className={s.capText}>
                {d.concept}
                <br />
                {d.accentUse}
              </span>
            </div>
            {/* 案を切り替えるたびに描き直して、数字と棒の動きをもう一度見せる */}
            <Panel key={`${d.key}-${dir === d.key}`} dir={d} mode={mode} data={data} usage={usage} onUsage={setUsage} />
          </section>
        ))}
      </div>
    </div>
  );
}
