import Link from "next/link";
import { getAllChannels, getAllTags } from "@/lib/articles";
import { siteConfig } from "@/site.config";

export default function Footer() {
  const channels = getAllChannels();
  const tags = getAllTags().slice(0, 20);

  return (
    <footer className="mt-20 border-t border-ink-100 bg-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-3">
        <div>
          <p className="text-lg font-bold text-ink-950">{siteConfig.name}</p>
          <p className="mt-3 text-sm leading-relaxed text-ink-500">
            {siteConfig.description}
          </p>
        </div>

        {channels.length > 0 && (
          <div>
            <p className="text-sm font-bold text-ink-950">チャンネル</p>
            <ul className="mt-3 space-y-2">
              {channels.map((channel) => (
                <li key={channel.slug}>
                  <Link
                    href={`/channels/${channel.slug}`}
                    className="text-sm text-ink-500 hover:text-accent"
                  >
                    {channel.label}（{channel.count}）
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        {tags.length > 0 && (
          <div>
            <p className="text-sm font-bold text-ink-950">人気のトピック</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {tags.map((tag) => (
                <li key={tag.slug}>
                  <Link
                    href={`/tags/${tag.slug}`}
                    className="inline-block rounded-full bg-ink-50 px-2.5 py-1 text-xs text-ink-500 hover:bg-accent-soft hover:text-accent"
                  >
                    #{tag.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="border-t border-ink-100 px-4 py-6 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 text-xs text-ink-300 sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {new Date().getFullYear()} {siteConfig.name}
          </p>
          <p>
            本サイトの記事は各社公式YouTube動画をAIが解析して自動生成しています。正確な情報は必ず公式発表をご確認ください。
          </p>
        </div>
      </div>
    </footer>
  );
}
