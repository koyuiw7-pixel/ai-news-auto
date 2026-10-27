/**
 * Cloudflare ビルド用の sharp の代役（next.config.ts の resolveAlias で差し替える）。
 * ビルド時の事前生成（Node）では本物の sharp を使い、Workers（sharp は動かない）では呼ぶと例外を投げる。
 * 呼び出し側はどちらも例外時の代わりの描き方を持っている。
 */
type Sharp = typeof import("sharp");

let real: Sharp | null = null;
try {
  // バンドラーに辿らせないため、実行時に createRequire で読む（Workers では失敗して null のまま）
  const { createRequire } = process.getBuiltinModule("node:module") as typeof import("node:module");
  real = createRequire(`${/*turbopackIgnore: true*/ process.cwd()}/package.json`)("sharp") as Sharp;
} catch {
  real = null;
}

function sharp(...args: Parameters<Sharp>): ReturnType<Sharp> {
  if (!real) throw new Error("sharp is not available on this runtime");
  return real(...args);
}
sharp.strategy = real?.strategy ?? ({ entropy: 16, attention: 17 } as Sharp["strategy"]);

export default sharp as unknown as Sharp;
