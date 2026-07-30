#!/usr/bin/env python3
"""YouTube 公式チャンネルの新着動画を Gemini 2.5 Flash でマルチモーダル解析し、
日本語 SEO 記事（JSON）を content/articles/ に自動生成するパイプライン。

  python3 scripts/main.py                # 通常実行（新着を最大 3 本処理）
  python3 scripts/main.py --max 1        # 1 本だけ
  python3 scripts/main.py --dry-run      # 対象を表示するだけ（API を呼ばない）
  python3 scripts/main.py --sample       # ダミー記事を 1 本生成（表示確認用）
  python3 scripts/main.py --video URL    # 特定の動画を強制処理
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from channels import CHANNELS, Channel  # noqa: E402

# --------------------------------------------------------------------------- #
# 設定
# --------------------------------------------------------------------------- #

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
STATE_PATH = ROOT / "content" / "state.json"

# 使用モデル。GEMINI_MODEL で上書き可。
# 先頭から順に試し、「そのモデルは存在しない」系のエラーなら次の候補へ自動フォールバックする。
# （gemini-2.5-flash は 2026-07 に generativelanguage 側で提供終了済みのため使用しない）
MODEL_CANDIDATES = [
    m
    for m in [
        os.environ.get("GEMINI_MODEL"),
        "gemini-3.5-flash",  # GA 安定版
        "gemini-3.6-flash",  # より新しい高性能版
        "gemini-flash-latest",  # 最終手段: 常に最新へ張り替わるエイリアス
    ]
    if m
]
MODEL = MODEL_CANDIDATES[0]
DEFAULT_MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES_PER_RUN", "3"))
DEFAULT_LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "10"))
MAX_ATTEMPTS_PER_VIDEO = 2  # これを超えて失敗した動画は諦める
REQUEST_RETRIES = 3

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"


def log(message: str) -> None:
    print(message, flush=True)


# --------------------------------------------------------------------------- #
# 状態管理（処理済み動画IDの記録）
# --------------------------------------------------------------------------- #


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text("utf-8"))
        except json.JSONDecodeError:
            log("[warn] state.json が壊れていたので初期化します")
    return {"processed": {}, "failed": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# RSS 取得
# --------------------------------------------------------------------------- #


def fetch(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def url_exists(url: str) -> bool:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300
    except Exception:  # noqa: BLE001 - 到達不能ならフォールバックすればよい
        return False


def parse_feed(channel: Channel) -> list[dict]:
    """RSS を取得して動画エントリのリストを返す。失敗しても例外は投げない。"""
    try:
        raw = fetch(channel.feed_url)
    except Exception as error:  # noqa: BLE001
        log(f"[warn] RSS 取得失敗 {channel.name}: {error}")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        log(f"[warn] RSS 解析失敗 {channel.name}: {error}")
        return []

    entries = []
    for entry in root.findall(f"{ATOM}entry"):
        video_id = entry.findtext(f"{YT}videoId")
        title = entry.findtext(f"{ATOM}title")
        published = entry.findtext(f"{ATOM}published")
        if not (video_id and title and published):
            continue

        group = entry.find(f"{MEDIA}group")
        summary = group.findtext(f"{MEDIA}description") if group is not None else ""

        entries.append(
            {
                "video_id": video_id,
                "title": title.strip(),
                "published": published,
                "summary": (summary or "").strip()[:1500],
                "channel": channel,
            }
        )
    return entries


def collect_candidates(
    channels: list[Channel], lookback_days: int, state: dict
) -> list[dict]:
    threshold = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    processed = state.get("processed", {})
    failed = state.get("failed", {})

    candidates = []
    for channel in channels:
        entries = parse_feed(channel)
        log(f"[feed] {channel.name}: {len(entries)} 件")
        for entry in entries:
            if entry["video_id"] in processed:
                continue
            if failed.get(entry["video_id"], 0) >= MAX_ATTEMPTS_PER_VIDEO:
                continue
            try:
                published_at = datetime.fromisoformat(entry["published"])
            except ValueError:
                continue
            if published_at < threshold:
                continue
            entry["published_at"] = published_at
            candidates.append(entry)

    # 新しい順
    candidates.sort(key=lambda e: e["published_at"], reverse=True)
    return candidates


# --------------------------------------------------------------------------- #
# Gemini による記事生成
# --------------------------------------------------------------------------- #

SYSTEM_INSTRUCTION = """あなたは日本のAI専門メディアのトップ編集者兼SEOスペシャリストです。
海外AI企業の公式発表動画を視聴し、日本のビジネスパーソン・エンジニア向けに
「この記事さえ読めば動画を見なくても内容が完全に分かる」水準の解説記事を執筆します。

