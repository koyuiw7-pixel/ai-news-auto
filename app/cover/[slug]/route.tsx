import fs from "node:fs/promises";
import path from "node:path";
import { loadDefaultJapaneseParser } from "budoux";
import { ImageResponse } from "next/og";
import { coverPath, getAllArticles, getArticle } from "@/lib/articles";
import { companyOf } from "@/lib/companies";

/**
 * 記事ごとのカバー画像（1200×630）。
 *
 * YouTube のサムネイルをそのまま使うと「よそのコンテンツを貼っただけ」に見えるので、
 * 日本語の見出し・発表元の企業・サイト名を載せた独自の画像を、ビルド時に静的に生成する。
 * SNS（Threads・X）でシェアされたときのカードもこの画像になる。
 * 外部の画像生成APIは使わないので費用はかからない。
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

/** 元動画の画像を埋め込み用に取得する。消えていれば標準画質、それも無ければ画像なし */
async function fetchPhoto(url: string): Promise<string | null> {
  const candidates = url.includes("maxresdefault") ? [url, url.replace("maxresdefault", "hqdefault")] : [url];
  for (const candidate of candidates) {
    if (!candidate) continue;
    try {
      const res = await fetch(candidate, { signal: AbortSignal.timeout(8000) });
      if (!res.ok) continue;
      const type = res.headers.get("content-type") ?? "image/jpeg";
      const data = Buffer.from(await res.arrayBuffer()).toString("base64");
      return `data:${type};base64,${data}`;
    } catch {
      // 取得できなくても画像なしで生成を続ける
    }
  }
  return null;
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

const TEXT_WIDTH = 640;

/** 文節ごとに分け、単語の途中で改行されないようにする */
function Phrases({ text, color, size }: { text: string; color: string; size: number }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", color, fontSize: size, lineHeight: 1.32 }}>
      {parser.parse(text).map((phrase, index) => (
        // 文節の途中で折り返させない（縮ませると文節の中で改行されてしまう）
        <span key={index} style={{ display: "flex", flexShrink: 0 }}>
          {phrase}
        </span>
      ))}
    </div>
  );
}

const dateFormat = new Intl.DateTimeFormat("ja-JP", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  timeZone: "Asia/Tokyo",
});

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article || !coverPath(article)) return new Response("Not found", { status: 404 });

  const company = companyOf(article);
  const isRoundup = article.type === "roundup";
  const title = article.seoTitle || article.title;
  const { head, tail } = splitTitle(title);
  const length = title.length;
  const size = length <= 18 ? 76 : length <= 26 ? 66 : 58;
  const [photo, fontData] = await Promise.all([fetchPhoto(article.thumbnail), loadFonts()]);

  return new ImageResponse(
    (
      <div
        style={{
          width: WIDTH,
          height: HEIGHT,
          display: "flex",
          position: "relative",
          background: "#0d0d0d",
          fontFamily: "Zen",
          fontWeight: 900,
        }}
      >
        {photo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={photo}
            alt=""
            width={780}
            height={HEIGHT}
            style={{ position: "absolute", right: 0, top: 0, width: 780, height: HEIGHT, objectFit: "cover" }}
          />
        )}
        {/* 写真の上に文字を載せても読めるよう、左から暗くする */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: WIDTH,
            height: HEIGHT,
            display: "flex",
            backgroundImage:
              "linear-gradient(90deg, #0d0d0d 0%, #0d0d0d 46%, rgba(13,13,13,0.92) 60%, rgba(13,13,13,0.55) 78%, rgba(13,13,13,0.2) 100%)",
          }}
        />
        {/* 発表元の企業色 */}
        <div style={{ position: "absolute", left: 0, top: 0, width: 16, height: HEIGHT, background: company.color }} />

        <div
          style={{
            position: "absolute",
            left: 76,
            top: 64,
            width: TEXT_WIDTH,
            height: HEIGHT - 120,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            {company.slug !== "other" && (
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: 12,
                background: company.color,
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: company.mark.length > 1 ? 22 : 28,
                fontWeight: 700,
              }}
            >
              {company.mark}
            </div>
            )}
            {company.slug !== "other" && (
              <div style={{ color: "#fff", fontSize: 32, fontWeight: 700 }}>{company.name}</div>
            )}
            <div
              style={{
                display: "flex",
                marginLeft: company.slug === "other" ? 0 : 6,
                padding: "6px 16px",
                borderRadius: 999,
                fontSize: 24,
                fontWeight: 700,
                background: isRoundup ? "#ffe873" : "#e5372b",
                color: isRoundup ? "#111" : "#fff",
              }}
            >
              {isRoundup ? `まとめ ${article.sources?.length ?? 0}本` : "速報"}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {head && (
              // 製品名は1行に収める（長ければ文字を小さくする）。途中で折れると名前が読み取りにくい
              <div
                style={{
                  display: "flex",
                  color: "#ffe873",
                  fontSize: Math.min(size, Math.floor(TEXT_WIDTH / emWidth(head))),
                  lineHeight: 1.25,
                }}
              >
                {head}
              </div>
            )}
            <Phrases text={tail} color="#ffffff" size={head ? Math.round(size * 0.82) : size} />
          </div>

          <div style={{ display: "flex", alignItems: "baseline", gap: 20 }}>
            <div style={{ fontFamily: "Dela", color: "#fff", fontSize: 40 }}>サイソク</div>
            <div style={{ color: "#a3a3a3", fontSize: 22, fontWeight: 700 }}>最速で、要点だけ。</div>
            <div style={{ color: "#a3a3a3", fontSize: 22, fontWeight: 700, marginLeft: "auto" }}>
              {dateFormat.format(new Date(article.publishedAt))}
            </div>
          </div>
        </div>
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
