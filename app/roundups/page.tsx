import type { Metadata } from "next";
import { withPageShare } from "@/lib/page-share";
import Link from "next/link";
import AssetShell, { Crumbs } from "@/components/assets/AssetShell";
import { recentEntries, TOPIC_LISTS, topicListsUpdatedAt, weekCount } from "@/lib/topic-lists";

const TITLE = "値上げ・障害・リコール・サービス終了の一覧　公式発表から毎日更新";
const DESCRIPTION =
  "値上げ・料金改定、通信や決済の障害と復旧、リコール・回収、サービスの終了と日本での提供開始を、公式の発表を確かめた記事から一覧にしています。記事ができるたびに自動で更新。";

export const metadata: Metadata = withPageShare("roundups", "/roundups", { title: TITLE, description: DESCRIPTION, alternates: { canonical: "/roundups" } });

/** 横断の一覧の入口（台帳 A52） */
export default function TopicListsIndex() {
  const updated = new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Tokyo" }).format(new Date(topicListsUpdatedAt()));
  return (
    <AssetShell>
      <Crumbs items={[{ href: "/", label: "ホーム" }, { label: "値上げ・障害などの一覧" }]} />
      <h1 className="t-h1 mt-5">値上げ・障害・リコール・サービス終了の一覧</h1>
      <p className="t-lead mt-3">ニュースを1本ずつ追わなくても、暮らしと仕事に関わる変更をまとめて確かめられるようにしています。どの項目も、公式の発表を確かめた記事と公式の発表へのリンク付きです。</p>
      <p className="mt-2 text-meta text-muted">最終更新: {updated}</p>
      <ul className="mt-8 grid gap-3 sm:grid-cols-2">
        {TOPIC_LISTS.map((m) => {
          const entries = recentEntries(m.kind);
          return (
            <li key={m.kind}>
              <Link href={`/roundups/${m.kind}`} className="group block h-full rounded-xl border border-line p-4 transition-colors hover:border-ink sm:p-5">
                <span className="block text-[17px] font-bold text-ink group-hover:underline">{m.heading}</span>
                <span className="mt-1 block text-meta text-muted">今週 {weekCount(m.kind)} 件 / 直近1か月 {entries.length} 件</span>
                <ul className="mt-2 grid gap-1 text-desc text-ink-soft">
                  {entries.slice(0, 3).map((e) => (
                    <li key={e.slug} className="line-clamp-1">・{e.title}</li>
                  ))}
                </ul>
              </Link>
            </li>
          );
        })}
      </ul>
    </AssetShell>
  );
}
