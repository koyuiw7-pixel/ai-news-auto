import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import { OtherSites, Pixels, PrFeature, PrTag } from "@/components/rail/parts";
import InternalMoneyCard from "@/components/InternalMoneyCard";
import Link from "next/link";
import { abCardFor } from "@/lib/ad-ab";
import AbBox from "@/components/rail/AbBox";

/**
 * 「すぐにできること」のすぐ下に置く、編集部の言葉で書いた PR の囲み（1記事に1つ。lib/action-ad.ts）。
 *
 * 2026-11-09 オーナー「PRってこんな大きく書いてる？みんな」: 広告の表示は右上の小さな「PR」の札（ステマ規制の「広告であることが分かる表示」）と、
 *   ページ冒頭の「本ページはプロモーションを含みます」。
 * 2026-11-10 オーナー決定（台帳 W37）「色の使い方が記事と同じすぎてメリハリがない」「広告（アフィリエイトリンク）を含みます…これ必要？結構邪魔」:
 *   囲み（app/globals.css の .ad-box）で本文と分け、札は塗りの「PR」（.ad-pr）。囲みの下の長い注記は出さない。
 *   2026-11-11 オーナー「このへんな黄色やめて。せめて黒とかで囲う感じに」: 砂色をやめ、白地に黒の細い枠・黒地に白の PR の札
 *   提携商品の無い案内だけの囲みは広告ではないので白地のまま
 * 2026-11-10 オーナー「広告が魅力的じゃない。わざとらしすぎず、でも目立って押してしまうような」:
 *  - 上の小さな1行は誰に向けた枠か（ad.title）。記事から商品へつなぐ一文（ad.lead）は 2026-11-11 に外した（オーナー「文字ばっか」。台帳 W39）
 *  - 1つ目は、読者がこの商品で確かめられること（pitch.gain）を見出しにし、良いところ2〜3つ（公式の事実だけ）と色のあるボタン（components/rail/parts.tsx の PrFeature）
 *  - バナーは 6:5 の小さな枠に収める（大きなバナーをそのまま貼らない）。場所は先に取り、読み込みで画面がずれない。ポップアップは出さない
 *  - 2つ目以降はボタンを付けず「ほかのサイト：〇〇」の1行のリンク（2026-11-11 オーナー「返礼品を探すボタンも2個あってどっちなんだ？」）
 * クリックは data-aff-pos（記事は "action-ad"。components/AffClickTracker.tsx → cloudflare/aff.ts の byPlacement）で、置き場所×提携先ごとに数える。
 * 手続きガイドと計算ツールにも同じ囲みを出す（pos は "guide-top"・"guide-lower"・"tool-result"。lib/guide-ads.ts。2026-11-10）。
 * data-ad-ab のある枠は、ボタンの色の A/B（<html data-adv>）もいっしょに送る（byVariant）。
 * 2026-11-10 M3: 囲みの1行目に、サイト内のお金のページへの案内（ad.internal。「サイソクの案内」、広告ではない）を出せる。置き場所（data-aff-pos）は変えない。
 *   提携商品がまだ無い話題（高額療養費のガイドの保険相談など）は、案内だけの囲みにする（PR の札と広告の注記は出さない。提携先が増えれば同じ場所に PR が並ぶ）
 * 2026-11-10 M6: 電気・ガス、家計、スマホ、引っ越し、ふるさと納税、年末調整の囲みは、すぐ下に1行「料金と条件を比べる：比較ページ」（ad.compare）を出す。
 *   囲みの外に置くサイト内リンク（rel=sponsored なし、data-money-link で読まれ方の記録に money として数える）。囲みの中身と位置は変えない。
 *   矢印の印は付けない（2026-11-09 オーナー「→みたいな印はいらない」。tests/test_action_ads.py）
 */
export default function ActionAd({ ad, className = "mt-4", pos = "action-ad" }: { ad: ActionAdData; className?: string; pos?: string }) {
  const internal = ad.internal ?? [];
  if (ad.items.length === 0 && internal.length === 0) return null;
  const [first, ...rest] = ad.items;
  const hasPr = Boolean(first);
  // 1つ目が数字のある提携商品なら、得のカードの A/B の囲み（lib/ad-ab.ts。台帳 W41）
  const ab = first ? abCardFor(first.item) : undefined;
  const box = ab && first ? (
    <AbBox
      card={ab}
      item={first.item}
      rest={rest.map(({ item }) => item)}
      pos={pos}
      internal={internal[0]}
      pixels={ad.items.map(({ pixel }) => pixel).filter((p): p is string => Boolean(p))}
      className={`max-w-[40em] ${className}`}
    />
  ) : (
    <aside
      data-aff-pos={pos}
      data-action-ad={ad.key}
      data-ad-ab=""
      aria-label={hasPr ? "PR：広告" : "サイソクの案内"}
      className={`relative max-w-[40em] overflow-hidden rounded-2xl border border-line ${hasPr ? "ad-box" : "bg-paper"} ${className}`}
    >
      <div className={`${hasPr ? "ad-head " : ""}border-b border-line px-4 pt-3 pb-3 sm:px-6`}>
        <div className="flex items-center justify-between gap-3">
          <p className="min-w-0 text-meta font-bold leading-snug text-ink-soft">{ad.title}</p>
          {hasPr && <PrTag />}
        </div>
        {/* 記事から商品へつなぐ一文（ad.lead）は出さない。見出しは囲みの中の1行だけ（2026-11-11 オーナー「文字ばっか」） */}
      </div>

      {internal.length > 0 && <InternalMoneyCard links={internal} className={hasPr ? "border-b border-line" : ""} />}

      {first && <PrFeature item={first.item} wide />}

      {/* 2つ目以降はボタンを付けず1行のリンク（1つの囲みにボタンは1つ。2026-11-11 オーナー） */}
      <OtherSites items={rest.map(({ item }) => item)} first={first?.item} className="px-4 pb-3 sm:px-6" />
      <Pixels pixels={ad.items.map(({ pixel }) => pixel).filter((p): p is string => Boolean(p))} />
    </aside>
  );
  if (!ad.compare) return box;
  return (
    <>
      {box}
      <p data-compare-link="" className="mt-2 max-w-[40em] text-note">
        <Link href={ad.compare.href} data-money-link="" className="font-bold text-ink underline decoration-accent underline-offset-4 hover:text-accent">
          料金と条件を比べる：{ad.compare.label}
        </Link>
      </p>
    </>
  );
}
