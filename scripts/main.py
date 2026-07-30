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

SYSTEM_INSTRUCTION = """あなたは日経クロステック / ITmedia / TechCrunch Japan で10年書いてきたベテランのテクノロジー記者です。
海外AI企業の公式発表動画を取材し、日本のビジネスパーソン・エンジニア向けの署名記事を執筆します。

## 文体の絶対規則（これを外すと記事として失格）
- **プロの記者の文体で書く。** 常体（だ・である）ではなく、報道記事の敬体（です・ます）で統一する。
- **禁止表現**: 「いかがでしたか」「〜と言えるでしょう」「〜ではないでしょうか」「注目が集まっています」
  「今後の動向に注目です」「衝撃」「驚愕」「revolutionary」などの中身のない煽り・締め文句。
  感嘆符（！）はタイトル・本文とも原則使わない。
- **箇条書きに逃げない。** 事実を並べるだけでなく、地の文で因果関係と意味を説明する。
  箇条書きは手順・仕様の列挙にのみ使う。
- **一文は60字以内**を目安に、主語と述語を明確に。修飾の入れ子を避ける。
- 主観を書くときは「取材班の見立てでは」と明示し、事実と分離する。

## 取材姿勢
- 動画の映像（スライド・デモ画面・UI・グラフ・テロップ）と音声の両方を一次資料として扱う。
- 動画内で確認できない事実は書かない。背景知識で補う箇所は「（編集部注）」と明記する。
- 数値・価格・モデル名・機能名・登壇者の発言は、提示されたとおり正確に転記する。
  発言を引用するときは「」で括り、原語と日本語訳を併記する。
- 「何が新しいのか」を、既存技術との差分として必ず言語化する。差分が不明なら不明と書く。
- 読者が次に取る行動（試す・様子見・投資判断）まで踏み込む。"""

