import fs from "node:fs/promises";
import path from "node:path";
import { loadDefaultJapaneseParser } from "budoux";
import { ImageResponse } from "next/og";
import sharp from "sharp";
import { coverPath, getAllArticles, getArticle } from "@/lib/articles";
import { companyOf } from "@/lib/companies";

/**
 * 記事ごとのカバー画像（1200×630）。
 *
 * YouTube のサムネイルをそのまま使うと「よそのコンテンツを貼っただけ」に見えるので、
 * 日本語の見出し・発表元の企業・サイト名を載せた独自の画像を、ビルド時に静的に生成する。
 * SNS（Threads・X）でシェアされたときのカードもこの画像になる。
 * 外部の画像生成APIは使わないので費用はかからない。
 *
 * 写真は全面に敷き、見出しの下だけ「すりガラス」にする。
 * ぼかしと暗さは下に行くほど強くし、写真を活かしたまま文字を確実に読めるようにする。
 */
export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return getAllArticles()
    .filter((article) => coverPath(article))
    .map((article) => ({ slug: article.slug }));
}

const WIDTH = 1200;
const HEIGHT = 630;
const FONT_DIR = path.join(process.cwd(), "assets", "fonts");
const parser = loadDefaultJapaneseParser();

let fonts: Promise<{ name: string; data: Buffer; weight: 700 | 900 }[]> | null = null;
function loadFonts() {
  fonts ??= Promise.all([
    fs.readFile(path.join(FONT_DIR, "ZenKakuGothicNew-Black.ttf")),
    fs.readFile(path.join(FONT_DIR, "ZenKakuGothicNew-Bold.ttf")),
    fs.readFile(path.join(FONT_DIR, "DelaGothicOne-Regular.ttf")),
  ]).then(([black, bold, dela]) => [
    { name: "Zen", data: black, weight: 900 as const },
    { name: "Zen", data: bold, weight: 700 as const },
    { name: "Dela", data: dela, weight: 900 as const },
  ]);
  return fonts;
}

/** 元動画の画像を取得する。消えていれば標準画質、それも無ければ null */
async function fetchPhoto(url: string): Promise<Buffer | null> {
  const candidates = url.includes("maxresdefault") ? [url, url.replace("maxresdefault", "hqdefault")] : [url];
  for (const candidate of candidates) {
    if (!candidate) continue;
    try {
      const res = await fetch(candidate, { signal: AbortSignal.timeout(8000) });
      if (res.ok) return Buffer.from(await res.arrayBuffer());
    } catch {
      // 取得できなくても写真なしで生成を続ける
    }
  }
  return null;
}

const svg = (body: string) =>
  Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}"><defs>${body}</defs><rect width="100%" height="100%" fill="url(#g)"/></svg>`,
  );

/** ぼかした写真を、下に行くほど不透明にするためのマスク */
const FROST_MASK = svg(
  `<linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
     <stop offset="0.34" stop-color="#fff" stop-opacity="0"/>
     <stop offset="0.58" stop-color="#fff" stop-opacity="0.85"/>
     <stop offset="0.74" stop-color="#fff" stop-opacity="1"/>
   </linearGradient>`,
);

/** すりガラスの色味。下に行くほど濃くする */
const FROST_TINT = svg(
  `<linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
     <stop offset="0.36" stop-color="#0b0b0f" stop-opacity="0"/>
     <stop offset="0.62" stop-color="#0b0b0f" stop-opacity="0.34"/>
     <stop offset="1" stop-color="#0b0b0f" stop-opacity="0.74"/>
   </linearGradient>`,
);

/** 写真＋下に向かって強くなるすりガラスを1枚の背景画像にする */
async function frostedBackground(photo: Buffer | null, color: string): Promise<string> {
  const base = photo
    ? await sharp(photo)
        .resize(WIDTH, HEIGHT, { fit: "cover", position: sharp.strategy.attention })
        .toBuffer()
    : await sharp({ create: { width: WIDTH, height: HEIGHT, channels: 3, background: color } })
        .png()
        .toBuffer();

  const frosted = await sharp(base)
    .blur(28)
    .modulate({ saturation: 1.15 })
    .ensureAlpha()
    .composite([{ input: FROST_MASK, blend: "dest-in" }])
    .png()
    .toBuffer();

  const result = await sharp(base)
    .composite([{ input: frosted }, { input: FROST_TINT }])
    .jpeg({ quality: 84 })
    .toBuffer();
  return `data:image/jpeg;base64,${result.toString("base64")}`;
}

/** 「製品名｜説明」の形なら製品名を強調色に分ける */
function splitTitle(title: string): { head: string; tail: string } {
  const match = /^(.{2,36}?)[｜：|:]\s*(.+)$/.exec(title);
  return match ? { head: match[1], tail: match[2] } : { head: "", tail: title };
}

