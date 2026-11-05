import { siteConfig } from "@/site.config";

/**
 * 記事末の「Threadsでフォロー」の案内（2026-11-05 オーナー承認）。
 * 固定投稿・プロフィールと同じ約束（毎朝7時に要点5本・決算や物価は速報）を伝える。
 */
const THREADS_URL = siteConfig.social.find((s) => s.label === "Threads")?.url ?? "https://www.threads.com/@saisoku637";

export default function ThreadsFollow({ className = "" }: { className?: string }) {
  return (
    <aside aria-labelledby="threads-follow-heading" className={`mt-8 rounded-3xl bg-surface px-5 py-5 sm:px-6 ${className}`}>
      <p id="threads-follow-heading" className="text-note font-bold text-ink">
        Threadsでサイソクをフォロー
      </p>
      <p className="mt-1.5 text-desc leading-relaxed text-ink-soft">
        毎朝7時に、仕事とお金に効くニュースの要点を5本お届けしています。決算や物価の発表は、公式の資料から速報でお知らせします。
      </p>
      <a
        href={THREADS_URL}
        target="_blank"
        rel="noopener noreferrer"
        data-cta="threads-follow"
        className="mt-3 inline-flex min-h-11 items-center rounded-full bg-ink px-5 text-note font-bold text-paper hover:opacity-85"
      >
        @saisoku637 をフォローする
      </a>
    </aside>
  );
}
