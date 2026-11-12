import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import NewsletterSignup from "@/components/NewsletterSignup";
import { guideShortName, LIFE_COMPARE_SLUGS, lifeCompareGuide } from "@/lib/buying-guides";
import { ROUNDUP_CHANNEL, getAllArticles, getAllChannels, getAllTags } from "@/lib/articles";
import { companyCounts } from "@/lib/companies";
import { CREATOR_CHANNELS, WIRE_SOURCES } from "@/lib/indexing";
import { isThinSourceChannel } from "@/lib/news-outlets";
import { genreNav } from "@/lib/nav";
import { siteConfig } from "@/site.config";

const LEGAL_LINKS = [
  { href: "/about", label: "運営者情報" },
  { href: "/editorial-policy", label: "編集方針・AI利用と事実確認" },
  { href: "/corrections", label: "訂正履歴" },
  { href: "/privacy", label: "プライバシーポリシー" },
  { href: "/disclaimer", label: "免責事項・広告について" },
  { href: "/contact", label: "お問い合わせ" },
];

// 何度も見に来てもらう定番ページ（ヘッダーはジャンルのタブが中心なので、ここにもまとめて置く）
const REFERENCE_LINKS = [
  { href: "/search", label: "記事を検索" },
  { href: "/news", label: "ジャンル別のニュース" },
  { href: "/usable", label: "今日から使えるAI" },
  { href: "/guides", label: "AIの使い方ガイド" },
  { href: "/ai-pricing", label: "AIの料金・日本対応 早見表" },
  // お金のページ（計算・比較・手続き）。AI の選び方ガイド（/choose/*）は一覧ページ /choose から見られる（2026-11-10 M6）
  { href: "/tools/furusato-limit", label: "ふるさと納税の上限額の計算" },
  { href: "/tools/defense-tax", label: "防衛特別所得税の計算" },
  ...LIFE_COMPARE_SLUGS.flatMap((slug) => {
    const found = lifeCompareGuide(slug);
    return found ? [{ href: found.href, label: `${guideShortName(found.guide)}の比較` }] : [];
  }),
  { href: "/dates", label: "暮らしとお金の日程（支給日・期限）" },
  { href: "/guides/jidou-teate", label: "児童手当の金額と対象" },
  { href: "/guides/kogaku-ryoyohi", label: "高額療養費の上限額" },
  { href: "/products", label: "AIサービス図鑑" },
  { href: "/choose", label: "選び方ガイドの一覧" },
  // ヘッダーの帯から移した一覧（2026-11-11 読者目線レビュー 14位。ヘッダーは暮らしとお金の入口にした）
  { href: "/roundups", label: "値上げ・障害・リコールの一覧" },
  { href: "/weekly", label: "今週のAIニュースまとめ" },
  { href: "/events", label: "AIイベントの日程（日本時間）" },
];

