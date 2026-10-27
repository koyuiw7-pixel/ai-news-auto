# AI速報ラボ — YouTube公式発表 → Gemini解析 → 全自動SEO記事メディア

OpenAI / Anthropic / Google DeepMind など **9社の公式YouTubeチャンネル**を3時間ごとに監視し、
新着動画を **Gemini のマルチモーダル解析（映像＋音声）** にかけて日本語SEO記事を自動生成、
GitHub へ commit → Vercel が自動再ビルド、という無人運用のメディアサイトです。

> **モデルについて**: 当初指定の `gemini-2.5-flash` は 2026年7月に Gemini API 側で提供終了しているため、
> 現行GA版の `gemini-3.5-flash` を既定にしています。利用不可のときは
> `gemini-3.6-flash` → `gemini-flash-latest` の順に**自動フォールバック**します。

```
YouTube RSS ──▶ scripts/main.py ──▶ Gemini 3.5 Flash ──▶ content/articles/*.json
                     ▲                                            │
              GitHub Actions（3時間ごと）                          ▼
                                                    commit & push ──▶ Vercel 自動デプロイ
```

## セットアップ（1コマンド）

```bash
bash setup.sh
```

対話が必要なのは **Gemini APIキーの貼り付け** と **Vercelの初回ログイン** の2つだけです。
何度実行しても壊れません（完了済みの工程は自動スキップ）。

APIキー取得: https://aistudio.google.com/apikey

## ディレクトリ構成

| パス | 役割 |
| --- | --- |
| `app/` | Next.js App Router。記事・タグ・チャンネルの各ページを**全て静的生成** |
| `components/` | Header / Footer / ArticleCard |
| `lib/articles.ts` | `content/articles/*.json` の読み込みと集約（タグ・チャンネル別） |
| `lib/markdown.ts` | Markdown→HTML変換とサニタイズ、目次抽出 |
| `scripts/main.py` | 記事生成パイプライン本体 |
| `scripts/channels.py` | 監視対象チャンネル定義（RSS疎通確認済み） |
| `scripts/resolve_handle.py` | `@ハンドル` → `channel_id` 変換ユーティリティ |
| `content/articles/` | 生成された記事（1記事 = 1 JSON） |
| `content/state.json` | 処理済み動画IDの記録（重複生成の防止） |
| `content/pricing.json` | AI料金・日本対応の早見表（`/ai-pricing`）。`scripts/pricing_table.py` が記事から抽出し、数字が記事本文にあるかを機械的に確認（毎晩） |
| `content/weekly.json` | 今週のAIニュースまとめ（`/weekly`）。`scripts/weekly.py` が毎週月曜 07:00 JST に追加 |
| `content/events.json` | イベント速報（`/events`）。日程・基調講演は公式で確認したものだけを手で入れ、`scripts/events.py` が開催状況・関連記事・発表内容を毎晩更新 |
| `.github/workflows/auto_run.yml` | 3時間ごとの自動実行 |
| `site.config.ts` | サイト名・説明文などのブランディング設定 |

## 手動での操作

```bash
# 対象になる新着動画を確認（APIを消費しません）
./.venv/bin/python scripts/main.py --dry-run

# 1本だけ生成
./.venv/bin/python scripts/main.py --max 1

# 特定チャンネルのみ
./.venv/bin/python scripts/main.py --channel openai --channel anthropic

# 特定の動画を強制的に記事化
./.venv/bin/python scripts/main.py --video "https://www.youtube.com/watch?v=XXXXXXXXXXX"

# ローカルプレビュー
npm run dev

# GitHub Actions を今すぐ手動実行
gh workflow run auto_run.yml -f max_articles=3
```

## SEO設計

- **静的生成**: 全ページを `generateStaticParams` でビルド時にHTML化（TTFBが最速）
- **pSEO**: `/tags/[tag]` と `/channels/[channel]` が記事の増加に応じて自動で増殖
- **構造化データ**: `NewsArticle` / `VideoObject` / `BreadcrumbList` / `WebSite` を JSON-LD で出力
- **sitemap.xml / robots.txt**: `app/sitemap.ts` `app/robots.ts` で記事追加時に自動更新
- **OGP**: 各記事に動画サムネイル（1280×720）を `summary_large_image` で設定
- **RSS**: `/feed.xml` を配信
- 記事内には「3秒でわかる要点」「発表タイムテーブル（動画の該当秒数へ直接リンク）」「競合比較表」「料金」「日本からの使い方」を必ず含める構成

