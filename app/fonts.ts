import { Martian_Mono, Zen_Kaku_Gothic_New } from "next/font/google";
import localFont from "next/font/local";

/*
 * 日本語フォントは next/font の subsets に "japanese" が無いため、
 * preload を切って全ての文字範囲を自前配信する（読み込みは unicode-range で必要分だけ）。
 */

/** 本文 */
export const zen = Zen_Kaku_Gothic_New({
  weight: ["400", "500", "700", "900"],
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-zen",
});

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
