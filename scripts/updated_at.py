#!/usr/bin/env python3
"""記事の「最終更新」（updatedAt・構造化データの dateModified・サイトマップの lastmod）を書くのはこの1か所だけ（SEO A16）。

決まり:
  - 事実が増えた・直した・続報を足したときだけ、更新日時を進めて「更新履歴」（updates）に1行残す。
      kind = "facts"（公式の資料から事実の欄を足した） / "correction"（誤りを直した） /
             "followup"（続報） / "refresh"（公式の資料を読み直して本文を書き直した。台帳 A68 の週1回の書き直し）
  - 言い回し・題名・章立て・見た目だけの直し（kind = "style" / "title" / "sections"）では、更新日時を動かさない。
  - 表示側（lib/article-index.mjs の trustedUpdatedAt）は、2026-11-12 までの更新履歴の無い updatedAt を「最終更新」として使わない。
    11/04 に一括で押された43本のような、中身の変わらない更新日時を Google と読者に見せないため。
  - 2026-11-13 から: 手で事実を足した・直したときは、updatedAt だけでも「最終更新」として出る（載せた時刻より10分を超えて新しいとき）。
    だから、記事の updatedAt を書く自動の処理はここ（touch_updated）だけにする。言い回し・章立て・かんたん版の作り直しで
    updatedAt を直接書かない（tests/test_updated_at.py の test_only_touch_updated_writes_article_updated_at が見張る）。

  python3 scripts/updated_at.py --backfill-depth          # 深掘りの欄を足した記事に、足した日時の更新履歴を付ける（表示だけ）
  python3 scripts/updated_at.py --backfill-depth --apply  # 書き込む
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"

# 更新日時を進める種類（事実が増えた・変わった）
CONTENT_KINDS = {"facts", "correction", "followup", "refresh"}
# 進めない種類（言い回し・題名・章立てだけ）
STYLE_KINDS = {"style", "title", "sections"}
MAX_UPDATES = 20

DEFAULT_TITLES = {
    "facts": "公式の資料をもとに、内容を追記しました",
    "correction": "誤りを訂正しました",
    "followup": "続報を追記しました",
    "refresh": "公式の資料を読み直し、本文を書き直しました",
}

# 深掘りの欄（scripts/depth_fields.py）。どれも公式のページで確かめた事実の欄
DEPTH_LABELS = {
    "insight": "なるほどの要点",
    "officialDesk": "公式の窓口",
    "todaySteps": "今日やること",
    "cause": "理由",
    "worries": "よくある不安",
    "decisionGuide": "判断の目安",
}
# 公開から短い時間で足した欄は「公開の準備の一部」として、更新履歴に出さない
DEPTH_GRACE = timedelta(minutes=30)


def _iso(at: datetime | str | None) -> str:
    if at is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    if isinstance(at, datetime):
        return at.isoformat(timespec="seconds") if at.tzinfo else at.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
    return str(at)


def touch_updated(record: dict, kind: str, *, at: datetime | str | None = None, title: str = "",
                  source_url: str = "", source_name: str = "", note: bool = True) -> bool:
    """記事の更新日時を進めるのはここだけ。kind が事実の更新なら updatedAt と更新履歴を書いて True。
    言い回し・題名・章立ての直しなら何もしないで False（呼び出し側はそのまま保存してよい）。
    note=False は更新履歴の欄が無い種類の記録（ガイドなど。自前の履歴を持つ）のときだけ使う。"""
    if kind in STYLE_KINDS:
        return False
    if kind not in CONTENT_KINDS:
        raise ValueError(f"更新の種類が分からない: {kind}")
    stamp = _iso(at)
    record["updatedAt"] = stamp
    if note:
        entry = {"at": stamp, "kind": kind, "title": title.strip() or DEFAULT_TITLES[kind]}
        if source_url:
            entry["sourceUrl"] = source_url
        if source_name:
            entry["sourceName"] = source_name
        record["updates"] = [*(record.get("updates") or []), entry][-MAX_UPDATES:]
    return True


def depth_note(fields: dict) -> str:
    labels = [label for key, label in DEPTH_LABELS.items() if fields.get(key)]
    if not labels:
        return ""
    return "公式の資料をもとに、" + "・".join(f"「{x}」" for x in labels) + "を追記しました"


def touch_depth(record: dict, fields: dict, at: datetime | str | None = None) -> bool:
    """深掘りの欄（事実の欄）を足したとき。公開から DEPTH_GRACE 以内なら公開の準備の一部として更新日時を動かさない"""
    note = depth_note(fields)
    stamp = _parse(_iso(at))
    born = _parse(record.get("generatedAt") or record.get("publishedAt") or "")
    if not note or not stamp or (born and stamp - born < DEPTH_GRACE):
        return False
    return touch_updated(record, "facts", at=_iso(at), title=note, source_url=_source_url(record),
                         source_name=str(record.get("sourceName") or ""))


def _source_url(record: dict) -> str:
    url = str(record.get("sourceUrl") or "")
    return url if url.startswith("https://") else ""


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def backfill_depth(record: dict) -> bool:
    """深掘りの欄を足した記事に、足した日時（depthAt）の更新履歴を1行付ける。足したのが公開直後なら付けない。
    すでに同じ日時の履歴があれば何もしない。更新日時は新しいほうを残す（続報の日時を戻さない）"""
    depth_at, born = _parse(record.get("depthAt") or ""), _parse(record.get("generatedAt") or record.get("publishedAt") or "")
    note = depth_note(record)
    if not depth_at or not born or not note or depth_at - born < DEPTH_GRACE:
        return False
    if any(u.get("kind") == "facts" and u.get("at") == record["depthAt"] for u in record.get("updates") or []):
        return False
    current = _parse(record.get("updatedAt") or "")
    keep_updates = [u for u in record.get("updates") or []]
    entry = {"at": record["depthAt"], "kind": "facts", "title": note}
    if _source_url(record):
        entry["sourceUrl"] = _source_url(record)
        if record.get("sourceName"):
            entry["sourceName"] = str(record["sourceName"])
    record["updates"] = sorted([*keep_updates, entry], key=lambda u: _parse(u.get("at") or "") or depth_at)[-MAX_UPDATES:]
    # 更新履歴の無い updatedAt（一括で押された日時）は事実の更新ではないので、足した日時に置きかえる
    if not current or current < depth_at or not keep_updates:
        record["updatedAt"] = record["depthAt"]
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill-depth", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.backfill_depth:
        ap.print_help()
        return 0
    changed = 0
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        record = json.loads(path.read_text("utf-8"))
        if backfill_depth(record):
            changed += 1
            if args.apply:
                path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[updated-at] 深掘りの更新履歴を付けた記事: {changed} 本{'（書き込み済み）' if args.apply else '（下見）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
