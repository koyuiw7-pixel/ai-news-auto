"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { PUSH_RULES, VAPID_PUBLIC_KEY } from "@/lib/push-config";

/**
 * 速報のプッシュ通知の登録（自前。送信は cloudflare/push.ts、表示は public/sw.js）。
 *
 * - ページを開いただけでは許可を求めない。ボタンを押したときだけ Notification.requestPermission() を呼ぶ
 * - 状態: 未登録 / 登録済み（解除できる）/ ブロック中（直し方を案内）/ iPhone の Safari（ホーム画面に追加の案内）
 * - ヘッダーの鈴（PushBell）と記事末の欄（PushOptIn）は同じ状態を共有する
 */

type State = "init" | "idle" | "working" | "leaving" | "subscribed" | "denied" | "ios" | "unsupported" | "error";

// ---------------------------------------------------------------------------
// 状態（ページ内で1つ）
// ---------------------------------------------------------------------------

let state: State = "init";
const listeners = new Set<() => void>();
let started = false;
/** 最後にサーバーへ購読を届けた時刻（端末の購読が変わっていても7日に1回は届け直す） */
const SYNC_KEY = "push-synced-at";
const shownAt = typeof window === "undefined" ? 0 : Date.now();

function setState(next: State) {
  state = next;
  listeners.forEach((l) => l());
}

function subscribeStore(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function isIos(): boolean {
  const ua = navigator.userAgent;
  return /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function supported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const b64 = base64url.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((base64url.length + 3) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(bin.length));
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function readSynced(): number {
  try {
    return Number(localStorage.getItem(SYNC_KEY) ?? 0);
  } catch {
    return 0;
  }
}

function writeSynced(value: number | null) {
  try {
    if (value === null) localStorage.removeItem(SYNC_KEY);
    else localStorage.setItem(SYNC_KEY, String(value));
  } catch {
    // 保存できなくても動く
  }
}

async function postSubscription(sub: PushSubscription, ts: number): Promise<boolean> {
  const res = await fetch("/api/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subscription: sub.toJSON(), ts }),
  });
  return res.ok;
}

async function start() {
  if (started) return;
  started = true;
  if (!supported()) {
    // iPhone の Safari は「ホーム画面に追加」したときだけ通知を使える
    setState(isIos() ? "ios" : "unsupported");
    return;
  }
  if (Notification.permission === "denied") {
    setState("denied");
    return;
  }
  try {
    const reg = await navigator.serviceWorker.getRegistration("/");
    const sub = Notification.permission === "granted" ? await reg?.pushManager.getSubscription() : null;
    setState(sub ? "subscribed" : "idle");
    // 端末の購読がサーバーから消えていても（送り先の変更など）、ときどき届け直して直す
    if (sub && Date.now() - readSynced() > 7 * 86_400_000) {
      if (await postSubscription(sub, 0)) writeSynced(Date.now());
    }
  } catch {
    setState("idle");
  }
}

async function enable() {
  setState("working");
  try {
    // ボタンを押した直後に呼ぶ（Safari は操作の直後でないと許可の確認を出さない）
    const permission = await Notification.requestPermission();
    if (permission === "denied") return setState("denied");
    if (permission !== "granted") return setState("idle");
    const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    await navigator.serviceWorker.ready;
    const sub =
      (await reg.pushManager.getSubscription()) ??
      (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(VAPID_PUBLIC_KEY) }));
    if (!(await postSubscription(sub, shownAt))) {
      await sub.unsubscribe().catch(() => {});
      return setState("error");
    }
    writeSynced(Date.now());
    setState("subscribed");
  } catch {
    setState(typeof Notification !== "undefined" && Notification.permission === "denied" ? "denied" : "error");
  }
}

async function disable() {
  setState("leaving");
  try {
    const reg = await navigator.serviceWorker.getRegistration("/");
    const sub = await reg?.pushManager.getSubscription();
    if (sub) {
      const json = sub.toJSON();
      await fetch("/api/push/unsubscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: json.endpoint, auth: json.keys?.auth }),
      }).catch(() => {});
      await sub.unsubscribe();
    }
    writeSynced(null);
    setState("idle");
  } catch {
    setState("error");
  }
}

function usePushState(): State {
  const current = useSyncExternalStore(subscribeStore, () => state, () => "init" as State);
  useEffect(() => {
    start();
  }, []);
  return current;
}

// ---------------------------------------------------------------------------
// 見た目
// ---------------------------------------------------------------------------

