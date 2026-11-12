#!/usr/bin/env python3
"""1日の記事の配分（2026-11-04 オーナー承認のピボット・台帳 A41）。

読まれないいちばんの理由は「何を選ぶか」だった（直近の約7割が海外の企業向け・開発者向けの発表）。
候補を7つの種類に分け、1日の割合のめやすに近づける:
  障害・情報流出・サポート終了・注意喚起 15% / 料金・制度・お金の変更 20% / 有名ブランドの新製品・日本の発売 25% /
  一般向けの大きな AI の動き 20% / 日本の大手企業の決算・提携 10% / 目を引く技術・研究 5% /
  企業向け・開発者向けの海外の発表 5%まで（上限。大きなニュースは上限の外）
2026-11-07 夜 オーナー承認（台帳 A57）: 1日の6割以上を日本の暮らし・お金の話題（life_group = 注意喚起・お金・暮らしの手続き）に。
  注意喚起 20% / お金 25% / 暮らしの手続き・交通・天気 15%（計60%）/ ブランド 15% / 一般向け AI 12% / 日本の大手 8% / 研究 3% /
  企業向け・開発者向けの海外の発表 2%（1日2本まで）。本数は減らさない（並びと発信元で寄せる。上限は増やさない）
  life_behind(counts)       … 今日の暮らし・お金の割合がめやす（life_min_share）に届いていないか

調整値（割合・判定の語・発信元）は scripts/news_mix.json。ここには値を書き込まない。
使い方（scripts/web_articles.py）:
  classify(item)            … 候補の種類
  today_counts(state)       … 今日作った記事の種類ごとの本数（processed_web の mix の印）
  order_key(item, counts)   … レーンの中の並び（今日まだ足りない種類を先に・企業向けは最後）
  over_cap(item, counts)    … 上限のある種類（企業向け・開発者向け）が今日の上限に達したか
API を使わない・通信しない。読めない設定は既定値で動く（記事づくりを止めない）。
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "scripts" / "news_mix.json"
JST = timezone(timedelta(hours=9))


def load_config(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or CONFIG_PATH).read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("daily_basis", 30)
    data.setdefault("order_by_mix", True)
    data.setdefault("categories", {"other": {"label": "そのほか", "share": 0.0}})
    data.setdefault("patterns", {})
    data.setdefault("sources", {})
    return data


CONFIG = load_config()


def _re(name: str) -> re.Pattern | None:
    pattern = (CONFIG.get("patterns") or {}).get(name)
    if not pattern:
        return None
    try:
        return re.compile(pattern, re.I)
    except re.error:
        return None


PATTERNS = {name: _re(name) for name in (CONFIG.get("patterns") or {})}
SOURCES = {name: set(slugs) for name, slugs in (CONFIG.get("sources") or {}).items()}


def _hit(name: str, text: str) -> bool:
    pattern = PATTERNS.get(name)
    return bool(pattern and pattern.search(text))


def is_japanese_item(item: dict) -> bool:
    """候補が日本語の発表か（2026-11-07 オーナー決定・台帳 A41/A47 の改定）。候補の lang か、発信元のフィードの言語（scripts/feeds.py）が ja。
    題名の文字では決めない（このサイトの記事の題名はいつも日本語なので、記事から数え直すときに海外の発表まで国内になってしまう）"""
    lang = str(item.get("lang") or "").lower()
    if not lang:
        try:
            import feeds  # noqa: PLC0415 - 発信元の言語だけ使う
        except Exception:  # noqa: BLE001
            return False
        slug = str(item.get("source_slug") or item.get("channelSlug") or "")
        lang = str((feeds.FEEDS_BY_SLUG.get(slug) or {}).get("lang") or "").lower()
    return lang == "ja"


# 広げた暮らしの話題（public_interest.wide_category・台帳 A56）をこの配分の種類に読み替える（2026-11-07 夜・台帳 A57）
WIDE_TO_MIX = {"outage": "alert", "service-end": "alert", "price": "money", "benefit": "money",
               "transport": "life", "weather": "life", "health": "life"}
# 注意喚起の語に当たっても、製品・対策の話（「詐欺対策の新機能」「漏えいを防ぐサービス」）は注意喚起にしない
NOT_ALERT_RE = re.compile(r"対策(?:の|を|に|機能|サービス|製品|ソフト|強化)|を防ぐ|防止(?:機能|サービス)|新機能|ソリューション|提供開始|導入|と提携|協業")


def classify(item: dict) -> str:
    """候補（フィードの項目）か記事の種類。判定の順: 注意喚起 → 企業向け（発信元・語）→ 一般向け AI → お金 → 暮らし → ブランド → 日本の大手 → 研究 → そのほか"""
    import public_interest  # noqa: PLC0415 - 公共性の判定と同じ語を使う

    title = unicodedata.normalize("NFKC", str(item.get("title") or ""))
    source = str(item.get("source_slug") or item.get("channelSlug") or "")
    # 公共性の種類は、事件・注意喚起の形の題名だけ（「詐欺対策の新機能」「脆弱性の発見」のような製品の話は注意喚起にしない）
    pi_cat = item.get("_public_interest") or item.get("publicInterest") or public_interest.record_category({"title": title})
    wide = WIDE_TO_MIX.get(public_interest.wide_category(title, source) or "")
    if pi_cat in ("breach", "missile", "disaster", "recall", "scam") or wide == "alert" or (_hit("alert", title) and not NOT_ALERT_RE.search(title)):
        return "alert"
    consumer_ai = _hit("ai_consumer", title)
    # 企業向け・開発者向けの発信元の記事と、企業向けの語のある題名は、AI の名前があっても企業向け（大きなニュースは上限の外）
    # 2026-11-07 オーナー決定: 日本語の企業向け・開発者向けの発表（AWS・Google Cloud の日本語ブログのトヨタ・KDDI の事例など）は
    # 国内のニュースとして扱い、企業向けの上限（A41）に数えない。英語など外国語の企業向けの発表は今までどおり上限あり
    if (source in SOURCES.get("enterprise_dev", set()) or _hit("enterprise_dev", title)) and not is_japanese_item(item):
        return "enterprise_dev"
    if consumer_ai and source not in SOURCES.get("brand", set()):
        return "ai_consumer"  # 一般向けの AI の新機能・無料の範囲の変更（料金の語があっても AI の動きとして数える）
    if pi_cat == "money" or wide == "money" or _hit("money", title):
        return "money"
    if wide == "life" or _hit("life", title):
        return "life"  # 暮らしの手続き・交通・天気・感染症・自治体のお知らせ（2026-11-07 夜・台帳 A57）
    if (source in SOURCES.get("brand", set()) or _hit("brand", title)) and (_hit("brand_event", title) or source in SOURCES.get("brand", set())):
        if not consumer_ai or source in SOURCES.get("brand", set()):
            return "brand"
    if consumer_ai:
        return "ai_consumer"
    if _hit("jp_corp", title) and _hit("jp_corp_names", title):
        return "jp_corp"
    if source in SOURCES.get("quirky", set()) or _hit("quirky", title):
        return "quirky"
    return "other"


def targets(basis: int | None = None) -> dict[str, float]:
    basis = int(basis or CONFIG.get("daily_basis") or 30)
    return {name: float(spec.get("share") or 0) * basis for name, spec in (CONFIG.get("categories") or {}).items()}


def cap_of(name: str, basis: int | None = None) -> int | None:
    """1日の上限（cap=true の種類だけ）。割合×本数のめやすを切り上げ、少なくとも1本"""
    spec = (CONFIG.get("categories") or {}).get(name) or {}
    if not spec.get("cap"):
        return None
    if spec.get("max_per_day") is not None:
        # 本数を決め打ちした上限（2026-11-06 台帳 A47: 1日の本数を増やしても海外の企業向け・開発者向けは増やさない）
        return max(0, int(spec["max_per_day"]))
    return max(1, math.ceil(targets(basis).get(name, 0)))


def today_counts(state: dict, now: datetime | None = None) -> dict[str, int]:
    """今日（JST）作った記事の種類ごとの本数（processed_web の mix の印。印の無い古い記録は数えない）"""
    today = (now or datetime.now(JST)).astimezone(JST).date()
    counts: dict[str, int] = {}
    for rec in (state.get("processed_web") or {}).values():
        if not isinstance(rec, dict) or not rec.get("slug") or not rec.get("mix"):
            continue
        try:
            at = datetime.fromisoformat(str(rec.get("at")))
        except ValueError:
            continue
        if (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(JST).date() == today:
            counts[rec["mix"]] = counts.get(rec["mix"], 0) + 1
    return counts


def life_group() -> set[str]:
    """暮らし・お金の種類（2026-11-07 夜・台帳 A57）。1日の割合のめやすは life_min_share（既定 0.6）"""
    return set(CONFIG.get("life_group") or ("alert", "money", "life"))


def life_share(counts: dict[str, int]) -> float | None:
    """今日作った記事のうち暮らし・お金の種類の割合（まだ0本なら None）"""
    total = sum(counts.values())
    if not total:
        return None
    return sum(n for name, n in counts.items() if name in life_group()) / total


def life_behind(counts: dict[str, int]) -> bool:
    """今日の暮らし・お金の割合がめやすに届いていないか（0本の朝も「届いていない」）"""
    share = life_share(counts)
    return share is None or share < float(CONFIG.get("life_min_share") or 0.6)


def deficit(name: str, counts: dict[str, int]) -> float:
    """今日のめやすまでの残り（多いほど先に作る）"""
    return targets().get(name, 0.0) - counts.get(name, 0)


def order_key(item: dict, counts: dict[str, int]) -> tuple:
    """レーンの中の並び。上限のある種類（企業向け・開発者向け）は最後、残りは今日まだ足りない種類から。
    暮らし・お金の割合がめやす（6割）に届いていない日は、暮らし・お金の種類をいちばん先に（2026-11-07 夜・台帳 A57）"""
    if not CONFIG.get("order_by_mix", True):
        return (0, 0.0)
    name = item.get("_mix") or classify(item)
    if cap_of(name) is not None:
        return (3, 0.0)
    gap = deficit(name, counts)
    if name in life_group() and life_behind(counts):
        return (0, -gap)
    return (1 if gap > 0 else 2, -gap)


def over_cap(item: dict, counts: dict[str, int]) -> bool:
    name = item.get("_mix") or classify(item)
    cap = cap_of(name)
    return cap is not None and counts.get(name, 0) >= cap


# AdSense の審査の期間（scripts/ramp.py の ADSENSE_REVIEW。2026-11-12 オーナー決定「自動のニュースは暮らしとお金だけ」）に作ってよい種類。
# 注意喚起・お金・暮らしの手続き・有名ブランドの新製品。それ以外の種類でも、題名がお金か暮らしにつながる（indexnow.life_link）
# 国内の記事は作る（リコール・電気代の割引など、種類の判定の語に当たらない暮らしとお金の記事を落とさない）。
# スポーツ・科学・エンタメ・AI の欄は、上の4つの種類のときだけ。速報・大きなニュース（major）はこの外（台帳 S41）
REVIEW_MIXES = frozenset({"alert", "money", "life", "brand"})
REVIEW_OFF_SECTIONS = frozenset({"ai", "sports", "science", "entertainment"})
# 種類の判定（alert）の語に当たらない注意喚起（「悪用を確認」の脆弱性・会員情報の漏えいなど）も、読者を守る話なので作る
REVIEW_ALERT_RE = re.compile(r"脆弱性[^。]{0,20}(?:悪用|修正|更新|注意)|漏えい|漏洩|流出|不正アクセス|リコール|詐欺|なりすまし")


def review_blocks(item: dict, today: str | None = None) -> bool:
    """審査の期間に、この候補を自動のニュースとして作らないか（作らないなら True）"""
    import ramp  # noqa: PLC0415

    today = today or datetime.now(JST).strftime("%Y-%m-%d")
    if not ramp.in_adsense_review(today):
        return False
    if (item.get("_mix") or classify(item)) in REVIEW_MIXES:
        return False
    if REVIEW_ALERT_RE.search(unicodedata.normalize("NFKC", str(item.get("title") or ""))):
        return False
    if str(item.get("section") or item.get("genreSlug") or "") in REVIEW_OFF_SECTIONS:
        return True
    import indexnow  # noqa: PLC0415

    return not indexnow.life_link(str(item.get("title") or ""))


def summary(counts: dict[str, int]) -> str:
    share = life_share(counts)
    parts = [f"暮らし・お金 {0 if share is None else round(share * 100)}%（めやす {round(float(CONFIG.get('life_min_share') or 0.6) * 100)}%以上）"]
    for name, target in targets().items():
        if target or counts.get(name):
            cap = cap_of(name)
            parts.append(f"{name} {counts.get(name, 0)}/{target:.0f}{'（上限）' if cap is not None else ''}")
    return " / ".join(parts)
