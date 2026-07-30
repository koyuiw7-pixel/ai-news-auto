# AI速報ラボ — YouTube公式発表 → Gemini解析 → 全自動SEO記事メディア

OpenAI / Anthropic / Google DeepMind など **9社の公式YouTubeチャンネル**を3時間ごとに監視し、
新着動画を **Gemini 2.5 Flash のマルチモーダル解析（映像＋音声）** にかけて日本語SEO記事を自動生成、
GitHub へ commit → Vercel が自動再ビルド、という無人運用のメディアサイトです。

```
YouTube RSS ──▶ scripts/main.py ──▶ Gemini 2.5 Flash ──▶ content/articles/*.json
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

## 監視対象チャンネル

OpenAI / Anthropic / Google DeepMind / Google / Google for Developers /
Microsoft Developer / NVIDIA / AI at Meta / Hugging Face

追加したい場合:

```bash
./.venv/bin/python scripts/resolve_handle.py @追加したいハンドル
# 出力された Channel(...) 行を scripts/channels.py の CHANNELS に貼り付ける
```

## 設定の変更

| やりたいこと | 変更箇所 |
| --- | --- |
| サイト名・説明文 | `site.config.ts` |
| 使用モデルの変更 | リポジトリ変数 `GEMINI_MODEL`（例: `gh variable set GEMINI_MODEL --body gemini-2.5-pro`） |
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
