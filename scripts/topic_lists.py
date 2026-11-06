#!/usr/bin/env python3
"""横断の一覧ページ（/roundups/<kind>）の中身を、公開中の記事から作る（2026-11-07 オーナー「旬の情報をまとめてあげたり」・台帳 A52）。

  1. price-hikes  … 値上げ・料金改定
  2. outages      … 障害・復旧（通信・決済・交通・クラウド）
  3. recalls      … リコール・回収（製品・医薬品）
  4. service-changes … サービス終了・提供開始（日本での提供開始だけ）

- LLM を使わない。記事の欄（publicInterest・newsType・題名・リード・要点）に決まった規則を当てて振り分ける
- 載せるのは、公開中で検索に出す記事（indexnow.noindex_reason が無い・重複の印が無い）だけ。書く事実は記事の題名・リード・要点からだけ取る
- 事件・事故・芸能・有名人の不祥事は載せない（オーナーの判断待ち）
- 出力は content/topic_lists.json（サイトの lib/topic-lists.ts が読む。横断まとめ記事〔type roundup・scripts/roundup.py〕とは別もの）。auto_run.yml が記事の変わった回に作り直す

  python3 scripts/topic_lists.py          # 作り直して件数を表示
  python3 scripts/topic_lists.py --check  # 書かずに件数だけ
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indexnow  # noqa: E402
import public_interest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
OUT = ROOT / "content" / "topic_lists.json"
JST = timezone(timedelta(hours=9))
KEEP_DAYS = 400  # 月ごとの一覧（アーカイブ）に残す期間

# 載せない話題（事件・事故・芸能・有名人の不祥事。オーナーの判断待ち）
EXCLUDE_RE = re.compile(r"逮捕|容疑|起訴|判決|事件|殺人|死亡|死去|重体|けが人|負傷|交通事故|衝突事故|転落|火災|不祥事|熱愛|離婚|謝罪会見|芸能|書類送検")
# 株価・決算・業績の「値上がり」は値上げではない
NOT_PRICE_RE = re.compile(r"株価|決算|業績|増収|増益|減益|上方修正|下方修正|売上高|営業利益|純利益|配当|自己株式|株式の取得|時価総額")

KINDS: dict[str, dict] = {
    "price-hikes": {
        "re": re.compile(
            r"値上げ|値下げ|価格改定|料金改定|料金を改定|価格を改定|料金の改定|価格の改定|改定後の(?:料金|価格)|料金(?:が|を)?(?:引き上げ|引き下げ)|"
            r"価格(?:を|が)?(?:引き上げ|引き下げ)|値上がり|料金変更|料金を変更|月額(?:料金)?が[0-9０-９,，]+円に|運賃(?:改定|を改定|の改定|値上げ)|"
            r"手数料(?:を)?(?:改定|引き上げ|引き下げ|無料化|有料化|を無料に|を有料に)|有料化|無料化"
        ),
        "news_types": {"pricing"},
    },
    "outages": {
        "re": re.compile(
            r"通信障害|システム障害|サービス障害|障害が発生|障害の発生|障害で|障害について|障害が復旧|復旧しました|【復旧】|つながりにくい|つながらない|"
            r"利用できない(?:状態|事象)|ログインできない|決済(?:が)?できない|不具合(?:が発生|の発生|により)|サービス(?:が)?停止|運転見合わせ|大規模な遅延|"
            r"outage|service disruption"
        ),
        "news_types": set(),
    },
    "recalls": {
        "re": re.compile(public_interest.CATEGORY_RES["recall"].pattern + r"|ニトロソ|出荷停止|供給停止|使用上の注意の改訂"),
        "news_types": set(),
        "public_interest": {"recall"},
    },
    "service-changes": {
        "end_re": re.compile(r"サービス終了|提供終了|提供を終了|サポート終了|サポートを終了|販売終了|販売を終了|終了へ|終了します|終了する|廃止|打ち切り|受付終了|新規受付を停止"),
        "start_re": re.compile(r"提供開始|提供を開始|提供へ|開始へ|利用可能に|使えるように|使える|上陸|発売|始まる|スタート"),
        "japan_re": re.compile(r"日本|国内|日本語"),
        "news_types": set(),
    },
}
EFFECTIVE_RE = re.compile(
    r"((?:20\d\d年)?\d{1,2}月(?:\d{1,2}日)?(?:（.）)?(?:出荷分|納品分|請求分|利用分|ご利用分|分)?)(から|より|以降|付け|付で|に(?:終了|開始|改定|値上げ|提供開始)|で(?:終了|提供を終了)|まで)"
)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or ""))


def _jst(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(JST)


def first_sentence(text: str, cap: int = 140) -> str:
    text = re.sub(r"\s+", " ", _norm(text)).strip()
    m = re.match(r"(.+?。)", text)
    out = m.group(1) if m else text
    return out if len(out) <= cap else out[: cap - 1] + "…"


def effective(article: dict) -> str | None:
    """いつから・いつまで（記事の題名・リード・要点にある言い方のまま。無ければ None）"""
    for text in (article.get("title"), article.get("lede"), *(article.get("highlights") or [])):
        m = EFFECTIVE_RE.search(_norm(text))
        if m:
            return m.group(1) + m.group(2)
    return None


# 障害の一覧に載せない題名（障害そのものではなく、障害に対応する製品・デモ・研究の話）
# 終了・開始の一覧に載せない題名（制度の解説・コラム）
NOT_SERVICE_RE = re.compile(r"解説|ポイント|とは|コラム|まとめ")
NOT_OUTAGE_RE = re.compile(r"障害対応|自動復旧|復旧ツール|障害を(?:自動|予測|検知)|デモ|脆弱性|ツール|エージェント|研究|調査")


def kinds_of(article: dict) -> list[str]:
    """記事が載る一覧（複数あり）。判定は題名（記事の中心の事実）だけ。リコールは公共性の枠の印（publicInterest）も見る"""
    title = _norm(article.get("title", ""))
    if EXCLUDE_RE.search(f"{title} {_norm(article.get('lede', ''))}"):
        return []
    out = []
    if (KINDS["price-hikes"]["re"].search(title) or article.get("newsType") in KINDS["price-hikes"]["news_types"]) \
            and KINDS["price-hikes"]["re"].search(title) and not NOT_PRICE_RE.search(title):
        out.append("price-hikes")
    if KINDS["outages"]["re"].search(title) and not NOT_OUTAGE_RE.search(title) and article.get("publicInterest") != "breach":
        out.append("outages")
    if article.get("publicInterest") == "recall" or KINDS["recalls"]["re"].search(title):
        out.append("recalls")
    sc = KINDS["service-changes"]
    if (sc["end_re"].search(title) or (sc["start_re"].search(title) and sc["japan_re"].search(title))) and not NOT_PRICE_RE.search(title) \
            and not NOT_SERVICE_RE.search(title):
        out.append("service-changes")
    return out


def eligible(article: dict) -> bool:
    """公開中で検索に出す記事か（一覧に載せる事実の元になる記事）"""
    if article.get("type") == "roundup" or article.get("disaster"):
        return False
    if article.get("duplicateOf") and article.get("duplicateOf") != article.get("slug"):
        return False
    if not article.get("sourceUrl"):
        return False
    return indexnow.noindex_reason(article) is None


def change_label(article: dict, kind: str) -> str:
    """一覧の「何が変わる」の短い印（終了／開始・値上げ／値下げ など。記事の題名の言葉から）"""
    title = _norm(article.get("title", ""))
    if kind == "service-changes":
        return "終了" if KINDS["service-changes"]["end_re"].search(title) else "提供開始"
    if kind == "price-hikes":
        if re.search(r"値下げ|引き下げ|無料化|無料に", title):
            return "値下げ"
        if re.search(r"値上げ|引き上げ|有料化|値上がり", title):
            return "値上げ"
        return "改定"
    if kind == "outages":
        return "復旧" if re.search(r"復旧", title) else "障害"
    return "回収・注意"


def build(articles_dir: Path | None = None, now: datetime | None = None) -> dict:
    now = (now or datetime.now(JST)).astimezone(JST)
    since = now - timedelta(days=KEEP_DAYS)
    lists: dict[str, list[dict]] = {k: [] for k in KINDS}
    for path in sorted((articles_dir or ARTICLES).glob("*.json")):
        try:
            article = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not eligible(article):
            continue
        at = _jst(article.get("publishedAt") or "")  # この記事を載せた時刻（一覧の並び・月）
        announced = _jst(article.get("sourcePublishedAt") or "")  # 公式の発表日
        if not at or at < since or at > now + timedelta(hours=1):
            continue
        for kind in kinds_of(article):
            lists[kind].append({
                "slug": article["slug"],
                "at": at.isoformat(timespec="minutes"),
                "month": at.strftime("%Y-%m"),
                "announced": announced.strftime("%Y-%m-%d") if announced else None,
                "title": article.get("title", ""),
                "change": change_label(article, kind),
                "what": first_sentence(article.get("lede") or (article.get("highlights") or [""])[0]),
                "effective": None if kind == "recalls" else effective(article),  # リコールの「〜から」は製造の期間なので出さない
                "sourceName": article.get("sourceName") or article.get("channel") or "",
                "sourceUrl": article.get("sourceUrl", ""),
            })
    for kind in lists:
        lists[kind].sort(key=lambda e: e["at"], reverse=True)
    return {"generatedAt": now.isoformat(timespec="seconds"), "lists": lists}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build()
    week_ago = (datetime.now(JST) - timedelta(days=7)).isoformat()
    for kind, entries in data["lists"].items():
        print(f"[topic-lists] {kind}: {len(entries)} 件（直近7日 {sum(1 for e in entries if e['at'] >= week_ago)} 件）")
    if args.check:
        return 0
    old = OUT.read_text("utf-8") if OUT.exists() else ""
    old_lists = json.loads(old).get("lists") if old else None
    if old_lists == data["lists"]:
        print("[topic-lists] 変化なし（書き直さない）")
        return 0
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"[topic-lists] {OUT.relative_to(ROOT)} を書きました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
