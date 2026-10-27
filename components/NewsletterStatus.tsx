"use client";

import { useSearchParams } from "next/navigation";

/** 確認リンクから戻ってきたときの結果（/newsletter?s=...） */
const MESSAGES: Record<string, { text: string; ok: boolean }> = {
  confirmed: { text: "登録が完了しました。明日の朝7時から配信します。", ok: true },
  invalid: { text: "リンクが無効か、期限が切れています。お手数ですが、もう一度登録してください。", ok: false },
  error: { text: "ただいま処理できませんでした。時間をおいてもう一度リンクを開いてください。", ok: false },
};

export default function NewsletterStatus() {
  const status = useSearchParams().get("s") ?? "";
  const message = MESSAGES[status];
  if (!message) return null;
  return (
    <p
      role="status"
      className={`mt-6 border-l-2 pl-3 text-[14px] leading-[1.8] ${message.ok ? "border-go text-ink" : "border-live text-ink"}`}
    >
      {message.text}
    </p>
  );
}
