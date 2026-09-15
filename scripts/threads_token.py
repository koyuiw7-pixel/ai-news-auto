"""Threads のアクセストークンを暗号化して保存・延長する。

長期トークンは60日で失効し、延長するたびに値が変わりうる。
GitHub の Secrets は Actions から書き換えられないため、トークン本体は
暗号化してリポジトリ（state/threads_token.enc）に置き、復号の鍵だけを
Secrets の THREADS_TOKEN_KEY に持たせる。鍵が無ければ中身は読めない。
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN_PATH = ROOT / "state" / "threads_token.enc"
KEY_ENV = "THREADS_TOKEN_KEY"
API_BASE = "https://graph.threads.net/v1.0"

# 失効（60日）よりずっと手前で延長する。延長は発行から24時間経過後でないとできない
REFRESH_AFTER = timedelta(days=7)

_CIPHER = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-base64", "-A", "-pass", f"env:{KEY_ENV}"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_token() -> dict | None:
    if not TOKEN_PATH.exists() or not os.environ.get(KEY_ENV):
        return None
    result = subprocess.run([*_CIPHER, "-d"], input=TOKEN_PATH.read_bytes(), capture_output=True, check=True)
    return json.loads(result.stdout)


def save_token(token: dict) -> None:
    if not os.environ.get(KEY_ENV):
        raise RuntimeError(f"{KEY_ENV} が未設定のため保存できません")
    result = subprocess.run([*_CIPHER, "-salt"], input=json.dumps(token).encode(), capture_output=True, check=True)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_bytes(result.stdout + b"\n")


def refresh_if_needed(token: dict) -> dict:
    """前回の延長から一定期間たっていれば延長し、暗号化ファイルを更新する。"""
    refreshed_at = datetime.fromisoformat(token["refreshed_at"])
    if datetime.now(timezone.utc) - refreshed_at < REFRESH_AFTER:
        return token

    query = urllib.parse.urlencode({"grant_type": "th_refresh_token", "access_token": token["access_token"]})
    try:
        with urllib.request.urlopen(f"{API_BASE.rsplit('/', 1)[0]}/refresh_access_token?{query}", timeout=60) as res:
            data = json.loads(res.read())
    except urllib.error.HTTPError as error:
        # 延長に失敗しても、今のトークンが有効なうちは投稿を続ける
        print(f"[warn] トークンの延長に失敗しました: {error.code} {error.read().decode()[:200]}", flush=True)
        return token

    token = {**token, "access_token": data["access_token"], "refreshed_at": now_iso()}
    save_token(token)
    print("[info] Threads のトークンを延長しました（60日）", flush=True)
    return token
