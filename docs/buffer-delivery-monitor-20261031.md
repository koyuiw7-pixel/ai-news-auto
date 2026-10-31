# Bufferの投稿状態監視（2026-10-31）

## 目的と境界

Bufferへの受付と、各SNSへの配信は別。既存の`state/threads_posted.json`は重複防止に使われているため変更・削除せず、`scripts/buffer_delivery_monitor.py`と`.github/workflows/buffer_delivery_monitor.yml`を独立させる。GraphQLは読み取りのqueryだけ。投稿・再送・予約変更・削除・履歴の更新、アカウント設定変更は一切しない。Buffer外からの直接投稿や、SNS上の実表示・返信まで検証したことにはならない。エラーや不明を再送理由にせず、個別のSNS実画面を先に確認し、投稿はオーナーの事前了承を得る。

## 見方

Actionsの「Buffer delivery monitor (read only)」の各runのSummaryで、Threads/X/Facebook別の直近7日間のBuffer送信済み、予約中、送信処理中、承認待ち、エラーを表示する。失敗と未送信の一覧自体には期間制限を付けない。過去のエラーは警告として残し、Buffer上で対象を確認する。新しいエラー（予定日時または作成日時から2時間以内、日時不明を含む）、予約時刻を30分超過した送信待ち、予約画像取得不可はrunを失敗にする。GitHubの通知が届くかは本人の通知設定次第であり、メールの到着は未検証。上記2時間判定は新たなエラー発生時刻そのものではなく、古い予約が遅れて失敗した場合は新規扱いできないことがある。

定期は毎時12・42分UTC（JSTも同じ分）、手動workflow_dispatchでも読み取りのみ。GitHub Actionsのスケジュールは遅延・欠落し得る。10/31 10:42と11:12 JSTのschedule起動は11:28時点で実行履歴なし。workflowはmain上でactive、手動実行は成功。欠落・遅延の個別原因は特定できていない。補助経路として、main上の同一repoからの通常「Auto Article Pipeline」（schedule/workflow_dispatch、速報レーン以外）の完了後に、この読み取り専用監視をworkflow_runで別起動する。親workflowやSNS投稿は起動・変更しない。補助経路による11:31 JSTの自動起動・監視成功を確認。親の記事処理が停止すると補助経路も止まり、GitHub workflow_runの遅延・欠落もあり得る。もとのscheduleそのものは未実証。BufferのAPIが失敗、空一覧、対象チャンネル不足、異常ページ送り、状態不明、最近に送信済みとして記録された対象が一覧に出ないなどは、0件や成功と扱わず監視run自体を失敗させる。過去の送信済み全ページ（上限100ページ）を取得した後、sentAtで7日間に絞る。上限到達時も不明扱い。

送信済みとそれ以外を一つのstatusフィルタで混ぜるとBufferが空一覧を返した事例、送信済みへの日付フィルタと下書きを含めないフィルタで同様の事例があった。送信済みとscheduled/sending/needs_approval/draft/errorの2回に分け、draftを取得後に表示から除く。フィルタ仕様全体の原因は不明のため、空の取得を安全に失敗扱いし、最近の既知のsent IDで照合する。監視のログ・Summaryは件数と区分のみで、本文、投稿ID、画像URL、生のエラー、資格情報を出さない（このリポジトリは公開）。対象を探すときはBuffer画面を使用する。

## 画像取得の再発を減らす

Buffer公式は、画像は予約時だけでなく公開時まで公開URLで外部から取得可能である必要があり、同じURLでもブラウザと外部サーバーでは結果が異なると説明している: https://support.buffer.com/en-us/articles/troubleshooting-buffers-api-VgBuQXUCDI 。既存の速報処理は記事と画像をGETして公開を待つが、MetaやBufferの取得成功は保証しない。

監視は予定の約2時間前から、自社ドメインまたは`images.buffer.com`の画像URLのみを読み取り、HTTP 200、画像Content-Type、PNG/JPEG/WebPの先頭バイトを確認する。リダイレクトは追わず、第三者ドメインは未確認として数える。URLの使い回しは1回だけ確認。これは実際のBuffer/SNSからのアクセスを再現しないため、成功を保証せず、予約を書き換えない。公開直前やBuffer→SNSの区間で失敗する可能性は残る。第三者画像への依存、CDN経路、Cloudflareのbot対策、投稿前後の配信監視を引き続き検討し、根拠なくセキュリティ設定を緩めない。

## 運用・停止

監視のみ停止するにはGitHub Actionsの当該workflowを無効化。既存SNSワークフローやBuffer予約には影響しない。監視自体は再送しない。新規サービス契約・課金はなし。GitHub公式によれば公開repoの標準GitHub-hosted runnerは無料（公開状態や課金条件が変われば再確認）: https://docs.github.com/en/actions/reference/runners/github-hosted-runners 。

隔離テストは`python3 -m unittest discover -s tests -p 'test_buffer_delivery_monitor.py'`。Bufferを模擬し、取得/媒体別状態/過去と新しいerror/予定超過/不明時失敗/重複ID/ページ送り/画像検査先とリダイレクト/ログ秘匿を確認。既存のSNS関連テストも実行する。

## 2026-10-31: 定期起動の遅延調査と独立した復旧経路

