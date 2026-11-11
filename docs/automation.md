# 本番ページを機械で開くときの決まり（エージェント・CI 向け）

本番（https://ai-tech-express.jp）のページには A8 などの提携リンクと表示計測の画像（`*.a8.net/0.gif`）が入っている。
自動ブラウザで開いたり、提携リンクを押したりすると、ASP の表示回数・クリック数が人以外で水増しされ、
成果ゼロのクリックが積み上がって不自然な数字に見える（2026-10-27: A8 クリック 134 回に対し、人の訪問は 61）。

## 守ること

1. **本番を実ブラウザで開くときは、次のドメインへの通信を止める**（スクショ・見た目の確認・読みやすさの検査すべて）
   - `*.a8.net`（`px.a8.net` `rpx.a8.net` `www*.a8.net` の計測画像・バナー）
   - `*.afl.rakuten.co.jp`（楽天アフィリエイト）
   - `amazon.co.jp` `*.amazon.co.jp` `amzn.to`（Amazonアソシエイト。tag=saisokuai-22 のリンク）
   - `*.amazon-adsystem.com`
   - `*.googlesyndication.com` `*.doubleclick.net` `*.googleadservices.com` `adservice.google.com` `*.adtrafficquality.google`（AdSense）
   - **訪問者の数の計測（2026-11-11 オーナー承認・台帳 O17。必ず）**: `static.cloudflareinsights.com`（Cloudflare Web Analytics の読み込み。エッジで全ページに差し込まれる）と、送り先の `/cdn-cgi/rum`。止めないと、撮影・確かめの1回ごとにその日の訪問者が増える（2026-11-11 に自分たちの撮影で訪問者の数が汚れた）
   - 確かめるだけのとき: サイトの自前の計測 `/api/aff/*`（クリック・入口の表示・読んだ深さ・お金の導線）
   - 止める決まりは1か所 `scripts/browser_guard.cjs`（Node）・`scripts/browser_guard.py`（Python）。本番を開く新しいスクリプトは必ずこれを使う（`tests/test_browser_guard_20261111.cjs` が見張る）
2. **提携リンク（`rel` に `sponsored` を含む a）は押さない・URL を取りに行かない**（curl・WebFetch・リンク切れ検査も禁止）。
   リンク先の確認は管理画面（A8 など）で行う。
3. **自社アクセスのしるしを付ける**: 本番の URL には `?_internal=1` を付けるか、ヘッダー `X-Saisoku-Internal: 1` を付ける（curl・Playwright の `extraHTTPHeaders`・Lighthouse の `--extra-headers`）。記事への流入数（`scripts/inflow_report.py`）と提携リンクのクリック数から除くため。
4. 見た目の確認はできるだけローカル（`npm run dev`）で行う。`next dev` では計測画像を出さない（`VERCEL_ENV` が production のときだけ出す）。
   `npm run cf:preview`（wrangler dev）は wrangler.jsonc の `VERCEL_ENV=production` で計測画像が出るので、1. と同じく止めること。

## 止め方

- **Chrome を自分で起動する場合**（いちばん確実。新しいタブ・ポップアップも止まる）:
  `--host-resolver-rules="MAP a8.net ~NOTFOUND, MAP *.a8.net ~NOTFOUND, MAP *.afl.rakuten.co.jp ~NOTFOUND, MAP amazon.co.jp ~NOTFOUND, MAP *.amazon.co.jp ~NOTFOUND, MAP amzn.to ~NOTFOUND, MAP *.amazon-adsystem.com ~NOTFOUND, MAP *.googlesyndication.com ~NOTFOUND, MAP *.doubleclick.net ~NOTFOUND"`
- **スクショが欲しいだけなら** `node scripts/safe_shot.mjs https://ai-tech-express.jp/articles/<slug> --out shot.png --width 390 [--full] [--selector CSS]` を使う（計測・広告を止め、`?_internal=1` と `X-Saisoku-Internal: 1` も付ける。最後に「Cloudflare の計測に届いた通信 なし」と出ることを確かめる）。まとめて撮るなら `npm run check:readability -- --paths /articles/<slug> --shots out/shots`（同じ止め方が入っている）
- **Playwright で自分で書くとき**: `const guard = require("./scripts/browser_guard.cjs"); await guard.guardPlaywright(context);`（ほかの route を登録した後に呼ぶ）。Python は `from browser_guard import guard_sync` → `guard_sync(context)`
- **Playwright**:
  ```js
  await context.route(/^https?:\/\/([^/]+\.)?(a8\.net|afl\.rakuten\.co\.jp|amazon\.co\.jp|amzn\.to|amazon-adsystem\.com|googlesyndication\.com|doubleclick\.net|googleadservices\.com)\//, (r) => r.abort());
  ```
- **通信を止められないブラウザ**（Claude のブラウザ画面・Chrome 拡張・computer use で動かす Safari / Chrome など）では本番のページを開かない（Cloudflare Web Analytics を止められず、訪問者に数えられる）。見た目は safe_shot.mjs で撮った画像で確かめる。
- 画面側でも、自前の計測（ReadingBeacon・InflowBeacon・AffClickTracker・RevenueFunnelTracker）は `navigator.webdriver` が true の自動ブラウザでは送らない。ただし Cloudflare Web Analytics は画面側で止められないので、上の止め方が必要

## 人のクリックの数え方

提携リンクのクリックは自前でも数えている（自動ブラウザ・クローラーは数えない）。
`python3 scripts/aff_stats.py --yesterday` で前日分が出る（A8 の数字と並べて見る）。仕組みは cloudflare/aff.ts。
記事に外から来た人（流入元・投稿ごと）は `python3 scripts/inflow_report.py --yesterday`。仕組みは cloudflare/inflow.ts。
