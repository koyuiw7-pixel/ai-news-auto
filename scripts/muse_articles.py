#!/usr/bin/env python3
"""Muse（Meta の AI の書き手）が書いた記事を、ふつうの記事と同じ門に通して公開する（2026-11-08 オーナー承認・台帳 A59）。

流れ（Muse には鍵を渡さない。Muse はオーナーの Mac のフォルダにファイルを置くだけ）:
  1. Mac: ~/Downloads/saisoku-articles/*.md → scripts/muse_articles_push.py が content/muse_inbox/ に入れて main に push（launchd で25分ごと）
  2. Actions（muse_inbox.yml。入稿の push ですぐ・30分ごとの予約でも。記事づくりの回とは別の列）: このスクリプトが content/muse_inbox/ を読む
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

  python3 scripts/muse_articles.py --daily-cap 60          # muse_inbox.yml から
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
import own_view  # noqa: E402
import quality_bar  # noqa: E402
import source_date  # noqa: E402

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
    "速報解説": "business", "ビジネス": "business", "AI・テック": "ai", "比較": "lifestyle",  # 2026-11-09 比較・選び方（収益の受け皿）
}
PROCEDURE_GENRES = {"手続き"}
COMPARISON_GENRE = "比較"  # 選び方・比較の記事（ニュース記事から「次に読む」で案内する受け皿。lib/comparison.ts）

MUSE_DRAFT_NOTE = """

# 記者の原稿（Muse）— これを土台にする
次は、当サイトの記者が上の公式資料を読んで書いた原稿です。記事はこの原稿を土台にしてください。
- body_markdown: 原稿の構成・見出し・文をできるだけそのまま使う。直すのは、資料と食い違う所、資料に無い事実（削る）、
  上の決まり（見出しの型・文の長さ・宣伝の言葉・自分で試したような書き方・出典の書き方）に合わない所だけ。新しい章や事実を足さない。
  ただし「サイソクの見方」の章は例外（2026-11-12 オーナー）: 原稿にあれば残し、資料で裏づけられない所だけ直す。無ければ上の「サイソクの見方」の決まりで、
  本文の事実だけを根拠に1章だけ足す。
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

