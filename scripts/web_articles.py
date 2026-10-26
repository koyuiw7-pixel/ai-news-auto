#!/usr/bin/env python3
"""公式ブログ・プレスリリース（文章）から、動画記事と同じ形式の記事 JSON を作る。

動画解析よりずっと少ないトークンで済むので、無料枠のまま本数を増やせる。

  python3 scripts/web_articles.py --dry-run --max 5     # 候補を表示（API なし）
  python3 scripts/web_articles.py --max 10              # 最大10本生成（bulk モデル）
  python3 scripts/web_articles.py --max 5 --tier quality --days 2 --daily-cap 40
  python3 scripts/web_articles.py --max 0 --trends 2          # 話題のニュース（キュー）だけ2本
"""

from __future__ import annotations

import argparse
import copy
import re
import urllib.parse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feeds  # noqa: E402
import llm  # noqa: E402
import main as m  # noqa: E402
import trends  # noqa: E402
from genres import AI, GENRES, GENRES_BY_SLUG  # noqa: E402

RUN_TIME_BUDGET_SEC = 25 * 60
MAX_FAILURES = 2
MIN_TEXT_CHARS = 600
JST = timezone(timedelta(hours=9))

# 告知だけの記事（ウェビナー・イベント募集など）は、製品発表を伴わない限り記事にしない
EVENT_RE = re.compile(
    r"webinar|ウェビナー|セミナー|meetup|ミートアップ|hackathon|ハッカソン|register now|join us|"
    r"livestream|ライブ配信|イベント開催|開催のお知らせ|参加者募集|登壇|出展|展示会|"
    r"award|受賞|認証を取得|資金調達|採用|募集開始|キャンペーン|プレゼント",
    re.IGNORECASE,
)
NOTABLE_RE = re.compile(
    r"launch|introduc|announc|release|available|general availability|\bGA\b|new model|open[- ]source|"
    r"発表|提供開始|公開|リリース|一般提供|新機能|新モデル|オープンソース|搭載",
    re.IGNORECASE,
)

WEB_SOURCE_NOTE = """## 今回の取材対象（重要）
今回は動画ではなく、公式ブログ・ニュースルーム・プレスリリースなどの「文章」が一次資料です。
上の規則や章立てにある「動画」「映像」「音声」「スライド」は、すべて「元記事」と読み替えてください。
- 元記事の文をそのまま訳したり書き写したりしない。内容を理解したうえで、自分の言葉で要約・解説する。
  引用は短いフレーズ（1文の一部、30字程度まで）にとどめ、「」で括る。
- 本文中で必ず一度は出典（発信元の名前）に触れる（例：「〇〇の公式ブログによると」）。
- 元記事に書かれていない事実・数値・価格・日付・発言は作らない。
  一般的な背景知識で補う場合は「（編集部注）」と明記し、具体的な数値は書かない。
- 元記事で触れられていない項目は「元記事では言及なし」と短く書き、水増ししない。"""

