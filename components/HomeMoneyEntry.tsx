import Link from "next/link";

/**
 * トップの最初の画面の入口「自分のお金と暮らしの数字」（2026-11-25 AdSense の3回目の申請の前の点検）。
 * 最初に見えるのが AI の写真や話題の記事ではなく、サイトの軸（暮らしとお金の「自分ごと」）だとわかるよう、
 * いつでも役に立つ5つのページ（早見表・一覧・計算）を主役の記事より上に並べる。行き先は実在するページだけ（tests/test_home_money_entry_20261125.cjs）。
 */
export const HOME_MONEY_ENTRY = [
  { href: "/articles/december-2026-money-calendar", label: "お金カレンダー", note: "12月の料金改定・支給日・締切" },
  { href: "/articles/price-changes-november-february", label: "値上げ・料金改定の一覧", note: "11月〜2月を実施日順に" },
  { href: "/articles/data-leaks-recalls-checklist", label: "漏えい・回収の対象チェック", note: "自分が対象かと確認先" },
  { href: "/articles/japan-benefits-allowances-guide", label: "給付と手当の早見表", note: "金額と申し込みの窓口" },
  { href: "/tools/child-allowance", label: "児童手当の計算", note: "わが家の受け取り額を計算" },
] as const;

export default function HomeMoneyEntry() {
  return (
    <section aria-labelledby="money-entry-heading" data-home-zone="money-entry" className="mb-6 sm:mb-10">
      <h2 id="money-entry-heading" className="flex items-center gap-2 text-[1.25rem] font-bold leading-[1.4] text-ink">
        <span aria-hidden className="h-5 w-[3px] rounded-full bg-live" />
        自分のお金と暮らしの数字
      </h2>
      <ul className="mt-2 grid gap-2 sm:mt-3 sm:grid-cols-2 lg:grid-cols-5">
        {HOME_MONEY_ENTRY.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              data-money-link=""
              className="flex h-full flex-col gap-0.5 rounded-xl border border-line px-4 py-3 transition-colors hover:border-ink"
            >
              <span className="text-[15.5px] font-bold leading-[1.5] text-ink">{item.label}</span>
              <span className="text-meta leading-relaxed text-ink-soft">{item.note}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
