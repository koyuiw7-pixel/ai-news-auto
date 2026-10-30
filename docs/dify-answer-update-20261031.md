# Dify公式変更の確認から既存回答を更新する経路（2026-10-31）

## 完成した範囲

`scripts/dify_search_watch.py` は公式の本文変更を検出して確認待ち候補を作る。新しい `scripts/dify_answer_update.py` は、その候補に更新先の既存ガイド・関連FAQ・記事と出典のhash・計測対象を付けて、編集者が確認するJSON資料を作る。初期動作は提案だけ。外部原文を命令として実行せず、LLM・有料API・SNS・広告への通信は行わない。

確認済みJSONを `--apply` で明示指定した場合だけ、既存2ガイドの一部をローカルで更新できる。公開、検索登録、検索クリック、訪問、比較への遷移、A8の発生・承認は別の段階であり、この処理の成功を流入や売上の成功とは呼ばない。

## 監視する公式資料と既存状態の保持

- `release`: GitHubの公開安定版release
- `docker-compose`: 公式Docker Compose設置手順
- `model-providers`: AIクレジット・自分のAPIキー・利用優先順位
- `knowledge-request-rate-limit`: Knowledgeの要求数制限
- `deployment-faqs`: 公式設置FAQ（今回追加）。特に `Remote branch null not found` の説明変更を候補化する。

追加資料の初回取得はbaselineであり、変更の発見とは扱わない。最初の2資料から計算した既存 `SOURCE_FINGERPRINT=bea8f580f106af9b` とstate version 1を保ち、従来4資料の成功基準・確認待ちキューを捨てない。資料取得失敗時にも直前の正常本文を維持する。公式HTTP取得は固定URL、HTTPS同一ホストへのリダイレクトのみ、応答の種類・サイズ・本文の見出しを確認する。

## 編集できる対象

`content/howto/dify-free-api-cost.json` と `content/howto/dify-1-18-startup-check.json` のみ。対象の `slug` と `refreshMode: editorial` が一致する必要があり、symlinkを拒否する。

編集できるのは既存FAQの質問/回答、FAQ1件追加、intro、conclusionの既存1項目、stepsの既存bodyだけ。配列全体の置換や削除はできない。料金表、title/seoTitle/description、URL、公開日、source一覧、広告、計測、商品、確認コマンド、自動再生成設定は編集対象外。既存広告URLを含む文章の編集や新しい広告URL追加も拒否する。

各変更は `path`・正確な `before`・編集後の `after` の3項目を指定する。FAQ追記は `/faq/-`、`before: null`、`after: {q, a}`。文章は通常の文字列に限り、HTMLタグに使う山括弧・危険な制御文字・空文字を拒否する。FAQの質問・編集先の重複を拒否する。

## 操作手順

リポジトリ直下で実行する。packetの出力先は `work/` 配下のJSONに限り、絶対パスのチャット作業用 `work/` も使える。repo内では `work/` 以外を禁止し、原稿・コード・入力state・既存の別種の作業資料を上書きしない。symlinkは解決後のパスで検査し、出力用の一時ファイル名は毎回新しく作る。監視の実行とレビュー済みJSON適用を同じ作業中に混ぜず、適用するまでstateを固定する。stateの確認日時だけが更新された場合も、現時点の安全側の設計ではpacket再作成を求める。

```sh
python3 scripts/dify_search_watch.py --state work/dify-review/state.json --report work/dify-review/watch-report.json
python3 scripts/dify_answer_update.py --state work/dify-review/state.json --packet work/dify-review/answer-review-packets.json
```

初回のstateや公式本文に変更がない場合、差分候補は0件になる。既存ガイドの不足回答を確認するために、例えば次を実行する。

```sh
python3 scripts/dify_answer_update.py --state work/dify-review/state.json --review-source knowledge-request-rate-limit --packet work/dify-review/manual-review.json
```

この場合は `trigger: manual_current_source_review`、`previousHash: null` となる。「新変更を検知した」とは記録しない。`--review-source deployment-faqs` で起動ガイド側の確認資料も作れる。

出力の `packets` から1件を `reviewed.json` にコピーする。出典URLと根拠本文、既存FAQと対象版を読み、`review` と `edits` だけ記入する。hashやID、根拠や更新先を手で都合よく書き替えない。

```json
{
  "review": {
    "reviewer": "確認担当者名",
    "checkedAt": "タイムゾーン付きの実際の確認日時",
    "decision": "approved",
    "rationale": "参照した公式節と、既存回答に何が不足しどこを直すか",
    "meaningAndPricingReviewed": true,
    "versionAndAudienceReviewed": true
  },
  "edits": [
    {
      "path": "/faq/-",
      "before": null,
      "after": {"q": "確認済みの質問", "a": "公式根拠に合う通常の文章"}
    }
  ]
}
```