WEB_PROMPT_TEMPLATE = """以下の一次情報（公式発表の文章）を読み解き、日本語のSEO記事を作成してください。

# 元記事
- 発信元: {source_name}
- タイトル: {title}
- 公開日: {published_date}
- URL: {url}
- 本文（抜粋・自動抽出。メニュー等の残骸が混ざることがあるので無視する）:
<<<
{text}
>>>

# 品質基準（商業メディアの水準）
- 本文は **2500〜5000字**。元記事の情報量に合わせ、薄い元記事なら短くてよい（水増し・推測で埋めない）。
- 各 `###` セクションには、元記事にある具体的な固有名詞・数値を含める。
- 見出しは内容を示す具体的なものにする（「概要」「まとめ」のような空疎な見出しは不可）。
- 表は「項目名 / 数値 / 出典（元記事 or 編集部注）」が分かる形にする。

# 出力する記事の構成（body_markdown に Markdown で記述）
次の見出し構成（`##` 見出し）を基本にする。「動画」は「元記事」と読み替え、元記事に材料がない章は1〜2文で「元記事では言及なし」と書く。

{outline}

# 各フィールドの要件
{field_notes}
- title: 32〜48文字。報道記事の見出しとして成立する体裁にする。
  主要SEOキーワードを前方に置き、**感嘆符・煽り語（衝撃／ヤバい／ついに／必見）は使わない**。
  元記事のタイトルの直訳にしない。
- seo_title: 検索結果に表示する短い題名。**全角24〜30文字**（英数字は半角0.5文字換算）。
  製品名・企業名・機能名を**先頭**に置き、何が分かる記事かを続ける。記号は「｜」「：」を最大1つまで。
- threads_post: Threadsに投稿する本文（全角80〜180字）。本文にURLは入れない。
  1行目：末尾の「Threads 紹介文の書き出し」から、この記事に合う型を1つ選んで書く（30字以内）。
  2行目：記事中でいちばん具体的な事実（数字・ビフォーアフター）。1行目と重複させない。
  3行目：何の発表か＋誰に関係があるか。
  専門用語を並べず、「誰の、どんな作業が、どう楽になるのか」をAIに詳しくない人にも伝わる言葉で言い換える。
  そのあとは「✅ 」で始まる要点2つ／短い感想1〜2文／意外な数字の補足 のどれかを選ぶ（毎回同じ形にしない）。
  最後は「記事で👇」か、短い問いかけで締める。
  禁止：記事にない事実・誇張・煽り語、ハッシュタグ、URL、✅と👇以外の絵文字。
- easy_markdown: 「かんたんに読む」版（全角700〜1300字）。body_markdown の内容をやさしく言い直したもの。
  見出しは次の4つを「## 」でこの順に使う：## ひとことで言うと / ## 何がすごいの？ / ## 自分に関係ある？ / ## 使ってみるには
  必ず「## ひとことで言うと」から始める。専門用語は使わない（使うなら直後に（＝〜のこと））。身近な例えを1つ以上入れる。
  body_markdown に無い事実・数字・価格は書かない。「使ってみるには」は verdict と矛盾させない。です・ます調。
- lede: 記事冒頭のリード文。150〜200字。結論を先に置き、発信元の名前を含める。
- description: 100〜130文字のメタディスクリプション。結論を含める。
- mentioned_tools: 記事中で言及した製品・サービス・企業の**正式名称**（3〜12個）。本文で触れたものだけ。
- slug_en: URL用の英小文字スラッグ。半角英数とハイフンのみ、3〜6単語、40文字以内。
- keywords: 検索されうる日本語キーワード 8〜12個。
- tags: 記事分類用のタグ 3〜6個。
- highlights: 「3秒でわかる要点」ちょうど3つ。各40〜60文字で、元記事にある数値や固有名詞を含める。
- timetable: 文章が元なので **必ず空配列 []** にする。
- verdict: 読者が「自分は今これを使えるか」を判断するための判定。本文の「料金・提供プラン」「日本から使う方法」と矛盾させない。
  元記事に根拠がない項目は推測せず unknown / 不明 / null にする。
  - status: available（一般提供中）/ limited（ウェイトリスト・一部ユーザー・地域限定・法人限定・段階展開）/
    soon（提供予定）/ demo（研究・技術デモ・事例紹介で、すぐ使える製品がない）
  - japan: ok / partial（英語のみ・API経由のみ等）/ no / unknown（元記事に記載なし）
  - price: 14字以内。例「無料」「無料枠あり」「月20ドル〜」「API従量課金」「法人向け」「不明」
  - free: 無料で試せるなら true、有料のみ false、不明なら null
  - audience: いちばん恩恵を受ける読者を2〜8字で
  - take: サイソクの判断。25〜55字の1文で、読者が次に何をすべきか。煽り語は禁止。
- is_relevant: 読者にとって実質的な情報価値のある発表・解説なら true。
  イベント・ウェビナーの告知だけ、採用・受賞・資格取得・キャンペーンのお知らせ、宣伝だけで中身のないもの、
  AI・テクノロジーとほぼ無関係なものは false。
{topic_guard}
- skip_reason: is_relevant が false のときだけ理由を書く。
- genre: 記事の内容に最もふさわしいジャンルを次から1つ選ぶ（迷ったら ai）。
{genre_choices}

body_markdown 内では h1 (`#`) を使わないでください（タイトルは別途表示されます）。
"""


# --------------------------------------------------------------------------- #
# 話題のニュース（Googleトレンド → state/trend_queue.json）
# --------------------------------------------------------------------------- #