export default function Footer() {
  const ai = getAllArticles().filter((a) => a.genreSlug === "ai");
  // 発信元はジャンルを問わず記事の多い順（AIだけに絞らない）。足元が伸びないよう上限を設ける
  // まとめ記事しかない発信元（名前が「◯本の記事から編集部が統合」のまま）は出さない
  // 足元の「情報源」には企業・機関の公式の発信元だけを並べる（個人・他媒体の動画やプレスリリース配信は出さない）
  // 報道機関の発信元（radar-<報道機関>）・話題のまとめも並べない（公式の発信元ではない。台帳 W12）。
  // 同じ名前の発信元（「NTT ニュースリリース」の全体版と AI 版など）は1つだけ（記事の多い方。2026-11-03 の点検で2回出ていた）
  const seenLabels = new Set<string>();
  const channels = getAllChannels()
    .filter((c) => !ROUNDUP_CHANNEL.test(c.label) && !CREATOR_CHANNELS.has(c.slug) && !WIRE_SOURCES.has(c.slug) && !isThinSourceChannel(c.slug))
    .filter((c) => {
      const key = c.label.replace(/\s+/g, "");
      if (seenLabels.has(key)) return false;
      seenLabels.add(key);
      return true;
    })
    .slice(0, 24);
  const genres = genreNav();
  const companies = companyCounts(ai).slice(0, 8);
  const tags = getAllTags(true).slice(0, 16);

  return (
    <footer data-funnel-pos="footer" className="mt-24 border-t-2 border-ink bg-surface">
      <div className="mx-auto max-w-[1240px] px-5 py-14 sm:px-8">
        <div className="grid gap-12 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <p className="font-display text-2xl leading-none text-ink">
              {siteConfig.name}
            </p>
            <p className="mt-2 text-meta font-bold text-muted">
              {siteConfig.tagline}
            </p>
            <p className="mt-4 max-w-md text-note leading-[1.9] text-ink-soft">
              {siteConfig.description}
            </p>

            {/* 記事・/newsletter では本文に登録欄があるので、ここは空になる（lib/newsletter-placement.ts） */}
            <div className="mt-8 empty:hidden">
              <NewsletterSignup variant="footer" />
            </div>

            {/* 2026-11-11 オーナー決定（台帳 W40）「広告の表示は『PR』だけ」: 足もとの広告の説明文は出さない。説明は /disclaimer・/privacy（下のリンク「免責事項・広告について」） */}

            <p className="mt-6 text-note font-bold text-ink">
              公式SNS：
              {siteConfig.social.map((s, i) => (
                <span key={s.url}>
                  {i > 0 && " ・ "}
                  <a href={s.url} target="_blank" rel="me noopener" className="text-accent underline-offset-4 hover:underline">
                    {s.label}
                  </a>
                </span>
              ))}
            </p>

            <ul className="mt-6 space-y-2">
              {LEGAL_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-note font-medium text-ink-soft underline-offset-4 hover:text-accent hover:underline"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="eyebrow">GENRES</p>
            <ul className="mb-8 mt-4 grid grid-cols-2 gap-x-4 gap-y-2.5">
              {genres.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-note font-semibold text-ink-soft hover:text-accent">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>

            <p className="eyebrow">REFERENCE</p>
            <ul className="mb-8 mt-4 space-y-2.5">
              {REFERENCE_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-note font-semibold text-ink-soft hover:text-accent">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>

            {/* AI の会社・発信元・話題の一覧。暮らしとお金の記事をスマホで読む人には長いだけなので、ノワールの記事ではスマホで隠す（components/noir/noir.css。2026-11-10 オーナー承認） */}
            <div className="ft-ai">
            <p className="eyebrow">COMPANIES</p>
            <ul className="mt-4 space-y-2.5">
              {companies.map(({ company, count }) => (
                <li key={company.slug}>
                  <Link
                    href={`/companies/${company.slug}`}
                    className="inline-flex items-center gap-2 text-note font-semibold text-ink-soft hover:text-accent"
                  >
                    <CompanyMark company={company} size={16} />
                    {company.name}
                    <span className="index-num text-meta text-muted">{count}</span>
                  </Link>
                </li>
              ))}
            </ul>

            {channels.length > 0 && (
              <>
                <p className="eyebrow mt-8">SOURCES</p>
                <ul className="mt-4 space-y-2">
                  {channels.map((channel) => (
                    <li key={channel.slug}>
                      <Link
                        href={`/channels/${channel.slug}`}
                        className="text-note text-muted hover:text-accent"
                      >
                        {channel.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
            </div>
          </div>

          {tags.length > 0 && (
            <div className="ft-ai">
              <p className="eyebrow">TOPICS</p>
              <ul className="mt-4 flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <li key={tag.slug}>
                    <Link
                      href={`/tags/${encodeURIComponent(tag.slug)}`}
                      className="inline-block border border-line px-2.5 py-1 text-meta text-muted hover:border-accent hover:text-accent"
                    >
                      {tag.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-line">
        <div className="mx-auto max-w-[1240px] px-5 py-6 sm:px-8">
          <p className="text-note leading-[1.9] text-muted">
            本サイトの記事は、公式発表・公開されている動画・報道をもとに生成AIが下書きし、元の発表と照らし合わせる自動の事実確認を通したものです。公開後は編集部（運営者）が速報や多くの人に読まれている記事を中心に読み、誤りは訂正方針に沿って直します（出典は各記事に記載。詳しくは<Link href="/editorial-policy" className="underline underline-offset-2 hover:text-ink">編集方針</Link>）。誤りが含まれる可能性があるため、重要な判断の際は必ず出典および各社の公式発表をご確認ください。
          </p>
          <p className="index-num mt-4 text-meta text-muted">
            © {new Date().getFullYear()} {siteConfig.name}
          </p>
        </div>
      </div>
    </footer>
  );
}
