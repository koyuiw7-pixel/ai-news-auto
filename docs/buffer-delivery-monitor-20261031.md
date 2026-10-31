# Bufferの投稿状態監視（2026-10-31）

## 目的と境界

Bufferへの受付と、各SNSへの配信は別。既存の`state/threads_posted.json`は重複防止に使われているため変更・削除せず、`scripts/buffer_delivery_monitor.py`と`.github/workflows/buffer_delivery_monitor.yml`を独立させる。GraphQLは読み取りのqueryだけ。投稿・再送・予約変更・削除・履歴の更新、アカウント設定変更は一切しない。Buffer外からの直接投稿や、SNS上の実表示・返信まで検証したことにはならない。エラーや不明を再送理由にせず、個別のSNS実画面を先に確認し、投稿はオーナーの事前了承を得る。

## 見方

Actionsの「Buffer delivery monitor (read only)」の各runのSummaryで、Threads/X/Facebook別の直近7日間のBuffer送信済み、予約中、送信処理中、承認待ち、エラーを表示する。失敗と未送信の一覧自体には期間制限を付けない。過去のエラーは警告として残し、Buffer上で対象を確認する。新しいエラー（予定日時または作成日時から2時間以内、日時不明を含む）、予約時刻を30分超過した送信待ち、予約画像取得不可はrunを失敗にする。GitHubの通知が届くかは本人の通知設定次第であり、メールの到着は未検証。上記2時間判定は新たなエラー発生時刻そのものではなく、古い予約が遅れて失敗した場合は新規扱いできないことがある。

定期は毎時12・42分UTC（JSTも同じ分）、手動workflow_dispatchでも読み取りのみ。GitHub Actionsのスケジュールは遅延・欠落し得る。手動照合のほか、次の定刻実行も運用開始後に確認する。BufferのAPIが失敗、空一覧、対象チャンネル不足、異常ページ送り、状態不明、最近に送信済みとして記録された対象が一覧に出ないなどは、0件や成功と扱わず監視run自体を失敗させる。過去の送信済み全ページ（上限100ページ）を取得した後、sentAtで7日間に絞る。上限到達時も不明扱い。

送信済みとそれ以外を一つのstatusフィルタで混ぜるとBufferが空一覧を返した事例、送信済みへの日付フィルタと下書きを含めないフィルタで同様の事例があった。送信済みとscheduled/sending/needs_approval/draft/errorの2回に分け、draftを取得後に表示から除く。フィルタ仕様全体の原因は不明のため、空の取得を安全に失敗扱いし、最近の既知のsent IDで照合する。監視のログ・Summaryは件数と区分のみで、本文、投稿ID、画像URL、生のエラー、資格情報を出さない（このリポジトリは公開）。対象を探すときはBuffer画面を使用する。

## 画像取得の再発を減らす

Buffer公式は、画像は予約時だけでなく公開時まで公開URLで外部から取得可能である必要があり、同じURLでもブラウザと外部サーバーでは結果が異なると説明している: https://support.buffer.com/en-us/articles/troubleshooting-buffers-api-VgBuQXUCDI 。既存の速報処理は記事と画像をGETして公開を待つが、MetaやBufferの取得成功は保証しない。

監視は予定の約2時間前から、自社ドメインまたは`images.buffer.com`の画像URLのみを読み取り、HTTP 200、画像Content-Type、PNG/JPEG/WebPの先頭バイトを確認する。リダイレクトは追わず、第三者ドメインは未確認として数える。URLの使い回しは1回だけ確認。これは実際のBuffer/SNSからのアクセスを再現しないため、成功を保証せず、予約を書き換えない。公開直前やBuffer→SNSの区間で失敗する可能性は残る。第三者画像への依存、CDN経路、Cloudflareのbot対策、投稿前後の配信監視を引き続き検討し、根拠なくセキュリティ設定を緩めない。

## 運用・停止

監視のみ停止するにはGitHub Actionsの当該workflowを無効化。既存SNSワークフローやBuffer予約には影響しない。監視自体は再送しない。新規サービス契約・課金はなし。GitHub公式によれば公開repoの標準GitHub-hosted runnerは無料（公開状態や課金条件が変われば再確認）: https://docs.github.com/en/actions/reference/runners/github-hosted-runners 。

隔離テストは`python3 -m unittest discover -s tests -p 'test_buffer_delivery_monitor.py'`。Bufferを模擬し、取得/媒体別状態/過去と新しいerror/予定超過/不明時失敗/重複ID/ページ送り/画像検査先とリダイレクト/ログ秘匿を確認。既存のSNS関連テストも実行する。
