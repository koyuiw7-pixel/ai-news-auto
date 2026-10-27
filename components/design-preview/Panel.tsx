"use client";

import { useEffect, useRef, useState } from "react";
import {
  ACTIVITIES,
  monthlyTokens,
  monthlyYen,
  PRESETS,
  RATE,
  tokenStyle,
  usd,
  yenDigits,
  type Direction,
  type Japan,
  type Mode,
  type PreviewData,
  type PreviewModel,
  type Usage,
} from "./data";
import s from "./preview.module.css";

type Props = {
  dir: Direction;
  mode: Mode;
  data: PreviewData;
  usage: Usage;
  onUsage: (usage: Usage) => void;
};

const dateJa = new Intl.DateTimeFormat("ja-JP", { year: "numeric", month: "long", day: "numeric", weekday: "short", timeZone: "Asia/Tokyo" });
const dayJa = new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", timeZone: "Asia/Tokyo" });
const timeJa = new Intl.DateTimeFormat("ja-JP", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Tokyo" });
const day = (iso: string) => dayJa.format(new Date(iso));
const time = (iso: string) => timeJa.format(new Date(iso));

/** 1案ぶんの画面（ヘッダー・大きな数字・棒グラフ・記事カード・製品・ラベル・色の設計） */
export default function Panel({ dir, mode, data, usage, onUsage }: Props) {
  const ranked = data.models
    .map((m) => ({ model: m, jpy: monthlyYen(m, usage) }))
    .sort((a, b) => a.jpy - b.jpy);
  const cheapest = ranked[0];
  const priciest = ranked.at(-1);
  const tokens = monthlyTokens(usage);

  return (
    <div className={s.panel} data-dir={dir.key} style={tokenStyle(dir, mode)}>
      <Masthead dir={dir} data={data} />

      <div className={s.page}>
        <nav aria-label="パンくず" className={s.crumb}>
          <a href="/">ホーム</a> / AI料金・日本対応 早見表
        </nav>
        <h1 className={s.h1}>
          AIの料金・<wbr />
          日本対応<wbr /> 早見表
        </h1>
        <p className={s.lead}>ChatGPT・Claude・GeminiなどのAIを使うと、月にいくらかかるか。使い方を選ぶだけで、円でわかります。</p>
        <p className={s.meta}>
          <span>
            最終更新 <b className={s.num}>{day(data.updatedAt)}</b>
          </span>
          <span>
            <span className={s.num}>{data.modelCount}</span>モデル
          </span>
          <span>数字はすべて記事で確認</span>
        </p>

        {/* ===== 大きな数字と使い方 ===== */}
        {cheapest && (
          <section className={s.hero} aria-label="いちばん安いといくら">
            <div>
              <p className={s.eyebrow}>APIで使うと月いくら？</p>
              <p className={s.heroLead}>いちばん安いモデルなら</p>
              <p className={s.bigRow} aria-live="polite">
                <span className={s.bigUnit}>月</span>
                <span className={`${s.bigUnit} ${s.bigApprox}`}>約</span>
                <Count value={cheapest.jpy} className={`${s.bigNum} ${s.num}`} />
                <span className={s.bigYen}>円</span>
                <span className={s.bigFrom}>から</span>
              </p>
              <p className={s.modelLine}>
                <Chip model={cheapest.model} />
                <strong>{cheapest.model.product}</strong>
                <span className={s.modelCo}>{cheapest.model.companyName}</span>
                <span className={`${s.tag} ${s.tagBest}`} data-allow-small="">
                  最安
                </span>
              </p>
              {tokens.actions > 0 && (
                <p className={s.perUse}>
                  1回あたり <b className={s.num}>約{yenDigits(cheapest.jpy / tokens.actions)}円</b>（月
                  <span className={s.num}>{tokens.actions.toLocaleString()}</span>回）
                </p>
              )}
              {priciest && priciest !== cheapest && (
                <p className={`${s.compare} text-note`}>
                  同じ使い方でも、いちばん高い{priciest.model.product}だと月<b className={s.num}>約{yenDigits(priciest.jpy)}円</b>
                  （約<span className={s.num}>{Math.round(priciest.jpy / cheapest.jpy)}</span>倍）。
                </p>
              )}
              <p className={s.calcNote}>1ドル＝{RATE}円・1日の回数は30日分で計算</p>
            </div>
            <UsagePanel usage={usage} onUsage={onUsage} />
          </section>
        )}

        {/* ===== 棒グラフ ===== */}
        <section className={s.section} aria-labelledby={`rank-${dir.key}`}>
          <SecHead id={`rank-${dir.key}`} no="01" kicker="料金ランキング" note="日本で使えるモデルを、選んだ使い方での月額が安い順に。棒が短いほど安い。">
            同じ使い方だと、<wbr />
            モデルごとに<wbr />
            月いくら？
          </SecHead>
          <Ranking ranked={ranked} pad={dir.key === "b"} />
        </section>

        {/* ===== 記事カード・製品・ラベル ===== */}
        <section className={s.section} aria-labelledby={`card-${dir.key}`}>
          <SecHead id={`card-${dir.key}`} no="02" kicker="記事と製品">
            最新の記事と、<wbr />
            製品まとめ
          </SecHead>
          <div className={s.duo}>
            <div>
              <p className={s.subHead}>最新の記事</p>
              <ArticleCard data={data} />
            </div>
            <div>
              {data.product && (
                <>
                  <p className={s.subHead}>製品まとめ</p>
                  <ProductRow product={data.product} usage={usage} />
                </>
              )}
              <p className={s.subHead} style={{ marginTop: 32 }}>
                ラベル
              </p>
              <Tags roundupCount={data.roundupCount} />
            </div>
          </div>
        </section>

        {/* ===== 色の設計 ===== */}
        <section className={s.section} aria-labelledby={`tokens-${dir.key}`}>
          <SecHead id={`tokens-${dir.key}`} no="03" kicker="デザイントークン">
            この案の色と形
          </SecHead>
          <Tokens dir={dir} mode={mode} />
        </section>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* ヘッダー（案ごとに組み方が違う）                                      */
/* ------------------------------------------------------------------ */

const NAV = [
  { label: "AI速報" },
  { label: "使えるAI", more: true },
  { label: "料金早見表", current: true },
  { label: "製品まとめ" },
  { label: "記事一覧", more: true },
];

function Nav() {
  return (
    <nav aria-label="メニュー（見本）" className={s.nav}>
      {NAV.map((item) => (
        <a
          key={item.label}
          href="#"
          onClick={(e) => e.preventDefault()}
          aria-current={item.current ? "page" : undefined}
          className={`${s.navItem} ${item.more ? s.navMore : ""}`}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

function Masthead({ dir, data }: { dir: Direction; data: PreviewData }) {
  const a = data.article;
  if (dir.key === "a") {
    return (
      <header>
        <div className={s.mastA}>
          <span className={s.logo}>サイソク</span>
          <Nav />
        </div>
        <div className={s.tickerA}>
          <span className={`${s.tag} ${s.tagLive}`} data-allow-small="">
            速報
          </span>
          <time className={s.num}>{time(a.publishedAt)}</time>
          <a href={`/articles/${a.slug}`}>{a.title}</a>
        </div>
      </header>
    );
  }
  if (dir.key === "b") {
    return (
      <header>
        <div className={s.statusB}>
          <span>
            <i className={s.okDot} aria-hidden />
            稼働中
          </span>
          <span>
            最終更新 <b>{time(a.publishedAt)}</b> JST
          </span>
          <span>
            記事 <b>{data.articleCount}</b>本
          </span>
          <span className={s.navMore}>
            料金 <b>{data.modelCount}</b>モデル
          </span>
        </div>
        <div className={s.mastB}>
          <span className={s.logo}>サイソク</span>
          <Nav />
          <span className={s.searchB}>
            <SearchIcon />
            記事を探す
            <kbd className={s.kbd}>⌘K</kbd>
          </span>
        </div>
      </header>
    );
  }
  return (
    <header className={s.mastC}>
      <div className={s.mastCTop}>
        <span>{dateJa.format(new Date(a.publishedAt))}</span>
        <span>海外AIの新機能が、今使えるかまで最速でわかる</span>
      </div>
      <div className={s.mastCMain}>
        <span className={s.logo}>サイソク</span>
        <Nav />
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* 数字のカウントアップ                                                 */
/* ------------------------------------------------------------------ */

function useCountUp(target: number, duration = 900): number {
  const [value, setValue] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      from.current = target;
      setValue(target);
      return;
    }
    const start = from.current;
    const t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration);
      const v = start + (target - start) * (1 - Math.pow(1 - p, 3));
      from.current = v;
      setValue(v);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}

function Count({ value, suffix = "", className }: { value: number; suffix?: string; className?: string }) {
  const v = useCountUp(value);
  return (
    <span className={className}>
      {yenDigits(v)}
      {suffix}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* 使い方                                                               */
/* ------------------------------------------------------------------ */

function UsagePanel({ usage, onUsage }: { usage: Usage; onUsage: (u: Usage) => void }) {
  const preset = PRESETS.find((p) => ACTIVITIES.every((a) => p.usage[a.key] === usage[a.key]));
  return (
    <div className={s.usage}>
      <p className={s.usageTitle}>どれくらい使う？</p>
      <div className={s.presets} role="group" aria-label="使い方の例">
        {PRESETS.map((p) => (
          <button key={p.key} type="button" className={s.preset} aria-pressed={preset?.key === p.key} onClick={() => onUsage(p.usage)}>
            {p.label}
          </button>
        ))}
      </div>
      <ul className={s.acts}>
        {ACTIVITIES.map((a) => {
          const value = usage[a.key];
          const step = value >= 20 ? 5 : 1;
          return (
            <li key={a.key} className={s.act}>
              <span className={s.actIcon} aria-hidden>
                <ActIcon kind={a.key} />
              </span>
              <span className={s.actText}>
                <span className={s.actLabel}>{a.label}</span>
                <span className={s.actPer}>{a.per === "day" ? "1日あたり" : "1か月あたり"}</span>
              </span>
              <span className={s.stepper}>
                <button
                  type="button"
                  className={s.stepBtn}
                  aria-label={`${a.label}を減らす`}
                  disabled={value <= 0}
                  onClick={() => onUsage({ ...usage, [a.key]: Math.max(0, value - step) })}
                >
                  −
                </button>
                <span className={`${s.stepVal} ${s.num}`}>
                  {value}
                  <small>{a.unit}</small>
                </span>
                <button
                  type="button"
                  className={s.stepBtn}
                  aria-label={`${a.label}を増やす`}
                  onClick={() => onUsage({ ...usage, [a.key]: Math.min(500, value + step) })}
                >
                  ＋
                </button>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 棒グラフ                                                             */
/* ------------------------------------------------------------------ */

/** 目盛りの間隔（1・2・2.5・3・4・5 × 10^n）。目盛りは常に4つ割り */
function niceStep(raw: number): number {
  const p = 10 ** Math.floor(Math.log10(raw));
  const n = raw / p;
  return ([1, 2, 2.5, 3, 4, 5, 10].find((m) => n <= m) ?? 10) * p;
}

function Ranking({ ranked, pad }: { ranked: { model: PreviewModel; jpy: number }[]; pad?: boolean }) {
  const min = ranked[0]?.jpy ?? 0;
  const max = ranked.at(-1)?.jpy ?? 0;
  // 一番長い棒の先に値を書けるよう、目盛りの最大は最高値より1割以上大きくする
  const step = max > 0 ? niceStep((max * 1.12) / 4) : 1;
  const top = step * 4;
  return (
    <div className={s.rank}>
      <ol>
        {ranked.map(({ model, jpy }, i) => {
          const best = i === 0;
          return (
            <li key={model.id} className={s.rankRow} data-best={best}>
              <span className={`${s.rankNo} ${s.num}`}>{pad ? String(i + 1).padStart(2, "0") : i + 1}</span>
              <span className={s.rankName}>
                <Chip model={model} />
                <span>
                  <span className={s.rankTitle}>{model.product}</span>
                  <span className={`${s.rankSub} ${s.num}`}>
                    入力{usd(model.input)}・出力{usd(model.output)}
                  </span>
                </span>
              </span>
              <span className={s.barCell} aria-hidden>
                <span className={s.track} style={{ ["--w" as string]: `${Math.max(0.6, (jpy / top) * 100)}%`, ["--i" as string]: i }}>
                  <span className={s.fill} />
                  <Count value={jpy} suffix="円" className={`${s.barLabel} ${s.num}`} />
                </span>
              </span>
              <span className={s.val}>
                <Count value={jpy} className={`${s.valNum} ${s.num}`} />
                {best ? (
                  <span className={s.mult}>最安</span>
                ) : (
                  <span className={`${s.mult} ${s.num}`}>最安の{Math.round(jpy / min).toLocaleString()}倍</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
      <div className={s.axis} aria-hidden>
        <span className={`${s.axisScale} ${s.num}`}>
          {[0, 1, 2, 3, 4].map((k) => (
            <span key={k} style={{ left: `${k * 25}%` }}>
              {(step * k).toLocaleString()}
              {k === 4 ? "円" : ""}
            </span>
          ))}
        </span>
      </div>
      <p className={s.rankFoot}>月額（円）・1ドル＝{RATE}円で計算</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 記事カード・製品・ラベル                                              */
/* ------------------------------------------------------------------ */

function ArticleCard({ data }: { data: PreviewData }) {
  const a = data.article;
  return (
    <a href={`/articles/${a.slug}`} className={`${s.card}`}>
      <div className={s.cover}>
        {/* カバーは報道テロップ型のまま（写真は加工しない） */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={a.cover} alt="" loading="eager" />
      </div>
      <div className={s.cardBody}>
        <p className={s.cardMeta}>
          <i className={s.coBar} style={{ background: a.companyColor }} aria-hidden />
          <b>{a.companyName}</b>
          <span className={s.num}>
            {day(a.publishedAt)} {time(a.publishedAt)}
          </span>
          <span className={`${s.tag} ${s.tagLive}`} data-allow-small="">
            {a.speed ?? "速報"}
          </span>
        </p>
        <h3 className={s.cardTitle}>{a.title}</h3>
        <p className={s.cardDesc}>{a.description}</p>
      </div>
    </a>
  );
}

function ProductRow({ product, usage }: { product: NonNullable<PreviewData["product"]>; usage: Usage }) {
  const priced = product.input !== null && product.output !== null;
  return (
    <a href={`/products/${product.slug}`} className={s.prow}>
      <span className={s.chip} style={{ background: product.color, width: 28, height: 28, fontSize: 13 }} aria-hidden data-decorative="">
        {product.mark}
      </span>
      <span className={s.prowName}>
        <strong>{product.name}</strong>
        <span>
          {product.companyName}・{product.category}
        </span>
      </span>
      <span className={s.prowArrow} aria-hidden>
        <ArrowIcon />
      </span>
      {priced && (
        <span className={`${s.prowSpec} ${s.num}`}>
          <span>
            <small>入力 </small>
            {usd(product.input)}
          </span>
          <span>
            <small>出力 </small>
            {usd(product.output)}
          </span>
          <span>
            <small>月 </small>
            <b>約{yenDigits(monthlyYen({ input: product.input!, output: product.output! }, usage))}円</b>
          </span>
          <JapanTag japan={product.japan} />
        </span>
      )}
      <span className={s.prowMeta}>
        記事<span className={s.num}>{product.articleCount}</span>本・<span className={s.num}>{day(product.updatedAt)}</span>更新
      </span>
    </a>
  );
}

function JapanTag({ japan }: { japan: Japan }) {
  if (japan === "ok")
    return (
      <span className={`${s.tag} ${s.tagOk}`} data-allow-small="">
        <CheckIcon />
        日本で使える
      </span>
    );
  if (japan === "partial")
    return (
      <span className={`${s.tag} ${s.tagPartial}`} data-allow-small="">
        日本は条件付き
      </span>
    );
  return (
    <span className={`${s.tag} ${s.tagFree}`} data-allow-small="">
      日本対応は未確認
    </span>
  );
}

function Tags({ roundupCount }: { roundupCount: number }) {
  return (
    <div className={s.tags}>
      <span className={`${s.tag} ${s.tagLive}`} data-allow-small="">
        速報
      </span>
      <span className={`${s.tag} ${s.tagBest}`} data-allow-small="">
        最安
      </span>
      <span className={`${s.tag} ${s.tagRoundup}`} data-allow-small="">
        {roundupCount > 0 ? `${roundupCount}本を統合` : "まとめ"}
      </span>
      <JapanTag japan="ok" />
      <JapanTag japan="partial" />
      <span className={`${s.tag} ${s.tagFree}`} data-allow-small="">
        無料で試せる
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 色の設計                                                             */
/* ------------------------------------------------------------------ */

const SHOWN: { key: keyof Direction["light"]; label: string }[] = [
  { key: "bg", label: "bg 地" },
  { key: "surface", label: "surface 面" },
  { key: "ink", label: "ink 文字" },
  { key: "ink-soft", label: "ink-soft 本文" },
  { key: "muted", label: "muted 補足" },
  { key: "line", label: "line 罫線" },
  { key: "accent", label: "accent" },
  { key: "accent-fill", label: "accent-fill 棒" },
  { key: "accent-soft", label: "accent-soft" },
  { key: "live", label: "live 速報" },
  { key: "positive", label: "positive 可" },
  { key: "caution", label: "caution 注意" },
];

function Tokens({ dir, mode }: { dir: Direction; mode: Mode }) {
  const t = dir[mode];
  return (
    <>
      <div className={s.tokens}>
        {SHOWN.map((x) => (
          <div key={x.key} className={s.token}>
            <span className={s.swatch} style={{ background: t[x.key] }} aria-hidden />
            <span>
              <span className={s.tokenName}>{x.label}</span>
              <span className={s.tokenHex}>{t[x.key]}</span>
            </span>
          </div>
        ))}
      </div>
      <p className={s.shapeRow}>
        <span>
          角丸 <b className={s.num}>{dir.shape["radius-sm"]} / {dir.shape["radius-md"]} / {dir.shape["radius-lg"]}</b>
        </span>
        <span>
          罫線 <b className={s.num}>{dir.shape.rule}</b>
        </span>
        <span>
          数字 <b>{dir.key === "b" ? "Martian Mono（等幅）" : "Noto Sans JP（等幅数字）"}</b>
        </span>
        <span>
          影 <b>{dir.shape.shadow === "none" ? "なし（罫線で区切る）" : "1段・ホバーで持ち上げ"}</b>
        </span>
      </p>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* 小さな部品                                                           */
/* ------------------------------------------------------------------ */

function SecHead({ id, no, kicker, note, children }: { id: string; no: string; kicker: string; note?: string; children: React.ReactNode }) {
  return (
    <div className={s.secHead}>
      <p className={s.secKicker}>
        <b className={s.num}>{no}</b>
        {kicker}
      </p>
      <h2 id={id} className={s.h2}>
        {children}
      </h2>
      {note && <p className={`${s.secNote} text-note`}>{note}</p>}
    </div>
  );
}

function Chip({ model }: { model: PreviewModel }) {
  return (
    <span className={s.chip} style={{ background: model.color }} aria-hidden data-decorative="">
      {model.mark}
    </span>
  );
}

const icon = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function ActIcon({ kind }: { kind: string }) {
  if (kind === "chat")
    return (
      <svg {...icon}>
        <path d="M4 5h16v11H9l-5 4z" />
        <path d="M8 9.5h8M8 12.5h5" />
      </svg>
    );
  if (kind === "summary")
    return (
      <svg {...icon}>
        <path d="M6 3h9l4 4v14H6z" />
        <path d="M14 3v5h5M9 12h7M9 16h5" />
      </svg>
    );
  if (kind === "blog")
    return (
      <svg {...icon}>
        <path d="M4 20h4L19 9l-4-4L4 16z" />
        <path d="M13.5 6.5l4 4" />
      </svg>
    );
  return (
    <svg {...icon}>
      <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
      <circle cx="9" cy="10" r="1.8" />
      <path d="M4 18l5-5 4 4 3-3 4 4" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg {...icon} width={20} height={20}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg {...icon} width={12} height={12} strokeWidth={2.6}>
      <path d="M4 12.5l5 5L20 6" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg {...icon} width={15} height={15}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4.5 4.5" />
    </svg>
  );
}
