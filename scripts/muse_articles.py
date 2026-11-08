#!/usr/bin/env python3
"""Muse（Meta の AI の書き手）が書いた記事を、ふつうの記事と同じ門に通して公開する（2026-11-08 オーナー承認・台帳 A59）。

流れ（Muse には鍵を渡さない。Muse はオーナーの Mac のフォルダにファイルを置くだけ）:
  1. Mac: ~/Downloads/saisoku-articles/*.md → scripts/muse_articles_push.py が content/muse_inbox/ に入れて main に push（launchd で25分ごと）
  2. Actions（auto_run.yml の「Muse articles」の段・ニュースの記事を作る前）: このスクリプトが content/muse_inbox/ を読む
     - 形の確かめ（scripts/muse_format.py）→ 重複（直近7日の記事・同じ発表）→ 今日の本数（段の上限 WEB_STAGE_TARGET の中に数える）
     - 公式の出典ページを取りに行き（報道は出典にしない W31）、Muse の原稿を土台に、ふつうの記事と同じ型（リード・要点・かんたん版・
       FAQ・判定カード）に整える（本文は Muse の構成・文をできるだけ残し、資料と食い違う所・決まりに合わない所だけ直す）
     - ふつうの記事と同じ門: 公開前の門（薄い・お知らせ・報道・主題外）→ 品質の門（形＋公式ページとの事実確認）。
       Muse の記事は事実確認の点数を MUSE_PASS_SCORE（手続きは PROCEDURE_PASS_SCORE）以上に限る
     - 合格: content/articles/<slug>.json（writer: "muse"・refreshMode: "editorial" で自動の書き直しの対象外）。
       今日の本数として content/state.json の processed_web に入れる（＝ニュースの記事はその分だけ少なく作る。scripts/pacing.py）
       画像はこのあとの「Article images」の段（公式の画像 → だめなら話題に合う AI のイメージ・「画像はイメージ（AI生成）」の札）
     - 不合格: 理由を state/muse_articles.json に書く（Mac のスクリプトが rejected/<名前>.reason.txt に写す）
  3. 結果: state/muse_articles.json の items[ファイル名] = {status: published|rejected|waiting, reason, slug, url, title, at}

  python3 scripts/muse_articles.py --daily-cap 60          # auto_run.yml から
  python3 scripts/muse_articles.py --check <file.md>        # 形の確かめだけ（LLM・ネットを使わない）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import muse_format  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "content" / "muse_inbox"
RESULTS = ROOT / "state" / "muse_articles.json"
SITE = "https://ai-tech-express.jp"
JST = timezone(timedelta(hours=9))
DEDUPE_DAYS = 7
MUSE_PASS_SCORE = 80  # ふつうのニュースの記事（quality.PASS_SCORE 70）より高く。人の目を通らない書き手なので
PROCEDURE_PASS_SCORE = 90  # 税・年金・行政の手続き（evergreen.py の PROCEDURE_PASS_SCORE と同じ）
MAX_ATTEMPTS = 2
KEEP_RESULTS = 300
# Muse のジャンル → サイトのレーン（書き方の人物像。最終のジャンルは build_web_record が中身で決め直す）
LANE_BY_GENRE = {
    "手続き": "public", "お金": "public", "早見表": "public", "値上げ": "lifestyle", "暮らし": "lifestyle",
    "速報解説": "business", "ビジネス": "business", "AI・テック": "ai",
}
PROCEDURE_GENRES = {"手続き"}

MUSE_DRAFT_NOTE = """

# 記者の原稿（Muse）— これを土台にする
次は、当サイトの記者が上の公式資料を読んで書いた原稿です。記事はこの原稿を土台にしてください。
- body_markdown: 原稿の構成・見出し・文をできるだけそのまま使う。直すのは、資料と食い違う所、資料に無い事実（削る）、
  上の決まり（見出しの型・文の長さ・宣伝の言葉・自分で試したような書き方・出典の書き方）に合わない所だけ。新しい章や事実を足さない。
- title は原稿の題名を使う（決まりに合わないときだけ最小限に直す。「｜」は使わない）。
- そのほかの欄（lede・description・highlights・easy_markdown・faq・today_actions・work_money・verdict・threads_post など）は、
  資料と原稿の両方にある事実だけで書く。
