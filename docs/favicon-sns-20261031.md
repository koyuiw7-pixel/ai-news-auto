# SNSとfaviconの絵柄をそろえる変更（2026-10-31）

## 変更理由と素材の来歴

Threadsのサイソク公式プロフィールを通常UIで目視すると、赤い背景に大きな白い「速」、その下に「サイソク」がある。既存のサイト用512px画像はこの構図だったが、`app/favicon.ico`だけ「速」単独だった。

既存ローカル原本 `out/brand/saisoku-icon-2048.png`（2048×2048）を使った。原本のSHA-256は `d04346c83ad967cbfb193bd54978951edfbb99915c77832c9752302459ded820`。SNS上の画像と目視で構図が一致している。SNS画像自体のダウンロードは取得できていないため、SNS配信ファイルとのバイト一致は未検証。古い黒地・青地の「サ」画像は使っていない。

## 最小の変更

- `app/favicon.ico`：原本をsharpのLanczos3で16・32・48・64・128・256pxへ縮小し、各RGBA PNGをICOへ格納。切り抜き、文字の描き直し、色変更、別デザインの作成はしていない。
- `app/layout.tsx`：metadata.iconsで既存の `/icons/icon-512.png` と `/icons/apple-icon-180.png` を明示。Next.jsが自動出力するfavicon.icoも残る。明示設定を入れると自動のapple-icon linkが補充されないため、appleも明示した。
- `scripts/check_search_identity.py`：安定URLのicon linkがあることと、既存 `/icon` が `/icons/icon-512.png` と同じPNGを返すことを追加確認。画像本体の比較は1MB上限、その他のアイコンは従来どおりヘッダー部分のみ取得。第三者ホストへの転送は追わず、広告・JavaScript・SNS送信・検索申請を実行しない。

新ICOのSHA-256は `8363526ef6b58772777a5d338cd80321bf90b34b3bcbb76fe975f77ef30daff0`、31,815バイト。

## 保持する経路

`app/icon.tsx` の `/icon`、`app/apple-icon.tsx` の `/apple-icon` は引き続き配信する。フィードは `/icon` を参照しており削除しない。manifest、ホーム画面用192/512px画像、maskable画像、通知の単色badge、Service Worker、push payloadは変更しない。publisherの512pxロゴ、canonical、サイト名、SNS用記事画像、広告リンク、計測、自動投稿枠も変更しない。

既存 `public/icons/icon-512.png` のSHA-256は `be4a586ada5218a5213457e09030ee4a1333ff8f5df0241f238d668bca8d7b33` のまま。

## 検証と限界

- ICOの6フレームを抽出し、寸法・PNG形式・ディレクトリのオフセットを検証。6サイズを実寸で目視した。
- 16pxでは大きな「速」は識別できるが、下の「サイソク」4文字を読むのは難しい。細部を勝手に省略せず、SNSと同じ構図を保持した。128/256pxでは下の文字も読める。
- CLIの14テスト成功。安定URLのlink欠落、同じ寸法で別画像を返す場合、旧 `/icon` の消失、1MBを超える画像を失敗として検出する。
- `npx tsc --noEmit --incremental false` と `git diff --check` 成功。保持対象13ファイルが変更前と同一であることを確認。本番ビルド・公開・HTML表示確認は別工程。commitだけでGoogleのfavicon表示を直したとは扱わない。

Google検索での地球アイコンは、サイト側の公開後もGoogleによる再取得・処理が必要。条件を満たしても表示は保証されず、数日〜数週間かかる場合がある。URLを頻繁に交換したり、再取得申請を連打したりしない。[Google公式faviconガイド](https://developers.google.com/search/docs/appearance/favicon-in-search)

## 本番確認

2026-10-31 01:39:48 JSTのDeploy41091544828で公開。本番favicon.icoは新ICOとバイト一致、6サイズを確認。stable PNG・旧/icon・旧/apple-icon・manifestはHTTP200、旧/iconと512PNG同一。検索監査fail0、旧Vercelの404警告3は既知で今回未解消。Google検索画面の地球アイコン置換は未確認。新しい課金やドメイン変更はしていない。
