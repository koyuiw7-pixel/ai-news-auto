import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import NewsletterSignup from "@/components/NewsletterSignup";
import { getAllArticles, getAllChannels, getAllTags } from "@/lib/articles";
import { companyCounts } from "@/lib/companies";
import { hasActiveAffiliate } from "@/lib/monetization";
import { siteConfig } from "@/site.config";

const LEGAL_LINKS = [
  { href: "/about", label: "運営者情報" },
  { href: "/editorial-policy", label: "編集方針・AI利用と事実確認" },
  { href: "/privacy", label: "プライバシーポリシー" },
  { href: "/disclaimer", label: "免責事項・広告について" },
  { href: "/contact", label: "お問い合わせ" },
];

export default function Footer() {
  const ai = getAllArticles().filter((a) => a.genreSlug === "ai");
  const liveChannels = new Set(ai.map((a) => a.channelSlug));
  // 発信元が増えても足元が伸びないよう、記事の多い順に上限を設ける
  const channels = getAllChannels().filter((c) => liveChannels.has(c.slug)).slice(0, 30);
  const companies = companyCounts(ai).slice(0, 8);
  const tags = getAllTags(true).slice(0, 16);

  return (
    <footer className="mt-24 border-t-2 border-ink bg-surface">
      <div className="mx-auto max-w-[1240px] px-5 py-14 sm:px-8">
        <div className="grid gap-12 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <p className="font-display text-2xl leading-none text-ink">
              {siteConfig.name}
            </p>
            <p className="mt-2 text-[13px] font-bold text-muted">
              {siteConfig.tagline}
            </p>
            <p className="mt-4 max-w-md text-[13px] leading-[1.9] text-muted">
              {siteConfig.description}
            </p>

            <div className="mt-8">
              <NewsletterSignup variant="footer" />
            </div>

            <p className="mt-8 max-w-md text-[12px] leading-[1.8] text-muted">
              当サイトはA8.netなどのアフィリエイトプログラムに参加しており、
              記事内に広告（プロモーション）を含む場合があります。
            </p>

            <ul className="mt-6 space-y-2">
              {LEGAL_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-[13px] font-medium text-ink-soft underline-offset-4 hover:text-accent hover:underline"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="eyebrow">COMPANIES</p>
            <ul className="mt-4 space-y-2.5">
              {companies.map(({ company, count }) => (
                <li key={company.slug}>
                  <Link
                    href={`/companies/${company.slug}`}
                    className="inline-flex items-center gap-2 text-sm font-semibold text-ink-soft hover:text-accent"
                  >
                    <CompanyMark company={company} size={16} />
                    {company.name}
                    <span className="index-num text-[11px] text-muted">{count}</span>
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
                        className="text-[13px] text-muted hover:text-accent"
                      >
                        {channel.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>

          {tags.length > 0 && (
            <div>
              <p className="eyebrow">TOPICS</p>
              <ul className="mt-4 flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <li key={tag.slug}>
                    <Link
                      href={`/tags/${encodeURIComponent(tag.slug)}`}
                      className="inline-block border border-line px-2.5 py-1 text-[11px] text-muted hover:border-accent hover:text-accent"
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
          <p className="text-[11px] leading-[1.9] text-muted">
            本サイトの記事は、公開されている動画を生成AIが解析して自動生成したものです。
            誤りが含まれる可能性があるため、重要な判断の際は必ず元動画および各社の公式発表をご確認ください。
            {hasActiveAffiliate() &&
              "当サイトは広告およびアフィリエイトプログラムによる収益を得ています。"}
          </p>
          <p className="index-num mt-4 text-[11px] text-muted">
            © {new Date().getFullYear()} {siteConfig.name}
          </p>
        </div>
      </div>
    </footer>
  );
}