## ジャンルと監視対象チャンネル

ジャンルごとに「記者ペルソナ」「記事の章立て」「免責文」が切り替わります。
定義は [`scripts/genres.py`](scripts/genres.py)、チャンネルとの紐付けは
[`scripts/channels.py`](scripts/channels.py) の `genre=` です。

| ジャンル | チャンネル |
| --- | --- |
| **AI・テクノロジー** | OpenAI / Anthropic / Google DeepMind / Google / Google for Developers / Microsoft Developer / NVIDIA / AI at Meta / Hugging Face |
| **不動産** | 楽待 RAKUMACHI / ウラケン不動産 / ゆっくり不動産 / マンションマニアの住まいカウンター / イエノミカタ |

- 候補動画は**ジャンル交互**に取り出されます。投稿頻度の高い1チャンネルが枠を占有して、
  他ジャンルの記事が生成されなくなるのを防ぐためです。
- 不動産はYMYL領域のため、投資助言・断定表現を禁止し、リスクの章を必須にし、
  「投資勧誘ではない」旨の免責文を自動表示します。
- サイト上は `/genres/ai` `/genres/real-estate` のジャンルページが自動生成されます。

新ジャンルを足すときは `scripts/genres.py` に `Genre` を1つ追加し、
チャンネル定義で `genre=` に指定するだけです。

チャンネルを追加したい場合:

```bash
./.venv/bin/python scripts/resolve_handle.py @追加したいハンドル
# 出力された Channel(...) 行を scripts/channels.py の CHANNELS に貼り付ける
```

## マネタイズ

### 収益導線（CTA）

[`monetization.json`](monetization.json) にジャンル別のCTAを定義すると、
サイト内の4箇所に自動で差し込まれます。

| 位置 | スロット | 意図 |
| --- | --- | --- |
| 記事中盤（後半セクションの前） | `inline` | 読んでいる流れを止めない軽い導線 |
| 記事末（読了直後） | `primary` | 最も成約しやすい位置。主力の1本を置く |
| サイドバー（追従） | `secondary` | 滞在中ずっと見えるサブ導線 |
| トップのジャンルセクション下 | `primary` | 回遊中のユーザーを拾う |

```json
{
  "real-estate": {
    "primary": {
      "eyebrow": "無料・1分で完了",
      "title": "あなたの条件で、収益物件の実際の利回りを調べる",
      "body": "記事で扱った数字はあくまで一例です。…",
      "buttonLabel": "無料で物件データを見る",
      "url": "https://www.rakumachi.jp/?ref=あなたのID",
      "note": "提供: 楽待"
    }
  }
}
```

**アフィリエイトIDが未設定（`YOUR_ID` のまま）の場合**、CTAは消えるのではなく
**計測パラメータを外した公式サイトへの通常リンク**として表示されます。
このとき「PR」表記と `rel="sponsored"` は付きません（未提携の状態で報酬リンクを装わないため）。
URLを実IDに差し替えた瞬間に、収益リンクへ自動で昇格します。

### 信頼性を担保するページ（審査の必須要件）

AdSenseとASPの審査では、運営者の実在と連絡手段の明示が求められます。以下を実装済みです。

| ページ | 内容 |
| --- | --- |
| `/about` | 運営者情報・編集方針・**AI生成であることの全面開示** |
| `/privacy` | Cookie・アクセス解析・AdSense・アフィリエイトの取り扱い |
| `/disclaimer` | 免責事項・投資勧誘ではない旨・著作権・削除依頼の受付 |
| `/contact` | 訂正依頼／権利者からの削除依頼の窓口 |

> **審査前に必ず [site.config.ts](site.config.ts) の `operator` を実際の情報に差し替えてください。**
> `representative`（運営責任者名）と `email` が初期値のままだと審査に通りません。

### 収益化の進め方（順番が重要）

#### ステップ0: 独自ドメインを取得する ← **これが最優先**

`*.vercel.app` のサブドメインでは **Google AdSense の審査に通りません**。
AdSense はサイトの所有権確認とルート直下の `ads.txt` 設置を求めますが、
共有ドメインである vercel.app ではどちらも行えないためです。
一部のASPも同様の理由でサブドメインを却下します。

```bash
# Vercel でドメインを取得して紐付ける（年1,500円前後から）
vercel domains buy sakiyomi.jp
vercel domains add sakiyomi.jp

# 取得後、絶対URL（sitemap / OGP / canonical）を新ドメインに向ける
vercel env add NEXT_PUBLIC_SITE_URL production   # https://sakiyomi.jp
vercel deploy --prod
```

