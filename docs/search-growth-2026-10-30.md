# 2026-10-30 検索流入の改善記録（Claude引き継ぎ）

## 目的と範囲

オーナーの「ほかにも集客のためにできることを進める」依頼。新しいSNS告知は許可されていないため検索施策に限定。既存の速報・定時SNS・投稿履歴・広告URL・クリック計測は変更していない。短期のクリックより、回答の正確さと長期の信頼を優先する。

## 施策前に確認した実績

- Google Search Consoleをログイン済み画面で再確認。3か月表示だが、実データは2026-10-20〜27の8日間。通常検索13クリック、713表示、CTR1.8%、平均掲載順位12。
- 生成AI機能レポートは69表示、ページ表は42URL。ページ行を足すと70となり上部69と一致しないため、観測値をそのまま保存した。集計差の原因は未確認。通常検索との重複は不明で、合算しない。AIでの表示は訪問や売上ではない。
- 既存エクスポートのIPA記事は22表示・0クリック・平均3.77位、Work IQ記事は18表示・0クリック・平均9位。生成AI欄でもIPA1表示、Work IQ5表示を確認した。少数なのでCTR悪化の統計的確証ではない。サイト全体のクエリを特定の記事のクエリとみなしていない。
- ChatGPT無料ガイドは自動内部リンクで既存56記事、製品3ページから案内されていた。新規リンクを大量追加する必要はなく、リンク先の回答不足を先に修正した。
- 既存750記事にDify関連記事は0件。ニュースからの到達0をリンク故障と扱わない。Difyの4入口の相互導線は既存のまま。

## 実装した変更

1. `content/howto/chatgpt-free-plan.json` と該当 `content/evergreen_plan.json.sources`
   - 機能別の無料枠、「上限」「会話がいっぱい」「添付失敗」の対処、有料との違いを公式専門FAQ7件から整理。
   - 固定モデル名の公式資料間の差を明記。音声チャットと音声ファイル添付、PlusとAPI請求を混同しない。
   - 旧AI検査のfact/model/promptVersion/sourceHashを除去し、実際の編集方法をeditorialNoteで開示。実機で上限に達する試験・課金は実施していない。
2. `scripts/evergreen.py`、`tests/test_evergreen_editorial.py`、`evergreen.yml`
   - 明示した `refreshMode: editorial` の記事は自動生成でも `--force` でも上書きしない。
   - 期限/関連ニュースでは `needsReview` と理由を一度記録し、確認日を勝手に進めない。通常ガイドの更新枠を消費しない。
   - **編集者が再確認したときは checkedAt を更新し、needsReview / needsReviewReason を除去。refreshModeは保持。** この保護記事は人/エージェントの内容確認が必要。通常ガイドの自動更新は維持。
   - 外部APIなしの8検査を定期ワークフローへ追加。
3. IPA記事の既存URLを改善
   - 見出し・導入を「個人情報が漏えいしたら何をする？」に合わせ、正規窓口確認から情報別の対処へ案内。
   - 本文/かんたん版の両方を更新。閲覧無料と手続き費用を分離し、相談急増・確実な防御といった過剰な説明を訂正。
   - publishedAt/generatedAtを保持、updatedAtと更新注を追加。本文2191→2444字、変更前後とも既存規則でindexable。
4. Work IQ記事の既存URLを改善
   - 現行CLI/MCPの利用条件を冒頭・料金・始め方・かんたん版へ追記。課金プランと管理者同意が必要な範囲を明確化。
   - 元動画の新API/Work IQ OS/MargoをCLIと混同しない。動画自体は今回再検証していないと開示。
   - free:trueをnullへ訂正。全体を一般提供とは認定しない。元の公開日と動画参照を保持。
5. `lib/howto.ts`、Dify2ガイドの `articleIntent`、`tests/test_howto_routing.cjs`
   - 同じDifyでも料金の疑問を料金ガイドへ、起動の疑問を起動ガイドへ案内。従来は先頭一致のため料金ニュースも起動記事へ向かうことを合成例で再現。
   - API単独では料金と判断しない。意図が不明な場合・他ツールは従来順を維持。実際のDify新着が発生した成果ではなく、将来の誤誘導防止。
   - 回帰7検査を公開ワークフローへ追加。
