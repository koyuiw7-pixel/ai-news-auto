# Dify検索入口の回答強化・公式変更監視（2026-10-30）

オーナー依頼：Googleの反映待ちに、根拠を持ってDify検索流入を増やす対策を進める。検索施策の範囲で、信頼・既存機能・広告を保持する。

## 優先順位と目的

1. 既存の費用記事で「何回使える？」に具体的に答える。クレジット消費量はモデル・呼出回数に依存するため、固定のモデル単価を作らず、読者が確認した残量と同じ処理1回の消費量から回数の目安を計算する。
2. 同じ記事に、クレジットとは別のCloudナレッジ要求数・保存量・文書数制限のFAQを補う。403を一律に回数制限のせいにせず、APIのHTTP応答とWorkflow内ノード失敗を区別する。
3. 公式変更監視へModel Providers・Knowledge Request Rate Limitを追加。原文の変更を検索疑問の編集候補へ変換する。自動公開しない。

これは需要・順位の予測順ではなく、既存回答の不足、根拠の明確さ、工数・破損リスクでの優先順位。既存のホーム→2記事、記事間、記事→比較の導線は存在するため、同じリンク施策を繰り返さない。無関係なニュースからDifyへ誘導しない。GSC実測・会員データは公開repoに入れず作業チャットの記録に保存する。

## 実装と保持したもの

- `components/DifyCreditEstimator.tsx`：費用記事だけに表示。空欄から始め、入力値を通信・保存・追加計測しない。APIキーは扱わない。SSRにも式・仮の200/1、200/5、200/10例・前提を出し、JavaScriptなしでも回答を読める。
- `lib/dify-credits.ts`：残量÷消費量を整数に切り捨て。小数は整数化して除算し、0.3÷0.1を2と誤算しない。残量0は可、消費0・負・非有限・範囲外は結果を出さない。
- `components/HowtoGuideView.tsx`：費用記事のslugでのみ計算欄と目次リンクを追加。他ガイドに計算欄を表示しない。
- `content/howto/dify-free-api-cost.json`：数式・3FAQ・description・実更新日時を更新。title/seoTitle/slug/初回公開日/比較先/編集保護/記事の振分け条件は保持。検索題名を連続変更しない。
- `scripts/dify_search_watch.py`：2→4資料。旧2資料の成功基準と確認待ちキューを保持するため、v1のcache識別子を維持。追加2資料は初回に基準を作り、次回以降に差分候補を出す。資料固有の見出しと必須節を検証。費用系2資料の候補は既存費用記事へ向ける。

同じ消費条件が続く場合の算数上の目安で、実行成功・無料利用・請求額を保証しない。自前APIキーの請求は別。Cloudのナレッジ制限をセルフホストの一律の制限としない。文書を安易に削除したり、VPS購入で制限が解決すると案内しない。

A8の元href・素材・rel・ピクセル・id分類、Dify計測v2、比較サービス順、SNSと自動記事作成、Cloudflare防御設定に変更なし。新しい有料契約・広告出稿・SNS投稿なし。

## 根拠

- https://docs.dify.ai/en/cloud/use-dify/workspace/model-providers ：モデル別消費、1応答と呼出数、自前キー請求。
- https://dify.ai/pricing ：Sandbox 200クレジット、10 Knowledge Request/min、50文書・50MB。
- https://docs.dify.ai/en/cloud/use-dify/knowledge/knowledge-request-rate-limit ：対象操作、403/forbidden、拒否も計上、再試行間隔。
- https://docs.dify.ai/en/cloud/use-dify/knowledge/knowledge-storage-limit ：検索用データ量、文書数、表示遅延。
- https://developers.google.com/search/docs/fundamentals/creating-helpful-content ：読者の役に立つ独自の付加価値。計算欄を追加すれば上位表示されるという保証ではない。

上記は10/30確認。Docsの10/28更新日を、制限が新設された日と解釈しない。実際のDify請求・エラー再現・負荷試験は未実施。

## 検証

公開前：クレジット境界7件、変更監視16件、手動原稿保護8件、既存広告/計測48件、記事振分け7件が成功。型検査・629ページのwebpackビルド・差分検査成功。ローカル画面で200/5→40、0.3/0.1→3、消費0エラー、残量0、空欄の5ケースを確認。ローカル起動では広告・外部解析を無効化。既存閲覧計測のローカルPOSTはローカル404であり本番へ送っていない。計算入力値はそのPOSTに含まれない。

直接`node --test lib/dify-credits.test.ts`は拡張子なしimportのため使わない。既存TS設定を変えず、次のように一時出力してテストする。

```sh
credit_test_dir=$(mktemp -d /private/tmp/saisoku-credits-test.XXXXXX)
npx --no-install tsc --target ES2022 --module commonjs --moduleResolution node --esModuleInterop --skipLibCheck --outDir "$credit_test_dir" lib/dify-credits.ts lib/dify-credits.test.ts
node --test "$credit_test_dir/dify-credits.test.js"
```

公式4資料の実取得は初回baseline4→2回目unchanged4、候補0・error0。レビュー候補の生成は、検索需要・記事公開・検索掲載・流入・収益とは別。

公開：実装`771a20997983a6e0011af7dc4f1f16d7fcf7440c`をmainへ反映。Deploy `41063760821`成功。通常のReadability `41064124863`は44条件、対象3記事の追加検査`41064510867`は12条件、計算欄を含む本番記事のローカル検査は4条件で、いずれも違反0・実行エラー0。375/1440pxと明暗テーマを確認し、広告配信先を遮断して検査した。実利用者の表示速度改善を証明する検査ではない。

本番HTML6ページを前後比較。HTTP 200、canonical、robots、広告リンク全属性、計測画像、Dify導線を保持。費用記事にだけ計算欄、403と保存量FAQが追加されたことを含む44項目が成功。sitemapのlastmodは`2026-10-30T13:23:07.000Z`で、本文updatedAtのJST 22:23:07と一致。初回の文字列一致検査はUTC/JST表記差で失敗したため、日時として比較し直した（公開データの修正不要）。費用記事1URLだけIndexNowへ通知しHTTP 200を確認。Googleの登録や検索流入増の証拠にはしない。

監視だけのGitHub実行`41063842366`を`watch_only=true`で依頼。既存の定期Evergreen実行`41063704253`を待つキューに入った。既存の自動記事作成は中断していない。新4資料の実取得は前述の独立検証で成功しているが、GitHubでの旧キャッシュ引継ぎ・定期実行結果はこのキューの完了後に確認する。

## 次の判定と戻し方

Googleが新内容を取得した後に、ページ別の表示・検索語・クリックと既存v2の可視閲覧→比較遷移を照合する。100表示または7日で初回見直し（統計的な有意差保証ではない）。表示がない間に題名を何度も変えず、登録状態と検索意図を先に確認。計算利用自体の追加イベントはなく、利用率・収益増の因果は証明できない。

問題時は今回の7ファイルの差分だけを戻す。既存記事・広告・SNS処理を停止しない。監視を2資料へ戻す場合も旧基準・既存キューを削除しない。実装コミットと公開証拠は作業チャットの`outputs/CLAUDE_HANDOFF.txt`にも保存する。
