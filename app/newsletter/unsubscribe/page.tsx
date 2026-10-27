import type { Metadata } from "next";
import { Suspense } from "react";
import UnsubscribeForm from "@/components/UnsubscribeForm";

export const metadata: Metadata = {
  title: "メール配信の解除",
  robots: { index: false, follow: false },
  alternates: { canonical: "/newsletter/unsubscribe" },
};

export default function UnsubscribePage() {
  return (
    <div className="mx-auto max-w-xl px-5 py-16 sm:px-8">
      <p className="eyebrow">NEWSLETTER</p>
      <h1 className="t-h1 mt-2">メール配信の解除</h1>
      <Suspense fallback={null}>
        <UnsubscribeForm />
      </Suspense>
    </div>
  );
}