- 記者のメモ（未確認の点）に書かれたことは、事実として書かない。

## 原稿の題名
{title}

## 記者のメモ（サイトには出さない）
{notes}

## 原稿の本文
<<<
{body}
>>>
"""


def log(message: str) -> None:
    print(message, flush=True)


def load_results() -> dict:
    try:
        data = json.loads(RESULTS.read_text("utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"items": {}}


def save_results(data: dict) -> None:
    items = data.get("items") or {}
    if len(items) > KEEP_RESULTS:
        keep = sorted(items.items(), key=lambda kv: str(kv[1].get("at") or ""), reverse=True)[:KEEP_RESULTS]
        items = dict(keep)
    data["items"] = items
    data["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_id(name: str) -> str:
    return "muse-" + hashlib.sha1(muse_format.nfc(name).encode("utf-8")).hexdigest()[:10]


def host_slug(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    host = re.sub(r"^www\.", "", host)
    return re.sub(r"[^a-z0-9]+", "-", host).strip("-")[:40] or "official"


def muse_disclaimer() -> str:
    return ("本記事は公式発表をもとに、AIの書き手（Muse）が下書きし、サイソクの仕組みで公式ページとの事実確認・編集をして掲載したものです。"
            "制度・金額・期限は変わることがあります。手続きの前に、発表元の公式ページで最新の情報をご確認ください。")


def pass_score(genre: str) -> int:
    return PROCEDURE_PASS_SCORE if genre in PROCEDURE_GENRES else MUSE_PASS_SCORE


def register_today(state: dict, fid: str, record: dict) -> None:
    """今日の本数に数える（scripts/pacing.py の live_today は processed_web の slug で数える）。
    Muse の記事が出た分、ニュースの記事は段の上限（WEB_STAGE_TARGET）までの残りが減る（台帳 A59）"""
    import news_mix  # noqa: PLC0415

    entry = {"url": record.get("sourceUrl", ""), "at": datetime.now(timezone.utc).isoformat(), "slug": record["slug"],
             "writer": "muse", "score": record.get("qualityScore")}
    try:
        entry["mix"] = news_mix.classify({"title": record.get("title", ""), "url": record.get("sourceUrl", ""),
                                          "channelSlug": record.get("channelSlug", "")})
    except Exception:  # noqa: BLE001 - 種類が分からなくても本数には数える
        pass
    state.setdefault("processed_web", {})[fid] = entry


def fetch_sources(sources: list[dict]) -> list[dict]:
    """[{url, name, title, text, image, published}]。1件目（一番の出典）が読めなければ空"""
    import feeds  # noqa: PLC0415

    out = []
    for i, s in enumerate(sources):
        try:
            page = feeds.fetch_article_text(s["url"])
        except Exception as error:  # noqa: BLE001
            log(f"   [muse] 出典を読めません {s['url'][:80]}: {str(error)[:80]}")
            if i == 0:
                return []
            continue
        text = (page.get("text") or "").strip()
        if len(text) < 300:
            log(f"   [muse] 出典の本文が短すぎます {s['url'][:80]}（{len(text)}字）")
            if i == 0:
                return []
            continue
        out.append({**s, "title": (page.get("title") or "").strip(), "text": text, "image": page.get("image") or "",
                    "published": page.get("published"), "page": page})
    return out


def source_text_of(fetched: list[dict]) -> str:
    return "\n\n".join(f"【{s.get('name') or s.get('title') or '公式'}】{s['url']}\n{s['text']}" for s in fetched)


def check_file(path: Path) -> tuple[dict | None, list[str]]:
    try:
        data = muse_format.parse(path.read_text("utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        return None, [f"ファイルを読めません（{str(error)[:60]}）"]
    except muse_format.FormatError as error:
        return None, [str(error)]
    problems = muse_format.problems(data, path.name)
    import public_interest  # noqa: PLC0415

    for s in data.get("sources") or []:
        if s.get("url") and public_interest.is_press_url(s["url"]):
            problems.append(f"報道機関のページは出典にできません（{s['url'][:80]}）。公式の発表を出典にしてください")
    return data, problems


def duplicate_of(data: dict) -> str | None:
    import dedupe  # noqa: PLC0415
    import story  # noqa: PLC0415

    url = data["sources"][0]["url"]
    recent = dedupe.load_recent(DEDUPE_DAYS)
    if hit := recent.find(data["title"], url):
        return hit
    try:
        same = story.Recent(DEDUPE_DAYS).match(data["title"], url)
    except Exception:  # noqa: BLE001
        same = None
    return str(same[0] if isinstance(same, (tuple, list)) else same) if same else None


def build_article(path: Path, data: dict, fetched: list[dict]) -> tuple[str, dict | str]:
    """("ok", record) / ("reject", 理由)。ふつうの記事と同じ型・同じ門"""
    import llm  # noqa: PLC0415
    import main as m  # noqa: PLC0415
    import quality  # noqa: PLC0415
    import web_articles as w  # noqa: PLC0415

    first = fetched[0]
    page = first["page"]
    published = first.get("published")
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            published = None
    guessed = not isinstance(published, datetime)
    if guessed:
        published = datetime.now(timezone.utc)  # 公式ページに日付が無い（PDF など）: 発表の時刻としては記録しない（stamp_times の published_guessed）
    if published.tzinfo is None:
        published = published.replace(tzinfo=JST)
    item = {
        "id": file_id(path.name), "url": first["url"], "title": data["title"],
        "source_name": first.get("name") or first.get("title") or host_slug(first["url"]),
        "source_slug": host_slug(first["url"]), "published_at": published, "image": first.get("image") or "",
        "muse": True, "published_guessed": guessed,
    }
    source_text = source_text_of(fetched)
    lane = LANE_BY_GENRE.get(data["genre"], "lifestyle")
    voice_key, voice_text = m.pick_voice()
    genre, system, prompt, schema, kind, context, bundle = w.compose_with_facts(item, source_text, lane, [], voice_text, page)
    prompt += MUSE_DRAFT_NOTE.format(title=data["title"], notes=data.get("notes") or "（なし）", body=data["body"])
    need = pass_score(data["genre"])
    problems: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            draft, model_name = llm.generate_json(system, prompt + (quality.feedback_block(problems) if problems else ""), schema,
                                                  temperature=0.3, max_output_tokens=32768, tier=w.write_tier("bulk"), purpose="core")
        except Exception as error:  # noqa: BLE001
            return "error", f"整える段の LLM が使えませんでした（{str(error)[:100]}）。次の回にもう一度試します"
        if not draft.get("is_relevant", True):
            return "reject", f"記事にする価値が足りないと判定: {str(draft.get('skip_reason') or '')[:200]}"
        try:
            record = w.build_web_record(item, draft, page, model_name, voice_key, bundle)
        except (KeyError, TypeError, ValueError) as error:
            problems = [f"形式が不正: {error}"]
            continue
        record.update({
            "writer": "muse", "refreshMode": "editorial", "museFile": muse_format.nfc(path.name),
            "disclaimer": muse_disclaimer(),
            # 自動の書き直し（見出し・章の手直し・種類の型）の対象から外す（scripts/rewrite_types.py の refreshMode・section_polish の sectionsPolishedAt）
            "sectionsPolishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        if len(fetched) > 1:
            record["museSources"] = [{"url": s["url"], "name": s.get("name") or s.get("title") or ""} for s in fetched]
        w.pre_gate(record, source_text, context)
        blocked = w.publish_blocked(record)
        if blocked and blocked not in w.indexnow.PUBLISH_RETRYABLE:
            return "reject", f"公開前の門: {w.indexnow.PUBLISH_FEEDBACK[blocked]}"
        if blocked:
            problems = [f"公開前の門: {w.indexnow.PUBLISH_FEEDBACK[blocked]}"]
            log(f"   [muse] 試行{attempt}: {problems[0][:160]}")
            continue
        verdict = quality.evaluate(record, source_text, kind, context, check_facts=True)
        if not verdict["ok"] and not verdict.get("soft") and quality.surgical_ok(verdict):
            fixed, info = quality.surgical_fix(record, source_text, kind, verdict.get("problems") or [], context)
            if fixed is not None:
                record, verdict = fixed, info
        if verdict.get("soft"):
            polished, info = quality.polish(record, source_text, kind, context)
            if polished is not None:
                record, verdict = polished, info
            verdict = {**verdict, "ok": verdict.get("ok") or verdict.get("soft")}
        score = verdict.get("score") or 0
        log(f"   [muse] 試行{attempt}: {'合格' if verdict.get('ok') else '不合格'} score={score}（必要 {need}）"
            f" {' | '.join((verdict.get('problems') or [])[:3])[:300]}")
        if verdict.get("ok") and score >= need:
            record["qualityScore"] = score
            w.finalize_facts(record, source_text)
            w.stamp_times(record, item, datetime.now(timezone.utc))
            return "ok", record
        problems = list(verdict.get("problems") or [])
        if verdict.get("ok") and score < need:
            problems = [f"公式ページとの事実確認の点数が {score} 点（Muse の記事は {need} 点以上）"] + problems
    return "reject", "品質の門で不合格: " + " / ".join(problems[:4])[:600]


def process(args) -> int:
    import main as m  # noqa: PLC0415
    import pacing  # noqa: PLC0415

    files = sorted(p for p in INBOX.glob("*.md")) if INBOX.exists() else []
    if not files:
        log("[muse] 入稿はありません")
        return 0
    results = load_results()
    state = m.load_state()
    state.setdefault("processed_web", {})
    published = rejected = 0
    started = time.time()
    for path in files:
        name = muse_format.nfc(path.name)
        if published >= args.max or time.time() - started > args.budget:
            log(f"[muse] この回はここまで（残りは次の回）: {name}")
            break
        log(f"\n[muse] {name}")
        data, problems = check_file(path)

        def finish(status: str, reason: str = "", record: dict | None = None) -> None:
            row = {"status": status, "reason": reason[:800], "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "title": (record or {}).get("title") or (data or {}).get("title") or ""}
            if record:
                row.update({"slug": record["slug"], "url": f"{SITE}/articles/{record['slug']}"})
            results["items"][name] = row
            # 1本ごとに記録を書く（途中で時間切れになっても、公開した記事・結果を取りこぼさない）
            m.save_state(state)
            save_results(results)
            if status != "waiting":
                path.unlink(missing_ok=True)
            log(f"   [muse] → {status} {reason[:200]}")

        if problems:
            finish("rejected", "書式: " + " / ".join(problems))
            rejected += 1
            continue
        if dup := duplicate_of(data):
            finish("rejected", f"重複: この7日の記事「{dup}」と同じ話題です。ledger.md を見て別の話題にしてください")
            rejected += 1
            continue
        if args.daily_cap and pacing.live_today(state) >= args.daily_cap:
            finish("waiting", f"今日の記事の本数（{args.daily_cap}本）がいっぱいなので、次の日に回します")
            continue
        fetched = fetch_sources(data["sources"])
        if not fetched:
            finish("rejected", "1件目の出典（公式ページ）を読めませんでした。URL が正しいか、ログインなしで開けるページかを確かめてください")
            rejected += 1
            continue
        status, out = build_article(path, data, fetched)
        if status == "error":
            log(f"   [muse] {out}（入稿はそのまま残します）")
            results["items"][name] = {"status": "waiting", "reason": str(out), "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                      "title": data["title"]}
            break
        if status != "ok":
            finish("rejected", str(out))
            rejected += 1
            continue
        record = out
        target = m.write_article(record)
        register_today(state, file_id(name), record)
        published += 1
        finish("published", "", record)
        log(f"   [muse] 公開へ: {target.relative_to(ROOT)}（score {record.get('qualityScore')}）")
    m.save_state(state)
    save_results(results)
    log(f"\n[muse] 公開 {published} 本 / 見送り {rejected} 本")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--daily-cap", type=int, default=int(os.environ.get("WEB_DAILY_CAP") or 0), help="今日の記事の本数の上限（段）")
    parser.add_argument("--max", type=int, default=3, help="この回に公開する最大本数")
    parser.add_argument("--budget", type=int, default=600, help="この回に使う秒数の目安")
    parser.add_argument("--check", help="形の確かめだけ（ファイルのパス）")
    args = parser.parse_args()
    if args.check:
        data, problems = check_file(Path(args.check))
        print(json.dumps({"ok": not problems, "problems": problems, "title": (data or {}).get("title")}, ensure_ascii=False, indent=2))
        return 0 if not problems else 2
    return process(args)


if __name__ == "__main__":
    sys.exit(main())
