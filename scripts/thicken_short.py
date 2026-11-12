#!/usr/bin/env python3
"""本文の短い記事を、元の公式の資料の事実で厚くする（2026-11-12 オーナー承認。AdSense の2回目の不承認「有用性の低いコンテンツ」への対策）。

数え方（2026-11-12・公開中 1,196 本）: 本文（空白を除く）が 800字未満 126本・800〜1,499字 257本。記事は消さない。短い記事を厚くする。

選び方: 公開中（取り下げ・転送・重複の代表以外は除く）の、公式の発表が元の記事。本文が 800字未満を先に、そのあと 1,500字未満。
同じ段の中では、検索に出している記事 → 短い順。人が確かめた記事（Muse・編集部の訂正）・動画が元の記事・報道が元の記事・まとめ・災害・
別の切り口の記事は書き直さない（記録だけ。オーナーに判断を聞く一覧に出す）。

書き直し: scripts/rewrite_types.py の rewrite と同じ部品（元の資料を取り直す → 確かな事実の束 → 種類の型 → 生成 → 品質ゲート〔うそだけを
落とす門・台帳 A60〕→ 合格したときだけ保存）。URL・題名（A29 の searchTitle も）・公開日時・続報・画像は変えない。更新日時を進める。
1回目は無料モデル、品質ゲートに落ちたら、今日の予算に余裕があるときだけ Sonnet（救済の段 rescue）。前より厚くなっていない原稿は
品質ゲートの前に落とす（水増しはさせない。資料が薄い記事は「厚くできない」として記録する）。

記録: state/thicken_short.json（記事ごとに thickened / gate-failed / not-thicker / source-unfetchable / source-short /
not-newsworthy / skipped と理由・回数）。同じ記事を何度も試さない（品質ゲート 2回・資料が読めない 2回〔2日あける〕で打ち切り）。

  python3 scripts/thicken_short.py                    # 次に厚くする記事を表示するだけ
  python3 scripts/thicken_short.py --apply --max 15   # 15本を書き直して保存（Actions の thicken_short.yml から）
  python3 scripts/thicken_short.py --apply --slug a,b
  python3 scripts/thicken_short.py --summary          # 段ごとの残り・状態の数
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
import updated_at  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
RETIRED_PATH = ROOT / "content" / "retired.json"
CORRECTIONS_PATH = ROOT / "content" / "corrections.json"
STATE = ROOT / "state" / "thicken_short.json"
TIERS = (800, 1500)  # この字数より短い記事を、この順に
DEFAULT_MAX = 15
MAX_GATE_TRIES = 2       # 品質ゲートに落ちた・厚くならなかった回数の上限
MAX_FETCH_TRIES = 2      # 資料が読めなかった回数の上限
FETCH_GAP = timedelta(days=2)
MAX_TRANSIENT_TRIES = 4  # 無料モデルが使えなかった回数の上限（モデルの都合なので多めに）
# Sonnet で書き直す1回あたりの費用の見込み（確認・手直しを含む）。今日の予算の残りから、Sonnet に回してよい本数を出す
EST_COST = float(os.environ.get("THICKEN_EST_COST_USD", "0.25"))
CORRECTION_RE = re.compile(r"編集部訂正|【訂正】|訂正（\d{4}年")
SOURCE_SHORT_RE = re.compile(r"元の資料が読めない・短い（(\d+)字）")
DONE = "thickened"
FINAL = {"thickened", "source-short", "not-newsworthy", "skipped"}
STATUS_LABELS = {
    "thickened": "厚くした", "gate-failed": "品質ゲートに不合格", "not-thicker": "厚くならなかった（資料の事実が少ない）",
    "source-unfetchable": "元の資料が読めない", "source-short": "元の資料が短い", "not-newsworthy": "記事にする価値なしと判定",
    "skipped": "書き直さない記事", "transient": "モデルが使えなかった（次の回）",
}

FOCUS = """# 今回の書き直しで必ず守ること（短すぎる記事を、公式の資料の事実で厚くする。2026-11-12 オーナー承認）
今の記事の本文は {chars}字で、読者が知りたいことに答えきれていません。上の資料（公式の発表）にある事実だけを使い、次の順で書いてください。
1. 本文の最初の段落（見出しなし）で答えを先に書く: だれに関係するか・いくら（金額・割合・件数）・いつから（日付・期限）を、資料にある事実で2〜3文。
   関係しない人には何も変わらない場合は、そのことも1文で書く。
