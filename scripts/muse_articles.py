#!/usr/bin/env python3
"""Muse（Meta の AI の書き手）が書いた記事を、ふつうの記事と同じ門に通して公開する（2026-11-08 オーナー承認・台帳 A59）。

流れ（Muse には鍵を渡さない。Muse はオーナーの Mac のフォルダにファイルを置くだけ）:
  1. Mac: ~/Downloads/saisoku-articles/*.md → scripts/muse_articles_push.py が content/muse_inbox/ に入れて main に push（launchd で25分ごと）
  2. Actions（muse_inbox.yml。入稿の push ですぐ・30分ごとの予約でも。記事づくりの回とは別の列）: このスクリプトが content/muse_inbox/ を読む
     - 形の確かめ（scripts/muse_format.py）→ 重複（直近7日の記事と見出し・固有名詞が重なる／同じ原稿の出し直し。出典の URL が同じだけでは重複にしない）→ 今日の本数（段の上限 WEB_STAGE_TARGET の中に数える）
     - 公式の出典ページを取りに行き（報道は、主要な報道機関の記事だけを報道の出典として使う。W31 の Muse の道の例外・2026-11-13）、Muse の原稿を土台に、ふつうの記事と同じ型（リード・要点・かんたん版・
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
import subprocess
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
# 2026-11-13: 合格点（手続き90点）に少し届かない原稿は落とさず、校閲の指摘の文だけを直して確かめ直す（合格点は変えない）。
# 7日で22本が点数だけで落ち、13本は88点だった。しかも作り直しには「点数が足りない」としか伝わっていなかった（指摘の中身が渡っていなかった）
SCORE_REPAIR_MIN = 80  # これ以上で合格点に届かないときだけ直す（もっと低い原稿は作り直しの試行へ）
SCORE_REPAIR_ROUNDS = 2
KEEP_RESULTS = 300
# 2026-11-13: 入稿の順番は「急ぎ → 日付の新しい順」（order_inbox）。これまではファイル名の順で、前の日の原稿の出し直し10本のうしろに
# 今日の話題の原稿（消費税の法案・X の機能・NVIDIA の決算日）が並んでいた。1回が25分を超えるので、うしろの原稿は次の回まで待つことになる。
# 1本の原稿が使える時間は、1回の時間（--budget）の DRAFT_BUDGET_SHARE まで（うしろに原稿が待っているときだけ）。
# 超えたら手直し・作り直しをやめて次の回に回す（見送りにはしない）。MAX_DEFERS 回回した原稿は、次の回に時間の区切りなしで最後まで審査する
DRAFT_BUDGET_SHARE = 0.4
MAX_DEFERS = 2
DEFER_REASON = "この原稿に使える時間（1回の4割）を使い切りました。ほかの原稿を先に進めて、次の回にもう一度試します"
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

# 2026-11-13: 1件目の出典（PDF・JavaScript で描くページなど）が読めなくても、ほかに読めた公式の出典があれば、それだけで記事にする
#（7日で6本が、記事の中身でなく取得の失敗で落ちていた）。読めなかったページにしか無い事実は書かせない。事実確認・数字の門は読めた資料だけで見る
MUSE_UNREAD_NOTE = """

# 読めなかった出典（この原稿だけの決まり）
記者が挙げた出典のうち、次のページは読めませんでした。上の資料には入っていません。
{urls}
- 原稿の事実・数字・日付のうち、上の資料（読めた出典）で確かめられないものは書かない（削る）。読めなかったページを根拠にしない。
  題名・lede・highlights・threads_post も同じ。
- 削ったあとも、記事の中心の事実が上の資料で確かめられるなら記事にする（短くなってよい）。
  中心の事実が確かめられないなら is_relevant を false にし、skip_reason に「どの事実が確かめられなかったか」を書く。
- sources（出典の一覧）に、読めなかったページを並べない。
"""

# 2026-11-13 オーナー承認（台帳 W31 の Muse の道だけの例外）: 主要な報道機関（muse_format.PRESS_ALLOWED）の記事を、報道の出典として使う。
# 報道にしか無い事実は必ず報道として書かせ（press_problems が数字を機械で確かめる）、文は写させない（書き写しの門）
MUSE_PRESS_NOTE = """

# 報道機関の記事を資料に使うときの決まり（この原稿だけ。上の「報道を引いた所の書き方」に足す）
上の資料のうち「【報道: 〇〇】」と書いた欄（{names}）は、報道機関の記事です。公式の発表ではありません。
- 公式の資料（【報道】でない欄）で確かめられる事実は、公式の資料をもとに書く。公式の資料と報道が食い違うときは公式の資料を採る。
- 報道の欄にしか無い事実・数字は、その文に必ず報道機関の名前を入れて「{first}によると」「{first}が報じた」と書く。
  確定した事実として言い切らない。続く文も「〜という」「〜としている」と報道の内容として書く。