#### ステップ1: ASPに登録する

不動産系は成果単価が高く（資料請求1件で数千円〜1万円超）、本サイトの主収益源になります。

| ASP | 審査 | 主な取り扱い | 備考 |
| --- | --- | --- | --- |
| **A8.net** | サイト審査なし | 楽待・タウンライフ・COZUCHI・モゲチェック | **最初はここ。即日登録できる** |
| **afb** | サイト審査あり | RENOSY・不動産一括査定・住宅ローン | 単価が高く、金融・不動産に強い |
| **もしもアフィリエイト** | ゆるい | 幅広い | W報酬（ボーナス）あり |
| **アクセストレード** | あり | 金融・不動産 | 上記で足りなければ |

海外のAIツール（ElevenLabs / Perplexity など）は日本のASPにほぼ無いため、
各社サイトの Affiliate / Partner ページから直接申し込みます。

#### ステップ2: IDを設定ファイルに反映する

提携が承認されたら、発行されたリンクを2つのファイルに書き込みます。

- [`monetization.json`](monetization.json) … CTA（記事中盤・記事末・サイドバー・トップ）
- [`affiliate_links.json`](affiliate_links.json) … 記事内で言及されたツールの自動リンク

```bash
./.venv/bin/python scripts/main.py --relink   # 既存記事にも遡って反映
git add -A && git commit -m "chore: アフィリエイトリンク設定" && git push
```

`YOUR_ID` を実IDに置き換えた項目から順に、公式リンク → 成果報酬リンクへ自動で切り替わります。
「PR」表記・`rel="sponsored"`・プライバシーポリシーの文言も自動で連動するため、
手作業での書き換えは不要です。

#### ステップ3: AdSenseに申請する

記事数・運営者情報・プライバシーポリシー・免責事項・お問い合わせは実装済みです。
独自ドメインを設定したうえで申請し、承認後に下記を設定してください。

### Google AdSense（3枠設置済み）

広告枠は既にテンプレートへ埋め込み済みです。設置箇所は以下の3つ。

| 位置 | 実装箇所 |
| --- | --- |
| ① 記事トップ（タイトル・リード文の下） | `app/articles/[slug]/page.tsx` の `<AdSlot position="article-top" />` |
| ② 記事中盤（第3章の直前に自動挿入） | 本文HTMLを3つ目の `<h2>` で分割して挿入 |
| ③ サイドバー最上部 | `components/Sidebar.tsx` の先頭 |

**現在はダミー枠（`AdSense Dummy`）が表示されています。** 本番広告への切り替えは
コード修正不要で、Vercel に環境変数を設定するだけです。

```bash
vercel env add NEXT_PUBLIC_ADSENSE_CLIENT production            # ca-pub-XXXXXXXXXXXXXXXX
vercel env add NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_TOP production  # 広告ユニットのスロットID
vercel env add NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_MIDDLE production
vercel env add NEXT_PUBLIC_ADSENSE_SLOT_SIDEBAR production
vercel deploy --prod
```

設定すると `adsbygoogle.js` の読み込みと `<ins class="adsbygoogle">` の出力が自動で有効になります。

### アフィリエイト（自動リンク挿入）

[`affiliate_links.json`](affiliate_links.json) にツール名とリンクを登録しておくと、
記事生成時に「その記事が言及したツール」と自動で照合され、リンクが挿入されます。

```json
{
  "OpenAI": {
    "url": "https://openai.com/?ref=あなたのID",
    "label": "ChatGPT / OpenAI 公式",
    "note": "補足説明（任意）",
    "aliases": ["ChatGPT", "GPT-5", "Sora"]
  },
  "11labs": "https://11labs.io/?あなたのリンク"
}
```

- 値は **文字列（URLだけ）でも、オブジェクトでも**書けます。
- `aliases` に表記ゆれを入れると拾える範囲が広がります（大文字小文字は無視）。
- **`YOUR_ID` を含んだままのURLは挿入されません。** 実IDに書き換えて初めて有効になります。
- 照合は Gemini が返す `mentioned_tools`（記事が実際に言及した製品名）を主に使い、
  本文の全文一致で取りこぼしを補います。
- 挿入先は「本文中の最初の1回」＋「記事末の紹介ボックス」＋「サイドバー」の3箇所。
- リンクには `rel="sponsored"` を付与し、**PR表記と免責文を自動表示**します
  （Googleのガイドラインと景品表示法のステマ規制への対応）。

