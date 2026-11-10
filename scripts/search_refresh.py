#!/usr/bin/env python3
"""Google で4〜10位にいる記事を、毎週「検索の答えを先に」書き直す（2026-11-09 オーナー承認・台帳 A68）。

Search Console（2026-10-20〜11-07）では、検索語の表示の約52%が7〜10位にあった（IPA の漏えい対策・Honda RN0 の価格・
Adobe MAX など）。題名は検索語と合っていて、上にいるのは公式サイトと大手のメディア。足りないのは「公式より分かりやすい答え」と新しさ。
そこで毎週月曜（日本時間）、content/search_positions.json で平均4〜10位・表示10回以上の記事を選び、scripts/rewrite_types.py と
同じ部品で書き直す: 元の公式の資料を取り直す → 検索語への答えを本文の最初の2文に書く指示を足す → 品質ゲート（資料に無いことは
書かない。うそだけを落とす門・台帳 A60）→ 合格したときだけ保存。URL・題名・公開日時は変えず、更新日時（updatedAt。
構造化データの dateModified）を進める。合格しなかった記事は今の版のまま。新しい似た記事は作らない。

書き直した記録は state/search_refresh.json（いつ・どの検索語・そのときの順位と表示）。14日後に同じ検索語の順位と比べる。
同じ記事は14日あけてから選び直す。

順位の一覧（content/search_positions.json）の更新のしかた（Search Console・週1回）:
  1. 検索パフォーマンス → 期間「過去28日間」→「ページ」タブで、/articles/<slug> ごとの表示・クリック・平均掲載順位を見る
  2. 「pages」の各記事に {"query": 主な検索語, "position": 平均順位, "impressions": 表示, "clicks": クリック} を書く（"updatedAt"・"window" も直す）
  3. 表示が1回でもあった記事は、掃除でも取り下げない・転送しない（scripts/search_protected.py が同じ一覧を読む）

  python3 scripts/search_refresh.py                     # 今週書き直す記事を表示するだけ
  python3 scripts/search_refresh.py --apply --weekly    # 月曜だけ書き直す（Actions の types_rewrite.yml から）
  python3 scripts/search_refresh.py --apply --slug a,b  # 指定した記事だけ
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search_protected  # noqa: E402
import updated_at  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
STATE = ROOT / "state" / "search_refresh.json"
JST = timezone(timedelta(hours=9))
POS_MIN, POS_MAX = 4.0, 10.0
MIN_IMPRESSIONS = 10
GAP_DAYS = 14
DEFAULT_MAX = 5

FOCUS = """# 今回の書き直しで必ず守ること（検索から来た人への答えを先に。2026-11-09 オーナー承認・台帳 A68）
この記事は Google で「{query}」と検索されて、平均{position}位に出ています。上にいるのは公式サイトと大手のメディアです。
- 本文の最初の2文で、「{query}」と調べた人が知りたいこと（何か・いつ・いくら・対象・何をすればいいか）に、資料にある事実で答える。
- 検索された言葉（「{query}」の中の言葉。支給日・いつ・いくら・対象・届かない など）を、資料で答えられるときは本文の最初の段落にそのまま1回入れる（題名より先に本文。SEO A14）。
- 公式の窓口・申し込み先・確かめ方が資料にあれば、URL とたどり方まで書く。数字は資料のとおり。
- 資料に無いことは書かない（推測・見込みの数字を足さない）。答えが資料に無い点は「公式の発表には記載がありません」と書く。
- 題名は変えない。全体の流れ（結論→要点→詳しく）は今の型のまま。"""


def load_state(path: Path = STATE) -> dict:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"refreshed": []}
    return data if isinstance(data, dict) else {"refreshed": []}


def _when(value) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def recently_refreshed(state: dict, now: datetime, days: int = GAP_DAYS) -> set[str]:
    out = set()
    for row in state.get("refreshed") or []:
        at = _when(row.get("at"))
        if at and now - at < timedelta(days=days):
            out.add(str(row.get("slug")))
    return out


def pick(pages: dict[str, dict], now: datetime, state: dict | None = None, articles_dir: Path = ARTICLES_DIR,
         limit: int = DEFAULT_MAX) -> list[tuple[str, dict]]:
    """今週書き直す記事 [(slug, 順位の行)]。平均4〜10位・表示10回以上・公開中・14日以内に書き直していない。表示の多い順"""
    skip = recently_refreshed(state or {}, now)
    rows = []
    for slug, row in pages.items():
        pos = row.get("position")
        if pos is None or not (POS_MIN <= float(pos) <= POS_MAX):
            continue
        if int(row.get("impressions") or 0) < MIN_IMPRESSIONS or slug in skip:
            continue
        if not (articles_dir / f"{slug}.json").exists():
            continue
        rows.append((slug, row))
    rows.sort(key=lambda kv: (-int(kv[1].get("impressions") or 0), float(kv[1].get("position") or 99)))
    return rows[:limit]


def focus_for(row: dict) -> str:
    query = str(row.get("query") or "").strip()
    if not query:
        return ""
    return FOCUS.format(query=query, position=f"{float(row.get('position')):.1f}")


def stamp(new: dict, row: dict, now: datetime) -> dict:
    """書き直した記事に更新日時（dateModified）と記録を付ける。題名・URL・公開日時はそのまま"""
    at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    # 公式の資料を取り直して本文を書き直したので、更新日時を進めて更新履歴に残す（共通の関数。SEO A16）
    updated_at.touch_updated(new, "refresh", at=at)
    new["searchRefreshedAt"] = at
    new["searchRefresh"] = {"query": row.get("query", ""), "position": row.get("position"), "impressions": row.get("impressions")}
    return new


def is_monday_jst(now: datetime) -> bool:
    return now.astimezone(JST).weekday() == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--weekly", action="store_true", help="月曜（日本時間）だけ動く")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX)
    ap.add_argument("--slug", default="", help="カンマ区切り（順位の一覧にある記事）")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    if args.weekly and not is_monday_jst(now):
        print("[search-refresh] 毎週月曜（日本時間）だけ書き直します。今日は何もしません")
        return 0
    data = search_protected.load_positions()
    pages = search_protected.positions_pages()
    print(f"[search-refresh] 順位の一覧: {len(pages)} 本（{data.get('window', '')}・更新 {data.get('updatedAt', '')}）")
    state = load_state()
    if args.slug:
        targets = [(s, pages.get(s, {})) for s in args.slug.split(",") if s]
    else:
        targets = pick(pages, now, state, limit=args.max)
    for slug, row in targets:
        print(f"  {slug:55} 「{row.get('query', '')}」 {row.get('position')}位・表示 {row.get('impressions')}")
    if not targets or not args.apply:
        return 0
    import rewrite_types  # noqa: PLC0415 - LLM の部品を読むのは書き直すときだけ

    if os.environ.get("ANTHROPIC_API_KEY"):
        allowed, why = rewrite_types.budget_allowance(len(targets))
        print(f"[budget] {why}")
        targets = targets[:allowed]
    done = 0
    for slug, row in targets:
        try:
            new, rep = rewrite_types.rewrite(slug, focus=focus_for(row))
        except Exception as error:  # noqa: BLE001 - 1本の失敗で止めない
            new, rep = None, {"why": f"失敗: {str(error)[:200]}"}
        if new is None:
            print(f"   [keep] {slug}: 今の版のまま（{rep.get('why')}）")
            continue
        stamp(new, row, now)
        (ARTICLES_DIR / f"{slug}.json").write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", "utf-8")
        state.setdefault("refreshed", []).append({"slug": slug, "at": new["searchRefreshedAt"], "query": row.get("query", ""),
                                                  "position": row.get("position"), "impressions": row.get("impressions"),
                                                  "checkAfter": (now + timedelta(days=14)).date().isoformat()})
        done += 1
        print(f"   [OK] {slug}: 書き直した（score {rep.get('score')}）")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"[search-refresh] 書き直し {done} 本 / 今の版のまま {len(targets) - done} 本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
