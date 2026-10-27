"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

/** 解除はボタンを押したときだけ（メールのリンクを自動で開く製品に解除されないように） */
export default function UnsubscribeForm() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  const t = params.get("t") ?? "";
  const [phase, setPhase] = useState<"idle" | "sending" | "done" | "error">("idle");

  if (!id || !t) {
    return <p className="mt-6 text-[14px] leading-[1.8] text-ink-soft">リンクが正しくありません。メール末尾の解除リンクから開いてください。</p>;
  }

  async function unsubscribe() {
    setPhase("sending");
    try {
      const res = await fetch("/api/newsletter/unsubscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, t }),
      });
      setPhase(res.ok ? "done" : "error");
    } catch {
      setPhase("error");
    }
  }

  if (phase === "done") {
    return (
      <p role="status" className="mt-6 border-l-2 border-go pl-3 text-[14px] leading-[1.8] text-ink">
        解除しました。これまでお読みいただき、ありがとうございました。
        <Link href="/" className="ml-1 underline underline-offset-2">トップへ</Link>
      </p>
    );
  }

  return (
    <div className="mt-6">
      <p className="text-[14px] leading-[1.8] text-ink-soft">下のボタンを押すと、毎朝のメール配信を止めます。</p>
      <button
        type="button"
        onClick={unsubscribe}
        disabled={phase === "sending"}
        className="mt-4 h-11 rounded-lg bg-ink px-5 text-[14px] font-semibold text-paper hover:opacity-85 disabled:opacity-60"
      >
        {phase === "sending" ? "処理中…" : "配信を解除する"}
      </button>
      {phase === "error" && (
        <p role="alert" className="mt-3 text-[13px] text-live">
          解除できませんでした。リンクが古い可能性があります。お手数ですがお問い合わせからご連絡ください。
        </p>
      )}
    </div>
  );
}