/** 文字幅のおおよその合計（全角=1、半角=0.56） */
function emWidth(text: string): number {
  let total = 0;
  for (const char of text) total += /[\u0000-\u00ff]/.test(char) ? 0.56 : 1;
  return total;
}

const PADDING = 56;
const TEXT_WIDTH = WIDTH - PADDING * 2;
const SHADOW = "0 2px 12px rgba(0,0,0,0.35)";

/** 文節ごとに分け、単語の途中で改行されないようにする */
function Phrases({ text, color, size }: { text: string; color: string; size: number }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", color, fontSize: size, lineHeight: 1.32, textShadow: SHADOW }}>
      {parser.parse(text).map((phrase, index) => (
        // 文節の途中で折り返させない（縮ませると文節の中で改行されてしまう）
        <span key={index} style={{ display: "flex", flexShrink: 0 }}>
          {phrase}
        </span>
      ))}
    </div>
  );
}

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article || !coverPath(article)) return new Response("Not found", { status: 404 });

  const company = companyOf(article);
  const isOther = company.slug === "other";
  const isRoundup = article.type === "roundup";
  const title = article.seoTitle || article.title;
  const { head, tail } = splitTitle(title);
  const [photo, fontData] = await Promise.all([fetchPhoto(article.thumbnail), loadFonts()]);
  const background = await frostedBackground(photo, isOther ? "#1d1d22" : company.color);

  // 製品名は1行に収める。長ければ文字を小さくする
  const headSize = Math.min(70, Math.floor(TEXT_WIDTH / Math.max(emWidth(head), 1)));
  const tailSize = head ? 44 : emWidth(tail) <= 16 ? 64 : 54;

  return new ImageResponse(
    (
      <div
        style={{
          width: WIDTH,
          height: HEIGHT,
          display: "flex",
          position: "relative",
          fontFamily: "Zen",
          fontWeight: 900,
          background: "#111",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={background} alt="" width={WIDTH} height={HEIGHT} style={{ position: "absolute", left: 0, top: 0 }} />

        {/* 元動画が削除されて写真が無いときは、企業色の地に企業名を大きく敷く */}
        {!photo && (
          <div
            style={{
              position: "absolute",
              left: 48,
              top: 120,
              display: "flex",
              fontSize: 210,
              letterSpacing: -6,
              color: "rgba(255,255,255,0.15)",
            }}
          >
            {isOther ? "AI NEWS" : company.name}
          </div>
        )}

        {/* 発表元と種類のバッジ */}
        <div style={{ position: "absolute", left: 40, top: 36, display: "flex", gap: 12 }}>
          {!isOther && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 22px 10px 12px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.94)",
                boxShadow: "0 6px 24px rgba(0,0,0,0.2)",
              }}
            >
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: company.color,
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: company.mark.length > 1 ? 17 : 22,
                  fontWeight: 700,
                }}
              >
                {company.mark}
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#111" }}>{company.name}</div>
            </div>
          )}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              padding: "10px 22px",
              borderRadius: 999,
              fontSize: 26,
              fontWeight: 700,
              background: isRoundup ? "#111111" : "#e5372b",
              color: "#ffffff",
              boxShadow: "0 6px 24px rgba(0,0,0,0.2)",
            }}
          >
            {isRoundup ? `${article.sources?.length ?? 0}本の発表を統合` : "速報"}
          </div>
        </div>

        {/* サイト名 */}
        <div
          style={{
            position: "absolute",
            right: 40,
            top: 36,
            display: "flex",
            alignItems: "center",
            padding: "10px 22px",
            borderRadius: 14,
            background: "#111111",
            color: "#ffffff",
            fontFamily: "Dela",
            fontSize: 30,
          }}
        >
          サイソク
        </div>

        {/* 見出し。すりガラスの上に白文字、製品名は黄色 */}
        <div
          style={{
            position: "absolute",
            left: PADDING,
            bottom: 50,
            width: TEXT_WIDTH,
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {head && (
            <div style={{ display: "flex", fontSize: headSize, lineHeight: 1.22, color: "#ffe873", textShadow: SHADOW }}>
              {head}
            </div>
          )}
          <Phrases text={tail} color="#ffffff" size={tailSize} />
        </div>

        {/* 下端に発表元の企業色 */}
        <div
          style={{
            position: "absolute",
            left: 0,
            bottom: 0,
            width: WIDTH,
            height: 10,
            background: isOther ? "#e5372b" : company.color,
          }}
        />
      </div>
    ),
    {
      width: WIDTH,
      height: HEIGHT,
      fonts: fontData,
      headers: { "Cache-Control": "public, max-age=31536000, immutable" },
    },
  );
}
