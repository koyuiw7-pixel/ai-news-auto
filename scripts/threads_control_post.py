#!/usr/bin/env python3
"""リンク無しの比べの Threads の投稿を1本、決めた時刻に Buffer に予約する（2026-11-06 テストの日・台帳 S39）。

オーナー・Muse 案（11/6 01:35）: リンクの無い投稿のビューと比べるための1本。オーナー（調整役）が書いた spec の JSON だけを出す。

  python3 scripts/threads_control_post.py --spec content/sns_reposts/<id>.json            # 下見だけ（Buffer を呼ばない）
  python3 scripts/threads_control_post.py --spec content/sns_reposts/<id>.json --live     # 予約する（THREADS_MODE=live も要る）

spec の形（すべて必須。image は省略すると記事の図解カード）:
  {"nolink": true, "slug": "<関係する記事の slug>", "at": "2026-11-06T07:20+09:00",
   "text": "本文（リンクを書かない）", "image": "https://...（16:9 前後のカード）", "ownerApproved": "2026-11-06 オーナー承認（…）"}

- Threads だけに出す（X・Facebook・Bluesky には出さない）。門番 sns_rules は kind="control"（リンクを1本も入れない・ほかの決まりは同じ）。
- 1日の上限・枠の記録（state/threads_posted.json）には入れず、state/threads_control.json に残す（ふつうの投稿・速報の枠を取らない）。
- 同じ spec を2回予約しない（state/threads_control.json に id があれば何もしない）。時刻が過ぎていれば出さない。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sns_rules  # noqa: E402
import threads_post as tp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "state" / "threads_control.json"
MIN_LEAD = timedelta(minutes=5)


def load_spec(path: Path) -> dict:
    return load_spec_dict(json.loads(path.read_text("utf-8")))


def load_spec_dict(spec: dict) -> dict:
    missing = [k for k in ("slug", "at", "text", "ownerApproved") if not str(spec.get(k) or "").strip()]
    if spec.get("nolink") is not True:
        missing.append("nolink=true")
    if missing:
        raise SystemExit(f"[control] spec に足りないもの: {', '.join(missing)}")
    return spec


def build_input(spec: dict, channel_id: str, article: dict) -> dict:
    """リンクの無い Threads の Buffer の入力（本文＋画像1枚・返信なし・決めた時刻に予約）"""
    due = datetime.fromisoformat(str(spec["at"])).astimezone(timezone.utc)
    text = str(spec["text"]).replace("\\n", "\n").strip()
    image = spec.get("image") or tp.card_url(article)
    return {
        "channelId": channel_id, "text": text, "schedulingType": "automatic", "assets": [],
        "mode": "customScheduled", "dueAt": due.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "metadata": {"threads": {"topic": tp.topic_of(article), "thread": [{"text": text, "assets": [{"image": {"url": image}}]}]}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--live", action="store_true", help="Buffer に予約する（THREADS_MODE=live のときだけ）")
    args = parser.parse_args()
    spec_path = Path(args.spec)
    spec = load_spec(spec_path)
    article = json.loads((tp.ARTICLES_DIR / f"{spec['slug']}.json").read_text("utf-8"))
    ledger = json.loads(LEDGER.read_text("utf-8")) if LEDGER.exists() else {"posts": {}}
    key_name = spec_path.stem
    if (ledger["posts"].get(key_name) or {}).get("id"):
        print(f"[control] {key_name} はもう予約済みです（{ledger['posts'][key_name]['id']}）。何もしません")
        return 0
    due = datetime.fromisoformat(str(spec["at"]))
    if due.tzinfo is None:
        raise SystemExit("[control] at に時差（+09:00）を書いてください")
    now = datetime.now(timezone.utc)
    live = args.live and os.environ.get("THREADS_MODE") == "live"
    if live and due - now < MIN_LEAD:
        print(f"[control] 時刻 {spec['at']} がもう近すぎるか過ぎています。出しません")
        return 1
    inp = build_input(spec, "preview", article)
    # 下見でも門番を通す（止まるならここで分かる）
    text, reply, media, links = sns_rules.buffer_parts("threads", inp)
    problems = sns_rules.check_post("threads", text, media, article, kind="control", reply_text=reply, links=links)
    print(f"--- {key_name}（{due.astimezone(tp.JST):%m/%d %H:%M} に予約・リンク無し・Threads だけ）\n{text}\n[画像] {media[0]['url'] if media else 'なし'}")
    if problems:
        print("[control] 門番に通りません: " + "; ".join(problems))
        return 1
    if not live:
        print("[control] 下見だけ（--live と THREADS_MODE=live で予約）")
        return 0
    api_key = os.environ.get("BUFFER_API_KEY", "").strip()
    channels = tp.buffer_channels(api_key)
    inp["channelId"] = channels["threads"]["id"]
    post_id = tp.create_post(api_key, inp, service="threads", article=article, source="threads_control_post", kind="control")
    ledger["posts"][key_name] = {"id": post_id, "slug": spec["slug"], "dueAt": inp["dueAt"], "text": text, "nolink": True,
                                 "ownerApproved": spec["ownerApproved"], "at": now.isoformat(timespec="seconds")}
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"[control] 予約しました: {post_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