TREND_MIN_SOURCE_CHARS = 400
TREND_MIN_SOURCES = 2
TREND_MAX_SOURCES = 3
TREND_SOURCE_CAP = 5000  # 1報道あたりの文字数上限（プロンプトを無料枠の範囲に収める）

# 「使えるか」判定は話題によっては当てはまらないので null を許す
TREND_SCHEMA = copy.deepcopy(m.ARTICLE_SCHEMA)
TREND_SCHEMA["properties"]["verdict"]["nullable"] = True
TREND_SCHEMA["required"] = [k for k in TREND_SCHEMA["required"] if k != "verdict"]

TREND_SOURCE_NOTE = """## 今回の取材対象（重要）
今回は動画ではなく、日本でいま話題になっているキーワードと、それを報じた複数の報道記事が資料です。
上の規則にある「動画」「映像」「音声」「スライド」は、すべて「関連報道」と読み替えてください。
- 報道の文をそのまま書き写さない。内容を理解したうえで自分の言葉で要約・解説する。
  引用は短いフレーズ（30字程度まで）にとどめ、「」で括る。
- 事実を書くたびに「〇〇（媒体名）によると」のように出典の媒体名を示す。複数の報道を突き合わせて書く。
- 報道に書かれていない事実・数値・日付・発言は作らない。

## トレンド記事の編集ルール（必ず守る）
{rules}"""

TREND_OUTLINE = """## ひとことで言うと
3〜4文で、何が話題になっていて、読者に何が関係するのかを専門用語なしで説明する。

## なぜいま話題なのか
きっかけ（発表・発売・料金改定・障害・制度変更など）を、報道に書かれた事実だけで説明する。

## 報道で分かっていること
各報道の内容を `###` 小見出しで整理し、媒体名を明示する。報道間で食い違う点はその旨を書く。

## 読者にとって何が変わるのか
お金・手間・使い方・注意点など、生活や仕事への具体的な影響。

## 使えるか・申し込めるか
話題がサービス・製品・制度など読者が実際に使う/申し込むものの場合だけ書く。当てはまらない話題ではこの章を省く。

## まだ分かっていないこと・注意点
報道で明らかになっていない点を「現時点では発表されていない」と明記する。

## まとめ
読者が次に取るべき行動を3行程度で。"""

TREND_PROMPT_TEMPLATE = """日本でいま話題になっているキーワードについて、関連報道を読み解き、日本語のSEO記事を作成してください。

# 話題
- キーワード: {keyword}
- 話題の度合い: {summary}
- 想定ジャンル: {genre_name}

# 関連報道（本文は自動抽出。メニュー等の残骸は無視する）
{sources}

# 品質基準
- 本文は **2000〜4500字**。報道の情報量に合わせ、水増し・推測で埋めない。
- 見出しは内容を示す具体的なものにする。

# 出力する記事の構成（body_markdown に Markdown で記述）
{outline}

# 各フィールドの要件
- title: 32〜48文字。「何が起きたか」が分かる平叙文。感嘆符・煽り語（衝撃／ヤバい／終了／知らないと損）は使わない。
- seo_title: 全角24〜30文字。検索されるキーワードを先頭に置く。記号は「｜」「：」を最大1つまで。
- threads_post: Threadsに投稿する本文（全角80〜180字）。URL・ハッシュタグは入れない。
  1行目：末尾の「Threads 紹介文の書き出し」から型を1つ選んで書く（30字以内）。
  2行目：報道にあるいちばん具体的な事実。3行目：誰に関係があるか。
  そのあとは「✅ 」で始まる要点2つ／短い感想／数字の補足 のどれか。最後は「記事で👇」か短い問いかけ。
  禁止：報道にない事実・誇張・煽り語、個人への憶測、✅と👇以外の絵文字。
- easy_markdown: 「かんたんに読む」版（全角700〜1300字）。必ず「## ひとことで言うと」から始め、
  ## ひとことで言うと / ## 何がすごいの？ / ## 自分に関係ある？ / ## 使ってみるには の4見出しをこの順に使う。
  話題が「使う」ものでない場合、「使ってみるには」では読者が取れる行動（公式情報の確認など）を書く。
  専門用語は使わない。body_markdown に無い事実は書かない。です・ます調。
- lede: 150〜200字。なぜ話題か＋結論を先に。
- description: 100〜130文字。
- mentioned_tools: 記事中で言及した製品・サービス・企業・制度の正式名称（0〜12個）。
- slug_en: 英小文字とハイフン、3〜6単語、40文字以内。
- keywords: 8〜12個。tags: 3〜6個。
- highlights: ちょうど3つ、各40〜60文字。報道にある数値や固有名詞を含める。
- timetable: **必ず空配列 []**。
- verdict: 話題がサービス・製品・制度など読者が使う/申し込むものの場合だけ埋める（基準: status available/limited/soon/demo、
  japan ok/partial/no/unknown、price 14字以内、free true/false/null、audience 2〜8字、take 25〜55字）。
  当てはまらない話題（相場の動き・業界ニュースなど）では **null** にする。
- is_relevant: サイトの軸（テクノロジー・お金・住まい）について読者に実質的な情報があれば true。
  事件・事故・災害・政治・芸能・スポーツが中心の話題、報道が薄く事実が確認できない話題は false。
- skip_reason: is_relevant が false のときだけ。
- genre: 次から1つ（想定ジャンルが合っていればそれを使う）。
{genre_choices}

body_markdown 内では h1 (`#`) を使わないでください。
"""


