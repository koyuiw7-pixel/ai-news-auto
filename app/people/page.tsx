import type { Metadata } from "next";
import { withPageShare } from "@/lib/page-share";
import Link from "next/link";
import AssetShell, { Crumbs } from "@/components/assets/AssetShell";
import { getAllPeople, personArticles } from "@/lib/people";

export const metadata: Metadata = withPageShare("people", "/people", {
  title: "AI・テックの人物まとめ　経歴と最新ニュース",
  description: "AI・テック企業の経営者などについて、公式の発表で確かめた経歴と、サイソクの関連記事をまとめています。",
  alternates: { canonical: "/people" },
  // 人物が1人だけの一覧は薄いので、2人以上になるまで検索に出さない（2026-11-12 AdSense 監査。サイトマップも同じ）
  ...(getAllPeople().length >= 2 ? {} : { robots: { index: false, follow: true } }),
});

/** 人物のまとめの一覧（台帳 A53） */
export default function PeopleIndex() {
  const people = getAllPeople();
  return (
    <AssetShell>
      <Crumbs items={[{ href: "/", label: "ホーム" }, { label: "人物" }]} />
      <h1 className="t-h1 mt-5">AI・テックの人物まとめ</h1>
      <p className="t-lead mt-3">公式の発表で確かめた経歴と、関連する記事を人物ごとにまとめています。</p>
      <ul className="mt-8 grid gap-3">
        {people.map((p) => (
          <li key={p.slug}>
            <Link href={`/people/${p.slug}`} className="block rounded-xl border border-line p-4 hover:border-ink sm:p-5">
              <span className="block text-[17px] font-bold text-ink">{p.nameJa}（{p.name}）</span>
              <span className="mt-1 block text-meta text-muted">{p.organization} {p.jobTitle}{personArticles(p).length > 0 ? ` ・ 記事 ${personArticles(p).length}本` : ""}</span>
            </Link>
          </li>
        ))}
      </ul>
    </AssetShell>
  );
}
