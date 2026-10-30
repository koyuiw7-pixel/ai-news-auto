# サイソクAIニュース 開発ガイド（AIアシスタント向け）

このファイルは、ChatGPT / Codex / Claude などのAIが、このリポジトリで開発や補助をするときに最初に読む説明書です。
オーナーはエンジニアではありません。**返事は日本語で、専門用語を避けて短く**伝えてください。

---

## 1. サイソクとは

- **サイト**: https://ai-tech-express.jp （サイソクAIニュース）
- **一言で**: 海外・国内のAIやテックの新発表を、**公式発表から最短数分で**日本語の記事にするニュースサイト。
- **強み**: 「どこよりも最速」。速報が最優先。
- **記事の特徴**: 結論→要点→「日本で使える？」「無料？」まで書く。専門用語なしの「かんたん版」と「専門家版」を切り替えられる。
- **運営**: 個人（オーナー1人）。記事・速報・SNS投稿はほぼ全自動。

## 2. 目標（数字）

| 時期 | 直近30日の目標粗利 | 日本の訪問者（1日） |
|---|---|---|
| 2026/11/26 | 10万円（努力目標） | 2,500人 |
| 2027/01/26 | **50万円（必達）** | 10,000人 |
| 2027/04/26 | 100万円 | — |

2026/10/30のオーナーの最新訂正により、この計画での「目標粗利」は次の式で追う。以前の全経費控除後の利益という定義を置き換える。
**判定日を含む直近30日の承認済み報酬などの確定売上 − 同期間に対応する、サイソク拡大のため今後新たに発生する費用。**
対象は広告費、新規契約、既存契約の増額・従量利用の増加、外注・検証費など、サイソク拡大に伴う追加分。契約後の継続費も対象とし、初回だけ差し引いて済ませない。
既存の共用ツール費・既存の運営固定費・他事業の費用は、この目標粗利から控除せず参考管理とする。既存共用費の円決済額や按分の調査を、集客改善の前提条件にしない。
未承認の発生額・入金額・30日換算ペースは別に記録し、達成額と混同しない。控除対象の追加費用が未確認なら0円扱いしない。追加投資の評価では「投資によって増えた承認報酬 − 追加費用」も別に確認する。

日々の数字は `.claude/metrics.json`（ローカルのみ）に記録している。

## 3. 仕組みの全体像

```
公式発表・ニュース ──▶ 見張り番(Cloudflare Worker, 2分ごと) ──▶ GitHub Actions で記事生成(Python + LLM)
                                                               │
                                     品質チェック(読みやすさ・事実確認) ─┤
                                                               ▼
                         content/articles/*.json ──▶ Next.js をビルド ──▶ Cloudflare Workers で公開
                                                               │
                                       SNS自動投稿(Threads / X / Facebook / Bluesky) ・ プッシュ通知 ・ メルマガ
```

- **サイト本体**: Next.js 16（App Router）＋ OpenNext で **Cloudflare Workers**（worker名 `saisoku-site`）に載せている。Vercel はもう使っていない。
- **記事を作る側**: `scripts/` の Python。GitHub Actions（`auto_run.yml`）が定期実行する。
- **速報の見張り**: `ops/watchdog/`（別の Cloudflare Worker）。公式サイト65社以上を2〜30分ごとに見て、大きな発表があれば記事生成をすぐ起動する。地震・津波（気象庁）も見ている。
- **公開**: main に push すると `deploy_cloudflare.yml` が自動でデプロイ（約3〜5分）。

## 4. フォルダの地図

| 場所 | 中身 |
|---|---|
| `app/` | ページ（トップ、記事、/news、/guides、/choose、/products、/ai-pricing など） |
| `components/` | 画面の部品 |
| `lib/` | 共通の処理（記事の読み込み、広告、インデックス判定など） |
| `cloudflare/` | Worker 側の処理（プッシュ通知、クリック計測、画像配信など） |
| `content/articles/` | 記事データ（1記事＝1つのJSON）。**ボットが毎日大量に更新する** |
| `content/howto/` | 「使い方・料金」の解説記事データ |
| `content/offers.json`, `content/affiliate_links.json` | 広告（A8・楽天・Amazon）の設定。`scripts/a8_import.py` で作り直す |
| `scripts/` | 記事生成・品質チェック・画像・SNS投稿・計測などのPython |
| `ops/watchdog/` | 速報の見張り番 Worker |
| `state/` | 自動処理の記録（投稿履歴など）。ボットが更新する |
| `docs/` | 文字の見やすさのルール（`typography.md`）、自動テストの決まり（`automation.md`）など |
| `.github/workflows/` | 自動実行の設定 |

## 5. 主な自動処理（GitHub Actions）

| ワークフロー | 役割 |
|---|---|
| `auto_run.yml` | 記事の生成（通常＋速報）、画像付け、公開判定 |
| `deploy_cloudflare.yml` | サイトの公開 |
| `breaking_post.yml` | 速報のSNS即時投稿＋プッシュ通知 |
| `sns_extra.yml` | 朝7:30のまとめ投稿、火・金の問いかけ投稿 |
| `bluesky.yml` | Bluesky への投稿 |
| `evergreen.yml` | 「使い方・料金」解説記事を1日4本 |
| `missed_check.yml` | 毎朝8:30、取りこぼした大ニュースがないか確認 |
| `newsletter.yml` | 毎朝7時のメルマガ |
| `readability.yml` | 文字の見やすさの自動チェック |

## 6. 大事なルール（必ず守る）

