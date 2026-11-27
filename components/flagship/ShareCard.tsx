"use client";

import { useEffect, useRef, useState } from "react";

/**
 * 結果を1枚の画像（1200×630の PNG）にして、保存・シェアする。画像はこの端末の中で描き、どこにも送らない。
 * 画像に入れるのは人数と金額だけ（生まれた年月・名前は入れない）。
 */
export type ShareCardData = {
  title: string;
  family: string;
  nextLabel: string;
  next: string;
  monthly: string;
  year: string;
  note: string;
  url: string;
};

const FONT = '"Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "BIZ UDPGothic", Meiryo, sans-serif';

function draw(data: ShareCardData): HTMLCanvasElement {
  const W = 1200;
  const H = 630;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const c = canvas.getContext("2d");
  if (!c) return canvas;
  // 地: 報道ネイビーに細い方眼、上に速報レッドの帯（サイトのシェア画像と同じ色）
  const bg = c.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#0b1f45");
  bg.addColorStop(1, "#10305f");
  c.fillStyle = bg;
  c.fillRect(0, 0, W, H);
  c.strokeStyle = "rgba(255,255,255,0.06)";
  c.lineWidth = 1;
  for (let x = 0; x <= W; x += 40) {
    c.beginPath();
    c.moveTo(x + 0.5, 0);
    c.lineTo(x + 0.5, H);
    c.stroke();
  }
  for (let y = 0; y <= H; y += 40) {
    c.beginPath();
    c.moveTo(0, y + 0.5);
    c.lineTo(W, y + 0.5);
    c.stroke();
  }
  c.fillStyle = "#c8221a";
  c.fillRect(0, 0, W, 12);

  const text = (s: string, x: number, y: number, size: number, color: string, weight = 700, align: CanvasTextAlign = "left") => {
    c.font = `${weight} ${size}px ${FONT}`;
    c.fillStyle = color;
    c.textAlign = align;
    c.textBaseline = "alphabetic";
    c.fillText(s, x, y);
  };
  text("サイソクニュース", 68, 86, 30, "#ffffff", 800);
  text(data.title, W - 68, 86, 30, "#b4c0d8", 700, "right");
  text(data.family, 68, 168, 40, "#ffffff", 800);

  // 次の支給（いちばん大きく）
  text(data.nextLabel, 68, 250, 30, "#b4c0d8", 700);
  text(data.next, 64, 372, 120, "#ffffff", 900);

  // 右の2つ
  const panel = (label: string, value: string, y: number) => {
    c.fillStyle = "rgba(255,255,255,0.08)";
    c.strokeStyle = "rgba(255,255,255,0.18)";
    c.lineWidth = 2;
    c.beginPath();
    if (typeof c.roundRect === "function") c.roundRect(780, y, 352, 112, 8);
    else c.rect(780, y, 352, 112);
    c.fill();
    c.stroke();
    text(label, 808, y + 42, 26, "#b4c0d8", 700);
    text(value, 808, y + 92, 44, "#ffffff", 800);
  };
  panel("1か月の合計", data.monthly, 196);
  panel("1年分（支給6回）", data.year, 324);

  c.fillStyle = "rgba(255,255,255,0.18)";
  c.fillRect(68, 482, W - 136, 2);
  text(data.note, 68, 530, 26, "#ffffff", 700);
  text(data.url, 68, 576, 24, "#b4c0d8", 600);
  return canvas;
}

export default function ShareCard({ data }: { data: ShareCardData }) {
  const [src, setSrc] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [message, setMessage] = useState("");
  const [canShareFile, setCanShareFile] = useState(false);
  const urlRef = useRef<string | null>(null);

  // 結果が変わったら、作った画像は古いので片付ける
  useEffect(() => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
    setSrc(null);
    setBlob(null);
    setMessage("");
  }, [data.next, data.monthly, data.year, data.family]);
  useEffect(() => () => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
  }, []);

  const make = () => {
    const canvas = draw(data);
    canvas.toBlob((b) => {
      if (!b) {
        setMessage("この端末では画像を作れませんでした。");
        return;
      }
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      const url = URL.createObjectURL(b);
      urlRef.current = url;
      setSrc(url);
      setBlob(b);
      try {
        const file = new File([b], "saisoku-jidouteate.png", { type: "image/png" });
        setCanShareFile(typeof navigator.canShare === "function" && navigator.canShare({ files: [file] }));
      } catch {
        setCanShareFile(false);
      }
    }, "image/png");
  };

  const share = async () => {
    if (!blob) return;
    try {
      const file = new File([blob], "saisoku-jidouteate.png", { type: "image/png" });
      await navigator.share({ files: [file], title: data.title, text: `${data.family}。${data.nextLabel} ${data.next}`, url: data.url.startsWith("http") ? data.url : `https://${data.url}` });
    } catch {
      /* 閉じたときは何もしない */
    }
  };

  return (
    <div className="fs-share" data-flagship-share="">
      <div className="fs-share-head">
        <p className="fs-share-title">結果を1枚の画像に</p>
        <p className="fs-share-sub">人数と金額だけを入れます。生まれた年月は入りません。画像はこの端末の中で作ります。</p>
      </div>
      <div className="fs-share-frame">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={`${data.title}：${data.family}、${data.nextLabel} ${data.next}、1か月 ${data.monthly}、1年分 ${data.year}`} width={1200} height={630} />
        ) : (
          <button type="button" onClick={make} className="fs-share-make">
            画像を作る
          </button>
        )}
      </div>
      {src ? (
        <div className="fs-share-actions">
          <a href={src} download="saisoku-jidouteate.png" className="fs-btn fs-btn-primary">
            画像を保存
          </a>
          {canShareFile ? (
            <button type="button" onClick={share} className="fs-btn">
              画像をシェア
            </button>
          ) : null}
          <button type="button" onClick={make} className="fs-btn fs-btn-quiet">
            作り直す
          </button>
        </div>
      ) : null}
      {message ? <p className="fs-share-sub" role="status">{message}</p> : null}
    </div>
  );
}
