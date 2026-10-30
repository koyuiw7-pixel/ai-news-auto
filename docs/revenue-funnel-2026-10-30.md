# 2026-10-30 計測とDify導線（Claude引き継ぎ）

## 依頼・判断の原則
収益と流入を前倒しで改善。ただし短期数字のために長期の信頼を犠牲にしない。成果は「実装」「公開」「計測」「ASP発生」「承認」「入金」を分ける。購入不要な読者に契約を勧めない。報酬を理由に順位や事実を変えない。

## 今回の導線
トップページの案内 / /guides → /choose/dify-hosting → 無料Dify Cloud / 手元のPCの公式手順 / XServer VPS既存提携リンク。
トップページの既存ニュース・PR枠の下に文字リンクの案内を追加し、/guidesとフッターにも入口を追加。トップの主役のニュースやメニュー5項目は維持。トップからのguide_clickはhome-guidesで区別（トップの案内表示数自体は未計測）。Difyをタイトル・SEOタイトル・タグに含むAI記事には既存chooseGuideForArticleの仕組みで関連案内。無関係なニュースには表示しない。既存 /compare の公開フラグや2,000字判定は変更しない。ニュース生成・SNS・災害・通知・記事データは変更しない。

## テーマと案件の根拠
- 既存GSCの8日分には n8n vps の表示1件。セルフホストの手掛かりだが、Difyの需要や検索ボリュームの証明ではない。需要が確立した勝ち筋とは呼ばない。
- Dify公式は2 CPUコア / 4 GiB RAMの最低要件を明示。macOSのDocker VMは8 GiBで、混同を避けた。
- 初心者に安い2GB VPSを売るより、無料クラウド・ローカル・常時運用を比較する具体的な疑問に答えられる。
- 既存のXServer VPS提携リンクがあり、公式にDifyアプリイメージ・4GB以上対応・SSL同時設定を確認できる。新規提携や契約はしていない。
- ConoHa VPSは公式料金ページに新規受付停止表示があるため今回の行き先から除外。既存の広告設定全体は変更していない。
- n8n v3はearly accessで、安定版の強制移行と扱うと誤認を招くためこの一本には混ぜない。
- ChatGPT一般記事は既存ガイドがあり、VPS案件への文脈の飛躍が大きいので今回の入口には選ばない。
- A8管理画面は未ログイン。最新の提携継続状態・成果報酬額・否認条件・承認期間は未確認。既存設定のリンクをそのまま使い、現在の単価や成約可能性を保証しない。

## 2026-10-30に確認した一次情報
- https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose : 最低要件、OS別の条件。
- https://dify.ai/pricing : Sandbox無料、200 message credits（毎月とは記載しない）、1人・5 apps。
- https://vps.xserver.ne.jp/price.php : 4GBの1か月契約は初回・更新2,640円、36か月契約は月額換算2,035円。36倍73,260円は編集部の算数。税込は下記Dify案内でも確認。
- https://vps.xserver.ne.jp/dify.php : 4GB以上、4vCPU / NVMe SSD150GB、DifyイメージとSSL同時設定。
- https://vps.conoha.jp/pricing/ : 新規受付停止表示。
- https://github.com/langgenius/dify/blob/main/LICENSE : 利用形態ごとに条件の確認が必要。法的適合性は断定しない。
比較対象は網羅的ランキングではない。実機・契約による速度比較はしておらず、その旨を公開ページに明記。

## 計測仕様と限界
既存 /api/aff/click の c: キー・集計は維持。新規 POST /api/aff/event は f: キー、90日保持。既存日次GET /api/aff/statsにfunnelフィールドを追加（Bearer認証継続）。scripts/aff_stats.py は旧JSONにも対応。
対象はdify-hosting一本。entry_view=/guidesが可視状態1秒、guide_click=導線への信頼されたクリック、guide_view=導線ページの可視状態1秒、comparison_view=比較表の見出しが半分以上表示、choice_click=行き先3種類の信頼されたクリック。1ページ滞在中は同種・同行き先を1回、サーバーは10秒重複排除と20件/10分制限。広告クリックとは制限枠を分離。
- 表示を確認したブラウザイベントであり、実在人間を完全に保証しない。訪問者は日次IP/UAハッシュの推定。人数を日をまたいで加算しない。
- 表示・遷移の周辺集計で、順番が成立したセッション数ではない。検索から直接入る人もいるので guide_click / guide_view の比率を一律CVRと呼ばない。
- 1秒以内に押すとクリックだけが記録される場合がある。未送信・広告ブロッカー・DNT/GPC等による欠測はあり、Cloudflare Web AnalyticsやGSCとは一致しない。
- 流入元はGoogle等の許可した分類のみ。UTMは自己申告で改変可能、SNSアプリで参照元が失われる場合はdirect/otherになる。
- タブ内sessionStorageに分類と時刻だけを保存し30分以内に再利用。氏名・検索語・全文URL・長期IDは保存しない。生IPは計測DBに残さない。プライバシー説明更新。
- A8発生・承認・入金はこの集計では分からない。ASP画面と別途照合する。
- 本番で自己クリックして数字を作らない。テストはモックKVとローカルで行う。クリック到達先の改変やA8タグ追記をしない。

