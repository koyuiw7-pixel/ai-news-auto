import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import { Pixels, PrFeature, PrRow, PrTag } from "@/components/rail/parts";
import InternalMoneyCard from "@/components/InternalMoneyCard";
import Link from "next/link";

/**
 * 「すぐにできること」のすぐ下に置く、編集部の言葉で書いた PR の囲み（1記事に1つ。lib/action-ad.ts）。
 *
 * 2026-11-09 オーナー「PRってこんな大きく書いてる？みんな」: 本文と同じ白地の囲み。広告の表示は右上の小さな「PR」の札と、
 *   囲みの下の注記（ステマ規制の「広告であることが分かる表示」。サイト全体の「本ページはプロモーションを含みます」もある）
 * 2026-11-10 オーナー「広告が魅力的じゃない。わざとらしすぎず、でも目立って押してしまうような」:
 *  - 上の小さな1行は誰に向けた枠か（ad.title）と、記事から商品へつなぐ一文（ad.lead）
 *  - 1つ目は、読者がこの商品で確かめられること（pitch.gain）を見出しにし、良いところ2〜3つ（公式の事実だけ）と色のあるボタン（components/rail/parts.tsx の PrFeature）
 *  - バナーは 6:5 の小さな枠に収める（大きなバナーをそのまま貼らない）。場所は先に取り、読み込みで画面がずれない。ポップアップは出さない
 *  - 2つ目は小さく1行
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
  const lead = ad.lead ?? ad.reason;
  const hasPr = Boolean(first);
  const box = (
    <aside
      data-aff-pos={pos}
      data-action-ad={ad.key}
      data-ad-ab=""
      aria-label={hasPr ? "PR：広告" : "サイソクの案内"}
      className={`relative max-w-[40em] overflow-hidden rounded-2xl border border-line bg-paper shadow-[0_1px_2px_rgb(11_26_51/0.05)] ${className}`}
    >
      <div className="border-b border-line px-4 pt-3 pb-3 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <p className="min-w-0 text-meta font-bold leading-snug text-ink-soft">{ad.title}</p>
          {hasPr && <PrTag />}
        </div>
        {/* 記事から商品へつなぐ一文。スマホは省いて囲みを低くする（見出しの1行が誰向けかを示す） */}
        {lead && <p className="mt-1 hidden text-note leading-[1.65] text-ink-soft sm:block">{lead}</p>}
      </div>

      {internal.length > 0 && <InternalMoneyCard links={internal} className={hasPr ? "border-b border-line" : ""} />}

      {first && <PrFeature item={first.item} wide />}

      {rest.length > 0 && (
        <ul className="border-t border-line">
          {rest.map(({ item }, index) => (
            <li key={item.key} className="border-b border-line last:border-b-0">
              <PrRow item={item} rank={index + 2} />
            </li>
          ))}
        </ul>
      )}
      {hasPr && (
        <p className="border-t border-line bg-surface px-4 py-2.5 text-note leading-relaxed text-muted sm:px-6">
          広告（アフィリエイトリンク）を含みます。申し込みがあると当サイトに紹介料が入ることがあります。料金・条件は各公式サイトで確認してください。
        </p>
      )}
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
