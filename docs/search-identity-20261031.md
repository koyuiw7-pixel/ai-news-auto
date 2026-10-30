# 媒体の同一性と速度の根拠 2026年10月31日

ブランド検索、旧サイトを引用するAI概要、検索結果のfavicon、ニュース枠について調査し、現サイトで検証可能な情報を整えた。検索順位やGoogle側の表示を操作・保証する修正ではない。会員画面の数値・画像・個人アカウント情報はこの公開文書に入れない。

## 変更

- `lib/publisher.ts` を7種類の構造化データ出力で共有。`NewsMediaOrganization`・`/#publisher`・既存512角ロゴ・媒体名・公式SNS・編集/訂正方針を統一。旧600×60の発行元ロゴは正方画像に変更したが、faviconとSNSカード画像は維持。
- 通常記事と試作記事に制作元と編集方針への可視リンク。人間が全記事を全文確認したとは表示しない。
- トップと`/about`で正式名/略称/正規URL/提供価値を明記。公式発表時刻とHTTP 200初確認を照合した3例を、定義とともに表示。
- 速度集計・旧推定バッジは`docs/latency-evidence-20261031.md`を参照。記事生成/SNSコード/予約/投稿履歴は不変。過去SNS文面の訂正を完了した意味ではない。
- `scripts/check_search_identity.py`：HTML、robots、favicon、媒体情報、news-sitemap、旧URLの転送を読む監査CLI。広告/JSを実行せず、正直な監査UA、許可ホスト外の転送拒否。現サイトの異常はexit1、旧404はwarning。`--legacy-retired`は意図的廃止の分類で、移転成功とはしない。新しい定期実行・通知は設定していない。

## 残課題

- 旧`ai-news-auto.vercel.app`はroot/about/記事とも404。現在のCloudflareで動く`next.config.ts`だけでは旧Vercelホストを転送できない。旧ホストの復旧、利用条件、必要な費用を決めてから対応する。正規サイトのDNSをVercelへ戻さない。
- faviconの現在のリンクと実体は正常。Googlebot-Imageを名乗る一般取得の成功は、実際のGoogleクローラによる最新取得の証明ではない。Googleのアイコン・サイト名・AI概要・順位反映は未確認。
- HTTPの正規ホストへのHEADが200で、HTTPSへの転送は別途検討。HTTPS canonicalは維持。今回Cloudflareの防御・API・キャッシュは変更していない。
- 文字数だけのnoindexを一括解除していない。独自価値の確認を通した記事の個別見直しは別工程。
- `generatedAt`と厳密な初公開日時の混同、原発表日時の精度保持は継続課題。Anthropic1記事の日時不一致は速度の確認済み集計から除外。出典日表示と抽出元の追跡を追加調査する。

## 検証

実装：`301e32c`、`11dc323`、`5648989`、`dad566f`。
Cloudflare公開：GitHub Actions `41085404033`、2026-10-31 00:58:52 JST、version `e650c360-4aa8-4cb5-b7f8-bdcea61f1b39`。CIの629ページbuild・deploy・既存計測/案内テスト成功。

ローカル型検査成功。通常Turbopackはローカルのポート割当エラー、Webpack本番build629ページ成功。Cloudflare用Turbopack buildはCIで成功したため、アプリのビルド不良と環境の失敗を区別する。
計測48、Dify案内7、速度6、検索監査10の計71テスト成功。ローカル44表示条件で違反0。本番8ページのHTTP/canonical/robots/広告全属性とpixel/Dify案内先を変更前後で照合し保持を確認。発行元情報、署名、速度実例も本番HTMLで確認。
本番検索監査：現サイトfail0、旧URL404警告3。news-sitemapの件数は直近2日という時間窓で変動する。
本番表示検査はCI `41085688835`で44条件・違反0・error0。ローカルからの重複本番検査は途中で進行が止まったため完走扱いにせず、CI結果を採用した。トップとaboutの2URLはIndexNowにHTTP200で受理された。Googleの取得/登録/順位更新の証拠とはしない。

```sh
python3 scripts/check_search_identity.py --json
python3 scripts/latency.py report --days 7 --json
python3 -m unittest discover -s tests -p test_latency.py
python3 -m unittest discover -s tests -p test_check_search_identity.py
node scripts/test_aff.mjs
node --test tests/test_howto_routing.cjs
```

## 復旧と引継ぎ

問題があれば上記の今回差分だけを戻して通常デプロイする。生成記事、投稿履歴、広告情報、Claudeが追加した1日9投稿枠は戻さない。監査用sidecarは公開日時と原資料を再照合し、未確認の値を一律verifiedへしない。公開・Google取得・検索表示・人の訪問・発生・承認を別段階で記録する。

根拠：[サイト移転](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)、[favicon](https://developers.google.com/search/docs/appearance/favicon-in-search)、[サイト名](https://developers.google.com/search/docs/appearance/site-names)、[AI機能](https://developers.google.com/search/docs/appearance/ai-features)、[News掲載](https://support.google.com/news/publisher-center/answer/9607025)、[News透明性](https://support.google.com/news/publisher-center/answer/6204050)。
