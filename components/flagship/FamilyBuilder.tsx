"use client";

import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import {
  CHILD_ALLOWANCE_AMOUNTS,
  childAllowance,
  familyCounts,
  nextPaymentMonth,
  remainingTotal,
  statusByBirth,
  statusLabel,
  tokyoYearMonth,
  ymJa,
  type ChildCategory,
  type ChildInput,
  type ChildMonth,
  type YearMonth,
} from "@/lib/child-allowance";
import { yen } from "@/lib/calc-math";
import type { NextLink } from "@/lib/flagship";
import CountUp from "@/components/flagship/CountUp";
import ShareCard from "@/components/flagship/ShareCard";

/**
 * 特集の中の「うちの子ども」（lib/child-allowance.ts の式だけを使う。金額をここで作らない）。
 * 子どもを足すと、第何子か・1か月の合計・次の支給（月と額）・1年分・次の6回の支給が、その場で出る。
 * 入力はこの画面の中の計算だけに使い、送信・保存はしない。
 */
type Mode = "category" | "birth";
type Kid =
  | { key: number; kind: "category"; category: ChildCategory }
  | { key: number; kind: "birth"; year: number; month: number; supported: boolean };

const MAX = 8;
const FIRST_YEAR = 2003;
const QUICK: { category: ChildCategory; label: string; hint: string }[] = [
  { category: "under3", label: "3歳未満", hint: "月1万5,000円（第3子以降は3万円）" },
  { category: "from3", label: "3歳〜高校生年代", hint: "月1万円（第3子以降は3万円）" },
  { category: "olderSupported", label: "大学生年代（生活費を負担）", hint: "手当はなし。数には入る" },
];
const CATEGORY_ORDER: Record<ChildCategory, number> = { olderSupported: 0, olderNotSupported: 0, from3: 1, under3: 2 };
const CATEGORY_LABEL: Record<ChildCategory, string> = {
  under3: "3歳未満",
  from3: "3歳〜高校生年代",
  olderSupported: "大学生年代（生活費を負担）",
  olderNotSupported: "大学生年代（負担なし）",
};

const toInput = (kid: Kid): ChildInput =>
  kid.kind === "category" ? { kind: "category", category: kid.category } : { kind: "birth", year: kid.year, month: kid.month, supported: kid.supported };
const ymIndex = (ym: YearMonth) => ym.year * 12 + ym.month - 1;
const sortKey = (kid: Kid) => (kid.kind === "category" ? CATEGORY_ORDER[kid.category] : kid.year * 12 + kid.month);

function rankText(row: ChildMonth): string {
  if (row.status === "notBorn") return "予定";
  if (row.rank === null) return "数に入らない";
  return `第${row.rank}子`;
}

