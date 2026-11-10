# 1時間ごとの数字の記録（com.komuro.saisoku-kpi）の入れ方

このMacで1時間に1回、`scripts/kpi_hourly.py` を動かします。
数えるもの：日本の人の訪問（自動ブラウザを除く。Threads のアプリ内ブラウザは「Unknown」と出るが人なので数える）、2ページ目に進んだ人の割合（推定）、人による広告クリック、今日の Threads 投稿。

## 入れる（リーダーが3つのコマンドを動かす）

```bash
git clone -q --filter=blob:none https://github.com/koyuiw7-pixel/ai-news-auto.git ~/.saisoku-kpi/repo
cp ~/.saisoku-kpi/repo/ops/launchd/com.komuro.saisoku-kpi.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.komuro.saisoku-kpi.plist
```

- 入れた直後は動きません（RunAtLoad は false）。1時間後から動きます。すぐに1回試すときは `python3 ~/.saisoku-kpi/repo/scripts/kpi_hourly.py --dry-run`（何も書きません）。
- 毎回のはじめに、専用の写し（~/.saisoku-kpi/repo）だけを `git pull -q --ff-only` で最新にします。メインのフォルダ（~/自動きじ）には触りません。

## 鍵（新しく作らない。今あるものを読むだけ）

- Cloudflare：このMacの wrangler のログイン（または環境変数 CLOUDFLARE_API_TOKEN）。plist には鍵を書きません。
- 広告クリック：AFF_STATS_TOKEN（環境変数、なければ ~/自動きじ/.env.local）。見つからないときは「数えられない」と記録します。
- 鍵の中身は表示も記録もしません。

## 書く場所

| 何を | どこに |
|---|---|
| 毎時の記録（1行ずつ足す） | ~/.saisoku-kpi/kpi_hourly.jsonl |
| 警報を出したかの覚え | ~/.saisoku-kpi/alerts_sent.json |
| 動いた記録 | ~/.saisoku-kpi/kpi.log |
| 今日の毎時の表（毎回上書き） | Googleドライブ「サイソク連絡/kpi-hourly.md」 |
| 警報（足すだけ。ほかの行は変えない） | Googleドライブ「サイソク連絡/to-claude.md」 |

- status.md には書きません（Claude が30分ごとに上書きするため）。status.md を更新するときは kpi-hourly.md から写します。
- 記録は GitHub に上げません。

## 警報が出るとき

- 12:00・16:00・20:00 を過ぎた最初の回に、訪問が目安より少ないときだけ1件（1日1回ずつ）。目安どおりなら何も書きません。
- 目安の線（500人の日）：9時50人、12時130人、15時230人、18時330人、21時430人、24時500人。その日の目標（.claude/metrics.json の days の target）に合わせて比例させます。
- Threads：直近3時間の「1投稿あたりの訪問」が、今日のこれまでの中央値の半分未満で、しかも5人未満のとき（投稿が2本以上の時間だけ、3時間に1回まで、6:00〜23:59）。
- Cloudflare のログインが切れたとき（1日1回）。直し方：`npx -y wrangler whoami`。

見出しの形：`## [K-1605] 2026-11-10 16:05 計測（自動）→Claude 【未対応】`

## 止める・外す

```bash
launchctl unload ~/Library/LaunchAgents/com.komuro.saisoku-kpi.plist
```

## 注意

- 2ページ目率と1訪問あたりのページ数は推定です。Cloudflare の集計には訪問ごとのページ数がないため、「サイト内から来たページ表示 ÷ 訪問」で出しています。
- 回数が多すぎると言われた（429）ときは5分待って1回だけやり直し、だめならその時間はあきらめます。
