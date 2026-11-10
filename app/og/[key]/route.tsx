import fs from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";
import { allShareKeys, shareFor } from "@/lib/page-share-items";

/**
 * 固定ページ（/tools・/ai-pricing・/guides など）のシェア画像（1200×630）。中身は lib/page-share.ts。
 * 形は /news/share.png（app/news/share.png/route.tsx）と同じ。フォントを読めるビルド時に描画する。
 */
export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  // 固定ページに加え、ガイド・行事・製品・選び方ガイドの1ページずつ（SEO A15。lib/page-share-items.ts）
  return allShareKeys().map((key) => ({ key }));
}

export async function GET(_request: Request, { params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const page = shareFor(key);
  if (!page) return new Response("Not found", { status: 404 });
  const fontDir = path.join(process.cwd(), "assets", "fonts");
  const [dela, noto] = await Promise.all([
    fs.readFile(path.join(fontDir, "DelaGothicOne-Regular.ttf")),
    fs.readFile(path.join(fontDir, "NotoSansJP-Bold.otf")),
  ]);
  // 長い見出し（ガイドの題名など）は小さくして2行まで（1行は約17字＝60px）
  const len = page.heading.length;
  const headingSize = len <= 6 ? 96 : len <= 8 ? 84 : len <= 13 ? 72 : 60;
  const twoLines = len > 17;

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: "#f3f5f8", color: "#0b1a33", fontFamily: "Noto", padding: "54px 68px", borderTop: "14px solid #c8221a" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontFamily: "Dela", fontSize: 48, color: "#1d4a8f" }}>サイソク</span>
          <span style={{ fontSize: 26, color: "#1d4a8f" }}>最速で、要点だけ。</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", marginTop: twoLines ? 36 : 54 }}>
          <span style={{ width: 12, height: twoLines ? headingSize * 2.4 + 6 : headingSize + 6, background: "#c8221a", marginRight: 26, flexShrink: 0 }} />
          {/* 見出しは読みやすい Noto（ロゴ用の書体はロゴだけ。台帳 W1・2026-11-04 オーナー承認） */}
          <span style={{ fontFamily: "Noto", fontWeight: 700, fontSize: headingSize, lineHeight: 1.2, flex: 1 }}>{page.heading}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", marginTop: twoLines ? 24 : 34, fontSize: twoLines ? 30 : 32, lineHeight: 1.6 }}>
          {page.lines[0] ? <span>{page.lines[0]}</span> : null}
          <span>{page.lines[1]}</span>
        </div>
        <div style={{ display: "flex", marginTop: "auto", paddingTop: 25, borderTop: "2px solid #cbd3df", fontSize: 26, color: "#1d4a8f" }}>
          {page.footer}
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      fonts: [
        { name: "Dela", data: dela, weight: 400, style: "normal" },
        { name: "Noto", data: noto, weight: 700, style: "normal" },
      ],
    },
  );
}