export default function FamilyBuilder({
  asOf,
  next,
  adSlot,
  shareTitle,
  shareNote,
  shareUrl,
}: {
  /** ページを作った日の年月（サーバーの HTML と最初の描画で使う。描いたあとは日本時間の今日に合わせる） */
  asOf: YearMonth;
  next: NextLink[];
  adSlot?: ReactNode;
  shareTitle: string;
  shareNote: string;
  shareUrl: string;
}) {
  const id = useId();
  const [today, setToday] = useState<YearMonth>(asOf);
  const [mode, setMode] = useState<Mode>("category");
  const [kids, setKids] = useState<Kid[]>([]);
  const [nextKey, setNextKey] = useState(1);
  const [year, setYear] = useState("");
  const [month, setMonth] = useState("");
  const [supported, setSupported] = useState(true);
  const [resultSeen, setResultSeen] = useState(true);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const now = tokyoYearMonth();
    if (ymIndex(now) > ymIndex(asOf)) setToday(now);
  }, [asOf]);

  // スマホの下の小さな合計: 結果の欄を通り過ぎた（画面より上に行った）ときだけ出す。位置は固定なので、ほかの部分を押し下げない（CLS）。
  // IntersectionObserver は一気に飛ぶスクロール（目次のリンクなど）で「見えた」を通らず変化を拾えないので、スクロールのたびに位置で決める
  useEffect(() => {
    const el = resultRef.current;
    if (!el) return;
    let raf = 0;
    const check = () => {
      raf = 0;
      setResultSeen(el.getBoundingClientRect().bottom > 72);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(check);
    };
    check();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  const shown = kids.filter((kid) => (mode === "category" ? kid.kind === "category" : kid.kind === "birth"));
  const ordered = [...shown].sort((a, b) => sortKey(a) - sortKey(b) || a.key - b.key);
  const inputs = ordered.map(toInput);
  const pay = nextPaymentMonth(today);
  const result = inputs.length > 0 ? childAllowance(inputs, pay) : null;
  const latest = result?.next.months[1] ?? null;
  const counts = result && latest ? familyCounts(inputs, latest) : null;
  const hasThird = Boolean(result?.children.some((c) => c.rank !== null && c.rank >= 3 && c.amount > 0));
  const remaining = useMemo(
    () => (result && mode === "birth" ? remainingTotal(inputs, result.next.months[0]) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [result?.next.amount, result?.year.total, mode, JSON.stringify(inputs)],
  );
  const maxPayment = result ? Math.max(...result.year.payments.map((p) => p.amount), 1) : 1;
  const newborn = ordered.some((kid) => kid.kind === "birth" && ymIndex({ year: kid.year, month: kid.month }) >= ymIndex(today) - 12);
  const links = [...next.filter((n) => n.when === "newborn" && newborn), ...next.filter((n) => n.when === "always"), ...next.filter((n) => n.when === "newborn" && !newborn)];

  const lastYear = today.year + 1;
  const years = Array.from({ length: lastYear - FIRST_YEAR + 1 }, (_, i) => lastYear - i);
  const draftOlder =
    year && month
      ? [today, { year: today.year + 1, month: today.month }].some((ym) => statusByBirth({ year: Number(year), month: Number(month), supported: true }, ym) === "olderCounted")
      : false;

  const addCategory = (category: ChildCategory) => {
    if (shown.length >= MAX) return;
    setKids((list) => [...list, { key: nextKey, kind: "category", category }]);
    setNextKey((n) => n + 1);
  };
  const addBirth = () => {
    if (!year || !month || shown.length >= MAX) return;
    setKids((list) => [...list, { key: nextKey, kind: "birth", year: Number(year), month: Number(month), supported: draftOlder ? supported : false }]);
    setNextKey((n) => n + 1);
    setYear("");
    setMonth("");
  };
  const remove = (key: number) => setKids((list) => list.filter((kid) => kid.key !== key));
  const tryExample = () => {
    setMode("category");
    setKids((list) => [
      ...list.filter((kid) => kid.kind === "birth"),
      { key: nextKey, kind: "category", category: "from3" },
      { key: nextKey + 1, kind: "category", category: "from3" },
      { key: nextKey + 2, kind: "category", category: "under3" },
    ]);
    setNextKey((n) => n + 3);
  };

  const kidLabel = (kid: Kid) =>
    kid.kind === "category" ? CATEGORY_LABEL[kid.category] : `${kid.year}年${kid.month}月生まれ${kid.supported ? "（生活費を負担）" : ""}`;
  const statusOf = (kid: Kid, row: ChildMonth) => {
    if (row.status === "notBorn") return "生まれた月の次の月から対象";
    if (kid.kind === "category") {
      if (row.status === "olderCounted") return "手当はなし。第3子の数え方に入る";
      if (row.status === "olderNotCounted") return "手当はなく、数にも入らない";
      return row.rank !== null && row.rank >= 3 ? "第3子以降の額（年齢に関係なし）" : "第1子・第2子の額";
    }
    return statusLabel(row).replace(/^第\d+子・/, "").replace(/^第\d+子として数える/, "数に入る");
  };

  const familyText = counts
    ? `子ども${counts.children}人${counts.expected > 0 ? `・出産予定${counts.expected}人` : ""}${counts.thirdOrLater > 0 ? `・第3子以降${counts.thirdOrLater}人` : ""}`
    : "";
  const liveText = result ? `次の支給は${ymJa(pay)}、${yen(result.next.amount)}。1か月の合計${yen(result.monthly)}、1年分${yen(result.year.total)}。` : "";

  return (
    <div className="fs-builder" data-flagship-builder="">
      <div className="fs-builder-grid">
        {/* 入れる側 */}
        <div className="fs-compose">
          <fieldset className="fs-seg">
            <legend className="fs-label">子どもの入れ方</legend>
            <div className="fs-seg-row">
              {(
                [
                  { value: "category", label: "年齢の区分で" },
                  { value: "birth", label: "生まれた年月で" },
                ] as const
              ).map((option) => (
                <label key={option.value} className="fs-seg-opt" data-on={mode === option.value ? "" : undefined}>
                  <input type="radio" name={`${id}-mode`} value={option.value} checked={mode === option.value} onChange={() => setMode(option.value)} className="sr-only" />
                  {option.label}
                </label>
              ))}
            </div>
          </fieldset>

          {mode === "category" ? (
            <div className="fs-quick" role="group" aria-label="子どもを足す（年齢の区分）">
              {QUICK.map((q) => (
                <button key={q.category} type="button" className="fs-chip-add" onClick={() => addCategory(q.category)} disabled={shown.length >= MAX}>
                  <span className="fs-chip-plus" aria-hidden="true">＋</span>
                  <span>
                    <b>{q.label}</b>
                    <small>{q.hint}</small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="fs-birth">
              <div className="fs-birth-row">
                <div>
                  <label htmlFor={`${id}-y`} className="fs-label">生まれた年（予定も可）</label>
                  <select id={`${id}-y`} value={year} onChange={(e) => setYear(e.target.value)} className="fs-input">
                    <option value="">選ぶ</option>
                    {years.map((y) => (
                      <option key={y} value={y}>{`${y}年`}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`${id}-m`} className="fs-label">生まれた月</label>
                  <select id={`${id}-m`} value={month} onChange={(e) => setMonth(e.target.value)} className="fs-input">
                    <option value="">選ぶ</option>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                      <option key={m} value={m}>{`${m}月`}</option>
                    ))}
                  </select>
                </div>
              </div>
              {draftOlder ? (
                <label className="fs-check">
                  <input type="checkbox" checked={supported} onChange={(e) => setSupported(e.target.checked)} />
                  <span>親が生活費を負担している（学生でなくてもかまいません。22歳の年度末まで）</span>
                </label>
              ) : null}
              <button type="button" className="fs-btn fs-btn-primary fs-birth-add" onClick={addBirth} disabled={!year || !month || shown.length >= MAX}>
                ＋ この子を足す
              </button>
            </div>
          )}
          <p className="fs-hint">
            {mode === "category"
              ? "大学生年代の上の子も入れてください。手当は出ませんが、生活費を負担していれば第3子の数え方に入ります。"
              : "年齢が上がって額が変わる月まで計算します。出産予定の月を入れると、生まれた月の次の月から数えます。"}
          </p>

          {ordered.length > 0 ? (
            <ol className="fs-kids" aria-label="入れた子ども（上の子から）">
              {ordered.map((kid, i) => {
                const row = result?.children[i];
                if (!row) return null;
                const third = row.rank !== null && row.rank >= 3 && row.amount > 0;
                return (
                  <li key={kid.key} className="fs-kid" data-third={third ? "" : undefined} data-rank={row.rank ?? "none"}>
                    <span className="fs-rank" data-none={row.rank === null ? "" : undefined}>{rankText(row)}</span>
                    <span className="fs-kid-main">
                      <b>{kidLabel(kid)}</b>
                      <small>{statusOf(kid, row)}</small>
                    </span>
                    <span className="fs-kid-amt">{row.amount > 0 ? `月${yen(row.amount)}` : "0円"}</span>
                    <button type="button" className="fs-kid-x" onClick={() => remove(kid.key)} aria-label={`${rankText(row)}（${kidLabel(kid)}）を消す`}>
                      消す
                    </button>
                  </li>
                );
              })}
            </ol>
          ) : (
            <div className="fs-empty">
              <p>上のボタンで子どもを足すと、右（スマホでは下）にうちの結果が出ます。</p>
              <button type="button" className="fs-btn" onClick={tryExample}>
                例で試す（小学生2人と3歳未満）
              </button>
            </div>
          )}
        </div>

        {/* 結果 */}
        <div className="fs-result" ref={resultRef} id="flagship-result" data-flagship-result="" data-state={result ? "ready" : "empty"}>
          <p className="sr-only" aria-live="polite">{liveText}</p>
          <div className="fs-result-top">
            <span className="fs-eyebrow">次の支給</span>
            <span className="fs-when">{result ? `${ymJa(pay)}（${result.next.months[0].month}月・${result.next.months[1].month}月分）` : `${ymJa(pay)}`}</span>
          </div>
          <div className="fs-big">
            <CountUp value={result?.next.amount ?? 0} format={(n) => n.toLocaleString("ja-JP")} className="fs-big-num" />
            <span className="fs-big-unit">円</span>
          </div>
          <dl className="fs-pair">
            <div>
              <dt>1か月の合計{latest ? `（${latest.month}月分）` : ""}</dt>
              <dd>
                <CountUp value={result?.monthly ?? 0} format={(n) => yen(n)} />
              </dd>
            </div>
            <div>
              <dt>1年分（支給6回）</dt>
              <dd>
                <CountUp value={result?.year.total ?? 0} format={(n) => yen(n)} />
              </dd>
            </div>
          </dl>
          {hasThird ? (
            <p className="fs-third-note">第3子以降の月{yen(CHILD_ALLOWANCE_AMOUNTS.third)}が入っています。</p>
          ) : result && counts && counts.counted === 2 ? (
            <p className="fs-third-note" data-quiet="">次に生まれる子は第3子になり、月{yen(CHILD_ALLOWANCE_AMOUNTS.third)}です（上の子が数に入っている間）。</p>
          ) : null}

          <div className="fs-timeline" aria-label="これからの6回の支給">
            <p className="fs-eyebrow">これからの6回</p>
            <ol>
              {(result?.year.payments ?? Array.from({ length: 6 }, (_, k) => ({ pay: { year: 0, month: 0 }, months: [{ year: 0, month: 0 }, { year: 0, month: 0 }], amount: 0, k }))).map((p, k) => {
                const label = result ? `${p.pay.year !== pay.year && p.pay.month <= 2 ? `${p.pay.year}年` : ""}${p.pay.month}月` : "";
                const width = result ? Math.max(2, Math.round((p.amount / maxPayment) * 100)) : 0;
                return (
                  <li key={k}>
                    <span className="fs-tl-m">{result ? label : "　"}</span>
                    <span className="fs-tl-bar" aria-hidden="true">
                      <i style={{ width: `${width}%`, transitionDelay: `${k * 60}ms` }} />
                    </span>
                    <span className="fs-tl-v">{result ? yen(p.amount) : "　"}</span>
                  </li>
                );
              })}
            </ol>
          </div>

          {remaining && remaining.last ? (
            <p className="fs-remaining">
              今の制度が変わらず、生活費の負担なども今のままなら、これから受け取る合計は<b>{yen(remaining.total)}</b>（{result ? `${ymJa(result.next.months[0])}分から` : ""}{ymJa(remaining.last)}分まで）です。
            </p>
          ) : mode === "category" && result ? (
            <p className="fs-hint">生まれた年月で入れると、年齢で額が変わる月と、これから受け取る合計まで出ます。</p>
          ) : null}
          <p className="fs-hint">支給日の日にちは市区町村ごとに違います。入れた内容は送信も保存もしません。</p>
        </div>
      </div>

      {result && counts ? (
        <ShareCard
          data={{
            title: shareTitle,
            family: familyText,
            nextLabel: `${ymJa(pay)}の支給`,
            next: yen(result.next.amount),
            monthly: yen(result.monthly),
            year: yen(result.year.total),
            note: shareNote,
            url: shareUrl,
          }}
        />
      ) : null}

      {/* 結果につながる次の一歩（サイト内）と、広告の枠1つ */}
      <section className="fs-nextstep" aria-labelledby={`${id}-next`}>
        <h3 id={`${id}-next`} className="fs-h3">{result ? "この結果の次に確かめること" : "子育ての家が12月に確かめること"}</h3>
        <ul className="fs-next-list">
          {links.map((link) => (
            <li key={link.href}>
              <Link href={link.href} className="fs-next-link" data-money-link="">
                <b>{link.label}</b>
                <small>{link.why}</small>
              </Link>
            </li>
          ))}
        </ul>
        {adSlot ? <div className="fs-ad">{adSlot}</div> : null}
      </section>

      {/* スマホの下の小さな合計 */}
      {result ? (
        <div className="fs-dock" data-show={!resultSeen ? "" : undefined} aria-hidden={resultSeen}>
          <span className="fs-dock-txt">
            <small>{`${pay.month}月の支給`}</small>
            <b>{yen(result.next.amount)}</b>
          </span>
          <span className="fs-dock-txt">
            <small>1か月</small>
            <b>{yen(result.monthly)}</b>
          </span>
          <button
            type="button"
            className="fs-dock-btn"
            tabIndex={resultSeen ? -1 : 0}
            onClick={() => resultRef.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" })}
          >
            結果を見る
          </button>
        </div>
      ) : null}
    </div>
  );
}
