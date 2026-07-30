#!/usr/bin/env bash
# =============================================================================
#  AI速報ラボ — ワンショット構築スクリプト
#
#  使い方:  bash setup.sh
#
#  何度実行しても壊れません（冪等）。すでに終わっている工程は自動でスキップします。
#  途中で対話が必要なのは次の2つだけです:
#    1) Gemini API キーの貼り付け  → https://aistudio.google.com/apikey
#    2) Vercel のログイン（初回のみブラウザが開きます）
# =============================================================================
set -euo pipefail

REPO_NAME="${REPO_NAME:-ai-news-auto}"
REPO_VISIBILITY="${REPO_VISIBILITY:-private}"   # public にしたい場合: REPO_VISIBILITY=public bash setup.sh
cd "$(dirname "$0")"

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
ok()    { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn()  { printf '\033[33m!\033[0m %s\n' "$*"; }
fail()  { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }
step()  { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
step "0. 前提コマンドの確認"
# ---------------------------------------------------------------------------
for cmd in node npm git python3 curl; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd が見つかりません。先にインストールしてください。"
done
ok "node $(node -v) / npm $(npm -v) / $(python3 -V)"

if ! command -v gh >/dev/null 2>&1; then
  warn "GitHub CLI (gh) が未インストールです。インストールします…"
  if command -v brew >/dev/null 2>&1; then brew install gh; else fail "gh を手動でインストールしてください: https://cli.github.com"; fi
fi

if ! gh auth status >/dev/null 2>&1; then
  bold "GitHub にログインします（ブラウザが開きます）"
  gh auth login -h github.com -p https -w -s repo,workflow
fi
ok "GitHub 認証済み: $(gh api user --jq .login)"

# ---------------------------------------------------------------------------
step "1. 依存パッケージのインストール"
# ---------------------------------------------------------------------------
[ -d node_modules ] || npm install
ok "Node パッケージ: OK"

if [ ! -d .venv ]; then python3 -m venv .venv; fi
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt
ok "Python パッケージ (google-genai): OK"

# ---------------------------------------------------------------------------
step "2. Gemini API キーの設定"
# ---------------------------------------------------------------------------
if [ -f .env.local ] && grep -q '^GEMINI_API_KEY=.\+' .env.local; then
  GEMINI_API_KEY="$(grep '^GEMINI_API_KEY=' .env.local | cut -d= -f2-)"
  ok ".env.local から読み込みました"
else
  bold "Gemini API キーを取得して貼り付けてください（入力は画面に表示されません）"
  echo "  取得先: https://aistudio.google.com/apikey"
  read -rsp "  GEMINI_API_KEY: " GEMINI_API_KEY
  echo
  [ -n "$GEMINI_API_KEY" ] || fail "APIキーが空です。"
  printf 'GEMINI_API_KEY=%s\n' "$GEMINI_API_KEY" > .env.local
  ok ".env.local に保存しました（git 管理外）"
fi

# 疎通確認
if curl -sf -H "x-goog-api-key: $GEMINI_API_KEY" \
     "https://generativelanguage.googleapis.com/v1beta/models" -o /dev/null; then
  ok "Gemini API 疎通確認: OK"
else
  warn "Gemini API に接続できませんでした。キーが正しいか確認してください（処理は続行します）"
fi

# ---------------------------------------------------------------------------
step "3. Git リポジトリの初期化と GitHub への push"
# ---------------------------------------------------------------------------
[ -d .git ] || { git init -q -b main; ok "git init"; }
git add -A
git diff --cached --quiet || git commit -q -m "chore: AI記事自動生成メディアの初期構築"

OWNER="$(gh api user --jq .login)"
if gh repo view "$OWNER/$REPO_NAME" >/dev/null 2>&1; then
  ok "リポジトリは既に存在します: $OWNER/$REPO_NAME"
  git remote get-url origin >/dev/null 2>&1 || \
    git remote add origin "https://github.com/$OWNER/$REPO_NAME.git"
else
  gh repo create "$REPO_NAME" "--$REPO_VISIBILITY" --source=. --remote=origin \
    --description "YouTube公式発表をGeminiが解析して日本語SEO記事を自動生成するメディア"
  ok "リポジトリを作成しました: $OWNER/$REPO_NAME ($REPO_VISIBILITY)"
fi
git push -u origin main
ok "push 完了"

# ---------------------------------------------------------------------------
step "4. GitHub Actions のシークレット登録"
# ---------------------------------------------------------------------------
gh secret set GEMINI_API_KEY --body "$GEMINI_API_KEY" --repo "$OWNER/$REPO_NAME"
ok "GEMINI_API_KEY を登録しました（3時間ごとの自動実行が有効化されます）"

# ---------------------------------------------------------------------------
step "5. Vercel へデプロイ"
# ---------------------------------------------------------------------------
if [ ! -d .vercel ]; then
  bold "Vercel にログインします（初回のみブラウザが開きます）"
  npx --yes vercel@latest login
fi
npx --yes vercel@latest link --yes --project "$REPO_NAME"
npx --yes vercel@latest pull --yes --environment=production >/dev/null 2>&1 || true
DEPLOY_URL="$(npx --yes vercel@latest deploy --prod --yes | tail -1)"
ok "デプロイ完了: $DEPLOY_URL"

# 本番URLをサイト設定へ反映（sitemap / OGP の絶対URL用）
npx --yes vercel@latest env rm NEXT_PUBLIC_SITE_URL production --yes >/dev/null 2>&1 || true
printf '%s' "$DEPLOY_URL" | npx --yes vercel@latest env add NEXT_PUBLIC_SITE_URL production >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
step "6. 初回の記事生成を今すぐ実行"
# ---------------------------------------------------------------------------
gh workflow run auto_run.yml --repo "$OWNER/$REPO_NAME" -f max_articles=3 -f days=10
ok "GitHub Actions を起動しました（記事生成に5〜15分かかります）"

cat <<EOF

$(bold "🎉 構築完了")

  サイト            : $DEPLOY_URL
  リポジトリ        : https://github.com/$OWNER/$REPO_NAME
  実行状況の確認    : gh run watch --repo $OWNER/$REPO_NAME
  自動更新          : 3時間ごと（.github/workflows/auto_run.yml）

  記事が生成されると自動で commit → push され、Vercel が再ビルドします。

  よく使うコマンド:
    ./.venv/bin/python scripts/main.py --dry-run    # 対象動画の確認
    ./.venv/bin/python scripts/main.py --max 1      # ローカルで1本生成
    npm run dev                                     # ローカルプレビュー
    gh run list --repo $OWNER/$REPO_NAME            # 自動実行の履歴

EOF