## 更新・撤退・拡張の基準
11/6まで待つ工程は撤廃し、一本を先に公開して計測開始。日付だけで成功・失敗を決めない。実需要がなければページ量産や無関係記事への広告増設をしない。
1. ガイド一覧からの遷移が少ない: 見出しと掲載位置、表示母数を確認。関連しない層への露出は増やさない。
2. ガイドの表示自体が少ない: GSCでクロール・インデックス・クエリ確認。Difyの公式変更から生じる実際の疑問を同URLに追記。SNS配信は既存実験を壊さず別途明示承認の範囲で。
3. 比較到達が少ない: 冒頭の回答を短く、費用と対象者を分かりやすく修正。無料枠を隠して広告へ誘導しない。
4. 無料・手元PCの選択が多い: 読者の現在の用途として尊重。VPSへの強制転換をしない。無料導入手順への需要を調べる。
5. VPSクリックがあるがASP発生がない: まず提携継続、クリック認識、対象プラン、否認条件を確認。量を増やす前に契約・計測上の問題を切り分ける。
6. 発生があるが承認が遅い: 事業者の承認期間と条件で判断。期限未到来を失敗や確定収益と扱わない。
母数100で成約0なら、真の成約率の片側95%上限は約3%という粗い目安になるが、期間・流入の偏りや承認遅延がある。少数データで勝ち負けを断定しない。

目標達成に必要な導線訪問は（目標純利益＋月間費用）÷（承認報酬単価×広告遷移率×発生率×承認率）。現在は報酬条件と実測率が未確認なので達成確証はない。データ不足を楽観値で埋めない。既存の11月/1月/4月目標は維持し、実測の到達可能額が不足したら、検証済みテーマの追加・再訪導線・広告以外の収益源も検討する。信用を落とす煽り、薄い量産、無理な長期契約の推奨は行わない。

## 検証・デプロイ
2026-10-30 11:24 JSTの本番読み取り: 10/28と10/29は0、10/30は既存記事で広告クリック2・日内推定訪問者1。テストクリックはしていない。ASP売上ではない。
14項目の計測回帰テスト node scripts/test_aff.mjs 成功。クロスオリジン拒否、認証、ボット/DNT/GPC除外、入力制限、重複排除、無料/広告の分離、旧クリック互換、ページネーションを確認。
ロールバックは今回の変更コミットをrevert。既存KVの削除は不要。新しいf:データは旧コードから無視され90日後に消える。

ローカル統合検証: 127.0.0.1のNext本番ビルドとhandleAffをメモリKVで接続。Chromeで/guides→Difyガイドへ操作し、entry_view / guide_click / guide_view / comparison_view / choice_clickを確認。無料先と広告先のchoice別保存、および従来c:クリックの保存を確認。検証用にローカルページのリンク既定遷移だけを止め、広告・外部解析の通信を遮断。実ASPと本番KVへの自己クリックなし。通信ログの保持範囲でも広告リクエストなし（ログは一部切り詰めあり）。
一時的にDocumentsのiCloudプレースホルダでI/Oが停止。元の変更を退避し、/private/tmp/saisoku-funnel-20261030 の feat/trusted-revenue-funnel-local で継続。旧work/sns-publish-fixは同一作業の古い途中コピーのため、そのままpushしない。

本番公開 38c9a96234028d10956cf889611426e75d8fc787 / Deploy run 40992654369 success（2026-10-30 11:38 JST）。
本番7ページHTTP200、Dify canonical / index,follow / sitemap / JSON-LD有効、既存A8 URL完全一致を確認。旧広告集計2回/推定1訪問者を維持し、新funnelは0から開始。HTTP所要時間はLCPや実利用者性能ではない。
既定Readability run 40992875115 は11ページ×2幅×2テーマ=44条件で違反0。
Google Search Console 2026-10-30 11:44:16 のライブテスト: Google検査ツール（スマートフォン）、クロール許可=はい、ページ取得=成功、インデックス登録許可=はい。インデックスには未登録。登録リクエストはreCAPTCHAサービスへの接続エラーで失敗。再読み込み後も同じエラーだったため、2回で中止し、申請受理とは扱わない。CAPTCHAの解答・迂回はしていない。サイトマップからの発見は可能だが登録・順位・時期の保証はない。
Google-InspectionToolはUAにbotを含まないため、画面/Worker共通の除外リストへ明記し回帰テストを追加。GoogleOtherも除外。サイトへのアクセス拒否ではなく計測対象から除くだけ。一次資料 https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers 。