上記は記入部分だけの例であり、適用ファイルには元packet全体が必要。確認日時は根拠観測以後、未来ではない、タイムゾーン付きISO形式とする。料金や意味、Cloud/セルフホスト・対象版・読者の違いを確認した明示フラグが必須だが、真偽をコードだけで保証できるわけではない。人または担当AIが一次資料に照らして内容を確認する責任を代替しない。

```sh
python3 scripts/dify_answer_update.py --state work/dify-review/state.json --reviewed work/dify-review/reviewed.json --dry-run
python3 scripts/dify_answer_update.py --state work/dify-review/state.json --reviewed work/dify-review/reviewed.json --apply
```

`--reviewed` だけでもdry-runになる。dry-runを含め、適用直前に固定された公式URLを再取得し、正規化後の本文hash・公式URLが確認時と同一でなければ停止する。packetのhashと現在の原稿バイト列、編集前の値、候補ID、確認担当/日時も照合する。外部取得や確認が失敗した場合は原稿を書き換えない。

書込み直前にも原稿の一致を確認し、同じディレクトリ内の一時ファイルから置き換える。並行編集用のロックではないので、同じガイドを同時に編集・適用しない。実行後はdiffを読み、必要な公開チェックを別に行う。CLIはcommit/push/deployを行わない。

## 記録と重複

実際に適用した場合、対象JSONの `answerUpdateHistory` に修正ID、候補ID、手動/変更検知の区別、担当、確認日時、適用日時、出典URL/hash、更新前の記事hash、編集path、判断理由を残す。`updatedAt` のみ元原稿と同じタイムゾーンで更新し、部分確認を記事全体の再確認としないため `checkedAt`・`needsReview`・sourcesの各確認日は維持する。

検知候補のIDは公式資料の変更前後hashと分類から決まる。適用済みIDは原稿内履歴から参照し、次のpacket出力では `completed` に分けて再依頼しない。既存watchの履歴キュー自体は消さない。手動確認IDは出典と記事のhashに依存し、記事が変わった後の新たな不足確認は可能。古い適用JSONの再利用、同一質問の再追加、古い記事に対する更新は拒否する。

## 定時実行と検証

既存 `evergreen.yml` の `dify-search-watch` ジョブだけを変更。1日4回の既存時刻を保ち、境界テスト→公式監視→packet作成→報告artifactの順で処理する。`dify-search-review` artifactには監視report、packet、**そのpacket作成時と同じ `source-state.json`** を30日保存する。stateは公式公開資料の本文と確認記録だけで、秘密・アクセス解析・会員情報は含まない。hidden cacheパス全体をartifactへ渡さず、対象stateだけを作業用ディレクトリへコピーする。workflowに `--apply` は追加しない。既存の有料記事生成ジョブ、SNS、手動原稿の保護は変更しない。`watch_only=true` の手動実行では生成ジョブをスキップして確認できる。

CIの資料を使う場合は、そのrun IDのartifactをまとめて取得する。`RUN_ID` は確認する実際の実行番号へ置き換える。

```sh
gh run download RUN_ID -n dify-search-review -D work/dify-review/from-ci
python3 scripts/dify_answer_update.py --state work/dify-review/from-ci/source-state.json --reviewed work/dify-review/reviewed.json --dry-run
```

`reviewed.json` は**同じrunの `answer-review-packets.json` の1件**へレビュー/編集を記入したものを使う。差分0件なら、同梱stateと `--review-source` で手動確認packetを作る。別runのcache、最新に再scanしたstate、別時点の記事を混ぜない。原稿または公式資料が変わった場合は、古いhashを改ざんして通さず再作成・再確認する。ダウンロードした同run stateでのdry-run後も、公開前の実表示と構造化データ検証は別に必要。

```sh
python3 -m unittest discover -s tests -p test_dify_search_watch.py
python3 -m unittest discover -s tests -p test_dify_answer_update.py
```

監視17件、適用14件のケースで確認。出典失敗時の基準保持、5番目資料の初回と差分の区別、cache互換、提案のみ/明示適用、原稿手編集と公式変更後の拒否、対象外フィールド・不正日時・HTML/広告URL・重複拒否、既存データ保持、取得中の並行編集保持、時間帯維持、proposal出力先による原稿上書き防止を含む。テストは外部接続しない。実運用の公開・流入・収益の実測は別記録に残す。
