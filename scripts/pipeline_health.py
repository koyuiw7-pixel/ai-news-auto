#!/usr/bin/env python3
"""記事づくりが止まっていないかの見張り（2026-11-03 オーナー「何回も記事作成が止まるのはやめたい」）。

web_articles.py が通常の回の終わりに record() を呼ぶ。候補があり、生成の失敗・品質ゲート不合格・モデル切れで
新しい記事・続報が 0 本の回が2回続いたら「止まっている」とし（記事にする価値なしの見送りだけの回は数えない）、state/pipeline_health.json に理由を書く（朝・夜の報告がこのファイルを読む）。
ファイルは状態が変わったときだけ書き直す（毎回のコミットを増やさない）。

  python3 scripts/pipeline_health.py            # いまの状態を表示
  python3 scripts/pipeline_health.py --alert    # 止まっていれば GitHub に issue（ラベル pipeline-stalled）を立てる。
                                                # 直ったら、その issue に一言書いて閉じる（gh と GH_TOKEN が必要）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEALTH_PATH = ROOT / "state" / "pipeline_health.json"
ARTICLES_DIR = ROOT / "content" / "articles"
STALL_RUNS = 2  # 救済モードを止めている（PIPELINE_RESCUE=0）ときだけ: この回数続けて 0 本なら「止まっている」
# 2026-11-06 オーナー「止まらない仕組み」（台帳 A48）: 0本の回が1回あれば次の回は救済モード（web_articles.py）。
# 救済モードでも0本の回がこの回数続いたときだけ issue でオーナーに知らせる
RESCUE_FAIL_ALERT = 2
LABEL = "pipeline-stalled"


def load() -> dict:
    try:
        data = json.loads(HEALTH_PATH.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save(data: dict) -> None:
    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")


def record(created: int, candidates: int, reason: str = "", now: datetime | None = None, rescue: bool = False,
           tried: list[str] | None = None) -> dict:
    """通常の回の結果を記録する。created = 新しい記事＋続報の本数、candidates = 作る対象だった候補の数。
    rescue = この回が救済モードだったか、tried = 救済モードで試したこと（issue にそのまま書く）"""
    now = now or datetime.now(timezone.utc)
    old = load()
    data = dict(old)
    if created > 0:
        data.update(status="ok", consecutive_zero=0, reason="", rescue_failed=0)
        data.pop("recovered_by", None)
        data.pop("tried", None)
        if old.get("status") != "ok" or old.get("consecutive_zero"):
            data["recovered_at"] = now.isoformat(timespec="seconds")
    elif candidates > 0:
        zero = int(old.get("consecutive_zero") or 0) + 1
        data.update(consecutive_zero=zero, reason=reason[:300], last_zero_at=now.isoformat(timespec="seconds"),
                    candidates=candidates)
        if rescue:
            data["rescue_failed"] = int(old.get("rescue_failed") or 0) + 1
            data["tried"] = list(tried or [])[:8]
        no_rescue = os.environ.get("PIPELINE_RESCUE") == "0"
        if int(data.get("rescue_failed") or 0) >= RESCUE_FAIL_ALERT or (no_rescue and zero >= STALL_RUNS):
            data["status"] = "stalled"
            data.setdefault("stalled_since", now.isoformat(timespec="seconds"))
        elif data.get("status") != "stalled":
            data["status"] = "rescue"  # 次の回は救済モード（まだオーナーには知らせない）
    else:
        return old  # 候補が無い回（作るものが無い）は数えない
    if data.get("status") == "ok":
        data.pop("stalled_since", None)
    if data != old:
        save(data)
    return data


def _parse_time(value) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def newest_article_after(since: str, articles_dir: Path | None = None) -> tuple[str, str] | None:
    """since より後に作られた記事（generatedAt）があれば、いちばん新しいものの (slug, 時刻) を返す。
    速報レーン・動画の記事・手で直した回など、通常の回の record() を通らない記事も「記事ができた」に数えるため"""
    start = _parse_time(since)
    if not start:
        return None
    newest: tuple[datetime, str] | None = None
    for path in (articles_dir or ARTICLES_DIR).glob("*.json"):
        try:
            data = json.loads(path.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict) or data.get("duplicateOf"):
            continue
        made = _parse_time(data.get("generatedAt"))
        if made and made > start and (newest is None or made > newest[0]):
            newest = (made, str(data.get("slug") or path.stem))
    return (newest[1], newest[0].isoformat(timespec="seconds")) if newest else None


def recover_from_articles(articles_dir: Path | None = None) -> dict:
    """止まっている印のあとに記事ができていれば、直ったことにする（issue は alert() が閉じる）"""
    data = load()
    if data.get("status") not in ("stalled", "rescue"):
        return data
    found = newest_article_after(data.get("last_zero_at") or data.get("stalled_since") or "", articles_dir)
    if not found:
        return data
    slug, made = found
    data.update(status="ok", consecutive_zero=0, reason="", recovered_at=made, recovered_by=slug, rescue_failed=0)
    data.pop("tried", None)
    data.pop("stalled_since", None)
    save(data)
    print(f"[health] 止まった印のあとに記事ができていました（{slug} {made}）。直ったことにします")
    return data


def issue_body(data: dict) -> str:
    """オーナー（専門家ではない）が読む issue の本文。むずかしい言葉を使わず、何が起きて何を試したかを書く"""
    tried = data.get("tried") or []
    lines = [
        "記事が自動で作れない状態が続いています。",
        "",
        f"- 0本の回: {data.get('consecutive_zero')} 回続いています（そのうち自動の立て直し〔救済モード〕でも0本: {data.get('rescue_failed', 0)} 回）",
        f"- 最後の回の理由: {data.get('reason') or '不明'}",
        f"- 記事にできそうな候補の数: {data.get('candidates')}",
        f"- 止まり始め: {data.get('stalled_since')}",
        "",
        "自動で試したこと:",
    ]
    lines += [f"- {t}" for t in tried] or ["- （記録なし）"]
    lines += [
        "- ニュースの記事ができなかった回は、使い方ガイドを1本作るよう自動で依頼しました",
        "",
        "品質の基準（本文1500字以上・元の発表にある事実だけ・事実の確認）は下げていません。",
        "記事が1本でもできたら、この知らせは自動で閉じます。",
        "（くわしい記録: state/pipeline_health.json と Auto Article Pipeline の実行ログ）",
    ]
    return "\n".join(lines)


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout.strip()


def alert() -> int:
    data = recover_from_articles()
    if data.get("status") == "stalled" and not data.get("issue"):
        body = issue_body(data)
        try:
            subprocess.run(["gh", "label", "create", LABEL, "--color", "B60205", "--description", "記事づくりが止まっている", "--force"],
                           check=False, capture_output=True, text=True)
            url = _gh("issue", "create", "--title", "記事づくりが止まっています（自動の立て直しでも0本）", "--label", LABEL, "--body", body)
        except Exception as error:  # noqa: BLE001
            print(f"[health] issue を立てられませんでした: {error}")
            return 0
        data["issue"] = url.rsplit("/", 1)[-1]
        save(data)
        print(f"[health] 止まっているので issue を立てました: {url}")
    elif data.get("status") == "ok" and data.get("issue"):
        try:
            _gh("issue", "close", str(data["issue"]), "--comment", f"記事づくりが再開しました（{data.get('recovered_at')}）。")
        except Exception as error:  # noqa: BLE001
            print(f"[health] issue を閉じられませんでした: {error}")
            return 0
        data.pop("issue", None)
        save(data)
        print("[health] 再開したので issue を閉じました")
    else:
        print(f"[health] {data.get('status') or '記録なし'}（0本の回が続いた数: {data.get('consecutive_zero', 0)}）")
    return 0


if __name__ == "__main__":
    if "--alert" in sys.argv:
        raise SystemExit(alert())
    print(json.dumps(load(), ensure_ascii=False, indent=2))
