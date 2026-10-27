/** X・はてなブックマークで共有するリンク（文字だけの控えめな行） */
export default function ShareLinks({ url, title }: { url: string; title: string }) {
  const x = `https://x.com/intent/post?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`;
  const hatena = `https://b.hatena.ne.jp/entry/s/${url.replace(/^https?:\/\//, "")}`;
  const link = "underline decoration-line-strong underline-offset-2 hover:text-ink";
  return (
    <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-muted">
      <span>このページを共有</span>
      <a href={x} target="_blank" rel="noopener noreferrer" className={link}>
        Xでポスト
      </a>
      <a href={hatena} target="_blank" rel="noopener noreferrer" className={link}>
        はてなブックマーク
      </a>
    </p>
  );
}
