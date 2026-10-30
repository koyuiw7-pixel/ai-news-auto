# 検索入口の改稿：Fusion / IPA / Work IQ（2026-10-30）

オーナー依頼：最新の検索語と表示内容を確認し、表示されてもクリックされていない既存記事を改善する。既存機能・広告・長期の信頼を守る。Search Consoleの会員データは公開リポジトリへ保存しない。

## 対象と変更

実装コミット：`13405b8652450e9a6da02068bbe7c50897e94c91`。3件のニュース記事JSONのみ。元の公開日・生成日・slug・出典・画像・広告素材・SNS用文面・投稿履歴を保持。

1. `github-copilot-fusion-release`：定義→料金・使い方→表示されない場合の確認へ題名・説明・本文・かんたん版を整合。GitHub DocsのSVG対応表も読み、Standardは全プラン、High/MaxはPro+/Max/Business/Enterprise対象と明記。複数モデルは常時ではなく使用する場合がある。有料プラン30%割引の期限、使えるモデルがない場合の非表示、採用しなかった下書きによるファイル変更を確認する案内を追加。性能・費用の保証表現を撤回。`free:false`が画面で「有料のみ」になるため`null`へ、地域別実機確認がないため`japan:unknown`へ訂正。
2. `ipa-personal-data-leak-countermeasures`：題名・description・要点のみを、IPA/二次被害対策/情報別の行動/相談先に合わせる。本文・かんたん版は先行改善を保持。相談無料と通話料別を区別。直近に公開した改稿がGoogleへ取り込まれたかは別途確認する。
3. `microsoft-work-iq-agent-context-m365`：定義・MCP・料金/利用条件を題名と冒頭へ。一般提供CLI、Previewプラグイン、元動画内の新APIの範囲を区別。未検証サンプルへの導入推奨を確認順へ置換。古い競合比較表と優位性の断定を削除。元動画の新API/Work IQ OS/Margoの細部は今回未再検証と明記。

## 一次資料

- https://github.blog/changelog/2026-10-28-route-and-orchestrate-models-with-github-copilot-fusion/
- https://docs.github.com/en/copilot/concepts/models/copilot-fusion
- https://www.ipa.go.jp/security/anshin/attention/2026/mgdayori20261026.html
- https://www.ipa.go.jp/security/anshin/about.html
- https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/cli
- https://github.com/microsoft/work-iq

## 保持した機能・境界

- 記事以外のコンポーネント・ルーティング・サイトマップ・索引ルール・ワークフローは変更していない。
- 本文長はFusion 3,913字、IPA 2,444字、Work IQ 6,915字。実際の索引判定を前後で比較し、3件とも対象を維持。
- `lib/howto`・choose・旧guideの選択は3件とも前後一致。商品枠、Amazon/楽天検索リンクも実装関数で前後一致。
- 通常/速報SNSは既存のposted slugとgeneratedAtで候補を選び、今回変えたupdatedAtでは再送しない。予約内容の修正・新規投稿・再送はしていない。予約済み文面が記事の訂正を自動反映したとは扱わない。
- 広告のhref/rel・A8画像は本番HTMLで前後比較する。広告先へのリクエストやテスト成果は作らない。実ブラウザ検査は広告通信を遮断する既存CIのみ。

## 検証

公開前：JSON構造・保護フィールド比較・`git diff --check`、`npx tsc --noEmit`、内部導線7テスト、webpackビルド628ページが成功。push直前に最新mainへrebaseし、別の新記事/商品/投稿履歴を保持。最新mainを含む標準CloudflareビルドもCIで実施する。

本番：Deploy `41054522572`が21:22:30 JSTに成功。最新mainを含むCI標準ビルド629ページ、計測48テスト、導線7テストが成功。本番HTMLは3件×11項目＝33項目成功。title/H1/description/canonical/index/構造化データ/公開日/広告hrefとrel/A8画像を照合した。初回に2件の旧HTMLが返ったが、既存stale-while-revalidateの更新後に新内容を再確認。キャッシュ実装変更なし。

表示検査：既定 `41054894837`の44条件、対象3記事 `41055380127`の12条件、合計56条件で違反0・未解消エラー0。375px/1440px、light/dark。広告通信を遮断した既存CIを使用。

サイトマップ3URLと更新日時を確認し、既存IndexNowで3件を通知、HTTP200受理。GoogleのFusion再取得依頼は送信エラー、画面更新後の一度の再試行も同じ。受付成功と記録しない。他2件の申請を重ねていない。サイトマップ経路は維持。Googleの新内容取得・検索表示反映・クリック増は未確認。

## 効果測定

公開成功、Google再取得、検索結果での表示、クリック増加を分ける。自サイトのtitle/descriptionをGoogleがそのまま表示するとは限らない。24時間速報値と通常集計を混ぜない。検索語表は匿名化等でページ全体の表示数と一致しないため、表にない検索語を補完しない。

変更後のGoogle取得を起点に、同じ検索語・端末・順位帯で表示/クリック/CTRを比較する。最初の見直しは各記事100表示または7日後を運用目安とし、統計的成功の保証とはしない。低母数のままなら題名を日々変えず、需要のある入口・本文・内部リンクの不足を調べる。ニュースの寿命や順位変動も分け、効果を本改稿だけへ帰属させない。

会員データ・Googleの保存HTML・変更前後HTML・最終検証は、作業チャットの`work/ctr-improvement/`と`outputs/Saisoku-search-CTR-improvement-2026-10-30.md`に保存する。ロールバックが必要なら3記事の対象フィールドだけ戻し、最新記事・商品・stateをまとめて巻き戻さない。