PROMPT_TEMPLATE = """以下のYouTube動画を「映像」と「音声」の両方から徹底的に解析し、日本語のSEO記事を作成してください。

# 対象動画
- チャンネル: {channel_name}
- 動画タイトル: {video_title}
- 公開日: {published_date}
- URL: {video_url}
- 概要欄（参考。矛盾する場合は動画本編を優先）:
{video_summary}

# 品質基準（商業メディアの水準）
- 本文は **4000〜6000字**。薄い記事は不可。
- 各 `###` セクションは **400字以上**、必ず動画内の具体的な固有名詞・数値・画面描写を含める。
- 見出しは内容を示す具体的なものにする（「概要」「まとめ」のような空疎な見出しは不可）。
- 表は「項目名 / 数値 / 出典（動画内 or 編集部注）」が分かる形にする。

# 出力する記事の構成（body_markdown に Markdown で記述）
必ず以下の見出し構成（`##` 見出し）を守り、各セクションを具体的に埋めてください。

## 何が発表されたのか
リード文の続きとして、300〜400字で「誰が・何を・いつ・どこまで」を事実ベースで整理。
発表の位置づけ（新製品なのか既存の改良なのか、研究段階か提供開始済みか）を明確にする。

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
- title: 32〜48文字。報道記事の見出しとして成立する体裁にする。
  主要SEOキーワードを前方に置き、**感嘆符・煽り語（衝撃／ヤバい／ついに／必見）は使わない**。
  良い例:「Google DeepMind、複数ロボットが言語で連携する『Gemini Robotics 2』を公開」
  悪い例:「Gemini Robotics 2発表！ロボット連携の衝撃」
- lede: 記事冒頭のリード文。150〜200字の1〜2段落。5W1Hを圧縮し、結論を先に置く。
  ここだけ読んでも発表の要点が分かる密度にする。
- description: 100〜130文字のメタディスクリプション。検索結果に出る想定で、結論を含める。
- mentioned_tools: 記事中で言及した製品・サービス・企業の**正式名称**の配列（5〜12個）。
  例: ["OpenAI", "ChatGPT", "Google Gemini", "Anthropic", "NVIDIA"]。
  実際に本文で触れたものだけを挙げること。
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
        "lede": {"type": "STRING"},
        "description": {"type": "STRING"},
        "mentioned_tools": {"type": "ARRAY", "items": {"type": "STRING"}},
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
        "lede",
        "description",
        "keywords",
        "tags",
        "highlights",
        "timetable",
        "mentioned_tools",
        "body_markdown",
    ],
    "propertyOrdering": [
        "is_relevant",
        "skip_reason",
        "title",
        "slug_en",
        "lede",
        "description",
        "mentioned_tools",
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


def normalize_body(text: str) -> str:
    """モデルが改行を二重エスケープして返した場合（本文に実改行が無く "\\n" が並ぶ）を救済する。

    そのまま保存すると Markdown が1行の塊になり、記事が壊れて表示される。
    """
    text = str(text or "")
    literal = text.count("\\n")
    if literal and text.count("\n") < literal / 4:
        text = (
            text.replace("\\r\\n", "\n")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
        )
        log(f"   [fix] 二重エスケープされた改行 {literal} 箇所を復元しました")
    return text.strip()


# --------------------------------------------------------------------------- #
# アフィリエイトリンクの自動挿入
# --------------------------------------------------------------------------- #

AFFILIATE_PATH = ROOT / "affiliate_links.json"


def load_affiliates() -> list[dict]:
    """affiliate_links.json を正規化して読み込む。

    値は文字列（URL）でも {url, label, note, aliases} でも書ける。
    """
    if not AFFILIATE_PATH.exists():
        return []
    try:
        raw = json.loads(AFFILIATE_PATH.read_text("utf-8"))
    except json.JSONDecodeError as error:
        log(f"[warn] affiliate_links.json が不正です: {error}")
        return []

    entries = []
    for name, value in raw.items():
        if name.startswith("_"):  # _README などのメモ用キーは無視
            continue
        if isinstance(value, str):
            value = {"url": value}
        if not isinstance(value, dict) or not value.get("url"):
            continue
        url = str(value["url"])
        if "YOUR_ID" in url or "your_aff_link" in url:
            # プレースホルダのままなら挿入しない（誤ったリンクを公開しないため）
            continue
        aliases = [name] + [str(a) for a in value.get("aliases", [])]
        entries.append(
            {
                "name": name,
                "label": str(value.get("label") or name),
                "url": url,
                "note": str(value.get("note") or ""),
                "aliases": [a.lower() for a in aliases if a],
            }
        )
    return entries


def match_affiliates(record: dict, mentioned: list[str]) -> list[dict]:
    """記事が言及したツール名を affiliate_links.json と突き合わせる。

    Gemini が返した mentioned_tools を主に使い、取りこぼしを本文の全文一致で補う。
    """
    catalog = load_affiliates()
    if not catalog:
        return []

    haystack = " ".join(
        [record["title"], record["description"], record.get("lede", ""), record["body"]]
    ).lower()
    mentioned_lower = {str(m).strip().lower() for m in mentioned if str(m).strip()}

    matched = []
    for entry in catalog:
        hit = any(a in mentioned_lower for a in entry["aliases"]) or any(
            a in haystack for a in entry["aliases"]
        )
        if hit:
            matched.append(
                {
                    "name": entry["name"],
                    "label": entry["label"],
                    "url": entry["url"],
                    "note": entry["note"],
                }
            )
    return matched[:6]


def linkify_first_mention(body: str, affiliates: list[dict]) -> str:
    """本文中の最初の1回だけ、ツール名をアフィリエイトリンクに置き換える。

    見出し行・表・コードブロック・既存リンク内は対象外にして Markdown を壊さない。
    """
    if not affiliates:
        return body

    remaining = {a["name"]: a["url"] for a in affiliates}
    lines = body.split("\n")
    in_code = False

    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line.strip():
            continue
        if line.lstrip().startswith(("#", "|", ">", "    ")):
            continue

        for name in list(remaining):
            if "[" in line or "](" in line:
                break  # すでにリンクを含む行は触らない
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            match = pattern.search(line)
            if not match:
                continue
            url = remaining.pop(name)
            line = (
                line[: match.start()]
                + f"[{match.group(0)}]({url})"
                + line[match.end() :]
            )
            lines[index] = line

    return "\n".join(lines)


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

    record = {
        "slug": unique_slug(slugify(data.get("slug_en", "")), video_id),
        "title": str(data["title"]).strip(),
        "lede": normalize_body(data.get("lede", "")),
        "description": str(data["description"]).strip(),
        "keywords": clean_list(data.get("keywords"), 14),
        "tags": tags,
        "highlights": clean_list(data.get("highlights"), 3),
        "timetable": timetable[:20],
        "body": normalize_body(data["body_markdown"]),
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
        "affiliates": [],
    }

    # 記事が言及したツールとアフィリエイト定義を突き合わせ、本文にもリンクを1回だけ挿入する
    affiliates = match_affiliates(record, data.get("mentioned_tools") or [])
    if affiliates:
        record["affiliates"] = affiliates
        record["body"] = linkify_first_mention(record["body"], affiliates)
        log(f"   [aff] {len(affiliates)}件: {', '.join(a['name'] for a in affiliates)}")

    return record


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


def relink_existing() -> int:
    """affiliate_links.json を更新したあと、既存記事のリンクを貼り直す（API不要）。"""
    if not ARTICLES_DIR.exists():
        log("[relink] 記事がありません")
        return 0

    updated = 0
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            record = json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError:
            log(f"[warn] 読み込み失敗: {path.name}")
            continue

        before = json.dumps(record.get("affiliates", []), sort_keys=True)
        affiliates = match_affiliates(record, record.get("tags", []))
        if json.dumps(affiliates, sort_keys=True) == before:
            continue

        record["affiliates"] = affiliates
        record["body"] = linkify_first_mention(record["body"], affiliates)
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        updated += 1
        log(f"[relink] {path.name}: {len(affiliates)}件")

    log(f"[done] {updated} 本を更新しました")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_ARTICLES, help="1回で生成する最大記事数")
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="何日前までの動画を対象にするか")
    parser.add_argument("--channel", action="append", help="対象チャンネル slug（複数指定可）")
    parser.add_argument("--video", help="この YouTube URL だけを処理する")
    parser.add_argument("--dry-run", action="store_true", help="API を呼ばず対象一覧のみ表示")
    parser.add_argument("--sample", action="store_true", help="ダミー記事を1本生成して終了")
    parser.add_argument(
        "--relink",
        action="store_true",
        help="APIを呼ばず、既存記事のアフィリエイトリンクだけを貼り直す",
    )
    args = parser.parse_args()

    if args.relink:
        return relink_existing()

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