`affiliate_links.json` を書き換えたあと、既存記事にも反映したい場合:

```bash
./.venv/bin/python scripts/main.py --relink   # APIを使わずリンクだけ貼り直す
git add content && git commit -m "chore: アフィリエイトリンク更新" && git push
```

## 外部システム連携API

社内の管理システムなどから、記事の生成状況を取得するための読み取り専用APIです。
すべて `Authorization: Bearer <token>` が必要で、**`INTEGRATION_API_TOKEN` が未設定のときは
API 自体が 503 で無効になります**（トークン未設定で誰でも読める状態を作らないため）。

| エンドポイント | 内容 |
| --- | --- |
| `GET /api/v1/stats` | 記事総数、ジャンル別・チャンネル別の内訳、24h/7d/30dの生成数、解析済み動画数・スキップ数・失敗数 |
| `GET /api/v1/articles` | 記事メタ一覧。`?genre=` `?channel=` `?since=`（ISO8601）`?limit=`（最大100）`?offset=` で絞り込み。`?include=body` で本文も取得 |
| `GET /api/v1/runs` | 実行状況。進行中か、最終成功日時、連続失敗回数、直近の実行履歴 |

```bash
curl -H "Authorization: Bearer $INTEGRATION_API_TOKEN" \
  "https://ai-tech-express.jp/api/v1/articles?genre=investment&limit=20"
```

### 必要な環境変数（Vercel）

| 変数名 | 必須 | 用途 |
| --- | --- | --- |
| `INTEGRATION_API_TOKEN` | ✅ | API認証。**設定済み** |
| `INTEGRATION_GITHUB_TOKEN` | `/runs` のみ | GitHub Fine-grained PAT。権限は `Actions: Read` だけでよい |
| `INTEGRATION_ALLOWED_ORIGINS` | ブラウザから叩く場合 | CORS許可オリジン（カンマ区切り） |

`/api/v1/runs` は GitHub Actions API をサーバ側でプロキシします。
連携先システムに GitHub の認証情報を渡さずに済ませるための構成です。

### Webhook（プッシュ通知）

記事が生成されるたびに、連携先へ POST します。GitHub Secrets に2つ設定すると有効になります。

| Secret | 用途 |
| --- | --- |
| `INTEGRATION_WEBHOOK_URL` | 通知先URL。**未設定なら通知処理はスキップされます** |
| `INTEGRATION_WEBHOOK_SECRET` | HMAC-SHA256の署名鍵 |

```json
{ "event": "articles.generated", "created": 3, "total": 141,
  "runId": "31287435207", "occurredAt": "2026-08-09T01:06:17Z" }
```

署名は `X-Saisoku-Signature: sha256=<hex>` ヘッダで送られます。受信側での検証例:

```python
import hmac, hashlib
expected = "sha256=" + hmac.new(SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, request.headers["X-Saisoku-Signature"]):
    abort(401)
```

> **PV・UUは取得できません。** アクセス解析を接続していないためです。
> 必要なら Vercel Analytics の有効化が別途必要です。

## 設定の変更

| やりたいこと | 変更箇所 |
| --- | --- |
| サイト名・説明文 | `site.config.ts` |
| 使用モデルの変更 | リポジトリ変数 `GEMINI_MODEL`（例: `gh variable set GEMINI_MODEL --body gemini-3.6-flash`） |
| 実行間隔 | `.github/workflows/auto_run.yml` の `cron` |
| 1回あたりの生成本数 | ワークフローの `max_articles`（既定3本） |
| 記事の構成・文体 | `scripts/main.py` の `PROMPT_TEMPLATE` / `SYSTEM_INSTRUCTION` |
| 配色 | `app/globals.css` の `@theme` |

## 運用上の注意

- **APIコスト**: 1記事あたり動画1本分の入力トークンを消費します。長時間動画（基調講演など）は高額になるため、
  `max_articles` を上げすぎないでください。無料枠には1日あたりのYouTube動画処理上限があります。
- **記事の正確性**: 生成物はAIの出力です。全記事フッターに免責表示を入れていますが、
  公開前に目視確認する運用を推奨します。
- **失敗時の挙動**: 動画の解析に2回失敗した動画は `content/state.json` の `failed` に記録され、以降スキップされます。
  再挑戦させたい場合は該当エントリを削除してください。
- **ショート動画**: RSSにはShortsも含まれます。Geminiが `is_relevant: false` と判定した動画は記事化されません。
