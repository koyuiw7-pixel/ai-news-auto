#!/usr/bin/env python3
"""
速報のプッシュ通知。速報記事（記事 JSON の breaking: true。SNS の即時投稿 breaking_post.py と同じ目印）が
開けるようになったら、サイトの Worker（/api/push/send）に「この記事を通知して」と頼む。

  breaking_post.yml の push ジョブが SNS の即時投稿と並んで呼ぶ。

  python3 scripts/push_notify.py --dry-run     # 対象を表示し、Worker の判定（送る/保留/上限…）だけ聞く。送らない
  python3 scripts/push_notify.py               # PUSH_SEND_TOKEN があるときだけ実際に頼む
  python3 scripts/push_notify.py --stats       # 購読者数・今日の送信数を表示（毎晩の報告用）

決まりごと（数字は lib/push-config.ts。判定は Worker の cloudflare/push.ts がする）:
- 対象は生成から3時間以内の速報記事。新しい順に頼み、同じ記事は Worker が二度と送らない
- 1日4回まで・前の通知から1時間は空ける・夜22時〜朝7時は保留して朝7時に一番新しい1本だけ送る
- 例外（安全）: 地震・津波の記事で大津波警報・津波警報・震度6弱以上（safetyAlert）は、夜間・上限・間隔を問わず送る
- 記事ページが 200 を返すまで最大 --wait 秒待つ（開けない記事の通知は出さない）
- 送り先（購読者の情報）はこのスクリプトには来ない。Worker の中だけで扱う
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import threads_post as tp  # noqa: E402

MAX_AGE_MIN = 180


def log(message: str) -> None:
    print(message, flush=True)


def ref_time(article: dict) -> str:
    """古さの基準。安全の通知（地震・津波で safetyAlert）は続報で警報が出ることがあるので最後の更新時刻"""
    if article.get("safetyAlert") and article.get("updatedAt"):
        return article["updatedAt"]
    return article["generatedAt"]


def targets(now: datetime) -> list[dict]:
    found = []
    for path in tp.ARTICLES_DIR.glob("*.json"):
        article = json.loads(path.read_text("utf-8"))
        if not article.get("breaking"):
            continue
        if now - datetime.fromisoformat(ref_time(article)) <= timedelta(minutes=MAX_AGE_MIN):
            found.append(article)
    return sorted(found, key=lambda a: a["generatedAt"], reverse=True)


def call(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{tp.site_url()}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "SaisokuPushBot/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read() or b"{}")
        except ValueError:
            return error.code, {}


def page_live(slug: str, timeout: int) -> bool:
    url = f"{tp.site_url()}/articles/{slug}"
    deadline = time.monotonic() + timeout
    while True:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SaisokuPushBot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as res:
                if res.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(15)


def lead(article: dict) -> str:
    text = article.get("description") or " ".join(article.get("highlights", [])[:1]) or article.get("lede", "")
    return " ".join(str(text).split())[:118]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--wait", type=int, default=480, help="記事ページの公開を待つ最大秒数")
    args = parser.parse_args()

    token = os.environ.get("PUSH_SEND_TOKEN", "").strip()
    if not token:
        log("[push] PUSH_SEND_TOKEN が無いため何もしません")
        return 0
    if args.stats:
        status, data = call("GET", "/api/push/stats", token)
        log(json.dumps(data, ensure_ascii=False, indent=2) if status == 200 else f"[push] stats {status} {data}")
        return 0 if status == 200 else 1

    found = targets(datetime.now(timezone.utc))
    if not found:
        log("[push] 通知する速報記事はありません")
        return 0

    summary = ["### 速報のプッシュ通知" + ("（判定だけ）" if args.dry_run else ""), ""]
    for article in found:
        slug = article["slug"]
        if not args.dry_run and not page_live(slug, args.wait):
            log(f"[push] {slug}: {args.wait}秒待っても記事が開けないため見送り")
            continue
        # urgent: 大津波警報・津波警報・震度6弱以上（scripts/quake.py の safetyAlert）。夜間・1日の上限を超えて送る
        body = {"slug": slug, "title": article["title"], "body": lead(article), "generatedAt": ref_time(article), "dryRun": args.dry_run,
                "urgent": bool(article.get("safetyAlert") and article.get("disaster"))}
        status, data = call("POST", "/api/push/send", token, body)
        # 購読者が多いときは続きから送る
        while status == 200 and data.get("status") == "sent" and data.get("cursor"):
            more_status, more = call("POST", "/api/push/send", token, {"job": data["job"], "cursor": data["cursor"]})
            if more_status != 200:
                log(f"[push] 続きの送信に失敗 {more_status} {more}")
                break
            for key in ("total", "delivered", "removed", "failed"):
                data[key] = data.get(key, 0) + more.get(key, 0)
            data["cursor"] = more.get("cursor")
        result = data.get("status", f"http {status}")
        detail = (
            f"（{data.get('delivered', 0)}/{data.get('total', 0)} 件に届けた・消えた購読 {data.get('removed', 0)}・失敗 {data.get('failed', 0)}）"
            if result == "sent" else ""
        )
        log(f"[push] {slug}: {result}{detail}")
        summary.append(f"- `{slug}`: {result}{detail}")
    tp.write_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