6. `lib/sitemap.ts`
   - 既存noindex方針とサイトマップを一致させた。単記事タグとAI記事のないチャンネルを除外し、/newsと記事のある7ジャンルを追加。
   - 同一750記事データの比較では483タグ+39チャンネルを除外、入口8件追加、新1109URL。対象ポリシーの混入0・重複0。全URLをHTTPで検査した数ではない。
   - 本番の旧sitemap1616URLとの照合はボット更新時点が違うため単純差分比較しない。2000字基準やPR配信元のnoindex方針は変更していない。記事は削除していない。
7. `/news` の共有情報
   - 固有OG/Twitterタイトル・説明・URLと1200×630のブランド画像を設定。2ページ目も自己URL。以前のトップ情報継承と画像未設定を解消。
   - SNSキャッシュ済みの古い投稿カードが更新されたとは確認していない。OG設定はGoogle順位上昇の根拠ではない。

## 一次資料

- ChatGPT無料FAQ: https://help.openai.com/en/articles/9275245-chatgpt-free-tier-faq
- 添付FAQ: https://help.openai.com/en/articles/8555545-uploading-files-and-audio-to-chatgpt
- Plus FAQ: https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus
- 残りは記事のsourcesに保存。公式資料の記述に差がある点を断定で埋めない。
- IPA: https://www.ipa.go.jp/security/anshin/attention/2026/mgdayori20261026.html
- IPA相談窓口: https://www.ipa.go.jp/security/anshin/about.html
- Work IQ CLI: https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/cli
- Googleサイトマップ方針: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap

## 検証・公開

- Python既存+追加87件、計測14件、Dify振分け7件が外部送信なしで成功。
- 型検査成功。通常のローカルTurbopack buildは環境のポートbind制限で失敗したため、`npm run build -- --webpack`で検証。コードの不具合と断定しない。本番標準ビルドはGitHub Actionsの結果を別途確認する。
- 最終webpack build成功。広告通信を遮断した既存readabilityテストで主要44条件＋対象20条件、違反0。保存画像を目視確認。HTMLでは8ページのHTTP200・canonical・index指定、ニュースOG、1200×630画像、1109URLのsitemap/重複0を確認。ローカルは開発用ドメイン設定のため、canonicalの本番ドメインは公開後に別照合する。
- 追加ブラウザ検証でraw CDP権限が拒否されたため、その操作を再試行せず、拒否以前に完了した表示テストの画像とHTML検証を使用。公開後の手動クリック操作は未検証。
- 公開結果は以下に追記する。

## 効果の見方と次の優先順位

現状の検索規模だけでは目標ペースを満たす根拠はない。検索の設定修正だけで数千人/日の流入になるとは予測しない。今回の中心は、既に少数でも表示があるURLに具体的な答えを載せ、実際にクリックへ進むかを測ること。

1. GSC更新時に対象3記事のページ別表示・クリック・クエリ、生成AI表示を確認。変更当日の0クリックで成否を決めず、クロール/索引/表示/クリックを分ける。国と流入先の指標も区別する。
2. 新しい公式変更が来たら、既存Dify監視の確認待ちリストから『何が変わり、誰が何をすればよいか』に答えられる疑問を選ぶ。根拠のない予測記事や同じ回答の量産はしない。
3. 表示のある具体的疑問で、公式要約だけでは足りない部分に操作例・比較・確認手順を足す。実測が必要なら実施できる範囲を定義し、未実測と混ぜない。Gemini Excelデモの一般利用・互換性は追加調査候補だが今回は未編集。
4. /news共有画像は修正したが、既存AI朝まとめのリンク先が非AI一覧/newsである不一致は残っている。今回は検索施策のためSNS処理を変えていない。次の定時SNS改修で/genres/aiへの変更を検討し、媒体別の既存履歴と重複防止を維持する。

## 戻し方

- 変更したファイルの該当差分だけを戻す。content全体・state全体を過去へ戻さない。
- /news画像はmetadata参照とrouteを一緒に戻す。
- 手動改稿を保持する間はrefreshMode保護を外さない。本文を新しいまま保護だけ外すと次の自動生成で上書きされうる。
- 記事URL・元公開日・広告URL/タグ・SNS履歴は今回のために変更しない。
