#!/usr/bin/env python3
"""Google で4〜20位にいる記事を、毎週「検索の答えを先に」書き直す（2026-11-09 オーナー承認・台帳 A68）。

Search Console（2026-10-20〜11-07）では、検索語の表示の約52%が7〜10位にあった（IPA の漏えい対策・Honda RN0 の価格・
Adobe MAX など）。題名は検索語と合っていて、上にいるのは公式サイトと大手のメディア。足りないのは「公式より分かりやすい答え」と新しさ。
そこで毎週月曜（日本時間）、content/search_positions.json で平均4〜20位（2026-11-22 に10位から広げた）・表示10回以上の記事を選び、scripts/rewrite_types.py と
同じ部品で書き直す: 元の公式の資料を取り直す → 検索語への答えを本文の最初の2文に書く指示を足す → 品質ゲート（資料に無いことは
書かない。うそだけを落とす門・台帳 A60）→ 合格したときだけ保存。URL・題名・公開日時は変えず、更新日時（updatedAt。
構造化データの dateModified）を進める。合格しなかった記事は今の版のまま。新しい似た記事は作らない。

書き直した記録は state/search_refresh.json（いつ・どの検索語・そのときの順位と表示）。14日後に同じ検索語の順位と比べる。
同じ記事は14日あけてから選び直す。

2026-11-22 オーナー決定「検索で8〜20位の記事を、新しく書くより先に厚くする」: 選ぶ範囲を平均4〜20位に広げた。
- 一番新しい日付（"asOf"）の行を先に、その中で表示の多い順に選ぶ（古い期間の表示と混ぜて比べない）。
- Search Console が検索語を隠した記事（query が空）は、検索語を作らず、記事の題名の疑問に答える指示にする。
- Muse・編集部の記事（museFile・refreshMode: editorial・writer: muse）と訂正した記事は選ばない（人が確かめた中身を LLM で作り直さない）。
- 資料の期限・受付・発売日などが今日より前なら、終わったこととして書く（これからの予定のように書かない）。

順位の一覧（content/search_positions.json）の更新のしかた（Search Console・週1回）:
  1. 検索パフォーマンス → 期間「過去28日間」→「ページ」タブで、/articles/<slug> ごとの表示・クリック・平均掲載順位を見る
  2. 「pages」の各記事に {"query": 主な検索語, "position": 平均順位, "impressions": 表示, "clicks": クリック} を書く（"asOf"〔確認した日〕・"updatedAt"・"window" も直す）
  3. 表示が1回でもあった記事は、掃除でも取り下げない・転送しない（scripts/search_protected.py が同じ一覧を読む）

  python3 scripts/search_refresh.py                     # 今週書き直す記事を表示するだけ
  python3 scripts/search_refresh.py --apply --weekly    # 月曜だけ書き直す（Actions の types_rewrite.yml から）
  python3 scripts/search_refresh.py --apply --slug a,b  # 指定した記事だけ
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search_protected  # noqa: E402
import updated_at  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
STATE = ROOT / "state" / "search_refresh.json"
CORRECTIONS_PATH = ROOT / "content" / "corrections.json"
# 訂正の注記（scripts/rewrite_types.py の CORRECTION_RE と同じ。LLM の部品を読まずに選ぶため、ここにも置く）
CORRECTION_RE = re.compile(r"編集部訂正|【訂正】|訂正（\d{4}年")
JST = timezone(timedelta(hours=9))
POS_MIN, POS_MAX = 4.0, 20.0  # 2026-11-22 オーナー決定: 8〜20位を1ページ目へ（前は10位まで）
MIN_IMPRESSIONS = 10
GAP_DAYS = 14
DEFAULT_MAX = 5
# 2026-11-22 オーナー「任せる」（台帳 A76）: Claude の月の予算を止めている間、この週1回の書き直しだけ OpenAI の API クレジットで書く。
# ワークフローのこの段だけが SEARCH_REFRESH_OPENAI=1 を渡す。予算の守り（llm.openai_block_reason）と品質ゲートは同じ
OPENAI_MAX = 5
TIME_BUDGET_SEC = 1200  # ワークフローの timeout 1500 秒より前に、新しい記事を始めるのをやめる

FOCUS = """# 今回の書き直しで必ず守ること（検索から来た人への答えを先に。2026-11-09 オーナー承認・台帳 A68）
この記事は Google で「{query}」と検索されて、平均{position}位に出ています。上にいるのは公式サイトと大手のメディアです。
- 本文の最初の2文で、「{query}」と調べた人が知りたいこと（何か・いつ・いくら・対象・何をすればいいか）に、資料にある事実で答える。
- 検索された言葉（「{query}」の中の言葉。支給日・いつ・いくら・対象・届かない など）を、資料で答えられるときは本文の最初の段落にそのまま1回入れる（題名より先に本文。SEO A14）。
- 公式の窓口・申し込み先・確かめ方が資料にあれば、URL とたどり方まで書く。数字は資料のとおり。
- 資料に無いことは書かない（推測・見込みの数字を足さない）。答えが資料に無い点は「公式の発表には記載がありません」と書く。
- 題名は変えない。全体の流れ（結論→要点→詳しく）は今の型のまま。"""

# 検索語が分からない記事（Search Console が隠した）の指示。検索語を作らない（2026-11-22）
FOCUS_NO_QUERY = """# 今回の書き直しで必ず守ること（検索から来た人への答えを先に。2026-11-22 オーナー決定・台帳 A68）
この記事は Google の検索結果に出ていますが、検索された言葉は分かっていません。言葉を推測して本文に入れないでください。
- 本文の最初の2文で、題名「{title}」を見て開いた人が知りたいこと（何か・いつ・いくら・対象・何をすればいいか）に、資料にある事実で答える。
- 公式の窓口・申し込み先・確かめ方が資料にあれば、URL とたどり方まで書く。数字は資料のとおり。
- 資料に無いことは書かない（推測・見込みの数字を足さない）。答えが資料に無い点は「公式の発表には記載がありません」と書く。
- 題名は変えない。全体の流れ（結論→要点→詳しく）は今の型のまま。"""

# 古い出来事を、これからの予定のように書かない（2026-11-22）
DATE_RULE = """- 今日は {today} です。資料にある期限・受付・発売日・支給日・開催日が今日より前なら、終わったこととして過去形で書く（「これから」「お早めに」と書かない）。今も続いているかが資料で分からないときは、その点を「公式の発表には記載がありません」と書く。
- 文字数を増やすためだけの言い換え・繰り返しを足さない。"""


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


def corrected_slugs(path: Path = CORRECTIONS_PATH) -> set[str]:
    try:
        return {str(x.get("slug")) for x in json.loads(path.read_text("utf-8")) if isinstance(x, dict)}
    except (OSError, ValueError):
        return set()


def protected_reason(article: dict, slug: str = "", corrected: set[str] | None = None) -> str:
    """自動で書き直さない記事の理由（無ければ空）。Muse・編集部の記事と、訂正した記事（台帳 A59 と scripts/rewrite_types.py の決まり）"""
    if article.get("museFile") or article.get("writer") == "muse":
        return "Muse の記事"
    if article.get("refreshMode") == "editorial":
        return "編集部の記事"
    if (slug or article.get("slug")) in (corrected_slugs() if corrected is None else corrected):
        return "訂正した記事"
    if CORRECTION_RE.search(str(article.get("body") or "")):
        return "訂正の注記がある記事"
    return ""


def _read_article(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _in_range(row: dict) -> bool:
    pos = row.get("position")
    return pos is not None and POS_MIN <= float(pos) <= POS_MAX and int(row.get("impressions") or 0) >= MIN_IMPRESSIONS


def _order(rows: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """一番新しい日付（asOf）の行を先に、その中で表示の多い順（違う期間の表示をそのまま比べない）"""
    latest = max((str(r.get("asOf") or "") for _, r in rows), default="")
    return sorted(rows, key=lambda kv: (str(kv[1].get("asOf") or "") != latest, -int(kv[1].get("impressions") or 0),
                                        float(kv[1].get("position") or 99)))


def pick(pages: dict[str, dict], now: datetime, state: dict | None = None, articles_dir: Path = ARTICLES_DIR,
         limit: int = DEFAULT_MAX) -> list[tuple[str, dict]]:
    """今週書き直す記事 [(slug, 順位の行)]。平均4〜20位・表示10回以上・公開中・14日以内に書き直していない・人が確かめた記事ではない"""
    skip = recently_refreshed(state or {}, now)
    corrected = corrected_slugs()
    rows = []
    for slug, row in pages.items():
        if not _in_range(row) or slug in skip:
            continue
        article = _read_article(articles_dir / f"{slug}.json")
        if article is None or protected_reason(article, slug, corrected):
            continue
        rows.append((slug, row))
    return _order(rows)[:limit]


def held_back(pages: dict[str, dict], articles_dir: Path = ARTICLES_DIR) -> list[tuple[str, dict, str]]:
    """順位の条件には合うが、人が確かめた記事なので自動では書き直さない記事 [(slug, 順位の行, 理由)]"""
    corrected = corrected_slugs()
    out = []
    for slug, row in _order([(s, r) for s, r in pages.items() if _in_range(r)]):
        article = _read_article(articles_dir / f"{slug}.json")
        why = protected_reason(article, slug, corrected) if article else ""
        if why:
            out.append((slug, row, why))
    return out


def focus_for(row: dict, title: str = "", today: str = "") -> str:
    """書き直しの指示。検索語が空なら題名の疑問に答える指示にする（検索語は作らない）。題名も無ければ空"""
    query = str(row.get("query") or "").strip()
    title = str(title or "").strip()
    if not query and not title:
        return ""
    day = today or datetime.now(JST).strftime("%Y年%-m月%-d日")
    if query:
        pos = row.get("position")
        head = FOCUS.format(query=query, position=f"{float(pos):.1f}" if pos is not None else "—")
    else:
        head = FOCUS_NO_QUERY.format(title=title)
    return head + "\n" + DATE_RULE.format(today=day)


def stamp(new: dict, row: dict, now: datetime) -> dict:
    """書き直した記事に更新日時（dateModified）と記録を付ける。題名・URL・公開日時はそのまま"""
    at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    # 公式の資料を取り直して本文を書き直したので、更新日時を進めて更新履歴に残す（共通の関数。SEO A16）
    updated_at.touch_updated(new, "refresh", at=at)
    new["searchRefreshedAt"] = at
    new["searchRefresh"] = {"query": row.get("query", ""), "position": row.get("position"), "impressions": row.get("impressions")}
    return new


def use_openai(llm) -> bool:
    """この回を OpenAI で書くか（専用の印があり、OpenAI が先頭の順番で、キーがあるときだけ）"""
    return os.environ.get("SEARCH_REFRESH_OPENAI") == "1" and llm.provider_order("core")[:1] == ["openai"]


def openai_allowance(want: int, llm, est_cost: float) -> tuple[int, str]:
    """OpenAI の予算（期間の上限−余裕、今日の目安）の中で、今回何本書いてよいか。最大 OPENAI_MAX 本"""
    s = llm.openai_ledger_summary()
    if why := llm.openai_block_reason("core", summary=s):
        return 0, f"OpenAI API を使えない（{why}）"
    room = min(float(s["budget"]) - float(s["margin"]) - float(s["spent"]), float(s["daily_limit"]) - float(s["spent_today"]))
    n = max(0, min(want, OPENAI_MAX, int(room // est_cost)))
    return n, (f"OpenAI: 期間 ${float(s['spent']):.2f}/${float(s['budget']):.0f}（余裕 ${float(s['margin']):.0f}）・"
               f"今日 ${float(s['spent_today']):.2f}/目安 ${float(s['daily_limit']):.2f} → {n} 本")


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", "utf-8")


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
        targets = []
        for s in (x for x in args.slug.split(",") if x):
            why = protected_reason(_read_article(ARTICLES_DIR / f"{s}.json") or {}, s)
            if why:
                print(f"  [守る] {s}: {why}なので書き直しません")
            else:
                targets.append((s, pages.get(s, {})))
    else:
        targets = pick(pages, now, state, limit=args.max)
    for slug, row in targets:
        print(f"  {slug:55} 「{row.get('query', '')}」 {row.get('position')}位・表示 {row.get('impressions')}")
    if not args.slug:
        for slug, row, why in held_back(pages):
            print(f"  [守る] {slug:50} {why}（自動では書き直さない） {row.get('position')}位・表示 {row.get('impressions')}")
    if not targets or not args.apply:
        return 0
    import rewrite_types  # noqa: PLC0415 - LLM の部品を読むのは書き直すときだけ

    llm = rewrite_types.llm
    writers = ("anthropic-api:claude-sonnet",)
    if use_openai(llm):
        allowed, why = openai_allowance(len(targets), llm, rewrite_types.EST_COST)
        print(f"[budget] {why}")
        targets = targets[:allowed]
        writers = (f"{llm.OPENAI_PREFIX}{llm.openai_model_for('core')}",)
    elif os.environ.get("ANTHROPIC_API_KEY"):
        allowed, why = rewrite_types.budget_allowance(len(targets))
        print(f"[budget] {why}")
        targets = targets[:allowed]
    done = 0
    started = time.monotonic()
    for index, (slug, row) in enumerate(targets):
        if time.monotonic() - started > TIME_BUDGET_SEC:
            print(f"[search-refresh] 時間の上限 {TIME_BUDGET_SEC} 秒に達したので、残り {len(targets) - index} 本は次の回に回します")
            break
        try:
            title = (_read_article(ARTICLES_DIR / f"{slug}.json") or {}).get("title", "")
            new, rep = rewrite_types.rewrite(slug, focus=focus_for(row, title), writers=writers)
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
        save_state(state)  # 途中で時間切れになっても、書き直した記事と記録がずれない
        done += 1
        print(f"   [OK] {slug}: 書き直した（score {rep.get('score')}）")
    save_state(state)
    print(f"[search-refresh] 書き直し {done} 本 / 今の版のまま {len(targets) - done} 本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
