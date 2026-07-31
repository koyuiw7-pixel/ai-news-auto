import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto grid max-w-3xl place-items-center px-4 py-32 text-center">
      <p className="text-6xl font-black text-accent">404</p>
      <h1 className="mt-4 text-xl font-bold text-ink">
        ページが見つかりませんでした
      </h1>
      <p className="mt-2 text-sm text-muted">
        記事が削除されたか、URLが変更された可能性があります。
      </p>
      <Link
        href="/"
        className="mt-8 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-paper transition-opacity hover:opacity-85"
      >
        トップへ戻る
      </Link>
    </div>
  );
}
