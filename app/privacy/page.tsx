import type { Metadata } from "next";
import LegalPage from "@/components/LegalPage";
import { hasActiveAffiliate } from "@/lib/monetization";
import { siteConfig } from "@/site.config";

export const metadata: Metadata = {
  title: "プライバシーポリシー",
  description: `${siteConfig.name}における個人情報・Cookie・アクセス解析・広告配信の取り扱いについて説明しています。`,
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalPage
      eyebrow="PRIVACY POLICY"
      title="プライバシーポリシー"
      lead={`${siteConfig.name}（以下「当サイト」）における、利用者情報の取り扱い方針です。`}
      updatedAt="2026年8月4日"
    >
      <h2>1. 取得する情報</h2>
      <p>
        当サイトは会員登録機能を持たず、氏名・住所・電話番号などの個人情報を
        利用者に入力していただくことはありません。取得するのは以下の情報に限られます。
      </p>
      <ul>
        <li>アクセス解析による閲覧履歴（閲覧ページ、滞在時間、参照元）</li>
        <li>端末情報（ブラウザの種類、OS、画面サイズ、おおよその地域）</li>
        <li>Cookieおよび類似技術によって保存される識別子</li>
        <li>お問い合わせをいただいた場合、そのメールアドレスと本文</li>
      </ul>

      <h2>2. アクセス解析ツールについて</h2>
      <p>
        当サイトは、閲覧状況を把握するためにアクセス解析ツールを使用する場合があります。
        これらのツールはCookieを利用してデータを収集しますが、
        収集されるデータは匿名であり、個人を特定するものではありません。
        Cookieの利用を望まない場合は、ブラウザの設定から無効化できます。
      </p>

      <h2>3. 広告配信について（Google AdSense）</h2>
      <p>
        当サイトは、第三者配信の広告サービス「Google AdSense」を利用する場合があります。
        Googleを含む第三者配信事業者は、Cookieを使用して、
        利用者が当サイトや他のサイトに過去にアクセスした際の情報に基づいて広告を配信します。
      </p>
      <p>
        利用者は、
        <a
          href="https://myadcenter.google.com/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Google広告設定
        </a>
        でパーソナライズ広告を無効にできます。また、
        <a
          href="https://www.aboutads.info/choices/"
          target="_blank"
          rel="noopener noreferrer"
        >
          aboutads.info
        </a>
        では、第三者配信事業者のCookie利用を一括で無効化できます。
      </p>
      <p>
        第三者配信事業者によるデータ利用については、
        <a
          href="https://policies.google.com/technologies/partner-sites"
          target="_blank"
          rel="noopener noreferrer"
        >
          Googleのポリシーと規約
        </a>
        をご確認ください。
      </p>

      <h2>4. アフィリエイトプログラムについて</h2>
      <p>
        {hasActiveAffiliate()
          ? "当サイトは、複数のアフィリエイトプログラムに参加しています。当サイト内のリンク経由で商品・サービスの申込や購入が行われた場合、当サイトは提携先から紹介料を受け取ることがあります。"
          : "当サイトは、今後アフィリエイトプログラムに参加する予定です。参加を開始した時点で、成果報酬が発生するリンクには「PR」表記を付与し、本ページにもその旨を反映します。現時点で当サイトから外部サイトへのリンクは、いずれも紹介料の発生しない通常のリンクです。"}
      </p>
      <p>
        これらのリンクを経由した際、提携先の判断でCookieが保存され、
        成果の計測に使用されることがあります。当サイトが利用者の個人情報を
        提携先に提供することはありません。該当するリンクには「PR」表記と
        <code>rel=&quot;sponsored&quot;</code> 属性を付与しています。
      </p>

      <h2>5. 情報の第三者提供</h2>
      <p>
        当サイトは、取得した情報を第三者に販売・貸与しません。
        ただし、法令に基づく開示請求があった場合はこの限りではありません。
      </p>

      <h2>6. 免責</h2>
      <p>
        当サイトからリンクした外部サイトにおける個人情報の取り扱いについては、
        当サイトは責任を負いません。各サイトのプライバシーポリシーをご確認ください。
      </p>

      <h2>7. 改定</h2>
      <p>
        本ポリシーは、法令の変更やサービス内容の変更に応じて予告なく改定することがあります。
        改定後の内容は本ページに掲載した時点から効力を持ちます。
      </p>

      <h2>8. お問い合わせ</h2>
      <p>
        本ポリシーに関するお問い合わせは、
        <a href="/contact">お問い合わせページ</a>
        よりご連絡ください。
      </p>
    </LegalPage>
  );
}