厳守事項:
- 動画の映像（スライド・デモ画面・UI・グラフ）と音声の両方を根拠にすること。
- 動画内で確認できない事実を捏造しないこと。推測を書く場合は「編集部推測」と明示すること。
- 数値・価格・モデル名・機能名は動画で提示されたものを正確に転記すること。
- 出力はすべて自然な日本語（固有名詞・製品名は原語のままでよい）。
- 誇張した煽り表現は使わず、事実ベースで具体的に書くこと。"""

PROMPT_TEMPLATE = """以下のYouTube動画を「映像」と「音声」の両方から徹底的に解析し、日本語のSEO記事を作成してください。

# 対象動画
- チャンネル: {channel_name}
- 動画タイトル: {video_title}
- 公開日: {published_date}
- URL: {video_url}
- 概要欄（参考。矛盾する場合は動画本編を優先）:
{video_summary}

# 出力する記事の構成（body_markdown に Markdown で記述）
必ず以下の見出し構成（`##` 見出し）を守り、各セクションを具体的に埋めてください。

## この発表を一言でいうと
200〜300字で、何が発表され、なぜ重要なのかを要約。

## 発表された機能・アップデートの全容
動画内のスライド・デモ画面を根拠に、目玉機能を1つずつ `###` 小見出しで詳細解説。
スライドに書かれていた文言・数値・ベンチマークスコア・図の内容を具体的に言語化すること。
デモがある場合は「画面上で何がどう動いたか」を描写すること。最低3つ、可能なら5つ以上。

## 性能・ベンチマーク
動画で示された評価指標、比較対象、スコアを表（Markdown table）で整理。
提示がない場合は「動画内で数値の提示はなし」と明記。

## 競合サービスとの比較
今回の発表内容を、競合（OpenAI / Anthropic / Google / Meta / Microsoft など該当するもの）の
同等機能と比較した表を作成し、どこが優位でどこが弱いかを論じる。
競合側の情報はあなたの知識ベースで補ってよいが、その旨を明示すること。

## 料金・提供プラン
価格、無料枠、APIの従量課金、提供開始時期を、動画で提示された範囲で整理。
提示がなければ「動画内では価格の言及なし」と明記。

## 日本から使う方法
日本のユーザーが今日から試すための具体的な手順（アクセス先、必要なアカウント、
日本語対応の有無、リージョン制限、注意点）を箇条書きで。

## 誰にどう効くのか
エンジニア / 企画・マーケ / 経営層 の3つの立場別に、実務インパクトを解説。

## まとめ
今後の見通しと、読者が次に取るべきアクションを3行程度で。

# 各フィールドの要件
- title: 32〜48文字。主要SEOキーワードを前方に置いた、クリックしたくなる日本語タイトル。誇大表現は禁止。
- description: 100〜130文字のメタディスクリプション。検索結果に出る想定で、結論を含める。
- slug_en: URL用の英小文字スラッグ。半角英数とハイフンのみ、3〜6単語、40文字以内。
- keywords: 検索されうる日本語キーワード 8〜12個（製品名、機能名、「使い方」「料金」「日本語」等の複合語を含める）。
- tags: 記事分類用のタグ 3〜6個。製品名・技術カテゴリなど短い語。
- highlights: 「3秒でわかる要点」ちょうど3つ。各40〜60文字で、数値や固有名詞を含む具体的な内容。
- timetable: 動画のタイムテーブル。5〜15項目。time は "M:SS" または "H:MM:SS" 形式の実際のタイムスタンプ、
  label は その時点で何が発表・実演されたかを30〜50文字で。必ず時刻の昇順。