10:42と11:12のmonitor `schedule` は11:53 JST時点でrunなし。workflowはactive、mainに存在し、手動および記事処理完了後の`workflow_run`は成功。別workflowでも同日に、07:00予定のメール処理が10:24、07:05予定のSNS追加処理が10:26、07:43予定の商品更新が10:51に`event=schedule`で開始した。これは当該runの起動時刻と、各ファイルに定義された時刻との比較であり、各処理の配信や更新完了時刻ではない。GitHub Statusは調査時点でActions operational、10/31の障害報告なし。10/30にはActions等の障害が報告され解決済みだが、今回の遅延との因果関係は未確定。GitHubはschedule遅延や欠落を明記する: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule 。個別に落ちたか、遅れて実行されるかは未特定。

従来のworkflow_run経由に加え、既存Cloudflare見張り番のSNS専用10分Cronから`bufferMonitorWatchdog`を**別のwaitUntil**で起動。`ops/watchdog/src/buffer-monitor.js`は監視workflowのrun一覧だけを読み、直近runから35分以上経過し、監視中runがない場合に限り、読み取り専用monitorのworkflow_dispatchを1回依頼する。SNSやBufferに対するPOST・更新・削除は一切しない。開始時刻を記した専用KV `buffer_monitor_watchdog:v1:last_attempt` をdispatch前に作り、35分の連続起動抑止（TTL2時間）。KVや履歴が読めない・不正・空、未知の応答、clock異常時は起動しない。dispatch応答が不明でも記録を戻さない。KVは原子的ロックではないため、同時刻競合の完全防止は保証せず、監視workflowのconcurrencyも維持。監視runが20分以上待機/実行中の場合は重複起動せずWorker Logsに `workflow-stuck` エラーを残す。GitHub通知やメールが届く保証はない。

切替は`BUFFER_MONITOR_WATCHDOG_ENABLED=0`のWorker反映。`BUFFER_MONITOR_WATCHDOG_DRY_RUN=1`は読み取りのみ。既存SNS回収用のKV・concurrency・cron、速報/災害・記事作成設定、Buffer予約を変更しない。元のGitHub scheduleは残す。Cloudflare Cron・GitHub API/Actionsの両方が止まる場合は自動回復できず、35〜45分程度の検知間隔も厳密な保証ではない。

本番の直前versionは`87d0ebec-c817-4c9f-ac15-a3cb5fd4ab0a`、先行版`a3b32965-5db2-4b74-ac38-72fc441d8f73`、停止中runの検知を加えた現行版`3812ea7d-b901-4a23-bc34-7b9b60318f48`。既存デプロイ済みbundleがローカルbaseと一致すること、vars・KV・secret binding、3 cronの維持を確認。11:53 JSTに先行版の本番Cronで `bufferMonitorWatchdog: recent-run` を観測し、同じCronで既存SNS回収もaccepted・新規投稿なし。記事処理後の監視も11:31・11:51に自動成功。最終versionも12:03 JSTの本番Cronで `bufferMonitorWatchdog: recent-run`（直近11分）とsnsExtra digest accepted / dispatched null、outcome okを確認。停止中の復旧dispatchは隔離テストとGitHub実データの未来時刻を用いたdry-runで確認しており、本番で実際に停止させて復旧させたわけではない。

## 2026-10-31: 本番の復旧経路を安全に実行

依頼に基づき、実際の障害を起こさず監視間隔を一時的に1分へ短縮し、直近の監視から12分経過した状態を「監視が古い」と判定させた。通常の投稿/予約/記事作成や監視を止めず、見張り番からの実際の起動だけを確認する試験。試験設定には12:27 JSTの自動終了期限を設けた。12:23 JSTの本番Cronは `bufferMonitorWatchdog: dispatched=true, probe=true, minutesSince=12` を記録し、同時のsnsExtraはdigest accepted / dispatched null。実際の[monitor run 41164156896](https://github.com/koyuiw7-pixel/ai-news-auto/actions/runs/41164156896)は12:23:15にworkflow_dispatchで起動、Bufferを読み取るstepまでsuccess。これは擬似的な停止判定を用いた実dispatchの証拠であり、実障害を発生させての検証ではない。

同runはThreads 58 sent/1 scheduled/1 error、X 47/2/1、Facebook 46/2/0、30分超過0。12:11からのThreads予約1件・送信済み1件の変化は、既存の12:15予約の進行と整合するが、当該IDの詳細照合は未実施。監視はSNS投稿しない。データは時点値。実行前にKV専用キーへ12:23:13を保存したことを確認、通常どおりTTL2時間・35分のcooldownを維持し、手動で消さない。試験コード・変数は削除し、workerは通常の35分へ復元、version `880e4181-9fc2-4b51-900b-8f7067551af7`。試験変数が本番から消えたこと、既存vars/KV/secret bindingおよび3 cronを確認した。試験用コミット `1be7348`、復元 `54ff711` とも[no-deploy]。10:42・11:12・11:42・12:12の元schedule起動は12:37時点で未観測、記事完了後の監視は12:11にも成功。原因やGitHub定期起動自体の正常化は未確定。

復元版は12:33:13 JSTの実Cronでoutcome ok、bufferMonitorWatchdogはrecent-run（1分）で重複起動なし、同時のsnsExtraはdigest accepted / dispatched null。試験後の通常運用に戻ったことを確認。
