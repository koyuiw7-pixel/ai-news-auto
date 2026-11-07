#!/usr/bin/env python3
"""検索で上位に出やすい話題を先に作るための、候補の並びの手がかり（2026-11-07 オーナー承認・Muse の5つの条件・台帳 A54）。

上限ではなく「並び」だけを変える（オーナー「制限しすぎない」・速報は上限なし）。LLM を使わない・通信しない。

  intent_of(item)   … "query"（検索で探される形）/ "breaking"（速報・Discover 向け）/ "head"（大きな語だけ）/ "neutral"
  rank_of(item)     … レーンの中の並び（小さいほど先）。
                       0: 発表から1時間以内の 障害・リコール・値上げ・発売（一番乗り）
                       1: 公式の PDF・表だけの発表を読める形にするもの / 固有名詞＋属性（対象・期限・いくら・手続き・型番＋価格・発売日・配当）
                          / 横断の一覧（値上げ・障害・リコール・終了）に載る話題
                       2: そのほか
                       3: 大きな語だけ（会社名＋「発表」「公開」で、数字も属性も無い）
  mix_order(item, counts) … 1日のめやす（検索で探される形 60% ／ 速報・Discover 40%）に近づける並び。足りない側を先に
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

QUERY_SHARE = 0.6  # 1日のめやす: 検索で探される形 60% / 速報・Discover 40%（並びだけ。上限にはしない）

INCIDENT_RE = re.compile(r"障害|復旧|つながりにくい|リコール|自主回収|回収|値上げ|値下げ|価格改定|料金改定|発売|販売開始|提供開始|サービス終了|提供終了")
ATTRIBUTE_RE = re.compile(
    r"対象|期限|締め?切り?|いつから|いつまで|いくら|料金|価格|円|ドル|手数料|手続き|申請|申し込み|受付|届出|発売日|発売|予約|配当|値上げ|値下げ|"
    r"開始日|終了日|上限|条件|使い方|始め方|対処|対策|修正版|バージョン|型番|対応機種|スペック|仕様|"
    # 暮らし・お金の話題で読者が知りたいこと（対象者・いつから・いくら・どうすれば・申請方法・一覧。2026-11-07 夜・台帳 A57）
    r"対象者|どうすれば|方法|やり方|一覧|必要なもの|窓口"
)
# 固有名詞の目印: 「」の名前・英数字の名前（型番を含む）・カタカナの名前・制度の名前
PROPER_RE = re.compile(r"「[^」]{2,30}」|[A-Za-z][A-Za-z0-9.+\-]{1,}[0-9][A-Za-z0-9.\-]*|[A-Z][A-Za-z]{2,}|[ァ-ヴー]{3,}|[一-龯]{2,8}(?:制度|給付金?|手当|補助金|助成金|控除|税|年金|保険|交付金|支援金)")
# 型番（RTX 5090・M5・SH-54F・iPhone 17 など）。年（2026）・会計年度（FY27）・四半期（Q1）は型番に数えない
MODEL_NUMBER_RE = re.compile(r"(?<![A-Za-z])(?!FY|Q[1-4]\b)[A-Z][A-Za-z]{0,5}[-‐ ]?(?!(?:19|20)\d\d\b)\d{1,5}[A-Za-z]{0,3}(?![\d.])|(?<![\d.])\d{1,2}\.\d{1,3}(?:\.\d{1,3})?(?![\d.])")
PDF_RE = re.compile(r"\.pdf(?:$|\?)", re.I)
TABLE_RE = re.compile(r"一覧|内訳|結果|統計|調査結果|表|名簿|PDF")
HEAD_VERB_RE = re.compile(r"(?:を|が)?(?:発表|公開|開催|紹介|解説)(?:へ|した|しました)?$")
BIG_NAMES = re.compile(r"^(?:OpenAI|Google|Microsoft|Apple|Amazon|AWS|Meta|NVIDIA|Anthropic|ソニー|トヨタ|ソフトバンク|楽天|NTT|KDDI|ドコモ)[、がは]")


def _title(item: dict) -> str:
    return unicodedata.normalize("NFKC", str(item.get("title") or ""))


def _fresh(item: dict, minutes: int = 60, now: datetime | None = None) -> bool:
    at = item.get("published_at")
    if not isinstance(at, datetime) or item.get("date_only"):
        return False
    return (now or datetime.now(timezone.utc)) - at <= timedelta(minutes=minutes)


def _roundup_kind(item: dict) -> bool:
    """横断の一覧（scripts/topic_lists.py）に載る形の題名か"""
    try:
        import topic_lists  # noqa: PLC0415

        return bool(topic_lists.kinds_of({"title": item.get("title") or "", "lede": item.get("summary") or ""}))
    except Exception:  # noqa: BLE001
        return False


def signals(item: dict, now: datetime | None = None) -> list[str]:
    """候補に当てはまる手がかり（ログ・テスト用）"""
    title = _title(item)
    out = []
    if INCIDENT_RE.search(title) and _fresh(item, now=now):
        out.append("first-mover")
    if PDF_RE.search(str(item.get("url") or "")) or (item.get("kind") == "gov" and TABLE_RE.search(title)):
        out.append("official-table")
    if PROPER_RE.search(title) and (ATTRIBUTE_RE.search(title) or MODEL_NUMBER_RE.search(title)):
        out.append("longtail")
    if _roundup_kind(item):
        out.append("roundup-feed")
    if not out and BIG_NAMES.search(title) and HEAD_VERB_RE.search(title.split("　")[0]) and not re.search(r"\d", title):
        out.append("head-only")
    return out


def rank_of(item: dict, now: datetime | None = None) -> int:
    s = signals(item, now)
    if "first-mover" in s:
        return 0
    if {"official-table", "longtail", "roundup-feed"} & set(s):
        return 1
    if "head-only" in s:
        return 3
    return 2


def intent_of(item: dict, now: datetime | None = None) -> str:
    s = signals(item, now)
    # 一番乗りの速報は、固有名詞＋属性の形でも速報として数える（時間が勝負）
    if "first-mover" in s or item.get("fast") or item.get("breaking"):
        return "breaking"
    if {"official-table", "longtail", "roundup-feed"} & set(s):
        return "query"
    if "head-only" in s:
        return "head"
    return "neutral"


def today_counts(state: dict, now: datetime | None = None) -> dict[str, int]:
    """今日（JST）作った記事の intent ごとの本数（processed_web の intent の印。印の無い記録は数えない）"""
    jst = timezone(timedelta(hours=9))
    today = (now or datetime.now(jst)).astimezone(jst).date()
    counts: dict[str, int] = {}
    for rec in (state.get("processed_web") or {}).values():
        if not isinstance(rec, dict) or not rec.get("slug") or not rec.get("intent"):
            continue
        try:
            at = datetime.fromisoformat(str(rec.get("at")))
        except ValueError:
            continue
        if (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(jst).date() == today:
            counts[rec["intent"]] = counts.get(rec["intent"], 0) + 1
    return counts


def mix_order(item: dict, counts: dict[str, int], now: datetime | None = None) -> int:
    """めやす（検索で探される形 60%）より少なければ query を先に、多ければ速報（一番乗り）を先に。上限にはしない"""
    query, breaking = counts.get("query", 0), counts.get("breaking", 0)
    total = query + breaking
    query_short = total == 0 or query / total < QUERY_SHARE
    intent = intent_of(item, now)
    if intent == "query":
        return 0 if query_short else 1
    if intent == "breaking":
        return 1 if query_short else 0
    return 2


def sort_key(item: dict, counts: dict[str, int], now: datetime | None = None) -> tuple[int, int]:
    """レーンの中の並び（web_articles.py が demand_rank の次に使う）"""
    return (rank_of(item, now), mix_order(item, counts, now))
