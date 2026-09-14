/**
 * 広告枠。
 *
 * 本番の AdSense を有効にするには Vercel の環境変数に次を設定するだけです:
 *   NEXT_PUBLIC_ADSENSE_CLIENT = ca-pub-XXXXXXXXXXXXXXXX
 *   NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_TOP    = 1234567890
 *   NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_MIDDLE = 1234567890
 *   NEXT_PUBLIC_ADSENSE_SLOT_SIDEBAR        = 1234567890
 *
 * 未設定の間はダミー枠（AdSense Dummy）が表示されます。
 */

const CLIENT = process.env.NEXT_PUBLIC_ADSENSE_CLIENT ?? "";

const SLOT_IDS: Record<AdPosition, string> = {
  "article-top": process.env.NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_TOP ?? "",
  "article-middle": process.env.NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_MIDDLE ?? "",
  sidebar: process.env.NEXT_PUBLIC_ADSENSE_SLOT_SIDEBAR ?? "",
};

export type AdPosition = "article-top" | "article-middle" | "sidebar";

type Props = {
  position: AdPosition;
  className?: string;
};

export default function AdSlot({ position, className }: Props) {
  const slot = SLOT_IDS[position];
  const enabled = Boolean(CLIENT && slot);

  return (
    <aside
      className={className}
      aria-label="広告"
      data-ad-position={position}
    >
      <p className="mb-1 text-[10px] tracking-widest text-muted">広告</p>

      {enabled ? (
        <>
          <ins
            className="adsbygoogle block"
            style={{ display: "block" }}
            data-ad-client={CLIENT}
            data-ad-slot={slot}
            data-ad-format={position === "sidebar" ? "vertical" : "auto"}
            data-full-width-responsive={position === "sidebar" ? "false" : "true"}
          />
          <script
            dangerouslySetInnerHTML={{
              __html:
                "(adsbygoogle = window.adsbygoogle || []).push({});",
            }}
          />
        </>
      ) : (
        <div className="rounded-2xl border border-dashed border-line-strong bg-surface px-5 py-5 text-center text-xs text-muted">
          AdSense Dummy
        </div>
      )}
    </aside>
  );
}