# 依頼した記事は、話題の分野で落とさない（2026-11-13 オーナー「落とすのは嘘だけ」）。
# 何を記事にするかは編集部が決めて Muse に頼んでいる。LLM が is_relevant=false にしてよいのは、読めた資料で主な事実を確かめられないときだけ
#（例: 障害の記事なのに、読めた資料が数か月前の一般の案内ページで障害に触れていない）。このあとの門（出典の日付・数字・出典の形式・重複・品質の点）は変えない
MUSE_DESK_NOTE = """

# 話題は編集部が決めた（この原稿だけの決まり。上の is_relevant の決まりより優先する）
この記事の話題は、編集部が選んで記者に依頼したものです。話題の分野を理由に対象外にしないでください。
- is_relevant は true にする。企業の人事・役員の交代、芸能、スポーツ、市場・株価、海外の話題など、どの分野でも同じ。
  上のジャンルの決まりに「この分野は is_relevant を false にする」とあっても、この原稿には当てはめない。
  「暮らし・制度・お金に直接関わらない」「公的な発表ではない」「人事のお知らせにすぎない」は、対象外にする理由にならない。
- is_relevant を false にしてよいのは、上の資料（読めた出典）で、記事の中心になる事実を確かめられないときだけ。
  例: 資料がその出来事にまったく触れていない。資料が別の日・別の出来事のものである。資料が古い一般の案内ページで、原稿が書く出来事が載っていない。
  そのときは skip_reason に「どの事実が、どの資料で確かめられなかったか」を具体的に書く。
- 資料で確かめられない所が一部だけなら、対象外にせず、その所だけを削って記事にする。

# 報道を引いた所の書き方
原稿が報道機関の名前を出して伝えている所（例:「FTが報じた」「ロイターによると」）は、本文に残してよい。
- 必ず「〇〇が報じた」「〇〇によると」と、どこの報道かが分かる形のままにする。確定した事実のようには書かない（「〜と報じられている」「〜とされる」）。
- 題名・lede・highlights・threads_post などでも、報道の内容を確定した事実として言い切らない。
- 資料の中に、相手側（会社・本人・役所）の公式のコメントや発表があるときは、必ず本文に入れる。資料に無いコメントは作らない。
- sources（出典の一覧）の決まりは変わらない。報道機関の記事の URL は出典に並べない。
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


def muse_disclaimer(genre_slug: str = "") -> str:
    text = ("本記事は公式発表をもとに、AIの書き手（Muse）が下書きし、サイソクの仕組みで公式ページとの事実確認・編集をして掲載したものです。"
            "制度・金額・期限は変わることがあります。手続きの前に、発表元の公式ページで最新の情報をご確認ください。")
    # 投資・マネーの記事は短い免責文が必須（genre_focus.ADVICE_DISCLAIMER_MARK）。Muse の免責文に無く、
    # 中身に関係なく門で落ちていた（2026-11-12「12月から変わること」v2・すかいらーくの株主優待など）
    if genre_slug == "investment":
        text += "特定の金融商品の売買をすすめるものではなく、投資助言ではありません。"
    return text


def pass_score(genre: str) -> int:
    return PROCEDURE_PASS_SCORE if genre in PROCEDURE_GENRES else MUSE_PASS_SCORE


def comparison_topic(title: str, body: str, override: str = "") -> str | None:
    """比較記事の話題（scripts/a8_import.py の ACTION_ADS の key）。lib/comparison.ts の comparisonTopicOf と同じ規則:
    題名に当たる話題を優先し、題名で当たった語の数 → 本文で当たった語の数の多い順。同点は ACTION_ADS の順。
    題名に当たらない話題は、本文で3語以上当たったときだけ。除く語（exclude）が題名にある話題は使わない"""
    import a8_import  # noqa: PLC0415

    keys = [rule["key"] for rule in a8_import.ACTION_ADS]
    if override and override in keys:
        return override
    best: tuple[tuple[int, int, int], str] | None = None
    for rule in a8_import.ACTION_ADS:
        try:
            pattern = re.compile(rule["match"], re.I)
            exclude = re.compile(rule["exclude"], re.I) if rule.get("exclude") else None
        except re.error:
            continue
        if exclude and exclude.search(title):
            continue
        t = len({m.group(0).lower() for m in pattern.finditer(title)})
        b = len({m.group(0).lower() for m in pattern.finditer(body)})
        if t == 0 and b < 3:
            continue
        score = (1 if t else 0, t, b)
        if best is None or score > best[0]:
            best = (score, rule["key"])
    return best[1] if best else None


def mark_comparison(record: dict, data: dict) -> None:
    """ジャンル「比較」の原稿なら、記事に kind: "comparison" と話題（comparisonTopic）を付ける
    （ニュース記事の「次に読む」の受け皿・話題の提携先の一覧。lib/comparison.ts）"""
    if data.get("genre") != COMPARISON_GENRE:
        return
    record["kind"] = "comparison"
    topic = comparison_topic(record.get("title") or data.get("title") or "",
                             " ".join([record.get("lede") or "", record.get("description") or "", record.get("body") or ""]),
                             str(data.get("topic") or "").strip())
    if topic:
        record["comparisonTopic"] = topic


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


MULTI_SOURCE_CAP = 26000  # quality.MULTI_SOURCE_CAP と同じ（出典が何本もある記事の事実確認に渡す長さ）
MIN_PER_SOURCE = 1800  # 1本あたりの最低の長さ（料金・プランの行が残るように）
NOTE_CAP = 300  # 書き手のメモ（sources[].facts）を出典の見出しに添える長さ


def fetch_sources(sources: list[dict], skip_unreadable_first: bool = False, unread: list[str] | None = None) -> list[dict]:
    """[{url, name, title, text, full_text, image, published, page}]。1件目（一番の出典）が読めなければ空。
    skip_unreadable_first（比較・選び方の記事）: 製品ごとに公式ページを挙げるので、1件目が読めなくても次に読めた出典を一番にする
    （2026-11-09: スマホと光回線の記事が、1件目の ahamo のページを読めなかっただけで落ちた）。
    unread に読めなかった出典の URL を入れる（落としたときの理由に書く）"""
    import feeds  # noqa: PLC0415

    out = []
    for i, s in enumerate(sources):
        try:
            page = feeds.fetch_article_text(s["url"])
        except Exception as error:  # noqa: BLE001
            log(f"   [muse] 出典を読めません {s['url'][:80]}: {str(error)[:80]}")
            page = None
        text = ((page or {}).get("text") or "").strip()
        if page is not None and len(text) < 300:
            log(f"   [muse] 出典の本文が短すぎます {s['url'][:80]}（{len(text)}字）")
        if page is None or len(text) < 300:
            if unread is not None:
                unread.append(s["url"])
            if i == 0 and not skip_unreadable_first:
                return []
            continue
        out.append({**s, "title": (page.get("title") or "").strip(), "text": text, "full_text": (page.get("full_text") or "").strip(),
                    "image": page.get("image") or "", "published": page.get("published"), "page": page})
    if out and out[0]["url"] != sources[0]["url"]:
        log(f"   [muse] 1件目の出典を読めないので、読めた出典 {out[0]['url'][:80]} を一番の出典にします")
    return out


def source_text_of(fetched: list[dict], title: str = "", cap: int = MULTI_SOURCE_CAP) -> str:
    """生成・事実確認に渡す出典の本文。出典が2本以上なら、全部の出典が事実確認（quality.source_cap）に入るよう1本ごとに長さを割り当て、
    長いページは記事の題名・書き手のメモ（sources[].facts）の言葉と数字・料金の行を優先して抜き出す（source_links.excerpt）。
    書き手のメモは「確かめる手がかり」として添えるだけで、根拠は下のページの本文（メモにしかない事実は創作扱いのまま）"""
    if len(fetched) <= 1:
        return "\n\n".join(f"【{s.get('name') or s.get('title') or '公式'}】{s['url']}\n{s['text']}" for s in fetched)
    import source_links  # noqa: PLC0415

    per = max(MIN_PER_SOURCE, cap // len(fetched) - 200)
    parts = []
    for s in fetched:
        body = s.get("full_text") or s["text"]
        note = re.sub(r"\s+", " ", str(s.get("facts") or "")).strip()
        if len(body) > per:
            body = source_links.excerpt(body, f"{title} {s.get('name') or ''} {note}", cap=per)
        head = f"【{s.get('name') or s.get('title') or '公式'}】{s['url']}"
        if note:
            head += f"\n（書き手のメモ。根拠ではない。下のページの本文にあるかで確かめる: {note[:NOTE_CAP]}）"
        parts.append(f"{head}\n{body}")
    return "\n\n".join(parts)


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


FOLLOWUP_RE = re.compile(r"続報|翌日|その後|2日目|二日目|第[0-9０-９一二三四五六七八九十]+報")


def is_followup(data: dict, name: str = "") -> bool:
    """続報・翌朝の解説（2026-11-09 オーナー: 当たった話題の「その後どうするか」を朝に出す）"""
    text = " ".join([name, data.get("title") or "", data.get("notes") or ""])
    return bool(FOLLOWUP_RE.search(text))


# 毎月の「〜月から変わること」のまとめ（2026-11-12 オーナー承認の定番）。まとめは最近の記事と同じ公式ページを出典に使うのが当たり前なので、
# 続報と同じく「見出しがほぼ同じ（同じ記事の出し直し）」のときだけ重複にする
ROUNDUP_RE = re.compile(r"[0-9０-９]{1,2}月から変わること|[0-9０-９]{4}年[0-9０-９]{1,2}月から変わること")


def is_roundup(data: dict, name: str = "") -> bool:
    return bool(ROUNDUP_RE.search(" ".join([name, data.get("title") or ""])))


def duplicate_of(data: dict, name: str = "") -> str | None:
    import dedupe  # noqa: PLC0415
    import story  # noqa: PLC0415

    url = data["sources"][0]["url"]
    recent = dedupe.load_recent(DEDUPE_DAYS)
    if is_followup(data, name) or is_roundup(data, name):
        # 続報は同じ出典・同じ固有名詞が当たり前。見出しがほぼ同じ（同じ記事の出し直し）のときだけ重複にする
        grams = dedupe.bigrams(data["title"])
        for entry in recent.entries:
            if dedupe.jaccard(grams, entry["bigrams"]) >= dedupe.JACCARD_DUP:
                return f"見出しがほぼ同じ: {entry['label'][:40]}"
        return None
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
    source_text = source_text_of(fetched, data["title"])
    lane = LANE_BY_GENRE.get(data["genre"], "lifestyle")
    voice_key, voice_text = m.pick_voice()
    genre, system, prompt, schema, kind, context, bundle = w.compose_with_facts(item, source_text, lane, [], voice_text, page,
                                                                                    extra_sources=fetched[1:])
    prompt += MUSE_DRAFT_NOTE.format(title=data["title"], notes=data.get("notes") or "（なし）", body=data["body"])
    prompt += MUSE_DESK_NOTE  # 話題は編集部が決めた。落とすのは資料で確かめられないときだけ（2026-11-13）
    # 出典の資料の日付・会議の回と、記事が書く出来事が合っているか（2026-11-10 の取り下げ。scripts/source_date.py）。
    # 下書きの時点で分かった食い違いは、最初の試行から直させる（公開前の門は下の試行の中で記事の JSON に当てる）
    today = datetime.now(JST).date()
    # もう始まった変更（実施済みの値上げなど）を「これから」と書いていないか（2026-11-12 の取り下げ7本。source_date.past_change）
    if early := source_date.check([data["title"], data["body"]], fetched, today) + source_date.past_change([data["title"], data["body"]], today):
        prompt += "\n\n【出典の日付の注意（必ず直す）】\n" + "\n".join(f"- {p}" for p in early)
        log(f"   [muse] 出典の日付の注意: {early[0][:160]}")
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
            "disclaimer": muse_disclaimer(record.get("genreSlug") or ""),
            # 自動の書き直し（見出し・章の手直し・種類の型）の対象から外す（scripts/rewrite_types.py の refreshMode・section_polish の sectionsPolishedAt）
            "sectionsPolishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        mark_comparison(record, data)
        if (data.get("depth") or "").strip():
            # 一歩深くする欄の材料（scripts/depth_fields.py が公式ページで確かめてから使い、使ったら記事から外す。台帳 A66）
            record["museDepthNotes"] = data["depth"].strip()[:3000]
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
        # 「サイソクの見方」の章が無い・本文が薄い原稿は、事実確認の前に1回だけ足す（scripts/own_view.py。足したものも下の事実確認を通す）。
        # Muse の記事は「落とす理由は嘘だけ」（2026-11-09 オーナー）なので、足せなくても章の有無・長さでは落とさない
        own_view.ensure(record, source_text, context, log=log)
        # 記事の8つの基準（scripts/quality_bar.py）: 足りない点を1回だけ手直しする（下の事実確認を通す）。Muse の記事は基準では落とさない（記録だけ）
        quality_bar.ensure(record, source_text, context, log=log)
        texts = source_date.record_texts(record) + [str(a) for a in record.get("todayActions") or []]
        if dated := source_date.check(texts, fetched, today) + source_date.past_change(texts, today):
            problems = dated
            log(f"   [muse] 試行{attempt}: {dated[0][:160]}")
            continue
        verdict = quality.evaluate(record, source_text, kind, context, check_facts=True)
        # 2026-11-09 オーナー（台帳 A60 をすべての経路に）: ふつうの記事と同じく、形の指摘（資料に無い数字・電話番号など）も
        # 作り直さずその場で直す（LLM の手直し → だめなら指摘の文をプログラムで削って門をもう一度。quality.surgical_fix）
        if not verdict["ok"] and not verdict.get("soft") and quality.repairable(verdict):
            try:
                fixed, info = quality.surgical_fix(record, source_text, kind, verdict.get("problems") or [], context)
            except Exception as error:  # noqa: BLE001 - 直す段が使えなくても、作り直しの試行は続ける
                fixed, info = None, f"その場の手直しに失敗（{str(error)[:80]}）"
            if fixed is not None:
                log(f"   [muse] 指摘の箇所を直して合格（{str(info.get('fixed_by'))[:80]}）")
                record, verdict = fixed, info
            else:
                log(f"   [muse] その場の手直しでは救えず: {str(info)[:200]}")
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
            bar = quality_bar.check(record, verdict, at_publish=True)
            quality_bar.stamp(record, bar, **{k: v for k, v in (record.get("qualityBar") or {}).items() if k in ("before", "repaired")})
            log(f"   [bar] {quality_bar.summary_line(bar)}（Muse の記事は記録だけ）")
            w.finalize_facts(record, source_text)
            w.stamp_times(record, item, datetime.now(timezone.utc))
            # Muse の原稿のかんたん版は「ひとことで言うと」の要約だけになりやすく、記事ページでは要約の章を出さないため
            # 「かんたんに読む」が消えていた（2026-11-10）。本文だけを材料に作り直す（scripts/easy_version.py。
            # 数字の照合＋本文との事実確認に通ったときだけ使う。だめでも公開は止めない）
            import easy_version  # noqa: PLC0415

            log(f"   [muse] かんたん版: {easy_version.ensure(record, log=log)[:200]}")
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
            row = {"status": status, "reason": reason[:1200], "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
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
        if dup := duplicate_of(data, name):
            finish("rejected", f"重複: この7日の記事「{dup}」と同じ話題です。ledger.md を見て別の話題にしてください")
            rejected += 1
            continue
        if args.daily_cap and pacing.live_today(state) >= args.daily_cap:
            finish("waiting", f"今日の記事の本数（{args.daily_cap}本）がいっぱいなので、次の日に回します")
            continue
        unread: list[str] = []
        fetched = fetch_sources(data["sources"], skip_unreadable_first=data["genre"] == COMPARISON_GENRE, unread=unread)
        if not fetched:
            finish("rejected", "1件目の出典（公式ページ）を読めませんでした。URL が正しいか、ログインなしで開けるページかを確かめてください"
                   if data["genre"] != COMPARISON_GENRE else "出典（公式ページ）を1本も読めませんでした。URL が正しいか、ログインなしで開けるページかを確かめてください")
            rejected += 1
            continue
        status, out = build_article(path, data, fetched)
        if status == "reject" and unread:
            out = f"{out}\n読めなかった出典（ここにだけ書かれた事実は確かめられません。読める公式ページに替えるか、その記述を外してください）: " + " / ".join(unread[:5])
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
