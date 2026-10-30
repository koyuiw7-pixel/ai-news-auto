# Google再取得申請の切り分け・トップからDify入口（2026-10-30）

オーナー依頼：Google再取得申請のエラーを調査して受付まで確認する。反映待ちの間も流入対策を進め、本人操作が必要な時点で知らせる。

## 申請の切り分け

- 前作業のFusion再取得申請は送信エラー、画面reload後1回だけの再試行も同じ。reCAPTCHA接続エラーを併記。
- 今回はGoogleの公開URLテストを実施。21:37:32 JST、Google検査ツール（スマートフォン）で取得成功・クロール許可・登録許可・自己canonical。記事の403/robotsが原因という証拠なし。Cloudflare防御設定は変更しない。
- 取得テスト成功と検索インデックス更新は別。本人確認/申請UI/利用上限の根本原因は未確定。詳細通信ログ取得の権限は拒否されたため、迂回せず通常UIで確認した。
- オーナーの22:06提示画像でも同じ個別申請の送信エラーを確認。本人操作でも再現する。個別申請を受付済みと書かない。
- 一般ニュースのRequest indexing送信用公開APIはない。URL Inspection APIは読取用。JobPosting/BroadcastEvent対象のIndexing APIを流用しない。反復申請で速くなるとは扱わない。

## トップ入口の最小改善

実装 `815b5b8180ca1ecba2883cbbccd08bf6a17d5ab6`。`app/page.tsx`の既存`AIの使い方と費用` navへ、`/guides/dify-free-api-cost`と`/guides/dify-1-18-startup-check`の2リンク、8行だけ追加。VPS比較と`/guides`一覧、`data-funnel-pos=home-guides`、ニュース順序・広告・サーバー構成を保持。新JS・外部リンク・UTM・計測改変なし。

目的は既存訪問者のDify記事閲覧・回遊。これだけで新規訪問や売上が増えたと報告しない。新2リンクのクリック・枠露出は未計測。到着後のDify `article_view`と比較 `guide_click`は既存v2で計測対象。比較への既存リンクは引き続きhome-guidesで計測する。

## 検証

型検査・差分検査・ローカルwebpack629ページ成功。最新bot記事/投稿履歴をrebaseで保持。Deploy `41057137805`は成功、21:42:49 JSTに本番公開。本番トップ4リンク/計測位置保持/リンク先2件HTTP200の6項目が成功。初回staleトップは次回取得で更新済みを確認し、キャッシュ設定変更なし。

Readability `41057424269`は44条件、違反0・未解消エラー0（トップ375px/1440px×light/dark含む）。広告通信遮断。更新トップ1URLだけIndexNow通知、HTTP200受理。Google申請受付や検索反映とは区別。

Googleの正式な別の通知方法として、更新済み`https://ai-tech-express.jp/sitemap.xml`を1回送信し、「サイトマップを送信しました」の受付を確認。3改稿記事と実更新日時が配信XMLに含まれることを事前確認した。GSC最終読み込み日は送信前の日付のままで、今回の再取得・検索反映完了とは扱わない。個別URL申請は未受理、サイトマップ送信は受付済みという別状態。

オーナーの直前の画面にChrome更新待ち表示がある。reCAPTCHA公式はブラウザ更新を対処候補にしているが、更新不足が原因とは断定しない。他作業を保存して本人が「再起動して更新」を行うよう依頼、完了待ち。ブラウザ再起動や保護設定変更を勝手に行わない。更新後に個別申請を1件だけ確認し、人間確認は本人へ渡す。

参考：https://support.google.com/chrome/answer/95414?hl=ja 、https://support.google.com/recaptcha/?hl=en 、https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl?hl=ja

会員画面・エラー証拠は作業チャットの`work/google-reindex-recovery/`、オーナー向け説明は`outputs/Google-reindex-and-Dify-entry-2026-10-30.md`に置く。公開repoへ会員データ・ログ原文を入れない。