2. 資料にある数字（金額・日付・期限・件数・割合・対象の条件・回数）は省かずに、資料のとおり書く。比べられる数字は表にしてよい。
3. 判断の目安を「〜の人は〜」の形で2〜4行書く（立場ごとに何が変わるか・何をすればいいか。資料で言えることだけ）。
4. 読者がやること・確かめることを書く: 申し込み先・窓口・期限・確かめ方を、資料にある URL とたどり方まで。資料に無ければ書かない。
5. 最後のほうに「## サイソクの見方」の章を置き、1〜3文で書く。この記事の事実から言えること（前との違い・見落としやすい条件・
   だれに影響が大きいか）だけ。資料に無い予測・見込みの数字・「〜になるだろう」「〜が期待される」は書かない。
- 水増しはしない: 同じことのくり返し・一般論・だれにでも当てはまる注意・資料に無い背景の説明で長くしない。資料の事実が少なければ短いままでよい。
- 資料の文をそのまま写さない（自分の言葉で言い換える。固有名詞・数字・制度名・発言の「」の引用はそのまま）。
- 題名は変えない。全体の流れ（結論→要点→詳しく）は今の型のまま。"""

THICKEN_NOTE = "公式の資料を読み直し、対象・数字・手続きを書き足しました"


def log(msg: str) -> None:
    print(msg, flush=True)


def chars(text: str | None) -> int:
    """本文の字数（空白・改行を除く。2026-11-12 の数え方と同じ）"""
    return len(re.sub(r"\s", "", text or ""))


def tier_of(n: int) -> int | None:
    for i, limit in enumerate(TIERS):
        if n < limit:
            return i
    return None


# --------------------------------------------------------------------------- #
# 記録
# --------------------------------------------------------------------------- #


def load_state(path: Path = STATE) -> dict:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("articles", {})
    data.setdefault("runs", [])
    return data


def save_state(state: dict, path: Path = STATE) -> None:
    state["runs"] = state.get("runs", [])[-60:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")


def _when(value) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def retry_allowed(row: dict | None, now: datetime) -> bool:
    """記録から見て、この記事をもう一度試してよいか（同じ記事を何度も試さない）"""
    if not row:
        return True
    status, tries = row.get("status"), int(row.get("tries") or 0)
    if status in FINAL:
        return False
    if status in ("gate-failed", "not-thicker"):
        return int(row.get("gateTries") or tries) < MAX_GATE_TRIES
    if status == "source-unfetchable":
        at = _when(row.get("at"))
        return int(row.get("fetchTries") or tries) < MAX_FETCH_TRIES and (at is None or now - at >= FETCH_GAP)
    if status == "transient":
        return int(row.get("transientTries") or tries) < MAX_TRANSIENT_TRIES
    return True


def record(state: dict, slug: str, status: str, why: str, now: datetime, **extra) -> dict:
    """記事ごとの結果を記録する。回数は種類ごとに数える（品質ゲート・資料・モデルの都合）"""
    row = dict(state["articles"].get(slug) or {})
    counter = {"gate-failed": "gateTries", "not-thicker": "gateTries", "source-unfetchable": "fetchTries",
               "source-short": "fetchTries", "transient": "transientTries"}.get(status)
    if counter:
        row[counter] = int(row.get(counter) or 0) + 1
    row["tries"] = int(row.get("tries") or 0) + (0 if status == "skipped" else 1)
    row.update({"status": status, "why": str(why)[:200], "at": now.astimezone(timezone.utc).isoformat(timespec="seconds"), **extra})
    state["articles"][slug] = row
    return row


# --------------------------------------------------------------------------- #
# 選び方
# --------------------------------------------------------------------------- #


def _retired() -> set[str]:
    try:
        return set((json.loads(RETIRED_PATH.read_text("utf-8")).get("articles") or {}).keys())
    except (OSError, ValueError):
        return set()


def _corrected() -> set[str]:
    try:
        return {str(x.get("slug")) for x in json.loads(CORRECTIONS_PATH.read_text("utf-8")) if isinstance(x, dict)}
    except (OSError, ValueError):
        return set()


def skip_reason(a: dict, corrected: set[str] = frozenset(), dups: set[str] = frozenset()) -> str | None:
    """この道具で書き直さない理由（書き直してよいなら None）。取り下げた記事は呼ぶ前に除く"""
    slug = a.get("slug")
    if a.get("duplicateOf") or slug in dups:
        return "重複（別の記事に転送・代表がある）"
    if a.get("museFile") or a.get("refreshMode") == "editorial":
        return "人が確かめた記事（Muse・編集部）"
    if slug in corrected or CORRECTION_RE.search(a.get("body") or ""):
        return "訂正した記事"
    if a.get("type") == "roundup" or a.get("trendKeyword"):
        return "まとめの記事（元の資料が1本ではない）"
    if a.get("disaster"):
        return "災害の記事（専用の手順で更新する）"
    if a.get("angleOf"):
        return "別の切り口の記事（親の記事と同じ資料）"
    if a.get("sourceType") != "web" or not a.get("sourceUrl"):
        return "公式の発表の資料が無い（動画などが元）"
    if a.get("secondary"):
        return "報道が元（公式の資料ではない）"
    return None


def load_articles(articles_dir: Path = ARTICLES_DIR) -> list[dict]:
    out = []
    for p in sorted(articles_dir.glob("*.json")):
        try:
            a = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(a, dict) and a.get("slug"):
            out.append(a)
    return out


def _noindexed(a: dict, dups: set[str]) -> bool:
    try:
        import indexnow  # noqa: PLC0415

        return indexnow.noindex_reason(a, dups) is not None
    except Exception:  # noqa: BLE001
        return False


def _dups(articles: list[dict]) -> set[str]:
    try:
        import indexnow  # noqa: PLC0415

        return set(indexnow.duplicate_slugs(articles))
    except Exception:  # noqa: BLE001
        return {a.get("slug", "") for a in articles if a.get("duplicateOf")}


def candidates(articles: list[dict], state: dict, now: datetime, retired: set[str] | None = None,
               corrected: set[str] | None = None, dups: set[str] | None = None) -> tuple[list[dict], list[tuple[dict, str]]]:
    """([次に厚くする記事（順番どおり）], [(書き直さない短い記事, 理由)])"""
    retired = _retired() if retired is None else retired
    corrected = _corrected() if corrected is None else corrected
    live = [a for a in articles if a.get("slug") not in retired]
    dups = _dups(live) if dups is None else dups
    rows, skipped = [], []
    for a in live:
        n = chars(a.get("body"))
        tier = tier_of(n)
        if tier is None:
            continue
        why = skip_reason(a, corrected, dups)
        if why:
            skipped.append((a, why))
            continue
        if not retry_allowed((state.get("articles") or {}).get(a["slug"]), now):
            continue
        rows.append((tier, _noindexed(a, dups), n, a["slug"], a))
    rows.sort(key=lambda r: r[:4])
    return [r[-1] for r in rows], skipped


def accept_for(old_chars: int):
    """前より厚くなったか（品質ゲートの前に見る）。+300字か1.3倍の多いほう。水増しをさせないよう、字数の目標はプロンプトに書かない"""
    need = max(old_chars + 300, int(old_chars * 1.3))

    def _accept(rec: dict) -> str | None:
        n = chars(rec.get("body"))
        if n >= need:
            return None
        return (f"本文が {n}字で、前の版（{old_chars}字）からほとんど厚くなっていません。資料にある数字・対象の条件・期限・窓口・"
                f"判断の目安（〜の人は〜）を足してください。資料に無いこと・くり返し・一般論で長くしないこと")
    return _accept


def paid_allowance(want: int) -> tuple[int, str]:
    """今日の予算の残りで Sonnet に回してよい本数（rewrite_types.budget_allowance と同じ計算・見込みの額だけ別）"""
    import llm  # noqa: PLC0415

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return 0, "ANTHROPIC_API_KEY が無い（無料モデルだけ）"
    s = llm.api_ledger_summary()
    if why := llm.api_block_reason("rescue", summary=s):
        return 0, f"Claude API を使えない（{why}）"
    daily = max(0.0, float(s["budget"]) - float(s["spent"])) / max(1, int(s.get("days_left") or 1))
    room = daily - float(s.get("spent_today") or 0)
    n = max(0, min(want, int(room // EST_COST)))
    return n, f"今日使ってよい額 ${daily:.2f}・今日使った額 ${float(s.get('spent_today') or 0):.2f} → Sonnet に回せる {n} 本"


def stamp(new: dict, now: datetime, before: int) -> dict:
    at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    updated_at.touch_updated(new, "refresh", at=at, title=THICKEN_NOTE, source_url=new.get("sourceUrl") or "",
                             source_name=new.get("sourceName") or "")
    new["thickenedAt"] = at
    new["thicken"] = {"before": before, "after": chars(new.get("body"))}
    return new


def classify(rep: dict) -> tuple[str, str]:
    """rewrite の報告 → (記録の状態, 理由)"""
    why = str(rep.get("why") or "")
    if m := SOURCE_SHORT_RE.search(why):
        return ("source-unfetchable" if int(m.group(1)) == 0 else "source-short"), why
    if rep.get("transient") or "Sonnet が使えなかった" in why or why.startswith("失敗:"):
        return "transient", why
    if "記事にする価値なし" in why:
        return "not-newsworthy", why
    if "訂正した記事" in why:
        return "skipped", why
    problems = rep.get("problems") or []
    if problems and all("ほとんど厚くなっていません" in str(p) for p in problems):
        return "not-thicker", why
    return "gate-failed", (why + (f"（{str(problems[0])[:120]}）" if problems else ""))


def write_article(slug: str, new: dict, articles_dir: Path = ARTICLES_DIR) -> None:
    (articles_dir / f"{slug}.json").write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", "utf-8")


def summary(articles: list[dict], state: dict, now: datetime) -> dict:
    todo, skipped = candidates(articles, state, now)
    retired = _retired()
    live = [a for a in articles if a.get("slug") not in retired]
    counts = {f"<{t}": sum(1 for a in live if chars(a.get("body")) < t) for t in TIERS}
    status: dict[str, int] = {}
    for row in (state.get("articles") or {}).values():
        status[row.get("status")] = status.get(row.get("status"), 0) + 1
    return {"live": len(live), "short": counts, "todo": {f"<{t}": sum(1 for a in todo if chars(a.get("body")) < t) for t in TIERS},
            "skipped": len(skipped), "status": status}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX)
    ap.add_argument("--slug", default="", help="カンマ区切り")
    ap.add_argument("--budget-sec", type=int, default=3000)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--report", default="", help="結果の JSON（前と後の字数つき）")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    state = load_state()
    articles = load_articles()
    if args.summary:
        print(json.dumps(summary(articles, state, now), ensure_ascii=False, indent=1))
        return 0
    todo, skipped = candidates(articles, state, now)
    if args.apply:
        for a, why in skipped:  # 書き直さない短い記事も記録する（オーナーに判断を聞く一覧）
            row = state["articles"].get(a["slug"]) or {}
            if row.get("status") != "skipped" or row.get("why") != why:
                record(state, a["slug"], "skipped", why, now, before=chars(a.get("body")))
    if args.slug:
        by_slug = {a["slug"]: a for a in articles}
        todo = [by_slug[s] for s in args.slug.split(",") if s in by_slug]
    todo = todo[: max(0, args.max)]
    log(f"[thicken] 次に厚くする記事 {len(todo)} 本（書き直さない短い記事 {len(skipped)} 本）")
    for a in todo:
        log(f"  {chars(a.get('body')):5}字  {a['slug'][:60]:60} {a.get('genre', '')}")
    if not todo or not args.apply:
        if args.apply:
            save_state(state)
        return 0
    import rewrite_types  # noqa: PLC0415 - LLM の部品を読むのは書き直すときだけ

    paid_left, why = paid_allowance(len(todo))
    log(f"[budget] {why}")
    started, results, done = time.time(), [], 0
    for i, a in enumerate(todo, 1):
        if time.time() - started > args.budget_sec:
            log("[info] 時間の上限なので、残りは次の回に回します")
            break
        slug, before = a["slug"], chars(a.get("body"))
        log(f"\n[{i}/{len(todo)}] {slug}（{before}字）")
        spent_before = rewrite_types.run_cost()
        try:
            new, rep = rewrite_types.rewrite(slug, focus=FOCUS.format(chars=before), free_first=True, paid_ok=paid_left > 0,
                                             write_purpose="rescue", accept=accept_for(before))
        except Exception as error:  # noqa: BLE001 - 1本の失敗で止めない
            new, rep = None, {"slug": slug, "why": f"失敗: {str(error)[:200]}"}
        used_paid = any(str(h.get("model") or "").startswith("anthropic-api:claude-sonnet") for h in rep.get("history") or [])
        if used_paid:
            paid_left -= 1
        if new is None:
            status, reason = classify(rep)
            record(state, slug, status, reason, now, before=before)
            log(f"   [keep] 今の版のまま（{STATUS_LABELS.get(status, status)}: {reason[:160]}）")
        else:
            stamp(new, now, before)
            write_article(slug, new)
            after = chars(new.get("body"))
            record(state, slug, DONE, "", now, before=before, after=after, model=str(rep.get("model") or ""))
            done += 1
            log(f"   [OK] {before}字 → {after}字（{rep.get('model')} / score {rep.get('score')}）")
        results.append({"slug": slug, "before": before, "after": chars((new or {}).get("body")) if new else None,
                        "status": state["articles"][slug]["status"], "why": state["articles"][slug].get("why"),
                        "usd": round(rewrite_types.run_cost() - spent_before, 4)})
        save_state(state)
        if args.report:
            Path(args.report).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", "utf-8")
    state["runs"].append({"at": now.isoformat(timespec="seconds"), "tried": len(results), "thickened": done,
                          "usd": round(rewrite_types.run_cost(), 4)})
    save_state(state)
    log(f"\n[done] 厚くした {done} 本 / 今の版のまま {len(results) - done} 本 / この回の費用 ${rewrite_types.run_cost():.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