- title・seo_title・lede・description・highlights・easy_markdown・faq・today_actions・work_money・threads_post など、すべての欄で同じ。
- 報道の文を写さない。事実だけを自分の言葉で短くまとめる（1つの報道から使うのは要点だけ）。見出し・言い回し・構成をまねない。
  報道の文を「」で長く引用しない。
- 報道が伝える見通し・関係者の話・匿名の情報は「〜と報じている」と報道の内容として書き、サイソクの見方の根拠にしない。
- sources（出典の一覧）には、公式の資料だけを並べる。
"""
MUSE_PRESS_ONLY_NOTE = """
- この原稿には、読めた公式の資料がありません（報道だけ）。title・lede・threads_post には必ず報道機関の名前を入れる
 （例:「〜と{first}が報じた」「{first}によると〜」）。本文も、報道が伝えた内容として書き、公式に確認された事実のように書かない。
- 公式（会社・役所・本人）の発表やコメントが報道の中で紹介されているときは「{first}によると、〇〇は〜と発表した」と書く。
- 「まだ分からないこと」の章に、公式の発表がまだ確認できていないことを書く。
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


def index_status(record: dict) -> str:
    """公開のログに出す「検索に出すか・出さない理由」（scripts/indexnow.py の index_status_line。2026-11-13:
    注文した記事が気づかないまま noindex で出ないように、公開のたびに見えるようにする）"""
    import indexnow  # noqa: PLC0415

    return indexnow.index_status_line(record)


def file_id(name: str) -> str:
    return "muse-" + hashlib.sha1(muse_format.nfc(name).encode("utf-8")).hexdigest()[:10]


