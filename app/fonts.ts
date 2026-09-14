import { Dela_Gothic_One, Martian_Mono, Zen_Kaku_Gothic_New } from "next/font/google";

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

/** 見出し。極太なので使いどころを絞る */
export const dela = Dela_Gothic_One({
  weight: "400",
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-dela",
});

/** 時刻・件数・統合本数 */
export const martian = Martian_Mono({
  weight: ["400", "600"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-martian",
});
