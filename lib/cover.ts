import sharp from "sharp";

/**
 * カバー画像の背景づくり（写真の取得・切り抜き・陰影・すりガラス）。
 * 文字の配置は app/cover/[slug]/route.tsx 側で行う。
 */
export const COVER_WIDTH = 1200;
export const COVER_HEIGHT = 630;

export type Box = { x: number; y: number; width: number; height: number };

/** 大きすぎる画像は読まない（外部サイトの og:image 対策） */
const MAX_PHOTO_BYTES = 15 * 1024 * 1024;

/**
 * 元動画（または元記事の og:image）の画像を取得する。
 * YouTube は消えていれば標準画質へ。取得できない・画像でない・sharp で読めないものは null
 */
export async function fetchPhoto(url: string): Promise<Buffer | null> {
  if (!url || !/^https?:\/\//.test(url)) return null;
  const candidates = url.includes("maxresdefault")
    ? [url, url.replace("maxresdefault", "hqdefault")]
    : [url];
  for (const candidate of candidates) {
    try {
      const res = await fetch(candidate, {
        signal: AbortSignal.timeout(8000),
        // 既定の UA だと画像を返さないサイトがある
        headers: { "User-Agent": "Mozilla/5.0 (compatible; SaisokuCoverBot/1.0)", Accept: "image/*" },
      });
      if (!res.ok) continue;
      const type = res.headers.get("content-type") ?? "";
      if (type && !type.startsWith("image/")) continue;
      if (Number(res.headers.get("content-length") ?? 0) > MAX_PHOTO_BYTES) continue;
      const buffer = Buffer.from(await res.arrayBuffer());
      if (buffer.length === 0 || buffer.length > MAX_PHOTO_BYTES) continue;
      // 壊れた画像・未対応形式はここで弾き、写真なしのカバーにする
      const meta = await sharp(buffer).metadata();
      if (!meta.width || !meta.height) continue;
      return buffer;
    } catch {
      // 取得できなくても写真なしで生成を続ける
    }
  }
  return null;
}

/** 写真を1200×630に切り抜く（顔など目立つ部分を残す）。写真が無ければ単色の地 */
export async function basePhoto(photo: Buffer | null, fallbackColor: string): Promise<Buffer> {
  if (photo) {
    try {
      return await sharp(photo)
        .resize(COVER_WIDTH, COVER_HEIGHT, { fit: "cover", position: sharp.strategy.attention })
        .toBuffer();
    } catch {
      // 読めない画像でもビルドを落とさず、単色の地にする
    }
  }
  return sharp({
    create: { width: COVER_WIDTH, height: COVER_HEIGHT, channels: 3, background: fallbackColor },
  })
    .png()
    .toBuffer();
}

const gradientSvg = (
  width: number,
  height: number,
  stops: { offset: number; color: string; opacity: number }[],
) =>
  Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">${stops
      .map((s) => `<stop offset="${s.offset}" stop-color="${s.color}" stop-opacity="${s.opacity}"/>`)
      .join("")}</linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/></svg>`,
  );

/** 下だけを暗くする陰影。start（0〜1）から下に向かって maxOpacity まで濃くなる */
export async function withBottomShade(base: Buffer, start: number, maxOpacity: number): Promise<Buffer> {
  const shade = gradientSvg(COVER_WIDTH, COVER_HEIGHT, [
    { offset: start, color: "#000", opacity: 0 },
    { offset: start + (1 - start) * 0.55, color: "#000", opacity: maxOpacity * 0.7 },
    { offset: 1, color: "#000", opacity: maxOpacity },
  ]);
  return sharp(base).composite([{ input: shade }]).toBuffer();
}

/** 指定範囲だけを角丸のすりガラスにする（ぼかし＋色味。色味は下ほど濃い） */
export async function withGlassCard(
  base: Buffer,
  box: Box,
  tint: { color: string; from: number; to: number },
  radius = 24,
): Promise<Buffer> {
  const region = await sharp(base)
    .blur(26)
    .extract({ left: box.x, top: box.y, width: box.width, height: box.height })
    .toBuffer();
  const mask = Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${box.width}" height="${box.height}"><rect width="100%" height="100%" rx="${radius}" ry="${radius}" fill="#fff"/></svg>`,
  );
  // sharp の composite は最後の呼び出ししか効かないので、色味と角丸は2段階に分ける
  const tinted = await sharp(region)
    .composite([
      {
        input: gradientSvg(box.width, box.height, [
          { offset: 0, color: tint.color, opacity: tint.from },
          { offset: 1, color: tint.color, opacity: tint.to },
        ]),
      },
    ])
    .png()
    .toBuffer();
  const glass = await sharp(tinted)
    .ensureAlpha()
    .composite([{ input: mask, blend: "dest-in" }])
    .png()
    .toBuffer();
  return sharp(base).composite([{ input: glass, left: box.x, top: box.y }]).toBuffer();
}

export async function toDataUrl(image: Buffer): Promise<string> {
  const jpeg = await sharp(image).jpeg({ quality: 86 }).toBuffer();
  return `data:image/jpeg;base64,${jpeg.toString("base64")}`;
}
