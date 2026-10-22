import VerdictIcon from "@/components/VerdictIcon";
import {
  STATUS_LABEL,
  freeLabel,
  japanLabel,
  usability,
  type Verdict,
} from "@/lib/verdict";

const dateFormat = new Intl.DateTimeFormat("ja-JP", {
  month: "numeric",
  day: "numeric",
  timeZone: "Asia/Tokyo",
});

const TONE = {
  go: "bg-go-soft text-go",
  partial: "bg-surface-2 text-ink",
  wait: "bg-surface-2 text-muted",
} as const;

/**
 * 記事冒頭の「使える？」判定カード。
 * 発表を読んだ人が最初に知りたい「自分は今これを使えるのか」に一目で答える。
 */
export default function VerdictCard({ verdict, judgedAt }: { verdict: Verdict; judgedAt: string }) {
  const kind = usability(verdict);
  const facts: { label: string; value: string; muted?: boolean }[] = [
    { label: "日本から使える？", value: japanLabel(verdict), muted: verdict.japan === "unknown" || verdict.status === "soon" || verdict.status === "demo" },
    { label: "料金は？", value: verdict.price || "不明", muted: !verdict.price || verdict.price === "不明" },
    { label: "無料で試せる？", value: freeLabel(verdict.free), muted: verdict.free === null },
    { label: "誰に向いている？", value: verdict.audience || "—", muted: !verdict.audience },
  ];

  return (
    <section aria-labelledby="verdict-heading" className="mt-6 overflow-hidden rounded-2xl border border-line-strong">
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start sm:gap-5 sm:p-6">
        <div className={`flex shrink-0 items-center gap-2 self-start rounded-xl px-3.5 py-2.5 ${TONE[kind]}`}>
          <VerdictIcon kind={kind} size={22} />
          <span className="text-[15px] font-bold leading-none">{STATUS_LABEL[verdict.status]}</span>
        </div>
        <div className="min-w-0">
          <h2 id="verdict-heading" className="text-[12px] font-bold tracking-wider text-muted">
            サイソクの判断
          </h2>
          <p className="mt-1 text-[16px] font-bold leading-[1.65] text-ink text-balance">{verdict.take}</p>
        </div>
      </div>

      <dl className="grid grid-cols-2 border-t border-line sm:grid-cols-4">
        {facts.map((fact, index) => (
          <div
            key={fact.label}
            className={`px-5 py-3.5 sm:px-6 ${index % 2 === 1 ? "border-l border-line" : ""} ${
              index >= 2 ? "border-t border-line sm:border-t-0" : ""
            } ${index === 2 ? "sm:border-l" : ""}`}
          >
            <dt className="text-[11px] text-muted">{fact.label}</dt>
            <dd className={`mt-0.5 text-[14px] font-bold leading-snug ${fact.muted ? "text-muted" : "text-ink"}`}>
              {fact.value}
            </dd>
          </div>
        ))}
      </dl>

      <p className="border-t border-line bg-surface px-5 py-2 text-[11px] text-muted sm:px-6">
        {dateFormat.format(Date.parse(judgedAt))}時点の判定。発表内容から編集部AIが判定しています。最新の提供状況は公式情報をご確認ください。
      </p>
    </section>
  );
}
