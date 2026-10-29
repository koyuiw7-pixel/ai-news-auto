import { Martian_Mono } from "next/font/google";

// 本文の Noto Sans JP は next/font を使わず、必要な端末だけ後から読む（app/layout.tsx の先頭のスクリプト）
import localFont from "next/font/local";

/**
 * ロゴ「サイソク」と決まった見出しだけに使う極太。
 * Google Fonts のままだと @font-face が 120 個以上（全ページで描画を止める CSS が約 30KB）になるため、
 * 使う文字（英数字・かな・一部の漢字）だけに絞った版を同梱する（scripts/subset_dela_font.py で作る）
 */
export const dela = localFont({
  src: "./_fonts/dela-gothic-one-subset.woff2",
  weight: "400",
  display: "swap",
  preload: false,
  variable: "--font-dela",
});

/** 時刻・件数・統合本数。小さい数字だけなので先読みはせず、LCP の画像・CSS に回線を譲る */
export const martian = Martian_Mono({
  weight: ["400", "600"],
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-martian",
});