def fetch_trend_sources(item: dict) -> list[dict]:
    """news.google.com 以外の報道 URL から本文を取り、400字以上取れたものを最大3本返す。"""
    got = []
    for source in item.get("sources") or []:
        if len(got) >= TREND_MAX_SOURCES:
            break
        url = source.get("url") or ""
        if not url or urllib.parse.urlsplit(url).netloc.endswith("news.google.com"):
            continue
        try:
            page = feeds.fetch_article_text(url)
        except Exception as error:  # noqa: BLE001
            log(f"   [warn] 報道の取得に失敗: {source.get('source')}（{str(error)[:60]}）")
            continue
        if len(page["text"]) < TREND_MIN_SOURCE_CHARS:
            continue
        got.append({**source, "text": page["text"][:TREND_SOURCE_CAP], "image": page.get("image")})
    return got


def trend_source_name(fetched: list[dict]) -> str:
    names = list(dict.fromkeys(s.get("source") for s in fetched if s.get("source")))
    if not names:
        return "話題のニュース"
    return "・".join(names[:2]) + (" ほか" if len(names) > 2 else "")


def build_trend_prompt(item: dict, fetched: list[dict], genre) -> str:
    blocks = []
    for n, s in enumerate(fetched, start=1):
        blocks.append(
            f"## 報道{n}: {s.get('source') or '不明'}「{s.get('title', '')}」（{s.get('published', '')}）\n"
            f"URL: {s['url']}\n<<<\n{s['text']}\n>>>"
        )
    prompt = TREND_PROMPT_TEMPLATE.format(
        keyword=item["title"],
        summary=item.get("summary", ""),
        genre_name=genre.name,
        sources="\n\n".join(blocks),
        outline=TREND_OUTLINE,
        genre_choices="\n".join(f"  - {g.slug}: {g.name}" for g in GENRES),
    )
    return prompt + "\n\n" + m.threads_hooks.prompt_block()


def build_trend_record(item: dict, fetched: list[dict], data: dict, model_name: str, voice_key: str) -> dict:
    genre = GENRES_BY_SLUG.get(item.get("genre") or "", AI)
    pseudo = {
        "id": item["id"],
        "url": fetched[0]["url"],
        "title": item["title"],
        "source_name": trend_source_name(fetched),
        "source_slug": "trends",
        "published_at": item["published_at"],
    }
    image = next((s["image"] for s in fetched if s.get("image")), "")
    record = build_web_record(pseudo, {**data, "genre": genre.slug}, {"image": image}, model_name, voice_key)
    record.update(
        {
            "channel": "話題のニュース",
            "channelSlug": "trends",
            "disclaimer": web_disclaimer(genre).replace("公式発表の文章", "複数の報道"),
            "trendKeyword": item["title"],
            "sources": [{"title": s.get("title", ""), "url": s["url"], "source": s.get("source", "")} for s in fetched],
        }
    )
    return record


def log(message: str) -> None:
    print(message, flush=True)