function BellIcon({ filled = false, size = 16 }: { filled?: boolean; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden className="shrink-0">
      <path
        d="M12 3.5a5.5 5.5 0 0 0-5.5 5.5v3.3c0 .8-.3 1.6-.8 2.2L4.5 16h15l-1.2-1.5a3.5 3.5 0 0 1-.8-2.2V9A5.5 5.5 0 0 0 12 3.5Z"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M9.8 19a2.3 2.3 0 0 0 4.4 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

/** 決まりごとの1文（時刻の途中で改行しない） */
function RuleText() {
  return (
    <>
      主要企業の大きな発表だけ、1日{PUSH_RULES.perDay}回まで。
      <span className="whitespace-nowrap">
        夜{PUSH_RULES.quietFrom}時〜朝{PUSH_RULES.quietUntil}時
      </span>
      は鳴らしません。
    </>
  );
}

const BUTTON =
  "inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-md border border-accent bg-paper px-4 text-note font-bold text-accent transition-colors hover:bg-accent hover:text-accent-ink disabled:opacity-60";
const QUIET_BUTTON =
  "inline-flex h-9 shrink-0 items-center rounded-md border border-line-strong px-3 text-meta font-bold text-ink-soft transition-colors hover:border-accent hover:text-accent disabled:opacity-60";

/** 状態ごとの中身（記事末の欄とヘッダーの吹き出しで共通） */
function Body({ current, compact }: { current: State; compact?: boolean }) {
  const busy = current === "working" || current === "leaving";
  if (current === "ios") {
    return (
      <div>
        <p className="text-desc font-bold leading-[1.7] text-ink">iPhoneは「ホーム画面に追加」すると通知を受け取れます</p>
        <ol className="mt-2 space-y-1.5 text-note leading-[1.75] text-ink-soft">
          <li className="grid grid-cols-[1.4em_minmax(0,1fr)]">
            <span className="index-num font-bold text-accent">1</span>
            <span>Safariの共有ボタン（四角から矢印が出たマーク）を押し、「ホーム画面に追加」を選ぶ</span>
          </li>
          <li className="grid grid-cols-[1.4em_minmax(0,1fr)]">
            <span className="index-num font-bold text-accent">2</span>
            <span>ホーム画面の「サイソク」を開き、ここの「速報を通知で受け取る」を押す</span>
          </li>
        </ol>
      </div>
    );
  }
  if (current === "unsupported") {
    return (
      <p className="text-note leading-[1.75] text-ink-soft">
        このブラウザは通知に対応していません。毎朝の
        <Link href="/newsletter" className="underline underline-offset-2 hover:text-accent">
          メール配信
        </Link>
        もご利用ください。
      </p>
    );
  }
  if (current === "denied") {
    return (
      <p role="status" className="border-l-2 border-live pl-3 text-note leading-[1.75] text-ink-soft">
        <span className="font-bold text-ink">通知がブロックされています。</span>
        アドレスバー左のアイコン（サイトの設定）で「通知」を「許可」に変えると受け取れます。
      </p>
    );
  }
  if (current === "subscribed" || current === "leaving") {
    return (
      <div className={`flex flex-wrap items-center gap-x-4 gap-y-2 ${compact ? "" : "sm:justify-between"}`}>
        <p role="status" className="flex items-center gap-2 text-note font-bold text-ink">
          <span className="text-accent">
            <BellIcon filled />
          </span>
          速報の通知を受け取る設定です
        </p>
        <button type="button" onClick={disable} disabled={busy} className={QUIET_BUTTON}>
          通知を解除する
        </button>
      </div>
    );
  }
  return (
    <div>
      <button type="button" onClick={enable} disabled={busy} className={BUTTON}>
        <BellIcon />
        {busy ? "設定中…" : "速報を通知で受け取る"}
      </button>
      {current === "error" && (
        <p role="alert" className="mt-2 text-meta text-live">
          登録できませんでした。時間をおいてお試しください。
        </p>
      )}
    </div>
  );
}

/** 記事末・/newsletter に置く欄。page は見出しをページ側に任せる */
export default function PushOptIn({ variant = "article" }: { variant?: "article" | "page" }) {
  const current = usePushState();
  if (variant === "page") {
    return (
      <div className="mt-4">
        <Body current={current} />
      </div>
    );
  }
  return (
    <section aria-labelledby="push-article" className="mt-6 max-w-[46em] rounded-lg border border-line bg-surface px-5 py-4">
      <h3 id="push-article" className="t-card">
        大きな速報を、通知ですぐに
      </h3>
      <p className="mt-1 text-note leading-[1.75] text-ink-soft">
        <RuleText />
        いつでも解除できます。
      </p>
      <div className="mt-3">
        <Body current={current} />
      </div>
    </section>
  );
}

/** ヘッダー下の速報の1行の右端に置く鈴。押すと小さな吹き出しで説明してから登録する */
export function PushBell() {
  const current = usePushState();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent | TouchEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // 通知が使えないブラウザ（iPhone 以外）には出さない
  if (current === "unsupported") return null;
  const on = current === "subscribed";

  return (
    <div ref={box} className="relative ml-auto shrink-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="push-bell-panel"
        aria-label={on ? "速報の通知（受け取る設定）" : "速報を通知で受け取る"}
        className={`flex h-9 items-center gap-1.5 rounded-[3px] px-2 text-meta font-bold transition-colors hover:text-accent ${on ? "text-accent" : "text-ink-soft"}`}
      >
        <BellIcon filled={on} />
        <span className="hidden sm:inline">{on ? "通知オン" : "速報を通知"}</span>
      </button>
      {open && (
        <div
          id="push-bell-panel"
          role="dialog"
          aria-label="速報の通知"
          className="absolute right-0 top-[calc(100%+6px)] z-40 w-[min(340px,calc(100vw-32px))] rounded-lg border border-line bg-paper p-4 shadow-[var(--shadow-lift)]"
        >
          {current !== "ios" && (
            <>
              <p className="text-desc font-bold text-ink">大きな速報を、通知ですぐに</p>
              <p className="mt-1 text-note leading-[1.75] text-ink-soft">
                <RuleText />
              </p>
            </>
          )}
          <div className={current !== "ios" ? "mt-3" : ""}>
            <Body current={current} compact />
          </div>
        </div>
      )}
    </div>
  );
}
