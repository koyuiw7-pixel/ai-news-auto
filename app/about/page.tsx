import type { Metadata } from "next";
import LegalPage from "@/components/LegalPage";
import { getAllArticles, getAllGenres } from "@/lib/articles";
import { siteConfig } from "@/site.config";

export const metadata: Metadata = {
  title: "運営者情報・編集方針",
  description: `${siteConfig.name}の運営者情報と、記事の制作方法・編集方針・AI利用の開示について説明しています。`,
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  const articles = getAllArticles();
  const genres = getAllGenres();
  const { operator } = siteConfig;

  return (
    <LegalPage
      eyebrow="ABOUT"
      title="運営者情報・編集方針"
      lead={`${siteConfig.name}は、公開されている一次情報（企業・研究機関・官公庁の公式発表、発表動画、プレスリリース）をAIで解析し、日本語の解説記事として再構成するメディアです。制作の手順と事実確認のルールは「編集方針」ページで開示しています。`}
      updatedAt="2026年8月4日"
    >
      <h2>運営者情報</h2>
      <table>
        <tbody>
          <tr>
            <th>サイト名</th>
            <td>{siteConfig.name}</td>
          </tr>
          <tr>
            <th>運営者</th>
            <td>{operator.name}</td>
          </tr>
          <tr>
            <th>運営責任者</th>
            <td>{operator.representative}</td>
          </tr>
          <tr>
            <th>所在地</th>
            <td>{operator.location}</td>
          </tr>
          <tr>
            <th>連絡先</th>
            <td>{operator.email}</td>
          </tr>
          <tr>
            <th>開設</th>
            <td>{operator.established}</td>
          </tr>
        </tbody>
      </table>

      <h2>このサイトが提供するもの</h2>
      <p>
        海外AI企業の公式発表や、国内の不動産・住宅ローンに関する専門家の解説は、その多くが動画で公開されています。
        しかし動画は「探しにくく」「検索できず」「見るのに時間がかかる」という弱点があります。
        {siteConfig.name}
        は、それらの動画を機械的に収集し、映像と音声の両方を解析したうえで、
        要点・数字・タイムテーブル・注意点を文章に再構成して公開しています。
      </p>
      <p>
        現在
        {genres.map((g, i) => (
          <span key={g.slug}>
            {i > 0 && "・"}
            <strong>{g.label}</strong>（{g.count}本）
          </span>
        ))}
        の計 {articles.length} 本を公開中です。記事は3時間ごとに自動で追加されます。
      </p>

      <h2>記事の制作方法（AI利用の開示）</h2>
      <p>
        本サイトの記事は、<strong>生成AIが動画を解析して自動生成しています</strong>。
        人間のライターが一本ずつ執筆しているわけではありません。具体的な工程は次のとおりです。
      </p>
      <ol>
        <li>対象チャンネルの公開RSSを3時間ごとに巡回し、新着動画を検出します。</li>
        <li>
          動画のURLを生成AI（Google Gemini）に渡し、<strong>映像と音声の両方</strong>
          を解析させます。スライドの文字、デモ画面の挙動、話者の発言がすべて解析対象です。
        </li>
        <li>
          あらかじめ設計した編集方針（後述）に沿って、日本語の記事構造に再構成させます。
        </li>
        <li>生成物を機械的に検証し、体裁の破損がないか確認したうえで公開します。</li>
      </ol>

      <h2>編集方針</h2>
      <ul>
        <li>
          <strong>一次情報のみを根拠にする。</strong>{" "}
          記事の中心となる事実は、動画内で実際に確認できた内容に限ります。
          背景説明のために外部知識を補う場合は「編集部注」と明記します。
        </li>
        <li>
          <strong>数字を省略しない。</strong>{" "}
          価格・利回り・ベンチマークスコア・金利などは、提示されたまま正確に転記します。
          提示がなかった場合は「動画内で言及なし」と明記し、推測で埋めません。
        </li>
        <li>
          <strong>煽らない。</strong>{" "}
          「衝撃」「ヤバい」といった内容のない誇張表現、断定的な将来予測、
          読者を急かす表現は使用しません。
        </li>
        <li>
          <strong>不利な情報も書く。</strong>{" "}
          リスク・制約・競合に劣る点は、確認できた範囲で必ず記載します。
        </li>
        <li>
          <strong>出典に必ず戻れるようにする。</strong>{" "}
          全記事に元動画へのリンクと、発言箇所へのタイムスタンプ付きリンクを掲載しています。
        </li>
      </ul>

      <h2>限界と、お願い</h2>
      <p>
        生成AIによる自動生成である以上、<strong>誤りが含まれる可能性があります</strong>。
        聞き取りの誤り、数値の取り違え、文脈の誤解が起こりえます。
        重要な判断（購入・契約・投資・技術選定）を行う際は、
        必ず記事に併記した元動画と、各社の公式発表をご自身で確認してください。
      </p>
      <p>
        誤りを見つけられた場合は、
        <a href="/contact">お問い合わせ</a>
        からご連絡ください。確認のうえ、訂正または記事の取り下げを行います。
        権利者の方からの削除・修正のご要望にも同様に対応します。
      </p>

      <h2>収益について</h2>
      <p>
        本サイトは、広告（Google AdSense）およびアフィリエイトプログラムによる収益で運営しています。
        詳細は<a href="/disclaimer">免責事項・広告について</a>および
        <a href="/privacy">プライバシーポリシー</a>をご覧ください。
        広告主から報酬を受け取っていることが、記事内の評価に影響しないよう、
        記事本文は広告の有無と切り離して生成しています。
      </p>
    </LegalPage>
  );
}