### 中身
- **事実だけを書く**。推測で数字や機能を作らない。出典は公式発表を優先し、確認日を書く。
- **地震・津波の記事はAIに文章を書かせない**（気象庁のデータを型に入れるだけ）。推測・被害の記述は禁止。
- 誇張した見出し・「戻れなくなる」等の根拠のない言い切りは禁止。

### 見た目（オーナーの好み）
- デザインは「報道ネイビー×速報レッド」（紺 `#1d4a8f` / 赤 `#c8221a` / 背景 `#f3f5f8` / 文字 `#0b1a33`）。
- **嫌いなもの**: 地味すぎる見た目、ごちゃごちゃ、AIっぽいボタン（右上矢印「↗」など）、黄色いマーカー、Zen Kaku フォント、PR感の強い広告枠。
- 広告は**ふつうのページと同じ見た目で自然に**。広告表記は小さな1行（法律上必要なので消さない）。
- 文字の見やすさ: `npm run check:readability` が **0件** であること（`docs/typography.md`）。

### 広告・計測
- 広告リンクは `rel="sponsored nofollow noopener noreferrer"`。広告主の素材URL・計測タグを独自に作り替えない。2026/10/30のオーナー指示による例外は、Dify比較の指定XServer VPSリンク2か所への**A8公式パラメータ機能のid1〜id3追記だけ**。元のa8mat・遷移先・エンコード・画像タグは保持し、他の広告へ広げない。仕様・制約は `docs/dify-a8-attribution-20261030.md` を参照。
- テストでブラウザを動かすときは、a8.net・楽天・Amazon・AdSense への通信を止める（`docs/automation.md`）。止めないと広告の数字が水増しされる。
- 訪問者数は **Cloudflare Web Analytics（ロボット除外）** を見る。Facebook からの大量アクセスはロボット（リンクプレビュー）なので人として数えない。
- 広告の「人によるクリック」は `python3 scripts/aff_stats.py --yesterday`。

### 安全
- **秘密の値（APIキー・パスワード・トークン）を画面やログに出さない**。保存場所は GitHub Secrets / Cloudflare の secret。
- パスワード入力・課金・規約への同意・アカウント作成は**オーナー本人が行う**。
- オーナーの名前でSNSに投稿・コメントするときは、**必ず事前にオーナーのOKをもらう**。
- 別プロジェクト（マイソク: maisoku-maker.jp、ポート3000 など）には触らない。
- 住所・電話番号はサイトに載せない（サイト上は「東京都」まで）。

## 7. 作業の進め方

1. `git fetch && git merge origin/main` で最新にする（ボットが頻繁に push している）。
   - 衝突したら `content/*`・`state/*`・`content/llm_usage.json` は **main 側（相手）を採用**。
2. 変更する。
3. 確認: `npx tsc --noEmit` / `npm run build` / `npm run check:readability`（0件）。
4. コミット → main に push → `deploy_cloudflare.yml` の成功を確認 → 本番で表示を確認。
5. オーナーへの報告は、**結果を最初に、日本語で短く**。

## 8. 主な秘密・設定の名前（値はここに書かない）

- GitHub Secrets: `CF_DEPLOY_TOKEN`, `BUFFER_API_KEY`, `RESEND_API_KEY`, `JINA_API_KEY`, `BLUESKY_APP_PASSWORD`, `VAPID_PRIVATE_KEY`, `PUSH_SEND_TOKEN`, `AFF_STATS_TOKEN` ほか
- GitHub Variables: `WEB_DAILY_CAP`（通常記事の1日上限）, `THREADS_MODE`, `BLUESKY_HANDLE`, `EVERGREEN_DAILY_CAP`, `SNS_FORMAT`, `SNS_DIGEST`
- Cloudflare: アカウント `51e37d82e15d397b9666dc3d09bd5b92`、KV（記事キャッシュ・画像・メルマガ・プッシュ・クリック計測）

## 9. アカウント（参考）

- SNS: Threads `@saisoku637` / X `@saisoku_ai` / Facebookページ「サイソクニュース」/ Bluesky `@ai-tech-express.jp`
- 収益: A8.net（通信・転職・ガジェットなど）、楽天（A8経由）、Amazonアソシエイト（`saisokuai-22`、180日以内に3件の販売が必要）、AdSense（審査中）
- 検索: Google Search Console（`sc-domain:ai-tech-express.jp`）、Bing Webmaster Tools、IndexNow

---
最終更新: 2026-10-30

最近の変更: [通常SNS投稿の403修正・掲載検証の記録](docs/sns-403-fix-2026-10-30.md)。復旧確認で前倒しした1件は、履歴を保持しつつ形式比較の学習対象から除外している。

- 計測とDify導線の変更・限界・運用判断: `docs/revenue-funnel-2026-10-30.md`。短期収益より長期の信頼を優先し、無料で足りる読者に契約を勧めない。

- Dify検索入口2記事・変更監視・検索申請・検証と未確認事項: `docs/dify-acquisition-2026-10-30.md`。今回は検索施策のみ。Threads草案に投稿許可はない。

- 定時SNSの遅延回収・媒体別履歴/Buffer照合・商品更新の分離: `docs/automation-recovery-2026-10-30.md`。今回の朝まとめ/火金企画の復旧検証はオーナー依頼済み。Dify単発草案の投稿許可とは別。商品更新は`product_refresh.yml`で行い、記事処理へ戻さない。SNSの受理不明記録を消して再送しない。

- 検索流入改善（ChatGPT/IPA/Work IQ、Dify振分け、sitemap、手動改稿保護）: `docs/search-growth-2026-10-30.md`。`refreshMode: editorial` は自動再生成せず編集待ちを記録する。確認後はcheckedAtを更新しneedsReviewとneedsReviewReasonを消す。
