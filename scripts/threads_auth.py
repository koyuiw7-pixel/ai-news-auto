#!/usr/bin/env python3
"""Threads への投稿許可を1回だけ設定する（あなたのMacのターミナルで実行）。

  python3 scripts/threads_auth.py

アプリシークレットやトークンはこのスクリプトの中だけで扱い、チャットには出さない。
取得した長期トークン（60日）は暗号化して state/threads_token.enc に保存し、
復号の鍵だけを GitHub の Secrets（THREADS_TOKEN_KEY）に登録する。
以後は自動投稿のたびに期限が延長されるので、再実行は不要。
"""

from __future__ import annotations

import getpass
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from threads_token import API_BASE, KEY_ENV, TOKEN_PATH, now_iso, save_token  # noqa: E402

AUTHORIZE_URL = "https://threads.com/oauth/authorize"
DEFAULT_REDIRECT = "https://ai-tech-express.jp/"
SCOPES = "threads_basic,threads_content_publish"


def request_json(url: str, data: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode() if data else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=60) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as error:
        sys.exit(f"\n[エラー] {error.code}: {error.read().decode()[:400]}")


def main() -> None:
    print("Threads 自動投稿の初期設定\n")
    app_id = input("① Threads アプリID（数字）: ").strip()
    app_secret = getpass.getpass("② Threads アプリシークレット（入力は表示されません）: ").strip()
    redirect = input(f"③ リダイレクトURI [Enterで {DEFAULT_REDIRECT}]: ").strip() or DEFAULT_REDIRECT

    state = secrets.token_urlsafe(16)
    url = f"{AUTHORIZE_URL}?" + urllib.parse.urlencode({
        "client_id": app_id,
        "redirect_uri": redirect,
        "scope": SCOPES,
        "response_type": "code",
        "state": state,
    })
    print("\nブラウザで許可画面を開きます。サイソクのアカウントで「許可」を押してください。")
    print(f"（開かない場合はこのURLをコピー）\n{url}\n")
    webbrowser.open(url)

    returned = input("④ 許可後に表示されたページのURLを丸ごと貼り付けてEnter: ").strip()
    query = urllib.parse.parse_qs(urllib.parse.urlparse(returned).query)
    if query.get("state", [""])[0] != state:
        sys.exit("[エラー] URLが一致しません。④で貼り付けたURLを確認して、最初からやり直してください。")
    # 公式仕様で末尾に #_ が付くことがあるが、コードの一部ではない
    code = query.get("code", [""])[0].removesuffix("#_")
    if not code:
        sys.exit("[エラー] URLに code が含まれていません。許可を押したあとのURLか確認してください。")

    short = request_json(f"{API_BASE.rsplit('/', 1)[0]}/oauth/access_token", {
        "client_id": app_id,
        "client_secret": app_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect,
    })
    long = request_json(f"{API_BASE.rsplit('/', 1)[0]}/access_token?" + urllib.parse.urlencode({
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": short["access_token"],
    }))
    me = request_json(f"{API_BASE}/me?" + urllib.parse.urlencode({
        "fields": "id,username",
        "access_token": long["access_token"],
    }))

    key = secrets.token_urlsafe(32)
    try:
        subprocess.run(["gh", "secret", "set", KEY_ENV], input=key, text=True, check=True,
                       capture_output=True, cwd=Path(__file__).resolve().parent.parent)
    except (OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"[エラー] GitHub への鍵の登録に失敗しました: {error}")

    os.environ[KEY_ENV] = key
    save_token({
        "access_token": long["access_token"],
        "user_id": str(me["id"]),
        "username": me.get("username", ""),
        "refreshed_at": now_iso(),
    })
    print(f"\n完了：@{me.get('username')} で投稿できる状態になりました。")
    print(f"保存先: {TOKEN_PATH.relative_to(Path.cwd()) if TOKEN_PATH.is_relative_to(Path.cwd()) else TOKEN_PATH}")
    print("Claude に「できた」と伝えてください。")


if __name__ == "__main__":
    main()
