#!/usr/bin/env bash
# Vercel の「Ignored Build Step」（vercel.json の ignoreCommand）。
# 終了コード 0 = ビルドしない / 1 = ビルドする。
#
# 記事は20分ごとにコミットするが、デプロイは1時間に1回にまとめる（Deployment Storage と
# デプロイごとの ISR キャッシュの作り直しを減らすため）。どのコミットでデプロイするかは
# GitHub Actions（.github/workflows/auto_run.yml の Commit & push）が決め、
# まとめる側のコミットには "[no-deploy]" を付ける。次にデプロイするコミットは HEAD を
# ビルドするので、それまでに溜まった記事もすべて公開される。
msg="$(git log -1 --pretty=%B HEAD 2>/dev/null)"

case "$msg" in
  *"[no-deploy]"*)
    echo "skip: [no-deploy]（次のデプロイでまとめて公開）"
    exit 0
    ;;
  *"[deploy]"*)
    echo "build: [deploy]（保留中の記事を公開）"
    exit 1
    ;;
esac

# state/（投稿履歴・デプロイ時刻など）だけの変更ではビルドしない
if git diff --quiet HEAD^ HEAD -- . ':(exclude)state'; then
  echo "skip: state/ only"
  exit 0
fi
exit 1
