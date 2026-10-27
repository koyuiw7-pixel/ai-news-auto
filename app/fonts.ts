import { Martian_Mono, Noto_Sans_JP } from "next/font/google";
import localFont from "next/font/local";

/*
 * 日本語フォントは next/font の subsets に "japanese" が無いため、
 * preload を切って全ての文字範囲を自前配信する（読み込みは unicode-range で必要分だけ）。
 */

/**
 * 本文・見出し・UI。線がしっかりしていて小さくてもかすれない Noto Sans JP（デジタル庁デザインシステムの本文書体）。
 * 太さを指定しない＝可変フォント1本で 400〜900 を賄う。太さを列挙しても Google は同じ可変フォントのファイルを返すため、
 * 列挙すると @font-face が太さの数だけ増えて CSS が重くなるだけ（3太さで 47KB→113KB、2026-10-27 計測）。
 * 旧 Zen Kaku Gothic New は 400 の線が細く「文字が見えない」と言われたため替えた（docs/typography.md）
 */
export const noto = Noto_Sans_JP({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-noto",
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