def host_slug(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    host = re.sub(r"^www\.", "", host)
    return re.sub(r"[^a-z0-9]+", "-", host).strip("-")[:40] or "official"


def muse_disclaimer(genre_slug: str = "", press: list[str] | None = None, press_only: bool = False) -> str:
    """press は使った報道機関の名前。press_only は公式の資料が無く、報道だけをもとにした記事（「公式発表をもとに」と名乗らない）"""
    names = "・".join(dict.fromkeys(press or []))
    if press_only and names:
        text = (f"本記事は報道（{names}）をもとに、AIの書き手（Muse）が下書きし、サイソクの仕組みで報道の内容との照合・編集をして掲載した速報です。"
                "公式の発表はまだ確認できていません。確認できしだい更新します。正確な情報は、元の報道と公式の発表をご確認ください。")
    else:
        text = ("本記事は公式発表をもとに、AIの書き手（Muse）が下書きし、サイソクの仕組みで公式ページとの事実確認・編集をして掲載したものです。"
                "制度・金額・期限は変わることがあります。手続きの前に、発表元の公式ページで最新の情報をご確認ください。")
        if names:
            text += f"一部は報道（{names}）が伝えた内容で、本文に報道と書いています。"
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
MAX_UNREAD_LISTED = 10


def fetch_sources(sources: list[dict], skip_unreadable_first: bool = False, unread: list[str] | None = None) -> list[dict]:
    """[{url, name, title, text, full_text, image, published, page}]。1件目（一番の出典）が読めなければ空。
    skip_unreadable_first: 1件目が読めなくても次に読めた出典を一番にする
    （2026-11-09: スマホと光回線の記事が、1件目の ahamo のページを読めなかっただけで落ちた。2026-11-13 から入稿の全ジャンルで使う）。
    PDF は feeds.fetch_article_text が文字を取り出す（pdftotext → pypdf → 読み取りサービス → API の順。scripts/pdf_text.py）。
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


def _source_head(s: dict) -> str:
    """出典の見出しの行。報道機関の記事（s["press"]）は、公式の資料と見分けが付くように書く"""
    if s.get("press"):
        return (f"【報道: {s['press']}】{s['url']}\n（報道機関の記事。公式の発表ではない。ここにしか無い事実は"
                f"「{s['press']}によると」と報道として書く。文を写さない）")
    return f"【{s.get('name') or s.get('title') or '公式'}】{s['url']}"


def source_text_of(fetched: list[dict], title: str = "", cap: int = MULTI_SOURCE_CAP) -> str:
    """生成・事実確認に渡す出典の本文。出典が2本以上なら、全部の出典が事実確認（quality.source_cap）に入るよう1本ごとに長さを割り当て、
    長いページは記事の題名・書き手のメモ（sources[].facts）の言葉と数字・料金の行を優先して抜き出す（source_links.excerpt）。
    書き手のメモは「確かめる手がかり」として添えるだけで、根拠は下のページの本文（メモにしかない事実は創作扱いのまま）"""
    if len(fetched) <= 1:
        return "\n\n".join(f"{_source_head(s)}\n{s['text']}" for s in fetched)
    import source_links  # noqa: PLC0415

    per = max(MIN_PER_SOURCE, cap // len(fetched) - 200)
    parts = []
    for s in fetched:
        body = s.get("full_text") or s["text"]
        note = re.sub(r"\s+", " ", str(s.get("facts") or "")).strip()
        if len(body) > per:
            body = source_links.excerpt(body, f"{title} {s.get('name') or ''} {note}", cap=per)
        head = _source_head(s)
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

    # 2026-11-13: 主要な報道機関（muse_format.PRESS_ALLOWED。s["press"] の付いた出典）は報道の出典として使う。
    # ほかの報道・ニュースブログは今までどおり出典にしない: ほかに出典があれば外して続け（落とす理由は嘘だけ）、それしか無ければ見送る
    sources = data.get("sources") or []
    other = [s for s in sources if s.get("url") and not s.get("press") and public_interest.is_press_url(s["url"])]
    keep = [s for s in sources if s not in other]
    if other and keep:
        data["sources"] = keep
        log(f"   [muse] 出典にできない報道のページを外しました: {' / '.join(s['url'][:60] for s in other[:3])}")
    else:
        for s in other:
            problems.append(f"報道機関のページは出典にできません（{s['url'][:80]}）。公式の発表か、主要な報道機関（FORMAT.md の一覧）の記事を出典にしてください")
    return data, problems


# ---- 報道機関の記事を出典に使った記事の確かめ（2026-11-13 オーナー承認・W31 の Muse の道だけの例外） ----
PRESS_WORD_RE = re.compile(r"報道|報じ")
PRESS_HEDGE_RE = re.compile(r"という|としている|としています|とされ|とのこと|と伝え|とみられ")
# 報道の文と、記号・空白を除いてこの字数以上つづけて同じ所がある文は「写し」とみなす。ふつうの出典の門（quality.copied_sentences は
# 文がまるごと同じで40字以上）より厳しく、文の一部でも見る（「NHKによると、」を頭に付けただけの写しを通さない）
PRESS_COPY_MIN = 30
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])|\n")


def press_copies(text: str, press_text: str, min_len: int = PRESS_COPY_MIN) -> list[str]:
    """報道の文と min_len 字以上つづけて同じ所がある文（記号・空白は無視）"""
    import quality  # noqa: PLC0415

    src = quality._norm(press_text)  # noqa: SLF001
    out = []
    if len(src) < min_len:
        return out
    for sentence in _SENTENCE_SPLIT_RE.split(text or ""):
        clean = quality._norm(re.sub(r"[#>*|`]", "", sentence))  # noqa: SLF001
        if any(clean[i:i + min_len] in src for i in range(0, max(len(clean) - min_len + 1, 0))):
            out.append(sentence.strip()[:50])
    return out


def press_sources(fetched: list[dict]) -> list[dict]:
    return [s for s in fetched if s.get("press")]


def press_names(fetched: list[dict]) -> list[str]:
    return list(dict.fromkeys(s["press"] for s in press_sources(fetched)))


def _press_named(text: str, names: list[str]) -> bool:
    """文に、どこの報道かが書いてあるか（報道機関の名前か、「報道」「報じた」）"""
    aliases = [a for n in names for a in muse_format.PRESS_ALIASES.get(n, (n,))]
    return any(a in text for a in aliases) or bool(PRESS_WORD_RE.search(text))


def _reader_fields(record: dict) -> list[tuple[str, str]]:
    """（欄の名前, 文）。読者が読むすべての欄（題名・リード・要点・本文・かんたん版・FAQ・今日やること・仕事とお金・SNS の文）"""
    out = [(k, str(record.get(k) or "")) for k in ("title", "seoTitle", "lede", "description", "summaryLine", "body", "easy",
                                                    "threadsPost", "threadsHook")]
    out += [("highlights", str(h)) for h in record.get("highlights") or []]
    out += [("faq", f"{r.get('q', '')}\n{r.get('a', '')}") for r in record.get("faq") or [] if isinstance(r, dict)]
    out += [("todayActions", str(a)) for a in record.get("todayActions") or []]
    out += [("workMoney", str(p)) for p in (record.get("workMoney") or {}).get("points") or []]
    return [(k, t) for k, t in out if t.strip()]


def press_problems(record: dict, fetched: list[dict]) -> list[str]:
    """報道機関の記事を出典に使った記事が、決まりどおりか（LLM なし）。問題の文のリスト（空なら合格）。
    1. 報道にしか無い数字（公式の資料に無く、報道の記事にある金額・割合・件数）のある文に、報道機関の名前か「報道」「報じた」がある
       （直前の文に名前があり、その文が「〜という」「〜としている」と続くのはよい。表・箇条書きの行は同じ段落に名前があればよい）
    2. 報道の文を写していない（記号・空白を除いて PRESS_COPY_MIN 字以上つづけて同じ所がある文）
    3. 公式の資料が無い記事（報道だけ）: 題名・リード・SNS の文に報道機関の名前があり、本文にも名前がある
    報道にしか無い「数字でない事実」は機械では見分けられない（指示文と、事実確認の門で見る）"""
    import calc_facts  # noqa: PLC0415

    press = press_sources(fetched)
    if not press:
        return []
    names = press_names(fetched)
    official = [s for s in fetched if not s.get("press")]
    press_text = "\n".join(s.get("full_text") or s.get("text") or "" for s in press)
    press_values = calc_facts.values(press_text)
    official_values = calc_facts.values("\n".join(s.get("full_text") or s.get("text") or "" for s in official))
    first = names[0]
    out: list[str] = []
    bare: list[str] = []
    for _field, text in _reader_fields(record):
        for block in re.split(r"\n\s*\n", text):
            prev = ""
            for unit in _SENTENCE_SPLIT_RE.split(block):
                unit = unit.strip()
                if not unit:
                    continue
                nums = [q for q in calc_facts.extract(unit) if calc_facts.checkable(q)
                        and calc_facts.supported(q, press_values) and not calc_facts.supported(q, official_values)]
                row = unit[:1] in ("|", "-", "*", "・")
                ok = (not nums or _press_named(unit, names) or (row and _press_named(block, names))
                      or (bool(prev) and _press_named(prev, names) and bool(PRESS_HEDGE_RE.search(unit))))
                if not ok and unit[:40] not in bare:
                    bare.append(unit[:40])
                prev = unit
    if bare:
        out.append(f"報道（{'・'.join(names)}）にしか無い数字を、報道と分かる形で書いていない（{'、'.join('「' + b + '」' for b in bare[:4])}）。"
                   f"その文に「{first}によると」「{first}が報じた」と入れ、確定した事実として言い切らない")
    copied = []
    for field, text in _reader_fields(record):
        if field in ("body", "easy", "lede", "description", "highlights", "threadsPost"):
            copied += press_copies(text, press_text)
    if copied:
        out.append(f"報道の文をそのまま写している（{len(copied)}文。例「{copied[0][:40]}」）。事実だけを自分の言葉で短くまとめる")
    if not official:
        for field, label in (("title", "題名"), ("lede", "リード"), ("threadsPost", "SNS の文（threads_post）")):
            text = str(record.get(field) or "")
            if text.strip() and not _press_named(text, names):
                out.append(f"公式の資料が無い記事（報道だけ）なのに、{label}に報道機関の名前が無い。「{first}によると」「{first}が報じた」と入れる")
        if not any(a in str(record.get("body") or "") for n in names for a in muse_format.PRESS_ALIASES.get(n, (n,))):
            out.append(f"本文に報道機関の名前（{first}）が無い。どこの報道かを書く")
    return out


PENDING_HEADING = "## まだ分からないこと"


def mark_press(record: dict, fetched: list[dict], now: datetime | None = None) -> None:
    """門を通った記事に、報道を出典に使った印を付ける（あとで公式の発表に差し替えられるように）。
    - pressSources: 使った報道の記事。記事末の「確かめた資料」の札は「報道」にする（「Museの出典」と出さない）
    - 公式の資料が無い記事: pressOnly・officialPending の印と、本文の「まだ分からないこと」に公式の発表が未確認であることを足す"""
    press = press_sources(fetched)
    if not press:
        return
    urls = {s["url"] for s in press}
    record["pressSources"] = [{"url": s["url"], "name": s["press"]} for s in press]
    for row in record.get("factSources") or []:
        if isinstance(row, dict) and row.get("url") in urls:
            row["label"] = "報道"
    if not record.get("pressOnly"):
        return
    day = (now or datetime.now(JST)).astimezone(JST)
    names = "・".join(press_names(fetched))
    line = f"この記事は{names}の報道をもとにしています。公式の発表は{day.month}月{day.day}日の時点で確認できていません。確認できしだい更新します。"
    body = str(record.get("body") or "").rstrip()
    if PENDING_HEADING in body:
        head, _, tail = body.partition(PENDING_HEADING)
        section, sep, rest = tail.partition("\n## ")
        body = f"{head}{PENDING_HEADING}{section.rstrip()}\n\n{line}\n{sep}{rest}" if sep else f"{head}{PENDING_HEADING}{section.rstrip()}\n\n{line}"
    else:
        body = f"{body}\n\n{PENDING_HEADING}\n\n{line}"
    record["body"] = body.rstrip() + "\n"


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


# 2026-11-13 オーナー「落とすのは嘘だけ」「とにかく数字」: 出典の URL が同じ、というだけでは重複にしない
#（7日で37本が、話題は別なのに国税庁などの同じページを引いただけで落ちていた。点検 audit_20261113）。
# 同じ出典を引く記事は、題名も似ているとき（同じ記事の出し直し）だけ止める。ふつうの重複（題名 0.5 以上）より低い境目にする。
# 37本の実績: 本当の出し直しは 0.25〜0.47（ハウス食品・電気代 v3・出産手当金・国民年金・マイナ保険証）、別の話題は 0.22 以下
SAME_SOURCE_JACCARD = 0.25
STEM_SUFFIX_RE = re.compile(r"(?:[-_ ]r\d*|[-_ ]?v\d+|[-_ ]\d{3,4})+$", re.I)


def topic_stem(name: str) -> tuple[str, str]:
    """ファイル名 →（日付, 題名の幹）。出し直しの印（-r・v2・v2-0038）を外して比べる。形が違えば ("", "")"""
    m = muse_format.NAME_RE.match(muse_format.nfc(name or ""))
    if not m:
        return "", ""
    return m.group(1), STEM_SUFFIX_RE.sub("", m.group(3)).strip().lower()


def _recent_articles(days: int) -> list[dict]:
    import dedupe  # noqa: PLC0415

    since = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for path in sorted(dedupe.ARTICLES_DIR.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        when = dedupe._article_time(row) if isinstance(row, dict) else None  # noqa: SLF001
        if when is None or when < since:
            continue
        row.setdefault("slug", path.stem)
        out.append(row)
    return out


def _article_urls(row: dict) -> set[str]:
    import dedupe  # noqa: PLC0415

    urls = [row.get("sourceUrl")] + [s.get("url") for s in row.get("museSources") or [] if isinstance(s, dict)]
    urls += [u.get("sourceUrl") for u in row.get("updates") or [] if isinstance(u, dict)]
    return {dedupe._norm_url(str(u)) for u in urls if u}  # noqa: SLF001


def resubmission_of(data: dict, name: str = "", articles: list[dict] | None = None) -> str | None:
    """同じ記事の出し直しか（この7日の記事と比べる）。
    1. 同じ日付・同じ題名の幹のファイル（v2・-r を外して同じ）から、もう記事が出ている
    2. 一番の出典が同じ記事で、題名も似ている（SAME_SOURCE_JACCARD 以上）
    出典が同じでも題名が別の話題なら None（別の疑問に答える記事として通す）"""
    import dedupe  # noqa: PLC0415

    rows = _recent_articles(DEDUPE_DAYS) if articles is None else articles
    day, stem = topic_stem(name)
    url = dedupe._norm_url(str((data.get("sources") or [{}])[0].get("url") or ""))  # noqa: SLF001
    grams = dedupe.bigrams(data.get("title") or "")
    for row in rows:
        slug = str(row.get("slug") or "")
        if stem and (day, stem) == topic_stem(str(row.get("museFile") or "")):
            return f"同じ原稿の出し直し（{row.get('museFile')}）: {slug[:40]}"
        if url and url in _article_urls(row):
            score = dedupe.jaccard(grams, dedupe.bigrams(str(row.get("title") or "")))
            if score >= SAME_SOURCE_JACCARD:
                return f"同じ出典で見出しも類似（{score:.2f}）: {slug[:40]}"
    return None


def duplicate_of(data: dict, name: str = "") -> str | None:
    import dedupe  # noqa: PLC0415
    import story  # noqa: PLC0415

    recent = dedupe.load_recent(DEDUPE_DAYS)
    if is_followup(data, name) or is_roundup(data, name):
        # 続報は同じ出典・同じ固有名詞が当たり前。見出しがほぼ同じ（同じ記事の出し直し）のときだけ重複にする
        grams = dedupe.bigrams(data["title"])
        for entry in recent.entries:
            if dedupe.jaccard(grams, entry["bigrams"]) >= dedupe.JACCARD_DUP:
                return f"見出しがほぼ同じ: {entry['label'][:40]}"
        return None
    # 出典の URL は渡さない（URL が同じだけでは重複にしない。取り下げた記事の出典も、Muse が正しく書き直すのは止めない）。
    # 見出しの類似・固有名詞の一致は今までどおり
    if hit := recent.find(data["title"], ""):
        return hit
    if hit := resubmission_of(data, name):
        return hit
    try:
        same = story.Recent(DEDUPE_DAYS).match(data["title"], "")
    except Exception:  # noqa: BLE001
        same = None
    return str(same[0] if isinstance(same, (tuple, list)) else same) if same else None


def inbox_commit_times() -> dict[str, int]:
    """入稿のファイル名 → いまの入稿がコミットされた時刻（秒）。git の履歴が手元にあるときだけ（1回の git log。無ければ空）。
    Actions の checkout は浅い（最新の1コミットだけ）ので、そこではどのファイルも同じ時刻になり、順番は日付で決まる"""
    try:
        out = subprocess.run(["git", "-c", "core.quotepath=false", "log", "--since=30.days.ago", "--diff-filter=A", "--name-only",
                              "--format=@%ct", "--", "content/muse_inbox"], cwd=ROOT, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    times: dict[str, int] = {}
    stamp = 0
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("@") and line[1:].isdigit():
            stamp = int(line[1:])
        elif line:
            times.setdefault(muse_format.nfc(Path(line).name), stamp)  # 新しい順に出るので、最初に見えたものがいまの入稿
    return times


def order_inbox(files: list[Path], results: dict | None = None, times: dict[str, int] | None = None) -> list[tuple[Path, str]]:
    """入稿を審査する順に並べる。[(ファイル, 理由)]。
    1. 急ぎ（genre が速報解説・「急ぎ: はい」の印）  2. 前の回に時間切れで回した原稿はその組のうしろ
    3. ファイル名の日付が新しい順（前の日の原稿の出し直しはうしろ）  4. 入稿（コミット）の新しい順  5. 名前の順"""
    items = (results or {}).get("items") or {}
    times = inbox_commit_times() if times is None else times
    rows = []
    for path in files:
        name = muse_format.nfc(path.name)
        named = muse_format.NAME_RE.match(name)
        date = int(named.group(1)) if named else 0
        try:
            data = muse_format.parse(path.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, muse_format.FormatError):
            data = {}
        genre = data.get("genre") or (named.group(2) if named else "")
        urgent = "急ぎの印" if muse_format.is_urgent(data) else (genre if genre in muse_format.URGENT_GENRES else "")
        deferred = int((items.get(name) or {}).get("deferred") or 0)
        why = f"急ぎ（{urgent}）" if urgent else f"日付 {date or 'なし'}"
        if deferred:
            why += f"・前の回から持ち越し{deferred}回"
        rows.append(((0 if urgent else 1, 1 if deferred else 0, -date, -int(times.get(name) or 0), name), path, why))
    rows.sort(key=lambda row: row[0])
    return [(path, why) for _, path, why in rows]


def order_line(queue: list[tuple[Path, str]]) -> str:
    """この回の順番と理由（Actions のログで確かめるための1行）"""
    return "[muse] 審査の順番（急ぎ → 日付の新しい順 → 入稿の新しい順）: " + " / ".join(
        f"{i}. {muse_format.nfc(path.name)[:48]}［{why}］" for i, (path, why) in enumerate(queue, 1))


def score_objections(verdict: dict) -> list[str]:
    """校閲（事実確認）が挙げた指摘。合格（70点以上）のとき quality.evaluate は problems を空にするので、fact から取る"""
    return [str(p).strip() for p in ((verdict.get("fact") or {}).get("problems") or []) if str(p).strip()]


def lift_score(record: dict, verdict: dict, need: int, source_text: str, kind: str, context,
               deadline: float | None = None) -> tuple[dict, dict]:
    """事実確認は通った（創作・矛盾なし）が、点数が Muse の合格点に少し届かない原稿を、校閲の指摘の文だけ直して確かめ直す。
    最大 SCORE_REPAIR_ROUNDS 回。直すのは quality.surgical_fix（指摘の文を資料どおりに直すか削る。書き足さない → 同じ門でもう一度事実確認）。
    返すのは、いちばん点の高かった（record, verdict）。合格点に届いたかは呼ぶ側が score で見る（合格点は下げない）"""
    import quality  # noqa: PLC0415

    best = (record, verdict)
    for round_no in range(1, SCORE_REPAIR_ROUNDS + 1):
        current, now = best
        score = now.get("score") or 0
        todo = score_objections(now)
        if not now.get("ok") or score >= need or score < SCORE_REPAIR_MIN or not todo:
            break
        if deadline and time.time() > deadline:
            log(f"   [muse] 点数の手直し{round_no}: この原稿に使える時間を超えたので、ここでやめます（次の回にもう一度）")
            break
        try:
            fixed, info = quality.surgical_fix(current, source_text, kind, todo, context)
        except Exception as error:  # noqa: BLE001 - 直す段が使えなくても、作り直しの試行は続ける
            log(f"   [muse] 点数の手直し{round_no}: 失敗（{str(error)[:80]}）")
            break
        if fixed is None:
            log(f"   [muse] 点数の手直し{round_no}: 直せず（{str(info)[:160]}）")
            break
        new_score = info.get("score") or 0
        log(f"   [muse] 点数の手直し{round_no}: {score} → {new_score} 点（必要 {need}）")
        if new_score <= score:
            break
        best = (fixed, info)
    return best


def build_article(path: Path, data: dict, fetched: list[dict], unread: list[str] | None = None,
                  deadline: float | None = None) -> tuple[str, dict | str]:
    """("ok", record) / ("reject", 理由) / ("error", 理由) / ("defer", 理由)。ふつうの記事と同じ型・同じ門。
    unread は読めなかった出典の URL（そこにしか無い事実は書かせない）。
    deadline（time.time() の秒）を過ぎたら、手直し・作り直しをやめて "defer"（見送りにせず、次の回にもう一度）"""
    import llm  # noqa: PLC0415
    import main as m  # noqa: PLC0415
    import quality  # noqa: PLC0415
    import web_articles as w  # noqa: PLC0415

    # 公式の出典を先に（報道は2番目以降）。読めた出典が報道だけなら、報道をもとにした速報として作る（press_only）
    fetched = sorted(fetched, key=lambda s: bool(s.get("press")))
    press = press_names(fetched)
    press_only = bool(fetched[0].get("press"))
    first = fetched[0]
    page = first["page"]
    if press_only:
        page = {**page, "image": None}  # 報道機関のページの写真は使わない
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
    if press_only:
        # 今までの「報道が出典」の形に合わせる（web_articles の secondary: 指示文・免責文・発信元の札「報道」。lib/news-outlets.ts は
        # channelSlug が radar-<報道機関のホスト> の記事を「出典（報道）」と表示する）
        host = re.sub(r"^www\.", "", (urlparse(first["url"]).hostname or "").lower())
        item.update({"source_name": first["press"], "source_slug": f"radar-{host}", "image": "", "secondary": True})
    source_text = source_text_of(fetched, data["title"])
    lane = LANE_BY_GENRE.get(data["genre"], "lifestyle")
    voice_key, voice_text = m.pick_voice()
    # 報道の出典は、束の中でも報道機関の名前で呼ぶ（記事がその数字を使うとき、名前を書いたかを数字の門が見る）
    extra = [{**s, "name": s["press"]} if s.get("press") else s for s in fetched[1:]]
    genre, system, prompt, schema, kind, context, bundle = w.compose_with_facts(item, source_text, lane, [], voice_text, page,
                                                                                    extra_sources=extra)
    prompt += MUSE_DRAFT_NOTE.format(title=data["title"], notes=data.get("notes") or "（なし）", body=data["body"])
    prompt += MUSE_DESK_NOTE  # 話題は編集部が決めた。落とすのは資料で確かめられないときだけ（2026-11-13）
    if press:
        prompt += MUSE_PRESS_NOTE.format(names="・".join(press), first=press[0])
        if press_only:
            prompt += MUSE_PRESS_ONLY_NOTE.format(first=press[0])
    if unread:
        prompt += MUSE_UNREAD_NOTE.format(urls="\n".join(f"- {u}" for u in unread[:MAX_UNREAD_LISTED]))
    # 出典の資料の日付・会議の回と、記事が書く出来事が合っているか（2026-11-10 の取り下げ。scripts/source_date.py）。
    # 下書きの時点で分かった食い違いは、最初の試行から直させる（公開前の門は下の試行の中で記事の JSON に当てる）
    today = datetime.now(JST).date()
    # もう始まった変更（実施済みの値上げなど）を「これから」と書いていないか（2026-11-12 の取り下げ7本。source_date.past_change）
    if early := source_date.check([data["title"], data["body"]], fetched, today) + source_date.past_change([data["title"], data["body"]], today):
        prompt += "\n\n【出典の日付の注意（必ず直す）】\n" + "\n".join(f"- {p}" for p in early)
        log(f"   [muse] 出典の日付の注意: {early[0][:160]}")
    need = pass_score(data["genre"])
    problems: list[str] = []
    cut_short = False  # 時間切れで点数の手直しを途中でやめた
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1 and deadline and time.time() > deadline:
            return "defer", DEFER_REASON
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
            "disclaimer": muse_disclaimer(record.get("genreSlug") or "", press, press_only),
            # 自動の書き直し（見出し・章の手直し・種類の型）の対象から外す（scripts/rewrite_types.py の refreshMode・section_polish の sectionsPolishedAt）
            "sectionsPolishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        if press_only:
            # 報道だけをもとにした速報の印。公式の発表が出たら officialPending を見て差し替える。
            # 2026-11-13 オーナー「とにかく数字」: 話題のレーンの報道の記事（scripts/trend_lane.py）と同じく検索に出す・サイトマップに入れる。
            # indexable の印は付けない（付けると公開前の門を素通りする）。ほかの Muse の記事と同じ門・同じ検索の基準（indexnow.noindex_reason）で見る
            record.update({"pressOnly": True, "officialPending": True})
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
        # 報道を出典に使った記事: 報道にしか無い数字が報道として書かれているか・報道の文を写していないか（LLM なし）
        if unattributed := press_problems(record, fetched):
            problems = unattributed
            log(f"   [muse] 試行{attempt}: {unattributed[0][:160]}")
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
        if verdict.get("ok") and SCORE_REPAIR_MIN <= score < need:
            # 合格点に少し届かない: 落とさず、校閲の指摘の文だけ直して確かめ直す（2026-11-13。合格点は変えない）
            record, verdict = lift_score(record, verdict, need, source_text, kind, context, deadline=deadline)
            score = verdict.get("score") or 0
            cut_short = bool(deadline and time.time() > deadline and score < need)
        log(f"   [muse] 試行{attempt}: {'合格' if verdict.get('ok') else '不合格'} score={score}（必要 {need}）"
            f" {' | '.join((verdict.get('problems') or [])[:3])[:300]}")
        if verdict.get("ok") and score >= need:
            record["qualityScore"] = score
            bar = quality_bar.check(record, verdict, at_publish=True)
            quality_bar.stamp(record, bar, **{k: v for k, v in (record.get("qualityBar") or {}).items() if k in ("before", "repaired")})
            log(f"   [bar] {quality_bar.summary_line(bar)}（Muse の記事は記録だけ）")
            # その場の手直し・点数の手直しで文が変わったあとも、報道の書き方の決まりを守っているか
            if unattributed := press_problems(record, fetched):
                problems = unattributed
                log(f"   [muse] 試行{attempt}: 手直しのあと {unattributed[0][:160]}")
                continue
            w.finalize_facts(record, source_text)
            mark_press(record, fetched)
            w.stamp_times(record, item, datetime.now(timezone.utc))
            # Muse の原稿のかんたん版は「ひとことで言うと」の要約だけになりやすく、記事ページでは要約の章を出さないため
            # 「かんたんに読む」が消えていた（2026-11-10）。本文だけを材料に作り直す（scripts/easy_version.py。
            # 数字の照合＋本文との事実確認に通ったときだけ使う。だめでも公開は止めない）
            import easy_version  # noqa: PLC0415

            log(f"   [muse] かんたん版: {easy_version.ensure(record, log=log)[:200]}")
            return "ok", record
        problems = list(verdict.get("problems") or [])
        if verdict.get("ok") and score < need:
            # 校閲の指摘の中身も渡す（作り直しの指示と、Muse に返す理由の両方に。点数だけでは何を直せばよいか分からない）
            problems = [f"公式ページとの事実確認の点数が {score} 点（Muse の記事は {need} 点以上）"] + score_objections(verdict) + problems
    if cut_short:
        return "defer", DEFER_REASON  # 手直しを時間切れでやめた原稿は、点数だけで見送りにしない
    return "reject", "品質の門で不合格: " + " / ".join(problems[:4])[:600]


def process(args) -> int:
    import main as m  # noqa: PLC0415
    import pacing  # noqa: PLC0415

    files = sorted(p for p in INBOX.glob("*.md")) if INBOX.exists() else []
    if not files:
        log("[muse] 入稿はありません")
        return 0
    results = load_results()
    # 急ぎ → 日付の新しい順（2026-11-13。ファイル名の順だと、前の日の原稿の出し直しが今日の話題の原稿より先になる）
    queue = order_inbox(files, results)
    log(order_line(queue))
    state = m.load_state()
    state.setdefault("processed_web", {})
    published = rejected = deferred = 0
    started = time.time()
    for index, (path, _why) in enumerate(queue):
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
        # 1本の原稿が使える時間（うしろに原稿が待っているときだけ。何度も回した原稿は区切りなしで最後まで）
        defers = int((results["items"].get(name) or {}).get("deferred") or 0)
        limited = index < len(queue) - 1 and defers < MAX_DEFERS
        extra = {"deadline": time.time() + args.budget * DRAFT_BUDGET_SHARE} if limited else {}
        unread: list[str] = []
        # 1件目が読めなくても、読めた公式の出典があれば進む（2026-11-13。読めなかったページにしか無い事実は build_article が書かせない）
        fetched = fetch_sources(data["sources"], skip_unreadable_first=True, unread=unread)
        if not fetched:
            finish("rejected", "出典（公式ページ）を1本も読めませんでした。URL が正しいか、ログインなしで開けるページかを確かめてください")
            rejected += 1
            continue
        status, out = build_article(path, data, fetched, unread=unread, **extra)
        if status == "reject" and unread:
            out = f"{out}\n読めなかった出典（ここにだけ書かれた事実は確かめられません。読める公式ページに替えるか、その記述を外してください）: " + " / ".join(unread[:5])
        if status == "error":
            log(f"   [muse] {out}（入稿はそのまま残します）")
            results["items"][name] = {"status": "waiting", "reason": str(out), "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                      "title": data["title"]}
            break
        if status == "defer":
            # 時間の持ち分を使い切った: 見送りにせず入稿に残し、うしろの原稿へ進む（次の回はその組のうしろに並ぶ）
            log(f"   [muse] {out}（入稿はそのまま残します・{defers + 1}回目）")
            results["items"][name] = {"status": "waiting", "reason": str(out), "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                      "title": data["title"], "deferred": defers + 1}
            save_results(results)
            deferred += 1
            continue
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
        log(f"   [muse] {index_status(record)}")
    m.save_state(state)
    save_results(results)
    left = len(list(INBOX.glob("*.md")))
    log(f"\n[muse] 公開 {published} 本 / 見送り {rejected} 本 / 次の回に回した {deferred} 本 / 入稿の残り {left} 本")
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
