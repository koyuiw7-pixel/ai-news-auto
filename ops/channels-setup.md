# 再訪・転載チャネルの設定（オーナー作業）

コードはすべて入っていて、鍵が無いあいだは何もしません（失敗もしません）。
下の手順で鍵を入れた時点から動きます。

## 1. メール配信（毎朝7時・前日の5本）

仕組み: 登録欄（記事末・フッター・/newsletter）→ Cloudflare KV `saisoku-newsletter` に保存（ダブルオプトイン）
→ 毎朝 22:00 UTC に `.github/workflows/newsletter.yml` が `scripts/newsletter.py` を実行。

送信は **Cloudflare Email Service**（Workers Paid に月3,000通が含まれる。超過は1,000通あたり $0.35）。
新規アカウントは1日の上限が控えめに始まり、送信実績で増えます。

### 手順（10分）

1. 送信ドメインを有効にする（DNS に SPF/DKIM が自動で入ります）
   ```sh
   npx wrangler email sending enable ai-tech-express.jp
   ```
2. Cloudflare ダッシュボード → My Profile → API Tokens → Create Token（Custom）
   - 権限: **Account / Email Sending / Edit**（アカウントは自分のもの）
   - 名前の例: `saisoku-email`
3. 発行したトークンを2か所に入れる
   ```sh
   npx wrangler secret put CF_EMAIL_TOKEN      # サイト（登録時の確認メール）
   gh secret set CF_EMAIL_TOKEN                # 毎朝の配信
   ```
4. 自分のアドレスで /newsletter から登録 → 確認メールのリンクを開く → 翌朝7時に届けば完了。
   すぐ試すなら GitHub の Actions → Daily Newsletter → Run workflow（force=true）。

鍵を入れる前に登録した人には、最初の実行で確認メールがまとめて送られます。

### 代わりに Resend を使う場合

Resend 無料枠: 月3,000通・**1日100通**（確認メール込み）・独自ドメイン認証が必要。
`RESEND_API_KEY` を同じく `wrangler secret put` と `gh secret set` で入れる（Cloudflare の鍵があればそちらが優先）。

## 2. LINE公式アカウント（任意）

無料のコミュニケーションプランは **月200通（＝配信回数×友だち数）で、超過配信できません**。
毎日配信すると友だち6人で上限に達するため、既定は **週1回（月曜朝7時）・直近7日のAI記事5本**。
送る前に「今月の残り通数 ≥ 友だち数」を確認し、足りなければ送りません。

1. LINE公式アカウントを作成（https://www.linebiz.com/jp/entry/ ）
2. 管理画面 → 設定 → Messaging API を有効化 → LINE Developers でチャネルアクセストークン（長期）を発行
3. `gh secret set LINE_CHANNEL_ACCESS_TOKEN`
4. 毎日にしたいとき（友だちが少ないうち・有料プラン）: `gh variable set LINE_DIGEST_DAYS --body daily`
5. サイトに友だち追加ボタンを置くときは、管理画面の「友だち追加ガイド」の URL を教えてください。

## 3. note / はてなブログ（転載用の下書き）

```sh
python3 scripts/crosspost_drafts.py          # out/drafts/YYYY-MM-DD/ に note用・はてな用の下書き
python3 scripts/crosspost_drafts.py --hatena # はてなブログへ「下書き」として送る（鍵があるとき）
```

- note: 公式の投稿 API が無いので手で貼る（自動投稿ツールは規約違反の恐れ）。1日1〜2本で十分。
- はてなブログ: 設定 → 詳細設定 → AtomPub の API キー。
  `HATENA_ID` / `HATENA_BLOG_ID`（例 saisoku.hatenablog.com）/ `HATENA_API_KEY` を環境変数に。
  既定は下書き。確認してから公開。`HATENA_PUBLISH=1` で即公開（おすすめしない）。
- はてなブックマーク: 自分の記事を自分でブックマークし続けるのはスパム扱いされやすいので、やらない。
  はてなブログに書いた要約が読まれて、自然にブックマークされるのを待つ。
- Qiita: 技術記事の共有の場で、ニュース要約や誘導目的の投稿はガイドライン違反になりやすい。
  実際に試した手順（例: CDK での構築）を自分で書くときだけにする。