新ガイド・既存比較2本・プライバシー・編集方針の追加Readability run 40993371061 は5ページ×2幅×2テーマ=20条件で違反0。初回の44条件と合わせて64条件を完了。
Google検査UAの除外修正 29e76b21101f40fbe5e2d19a20753692353302e9 / Deploy run 40993668196 success。14項目テスト・OpenNextビルド・Cloudflareデプロイが成功。
11:55 JSTの最終読み取り: 新ガイドHTTP200、配信中のJavaScriptにも除外修正を確認。認証付き集計APIはfunnel version 1有効。旧集計2クリック/日内推定1訪問者、新導線の全5段階は0。実訪問・成約を証明する数字はまだない。
ローカル検証では通常TypeScriptとWorker単体の型検査、npm run build、SNS公開確認の既存7テストが成功。モバイル375pxで横はみ出しなし、PC1440pxで比較表確認、ブラウザのコンソールエラーなし。これらは回帰確認であり全機能の無欠陥や実ユーザーLCP改善の証明ではない。

## Claudeが次に見る順序
1. origin/mainの最新を取得し、この記録とAGENTS.mdを読む。元のfeat/web-sourcesと古いwork/sns-publish-fixをmainへ上書きしない。実装は38c9a96、計測除外の追補は29e76b2。
2. scripts/aff_stats.py --date YYYY-MM-DD --json で日付別の実測を読み、無料/有料の行き先と流入元を分ける。鍵は既存.env.localから読み、中身を表示・記録しない。
3. A8で最新の提携状態・成果条件・認識クリック・発生・承認を照合する。今回A8は未ログインで、ログインや契約を代行していない。固定報酬額や成約率を仮定して収益確定としない。
4. GSCのURL検査を後で再確認。取得成功とインデックス登録は分ける。登録申請の接続障害は未解消のまま記録する。
5. 需要の観測に応じて上の改善基準を適用。購入不要な読者を有料へ追い込まず、料金や提供条件が変わったら同じURLを更新する。期間限定価格や未確認機能でクリックを煽らない。

変更一覧: lib/choose-dify.ts、lib/choose-data.ts、components/choose/ChooseView.tsx、app/page.tsx、app/guides/page.tsx、components/Footer.tsx、app/articles/[slug]/page.tsx、lib/revenue-funnel.ts、components/RevenueFunnelTracker.tsx、components/AffClickTracker.tsx、app/layout.tsx、cloudflare/aff.ts、cloudflare/aff.test.ts、scripts/test_aff.mjs、scripts/aff_stats.py、.github/workflows/deploy_cloudflare.yml、app/privacy/page.tsx、app/editorial-policy/page.tsx、AGENTS.md、この記録。
証拠はCodexチャットのoutputs/REVENUE-FUNNEL-change-record.txt、dify-funnel-production-verification.json、dify-funnel-local-verification.json、dify-readability-*.json、画面キャプチャ。SNSの前回記録はSNS-403-change-record.txtを参照。

最終Readability run 40993891924 は初回に /ai-pricing 375/light のPage.navigate応答待ちで失敗（他43条件は違反0）。/ai-pricing と /usable は別のHTTP読取で200・約1.2〜1.3秒を確認。同じ検査ジョブを再実行し、attempt 2 は44条件で成功。コードや閾値を変更して通したものではない。初回エラーは検査中の一時的な応答停止で、発生原因の断定や実利用者の速度保証はしない。


## A8本人ログイン後の追加確認（2026-10-30 12:42 JST）
XServer VPS（s00000001642013）は提携中、提携日10/26、終了未定。4GB通常プランは1か月契約の報酬2,000円、3か月以上は3,000円。Web申込＋料金支払が成果条件。重複、トラフィックサイト、返金キャンセル、リスティング違反、対象の紹介/割引経由、初回30日未満かつ判定時点未更新などは否認対象。
再訪問期間90日、成果確定目安は約30日。プログラム全体の確定率91.34%をサイソク自身の確定率には置き換えない。
4GBのみで報酬10万円に届かせるには承認34件（3,000円）〜50件（2,000円）が必要。経費前の計算。流入・遷移・申込・承認率はまだ実績不足で、達成予測には使えない。11/26という日付に対し、発生・承認・入金の期限を分けて管理する。10/30から獲得を開始しても約30日の承認目安があるため、11/26までに承認される前提を置かない。
A8今月の概要: 表示8,489/クリック515/発生0件0円/確定0円/累計未確定0円（セルフバック除外）。これは新導線の数字ではない。KVとの計測範囲・期間・ボット除外をそろえる前に、515を人の訪問者や有効クリックと扱わない。
公開したDify導線を当該プログラムの広告掲載URL管理へ提出。提出済み一覧に https://ai-tech-express.jp/choose/dify-hosting と更新日時2026-10-30 12:42:23を確認。広告をクリックせずURLの管理登録だけを行った。証拠outputs/dify-a8-url-submitted.png。
新規契約・購入・支払い・自己成果づくりは行っていない。応募コンテストの賞金は一時収益として継続収益と分ける。
