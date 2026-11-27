"use client";

import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { AD_SLOT_EVENT } from "@/lib/ad-seen";

const noop = () => () => {};
const clientVariant = (): "a" | "b" => {
  try {
    return document.documentElement.getAttribute("data-adv") === "b" ? "b" : "a";
  } catch {
    return "a";
  }
};
const serverVariant = () => null;

/**
 * 計算ツールの結果の下の PR（pos "tool-result"）の A/B を、1ページに1つだけ置く（2026-11-27）。
 * オーナーのルール W10（2026-11-03）「同じ広告の枠は1ページに1つまで（見えていない方も数える）」:
 *   A と B を両方 HTML に入れて CSS で片方を隠すと、枠が2つになり、提携先の表示の画像（Pixels）も2回読まれる。
 * <html data-adv="a|b">（app/layout.tsx の最初のスクリプト。?adv=a|b で固定）を読み、選ばれた方だけを描く。
 * サーバーの HTML は空の枠だけ（data-aff-pos なし）。高さは app/globals.css の .tool-ad-slot:empty で A・B ごとに先に取り、画面がずれないようにする。
 */
export default function ToolAdSlot({ a, b }: { a: ReactNode; b: ReactNode }) {
  const variant = useSyncExternalStore(noop, clientVariant, serverVariant);
  useEffect(() => {
    if (!variant) return;
    try {
      window.dispatchEvent(new Event(AD_SLOT_EVENT));
    } catch {
      /* 計測は表示を止めない */
    }
  }, [variant]);
  return (
    <div className="tool-ad-slot" data-tool-ad-slot={variant ?? ""}>
      {variant === "b" ? b : variant === "a" ? a : null}
    </div>
  );
}