- is_relevant: この動画が「AI・テクノロジーに関する実質的な発表/解説」であれば true。
  ショート動画、音楽、告知のみ、内容の薄いティーザーなど記事にする価値がない場合は false。
- skip_reason: is_relevant が false のときだけ理由を書く。

body_markdown 内では h1 (`#`) を使わないでください（タイトルは別途表示されます）。
"""

ARTICLE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_relevant": {"type": "BOOLEAN"},
        "skip_reason": {"type": "STRING"},
        "title": {"type": "STRING"},
        "slug_en": {"type": "STRING"},
        "description": {"type": "STRING"},
        "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "tags": {"type": "ARRAY", "items": {"type": "STRING"}},
        "highlights": {"type": "ARRAY", "items": {"type": "STRING"}},
        "timetable": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "time": {"type": "STRING"},
                    "label": {"type": "STRING"},
                },
                "required": ["time", "label"],
                "propertyOrdering": ["time", "label"],
            },
        },
        "body_markdown": {"type": "STRING"},
    },
    "required": [
        "is_relevant",
        "title",
        "slug_en",
        "description",
        "keywords",
        "tags",
        "highlights",
        "timetable",
        "body_markdown",
    ],
    "propertyOrdering": [
        "is_relevant",
        "skip_reason",
        "title",
        "slug_en",
        "description",
        "keywords",
        "tags",
        "highlights",
        "timetable",
        "body_markdown",
    ],
}


def build_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit(
            "GEMINI_API_KEY が未設定です。\n"
            "  ローカル : export GEMINI_API_KEY='...'  （または .env.local に記載）\n"
            "  GitHub   : gh secret set GEMINI_API_KEY\n"
            "キーの取得: https://aistudio.google.com/apikey"
        )

    from google import genai  # 遅延 import（--dry-run では不要なため）

    return genai.Client(api_key=api_key)


def generate_article(client, entry: dict) -> dict:
    from google.genai import types

    channel: Channel = entry["channel"]
    video_url = f"https://www.youtube.com/watch?v={entry['video_id']}"
    prompt = PROMPT_TEMPLATE.format(
        channel_name=channel.name,
        video_title=entry["title"],
        published_date=entry["published_at"].strftime("%Y-%m-%d"),
        video_url=video_url,
        video_summary=entry["summary"] or "（概要欄なし）",
    )

    contents = types.Content(
        role="user",
        parts=[
            types.Part(
                file_data=types.FileData(file_uri=video_url, mime_type="video/*")
            ),
            types.Part(text=prompt),
        ],
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=ARTICLE_SCHEMA,
        temperature=0.65,
        max_output_tokens=32768,
    )

    global MODEL

    last_error: Exception | None = None
    # 一度使えるモデルが確定したら以降はそれだけを使う
    models = MODEL_CANDIDATES[MODEL_CANDIDATES.index(MODEL) :]

    for model_name in models:
        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=model_name, contents=contents, config=config
                )
                text = (response.text or "").strip()
                if not text:
                    finish = (
                        getattr(response.candidates[0], "finish_reason", "?")
                        if response.candidates
                        else "?"
                    )
                    raise RuntimeError(f"空のレスポンス (finish_reason={finish})")
                MODEL = model_name
                return json.loads(text)
            except Exception as error:  # noqa: BLE001 - API 由来の例外を一括で扱う
                last_error = error
                if _is_model_unavailable(error):
                    log(f"   [warn] モデル {model_name} が利用できません -> 次の候補へ")
                    break  # 再試行せず次のモデルへ
                if attempt == REQUEST_RETRIES:
                    break
                wait = min(60, 2**attempt * 5) + random.uniform(0, 3)
                log(f"   [retry {attempt}/{REQUEST_RETRIES - 1}] {error} -> {wait:.0f}s 待機")
                time.sleep(wait)

    raise RuntimeError(f"Gemini 呼び出しに失敗: {last_error}")


def _is_model_unavailable(error: Exception) -> bool:
    """モデル未提供/未知モデルを示すエラーかどうか（リトライせず別モデルへ切替）"""
    text = str(error).lower()
    return ("404" in text or "not_found" in text or "not found" in text) and (
        "model" in text or "no longer available" in text
    )


# --------------------------------------------------------------------------- #
# 記事の保存
# --------------------------------------------------------------------------- #


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    value = re.sub(r"-{2,}", "-", value)
    return value[:60].strip("-")


def unique_slug(base: str, video_id: str) -> str:
    slug = base or video_id.lower()
    if not (ARTICLES_DIR / f"{slug}.json").exists():
        return slug
    return f"{slug}-{video_id.lower()}"


def clean_list(values, limit: int) -> list[str]:
    seen: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
        if len(seen) >= limit:
            break
    return seen


def pick_thumbnail(video_id: str) -> str:
    maxres = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    if url_exists(maxres):
        return maxres
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def build_record(entry: dict, data: dict) -> dict:
    channel: Channel = entry["channel"]
    video_id = entry["video_id"]

    tags = clean_list(list(channel.base_tags) + list(data.get("tags") or []), 8)
    timetable = []
    for item in data.get("timetable") or []:
        time_value = str(item.get("time", "")).strip()
        label = str(item.get("label", "")).strip()
        if re.fullmatch(r"\d{1,2}(:\d{2}){1,2}", time_value) and label:
            timetable.append({"time": time_value, "label": label})

    return {
        "slug": unique_slug(slugify(data.get("slug_en", "")), video_id),
        "title": str(data["title"]).strip(),
        "description": str(data["description"]).strip(),
        "keywords": clean_list(data.get("keywords"), 14),
        "tags": tags,
        "highlights": clean_list(data.get("highlights"), 3),
        "timetable": timetable[:20],
        "body": str(data["body_markdown"]).strip(),
        "channel": channel.name,
        "channelId": channel.channel_id,
        "channelSlug": channel.slug,
        "videoId": video_id,
        "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
        "videoTitle": entry["title"],
        "publishedAt": entry["published_at"].astimezone(timezone.utc).isoformat(),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "thumbnail": pick_thumbnail(video_id),
        "model": MODEL,
    }


def write_article(record: dict) -> Path:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTICLES_DIR / f"{record['slug']}.json"
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


# --------------------------------------------------------------------------- #
# 単発の動画URL指定
# --------------------------------------------------------------------------- #


def entry_from_url(url: str, channel_slug: str | None = None) -> dict:
    match = re.search(r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})", url)
    if not match:
        raise SystemExit(f"動画IDを URL から抽出できません: {url}")
    video_id = match.group(1)

    channel = next((c for c in CHANNELS if c.slug == channel_slug), None)
    if channel is None:
        # チャンネル未指定なら、どのRSSに含まれているかを探して自動判定する
        for candidate in CHANNELS:
            if any(e["video_id"] == video_id for e in parse_feed(candidate)):
                channel = candidate
                break
    if channel is None:
        raise SystemExit(
            "この動画のチャンネルを特定できませんでした。"
            "--channel <slug> で明示してください（slug は scripts/channels.py 参照）"
        )

    return {
        "video_id": video_id,
        "title": f"YouTube video {video_id}",
        "summary": "",
        "published": "",
        "published_at": datetime.now(timezone.utc),
        "channel": channel,
    }


# --------------------------------------------------------------------------- #
# サンプル記事（表示確認用）
# --------------------------------------------------------------------------- #


def write_sample() -> Path:
    entry = {
        "video_id": "SAMPLE00000",
        "title": "【サンプル】自動生成パイプラインの動作確認用記事",
        "published_at": datetime.now(timezone.utc),
        "channel": CHANNELS[0],
    }
    data = {
        "title": "【サンプル記事】自動生成パイプラインの表示確認用ダミー",
        "slug_en": "sample-preview-article",
        "description": "レイアウト確認用のダミー記事です。GEMINI_API_KEY を設定して python3 scripts/main.py を実行すると本物の記事に置き換わります。",
        "keywords": ["サンプル", "動作確認"],
        "tags": ["サンプル"],
        "highlights": [
            "これはレイアウト確認のためのダミーテキストです（要点1）",
            "本番では動画から抽出した具体的な数値が入ります（要点2）",
            "GEMINI_API_KEY 設定後に本物の記事が生成されます（要点3）",
        ],
        "timetable": [
            {"time": "0:00", "label": "オープニング（ダミー）"},
            {"time": "1:23", "label": "主要機能のデモ（ダミー）"},
        ],
        "body_markdown": (
            "## この発表を一言でいうと\n\nこれはサンプル記事です。実際の記事は "
            "Gemini が動画を解析して生成します。\n\n"
            "## 発表された機能・アップデートの全容\n\n### ダミー機能A\n\n本文サンプル。\n\n"
            "## 性能・ベンチマーク\n\n| 項目 | 値 |\n| --- | --- |\n| ダミー | 100 |\n\n"
            "## まとめ\n\n`python3 scripts/main.py --max 1` で本物の記事を生成できます。\n"
        ),
    }
    record = build_record(entry, data)
    record["thumbnail"] = "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
    return write_article(record)


# --------------------------------------------------------------------------- #
# メイン
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_ARTICLES, help="1回で生成する最大記事数")
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="何日前までの動画を対象にするか")
    parser.add_argument("--channel", action="append", help="対象チャンネル slug（複数指定可）")
    parser.add_argument("--video", help="この YouTube URL だけを処理する")
    parser.add_argument("--dry-run", action="store_true", help="API を呼ばず対象一覧のみ表示")
    parser.add_argument("--sample", action="store_true", help="ダミー記事を1本生成して終了")
    args = parser.parse_args()

    if args.sample:
        path = write_sample()
        log(f"[sample] 生成しました: {path.relative_to(ROOT)}")
        return 0

    state = load_state()
    state.setdefault("processed", {})
    state.setdefault("failed", {})

    if args.video:
        candidates = [
            entry_from_url(args.video, args.channel[0] if args.channel else None)
        ]
    else:
        channels = CHANNELS
        if args.channel:
            wanted = set(args.channel)
            channels = [c for c in CHANNELS if c.slug in wanted]
            if not channels:
                raise SystemExit(f"該当するチャンネルがありません: {args.channel}")
        candidates = collect_candidates(channels, args.days, state)

    log(f"[info] 候補 {len(candidates)} 件 / 上限 {args.max} 件")
    targets = candidates[: args.max]

    if not targets:
        log("[done] 新規に処理すべき動画はありません")
        return 0

    for entry in targets:
        log(f"  - [{entry['channel'].name}] {entry['title']} ({entry['video_id']})")

    if args.dry_run:
        log("[dry-run] API 呼び出しはスキップしました")
        return 0

    client = build_client()
    created = 0

    for index, entry in enumerate(targets, start=1):
        video_id = entry["video_id"]
        log(f"\n[{index}/{len(targets)}] 解析中: {entry['title']}")
        started = time.time()

        try:
            data = generate_article(client, entry)
        except Exception as error:  # noqa: BLE001
            log(f"   [NG] {error}")
            state["failed"][video_id] = state["failed"].get(video_id, 0) + 1
            continue

        if not data.get("is_relevant", True):
            reason = data.get("skip_reason") or "記事化の価値なしと判定"
            log(f"   [skip] {reason}")
            state["processed"][video_id] = {
                "skipped": True,
                "reason": reason,
                "at": datetime.now(timezone.utc).isoformat(),
            }
            continue

        try:
            record = build_record(entry, data)
        except (KeyError, TypeError, ValueError) as error:
            log(f"   [NG] レスポンスの形式が不正: {error}")
            state["failed"][video_id] = state["failed"].get(video_id, 0) + 1
            continue

        path = write_article(record)
        state["processed"][video_id] = {
            "slug": record["slug"],
            "at": record["generatedAt"],
        }
        state["failed"].pop(video_id, None)
        created += 1
        log(
            f"   [OK] {path.relative_to(ROOT)} "
            f"({len(record['body'])}文字 / {time.time() - started:.0f}s)"
        )

    save_state(state)
    log(f"\n[done] 新規記事 {created} 本を生成しました")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