def build_prompt(item: dict, text: str) -> str:
    genre = AI
    prompt = WEB_PROMPT_TEMPLATE.format(
        source_name=item["source_name"],
        title=item["title"],
        published_date=item["published_at"].astimezone(JST).strftime("%Y-%m-%d"),
        url=item["url"],
        text=text,
        outline=genre.outline,
        field_notes=genre.field_notes,
        topic_guard=f"  **このジャンルの対象範囲**: {genre.topic_guard}" if genre.topic_guard else "",
        genre_choices="\n".join(f"  - {g.slug}: {g.name}（{g.description[:48]}…）" for g in GENRES),
    )
    return prompt + "\n\n" + m.threads_hooks.prompt_block()


def prefilter(item: dict) -> str | None:
    """API を呼ぶ前の安い足切り。除外理由（文字列）か None"""
    title = item["title"]
    if EVENT_RE.search(title) and not NOTABLE_RE.search(title):
        return "告知・お知らせ系"
    return None


def web_disclaimer(genre) -> str:
    text = genre.disclaimer.replace("元動画の映像・音声をAIが解析して", "公式発表の文章をもとにAIが要約・解説して")
    if text == genre.disclaimer:
        text = "本記事は公式発表の文章をもとにAIが要約・解説して自動生成したものです。" + text
    return text


def build_web_record(item: dict, data: dict, page: dict, model_name: str, voice_key: str) -> dict:
    resolved = GENRES_BY_SLUG.get(str(data.get("genre", "")).strip(), AI)
    thumbnail = page.get("image") or item.get("image") or ""
    record = {
        "slug": m.unique_slug(m.slugify(data.get("slug_en", "")), item["id"][:8]),
        "sourceType": "web",
        "sourceUrl": item["url"],
        "sourceName": item["source_name"],
        "title": str(data["title"]).strip(),
        "seoTitle": str(data.get("seo_title", "")).strip(),
        "threadsPost": m.normalize_body(str(data.get("threads_post", ""))).strip(),
        "threadsHook": m.threads_hooks.clean_hook(data.get("threads_hook")),
        "writingVoice": voice_key,
        "lede": m.normalize_body(data.get("lede", "")),
        "description": str(data["description"]).strip(),
        "keywords": m.clean_list(data.get("keywords"), 14),
        "tags": m.clean_list(data.get("tags"), 8),
        "highlights": m.clean_list(data.get("highlights"), 3),
        "timetable": [],
        "verdict": m.clean_verdict(data.get("verdict")),
        "body": m.normalize_body(data["body_markdown"]),
        "easy": m.normalize_body(str(data.get("easy_markdown", ""))),
        "channel": item["source_name"],
        "channelId": "",
        "channelSlug": item["source_slug"],
        "genre": resolved.name,
        "genreSlug": resolved.slug,
        "disclaimer": web_disclaimer(resolved),
        "videoId": "",
        "videoUrl": "",
        "videoTitle": item["title"],
        "publishedAt": item["published_at"].astimezone(timezone.utc).isoformat(),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "thumbnail": thumbnail,
        "model": model_name,
        "affiliates": [],
    }
    if not record["body"] or len(record["body"]) < 800:
        raise ValueError(f"本文が短すぎます（{len(record['body'])}字）")
    affiliates = m.match_affiliates(record, data.get("mentioned_tools") or [])
    if affiliates:
        record["affiliates"] = affiliates
        record["body"] = m.linkify_first_mention(record["body"], affiliates)
        log(f"   [aff] {len(affiliates)}件: {', '.join(a['name'] for a in affiliates)}")
    return record


def generated_today(state: dict) -> int:
    today = datetime.now(JST).date()
    count = 0
    for value in (state.get("processed_web") or {}).values():
        if isinstance(value, dict) and value.get("slug"):
            try:
                if datetime.fromisoformat(value["at"]).astimezone(JST).date() == today:
                    count += 1
            except (KeyError, ValueError):
                continue
    return count


