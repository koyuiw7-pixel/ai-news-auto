import VerdictIcon from "@/components/VerdictIcon";
import { USABILITY_LABEL, type Usability } from "@/lib/verdict";

const STYLE: Record<Usability, string> = {
  go: "bg-go-soft text-go",
  partial: "border border-line-strong text-ink-soft",
  wait: "bg-surface text-muted",
};

/** 一覧の行頭に置く「使える／一部／まだ」 */
export default function VerdictBadge({ kind, block }: { kind: Usability; block?: boolean }) {
  if (block) {
    return (
      <span className={`grid justify-items-center gap-1 rounded-lg px-1 py-2 ${STYLE[kind]}`}>
        <VerdictIcon kind={kind} size={18} />
        <span className="text-[11.5px] font-bold leading-none">{USABILITY_LABEL[kind]}</span>
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-[2px] text-[11px] font-bold ${STYLE[kind]}`}>
      <VerdictIcon kind={kind} size={12} />
      {USABILITY_LABEL[kind]}
    </span>
  );
}
