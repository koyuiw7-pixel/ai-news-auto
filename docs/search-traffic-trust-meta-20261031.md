# 流入の切り分け・検索記事の訂正・Metaの見落とし（2026-10-31）

## 調査・判断

- オーナー提供のログイン済みCloudflare Web Analyticsを参照。日本・bot除外・同じ00:00〜18:30 JSTで10/29、10/30、10/31を比較した。非公開の詳細数値は公開repoに載せず、オーナー用ローカル記録に保存。Web Analyticsの訪問は人数ではなく、自己アクセスや未検出botも混ざり得る。日本の参照元不明は直接入力に限らずアプリ等で参照元が渡らない場合もある。減少の原因や媒体を断定しない。
- Search Consoleの7日間は10/22〜28の確定データ。直近記事修正の効果は時期が重なっておらず、平均順位や少数の表示だけで低CTRの原因を断定しない。`/articles` は検索語が表示されなかったため安易にタイトル変更しない。IPA/PHP/Work IQは直近改修済みのため、反映と十分な観測を待って評価する。
- 数学記事は一次資料の更新と異なる記載を確認。検索優先より事実の訂正を先に行う。証明の発表、Lean形式化、専門家による評価、懸賞の認定を混同しない。

## 変更

- `openai-solves-navier-stokes-millennium-problem`: URL・動画・サムネイル・広告情報・元の公開時刻を保持し、OpenAIの9/10追記とClay数学研究所の声明に合わせて本文・かんたん版・要点を修正。外部研究者のCodex入力について、同社の調査後の説明に合わせ、以前の不正確な記述を読者に明示して訂正。88時間は導出、別途Leanに17時間、証明の独立検証は未実施。未検証のベンチマークや誇張された100%の主張を削除。時刻付き動画目次は照合できないため除去。ソースは元動画とOpenAI、Clayを併記。
- `sam-altman-ai-advice-human-centric`: Search Consoleで人名の検索が観測されたため、内容に沿い人生の相談とAIという具体的な検索タイトルと説明文にした。人名検索の多くが伝記等を求める可能性もあり、CTR向上は仮説。既存URL、記事内容、広告、SNS原稿は変更しない。
- 全記事共通の発信元バッジは、動画由来も一律「公式発表」と誤表示していたため、動画は「動画紹介」、web記事は「公開情報」に変更。まとめの表示は従来どおり。実際の公式性を一律に推定しない。
- `meta-ray-ban-ai-glasses-japan-2026`: Meta日本公式の未照合候補を補う手動保護ガイド。Audioの日本展開2027年予定、Gen 3の日本販売、撮影、MuseのAIグラスでの日本対応未定を発表時点の情報として区別。日本価格・在庫・連携開始を推測せず、実機確認もしていないことを明記。Muse日本ガイドの関連記事にもつながる既存のガイド分類を使う。独自の広告リンクや投稿は追加しない。
- Meta日本一覧の監査を再実行し、直近11リンク・AI関連3件の一次URLが記事かガイドと照合された。過去の全発表に漏れがないことは意味しない。

## 保守と検証上の注意

- `refreshMode: editorial` はガイド自動生成の上書きを防ぐ。通常ニュース2記事は `followup.py` が続報時に要点や説明を更新しうるため、訂正文が残っているか次の続報時に確認する。
- `npm run build` はローカルTurbopackのポートbind `Operation not permitted` により停止し、`npm run build -- --webpack` は成功。`npx tsc --noEmit`、ガイドルーティング・Meta監査・手動編集保護の既存テストを通過。PRや計測リンクを踏まず、ブラウザは広告通信遮断で確認する。
- 変更後のGoogle再取得・表示文言・順位・流入・承認報酬は別途確認が必要。Googleが検索タイトルを必ず採用する保証はない。
- 既存コードのインデックス対象判定は、web記事について原則本文2000文字未満をnoindexにする。Googleは文字数自体を優先順位の基準としないと説明しているため、別途、短くても一次情報と読者価値のある記事の標本を調査し、既存ルールの影響と品質を確認した後に扱う。今回そのルールは変更していない。

## 本番の確認

- `cd3dc97` のCloudflareデプロイ `41193881256` は成功。数学記事・アルトマン記事・PHP記事・新ガイド・sitemapがHTTP 200。旧2記事は最初に古いHTML（`x-nextjs-cache: STALE`）が返り、再取得後に新タイトルと「動画紹介」、数学記事の訂正を確認した。新ガイドはサイトマップに含まれ、noindexなし。
- 広告・計測機能の既存テスト、ガイド導線テスト、Meta監査・手動編集保護・IndexNowのテストは成功。ローカルと本番の文字検査は広告ドメインを遮断し375/1440pxの明暗で実行。実広告主への通信や広告リンクのクリックは行っていない。実利用者の広告成果やGoogle検索反映は未確認。
- 本番数学記事の共有画像を確認し、訂正後のタイトルが反映されていることを確認。元のSNS投稿や予約は変更していない。

## 一次資料

- https://openai.com/index/navier-stokes-solution/
- https://www.claymath.org/news/navier-stokes-announcement/
- https://www.claymath.org/millennium-problems/rules/
- https://about.fb.com/ja/news/2026/09/ai-glasses-lineup-added/
- https://about.fb.com/ja/news/2026/09/meta-connect-2026-everything-we-announced/
- https://developers.google.com/search/docs/fundamentals/creating-helpful-content
