import type { Usability } from "@/lib/verdict";

/** 判定アイコン。色だけに頼らず形でも区別できるようにする（✓／半円／砂時計） */
export default function VerdictIcon({ kind, size = 14 }: { kind: Usability; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  if (kind === "go") {
    return (
      <svg {...common}>
        <circle cx="8" cy="8" r="6.6" />
        <path d="M5.2 8.2l1.9 1.9 3.8-4" />
      </svg>
    );
  }
  if (kind === "partial") {
    return (
      <svg {...common}>
        <circle cx="8" cy="8" r="6.6" />
        <path d="M8 1.4a6.6 6.6 0 0 1 0 13.2z" fill="currentColor" stroke="none" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <circle cx="8" cy="8" r="6.6" />
      <path d="M8 4.6V8l2.2 1.4" />
    </svg>
  );
}