def mark(state: dict, item: dict, **extra) -> None:
    state["processed_web"][item["id"]] = {
        "url": item["url"],
        "at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    state["failed_web"].pop(item["id"], None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=5, help="この実行で生成する最大記事数")
    parser.add_argument("--days", type=int, default=3, help="何日前までの記事を対象にするか")
    parser.add_argument("--dry-run", action="store_true", help="API を呼ばず候補一覧のみ表示")
    parser.add_argument("--daily-cap", type=int, default=0, help="今日（JST）の生成数がこれ以上なら何もしない（0=無制限）")
    parser.add_argument("--tier", choices=["bulk", "quality"], default="bulk")
    parser.add_argument("--source", action="append", help="対象フィード slug（複数可。scripts/feeds.py 参照）")
    parser.add_argument("--trends", type=int, default=0, help="話題のニュース（state/trend_queue.json）から生成する最大本数")
    args = parser.parse_args()

    llm._load_env_local()
    state = m.load_state()
    state.setdefault("processed_web", {})
    state.setdefault("failed_web", {})

    done_today = generated_today(state)
    remaining = (args.daily_cap - done_today) if args.daily_cap else 10**6
    if remaining <= 0:
        log(f"[info] 今日はすでに {done_today} 本生成済み（上限 {args.daily_cap}）")
        return 0
    trend_limit = min(args.trends, remaining)
    log(f"[info] 今日の生成済み {done_today} 本 / 上限 {args.daily_cap or 'なし'}")

    # --- 話題のニュース ---
    queue = []
    if trend_limit > 0:
        queue = [
            q for q in trends.load_queue()
            if q["id"] not in state["processed_web"] and state["failed_web"].get(q["id"], 0) < MAX_FAILURES
        ]
        queue.sort(key=lambda q: q.get("traffic", 0), reverse=True)
        log(f"[info] 話題キュー {len(queue)} 件 / 上限 {trend_limit} 本")

    # --- 公式フィード ---
    items = []
    if args.max > 0:
        selected = [f for f in feeds.FEEDS if not args.source or f["slug"] in args.source]
        items = feeds.collect(args.days, state, selected)
        items = [i for i in items if state["failed_web"].get(i["id"], 0) < MAX_FAILURES]
        log(f"[info] フィード候補 {len(items)} 件 / 上限 {min(args.max, remaining)} 本")

    if args.dry_run:
        for q in queue[: max(trend_limit * 3, 5)]:
            fetched = fetch_trend_sources(q)
            ok = len(fetched) >= TREND_MIN_SOURCES
            log(
                f"  - [trend/{q.get('genre')}] {q['title']}（traffic {q.get('traffic', 0):,}）"
                f" 本文の取れた報道 {len(fetched)} 本 → {'対象' if ok else '除外'}"
                f"  {trend_source_name(fetched) if fetched else ''}"
            )
        shown = 0
        for item in items:
            reason = prefilter(item)
            flag = f"除外: {reason}" if reason else "対象"
            log(f"  - [{item['source_slug']}] {item['published_at'].astimezone(JST):%m-%d %H:%M} {item['title'][:70]}  ({flag})")
            shown += 0 if reason else 1
            if shown >= min(args.max, remaining) * 3:
                break
        log("[dry-run] API 呼び出しはスキップしました")
        return 0

    created_feed = created_trend = 0
    used_queue_ids: set[str] = set()
    run_started = time.time()

    def time_up() -> bool:
        if time.time() - run_started > RUN_TIME_BUDGET_SEC:
            log("[info] 時間の上限に達したため、残りは次回に回します")
            return True
        return False

    def generate(system: str, prompt: str, schema: dict, item_id: str):
        try:
            return llm.generate_json(system, prompt, schema, temperature=0.6, max_output_tokens=32768, tier=args.tier)
        except Exception as error:  # noqa: BLE001
            log(f"   [NG] {str(error)[:200]}")
            state["failed_web"][item_id] = state["failed_web"].get(item_id, 0) + 1
            return None, None

    try:
        # 話題は鮮度が命なので先に処理する
        for q in queue:
            if created_trend >= trend_limit or created_feed + created_trend >= remaining or time_up():
                break
            if llm.all_exhausted(args.tier):
                break
            log(f"\n[trend] {q['title']}（{q.get('genre')} / traffic {q.get('traffic', 0):,}）")
            fetched = fetch_trend_sources(q)
            if len(fetched) < TREND_MIN_SOURCES:
                log(f"   [skip] 本文の取れた報道が {len(fetched)} 本")
                mark(state, q, skipped=True, reason=f"trend sources {len(fetched)}")
                used_queue_ids.add(q["id"])
                continue
            genre = GENRES_BY_SLUG.get(q.get("genre") or "", AI)
            voice_key, voice_text = m.pick_voice()
            system = (
                f"{m.SYSTEM_INSTRUCTION_BASE}\n\n{genre.persona}\n\n"
                f"{TREND_SOURCE_NOTE.format(rules=trends.EDITORIAL_RULES)}\n\n## 今回の語り口\n{voice_text}"
            )
            started = time.time()
            data, model_name = generate(system, build_trend_prompt(q, fetched, genre), TREND_SCHEMA, q["id"])
            if data is None:
                if state["failed_web"].get(q["id"], 0) >= MAX_FAILURES:
                    used_queue_ids.add(q["id"])
                continue
            used_queue_ids.add(q["id"])
            if not data.get("is_relevant", True):
                reason = data.get("skip_reason") or "記事化の価値なしと判定"
                log(f"   [skip] {reason}（{model_name}）")
                mark(state, q, skipped=True, reason=str(reason)[:200], model=model_name)
                continue
            try:
                record = build_trend_record(q, fetched, data, model_name, voice_key)
            except (KeyError, TypeError, ValueError) as error:
                log(f"   [NG] レスポンスの形式が不正: {error}")
                state["failed_web"][q["id"]] = state["failed_web"].get(q["id"], 0) + 1
                continue
            path = m.write_article(record)
            mark(state, q, slug=record["slug"], model=model_name, kind="trend")
            created_trend += 1
            log(f"   [OK] {path.relative_to(m.ROOT)} ({len(record['body'])}字 / {model_name} / {time.time() - started:.0f}s)")

        for index, item in enumerate(items, start=1):
            if created_feed >= args.max or created_feed + created_trend >= remaining or time_up():
                break
            if llm.all_exhausted(args.tier):
                log("[info] すべてのモデルが無料枠の上限に達したため終了します")
                break
            reason = prefilter(item)
            if reason:
                mark(state, item, skipped=True, reason=f"prefilter: {reason}")
                continue

            log(f"\n[{index}/{len(items)}] {item['source_name']}: {item['title']}")
            try:
                page = feeds.fetch_article_text(item["url"])
            except Exception as error:  # noqa: BLE001
                log(f"   [warn] 本文の取得に失敗（{str(error)[:80]}）。フィードの本文を使います")
                page = {"text": "", "image": None}
            text = max([page.get("text") or "", item.get("content") or ""], key=len)
            if len(text) < MIN_TEXT_CHARS:
                log(f"   [skip] 本文が短い（{len(text)}字）")
                mark(state, item, skipped=True, reason=f"short text {len(text)}")
                continue

            voice_key, voice_text = m.pick_voice()
            system = f"{m.SYSTEM_INSTRUCTION_BASE}\n\n{AI.persona}\n\n{WEB_SOURCE_NOTE}\n\n## 今回の語り口\n{voice_text}"
            started = time.time()
            data, model_name = generate(system, build_prompt(item, text), m.ARTICLE_SCHEMA, item["id"])
            if data is None:
                continue

            if not data.get("is_relevant", True):
                reason = data.get("skip_reason") or "記事化の価値なしと判定"
                log(f"   [skip] {reason}（{model_name}）")
                mark(state, item, skipped=True, reason=str(reason)[:200], model=model_name)
                continue

            try:
                record = build_web_record(item, data, page, model_name, voice_key)
            except (KeyError, TypeError, ValueError) as error:
                log(f"   [NG] レスポンスの形式が不正: {error}")
                state["failed_web"][item["id"]] = state["failed_web"].get(item["id"], 0) + 1
                continue

            path = m.write_article(record)
            mark(state, item, slug=record["slug"], model=model_name)
            created_feed += 1
            log(f"   [OK] {path.relative_to(m.ROOT)} ({len(record['body'])}字 / {model_name} / {time.time() - started:.0f}s)")
    finally:
        m.save_state(state)
        trends.remove_from_queue(used_queue_ids)

    log(
        f"\n[done] 新規記事 {created_feed + created_trend} 本（フィード {created_feed} / 話題 {created_trend}）"
        f" / 今日の使用回数 {llm.usage_today()}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
