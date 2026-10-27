#!/bin/sh
# Cloudflare Workers 用のビルド（OpenNext）。公開値なのでここに書く（Vercel の環境変数と同じ値）
set -e
export CF_BUILD=1
export NEXT_PUBLIC_SITE_URL="${NEXT_PUBLIC_SITE_URL:-https://ai-tech-express.jp}"
export NEXT_PUBLIC_ADSENSE_CLIENT="${NEXT_PUBLIC_ADSENSE_CLIENT:-ca-pub-6839851749981405}"
export GOOGLE_SITE_VERIFICATION="${GOOGLE_SITE_VERIFICATION:-SWdd2Ggark2QkWBMpckwvsXoRey83xM45id9KQaiDgg}"
# ASP の表示回数ピクセルを本番として出す（components/rail/parts.tsx などが見ている）
export VERCEL_ENV="${VERCEL_ENV:-production}"
# Vercel Analytics は Cloudflare では動かない。代わりに NEXT_PUBLIC_CF_BEACON_TOKEN で Cloudflare Web Analytics
export NEXT_PUBLIC_VERCEL_ANALYTICS="${NEXT_PUBLIC_VERCEL_ANALYTICS:-off}"
npx opennextjs-cloudflare build
node scripts/cf_content.mjs
