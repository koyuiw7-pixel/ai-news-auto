#!/usr/bin/env python3
"""「自分は対象か」の事故（情報流出・リコール/回収・大きな障害）の見張り（2026-11-14 オーナー「全然最速でもない」・台帳 W44）。

無印良品（MUJI Card 約109万件）の発表を10日間、ほかにも8件の同じ型の事故を取りこぼした。原因は、会社自身の「お知らせ」が
どの発信元の一覧にも無く（ニュースリリースではなく「重要なお知らせ」の欄・PDF に出る）、毎朝の見逃しチェックも AI・テックの
見出ししか「大きなニュース」にしていなかったこと。ここでは:

  1. 見つけるためだけの発信元（scripts/incident_watch.json の discovery。セキュリティの専門メディア・適時開示・PR TIMES の事故の語・
     消費者庁のリコール情報）の新しい見出しから、会社の名前・事故の種類・規模（件数・台数）を取り出す（正規表現だけ。LLM は使わない）
  2. その会社自身のお知らせ（公式の一次情報）を探す: 見つけた記事の中のリンク → 会社のトップ/お知らせ一覧の「お詫び・不正アクセス・回収」の
     リンク。本文に会社の名前と事故の語があることを確かめる。見つけた記事そのものは出典にしない
  3. 直近の記事に同じ事故があれば作らない（出典の URL・会社の名前＋事故の語・同じ会社のサイト＋事故の語）
  4. 公式のお知らせが見つかったら、速報レーン（auto_run.yml の fast_url・fast_meta の incident）に回す。1日の上限・審査の期間の門・
     48/96時間の古さの決まりの外で作り、公開した回はすぐデプロイする（速報レーンの決まり）。48時間を超えた発表は「速報ではない」形になる
  5. 公式のお知らせが見つからないときは、話題のレーン（scripts/trend_lane.py）の決まり（主要な報道機関の独立した2社以上・報道と明記）で
     作れるよう、話題キュー（state/trend_queue.json）に「会社名＋事故の種類」を先頭で足す
  6. 発表 → 他社の初報 → 検知 → 速報レーンに渡した → 公開 の時刻を state/incident_watch.json に残す（report で「発表から何分」を出す）

  python scripts/incident_watch.py run                 # 見張り（新しい事故を見つけて速報レーンに回す）
  python scripts/incident_watch.py run --backfill      # 取りこぼしの一覧（incident_watch.json の backfill）も1回だけ拾い直す
  python scripts/incident_watch.py run --dry-run       # 何を回すかだけ出す（速報レーンを起こさない・state を書かない）
  python scripts/incident_watch.py apply-press         # 報道の決まりで作る話題を話題キューに足し直す（push のやり直しのあと用）
  python scripts/incident_watch.py report [--markdown] # 発表から公開までの時間の一覧
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fast_lane  # noqa: E402
import public_interest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "scripts" / "incident_watch.json"
STATE_PATH = ROOT / "state" / "incident_watch.json"
ARTICLES_DIR = ROOT / "content" / "articles"
LIVE_PATH = ROOT / "state" / "live_log.json"
JST = timezone(timedelta(hours=9))
UTC = timezone.utc
KEEP_DAYS = 45
SEEN_KEEP_DAYS = 21
PRESS_TRAFFIC = 10_000_000  # 話題キューの先頭に置く（急上昇の検索数の代わり）


def log(message: str) -> None:
    print(message, flush=True)


def load_config(path: Path | None = None) -> dict:
    data = json.loads((path or CONFIG_PATH).read_text("utf-8"))
    for kind, spec in data["types"].items():
        spec["_re"] = re.compile(spec["re"])
        spec["_anchor_re"] = re.compile(spec["anchor_re"])
    data["_exclude_re"] = re.compile(data["exclude_re"])
    return data


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def norm(text: str) -> str:
    return re.sub(r"[\s　・･\-‐－―.．]+", "", nfkc(text)).lower()


def iso(dt: datetime | None) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds") if dt else ""


def parse_time(value) -> datetime | None:
    return fast_lane.parse_time(value)


# --------------------------------------------------------------------------- #
# 1. 見出しから: 事故の種類・会社の名前・規模
# --------------------------------------------------------------------------- #
def classify(title: str, summary: str = "", cfg: dict | None = None) -> str | None:
    """事故の種類（breach / recall / outage）。題名に事故の語があり、除外の語（脆弱性・セミナー・解説など）が無いもの"""
    cfg = cfg or CONFIG
    head = nfkc(title)
    if cfg["_exclude_re"].search(head):
        return None
    for kind, spec in cfg["types"].items():
        if spec["_re"].search(head):
            return kind
    return None


_GENERIC_NAME = re.compile(
    r"^(?:当社|弊社|委託先|業務委託先|子会社|グループ会社|複数|相次ぐ|新たに|続報|第[0-9一二三四五六七八九]報|お詫び|お知らせ|重要|"
    r"個人情報|会員情報|顧客情報|メールアドレス|認証情報|不正アクセス|情報流出|情報漏えい|サイバー攻撃|ランサムウェア|システム障害|"
    r"オンライン[^\s]{0,6}|サイト|アプリ|\d.*)$"
)
_LEAD_NAME = re.compile(r"^(.{2,40}?)(?=、|,|，|が|で|に|へ|を|の|と|など|から|「|『|（|\(|\s|　|$)")
_BRACKET_NAME = re.compile(r"^[「『]([^」』]{2,30})[」』]")
_PIYO_NAME = re.compile(r"^(.{2,40}?)(?:への|での|における|で発生した|に対する|を騙る|の).{0,40}?についてまとめてみた")
_TAIL_NAME = re.compile(r"\s[-－–—]\s([^-－–—]{2,25})$")
_CORP_WORDS = re.compile(r"株式会社|（株）|\(株\)|㈱|有限会社|合同会社|ホールディングス|HD$|グループ$|子会社$|公式$")
_HEAD_NOISE = re.compile(r"^(?:【[^】]{0,12}】|\[[^\]]{0,12}\]|＜[^＞]{0,12}＞|<[^>]{0,12}>|続報|速報|重要)[\s　:：]*")


_LATIN_NAME = re.compile(r"^[A-Za-z0-9&'.@+\-]+(?: [A-Z0-9][A-Za-z0-9&'.+\-]*)*")
_CATEGORY_LEAD = re.compile(r"(?:印刷|サービス|サイト|アプリ|通販|ショップ|ストア|ゲーム|麻雀|システム|プラットフォーム|チケット|ツール|ソフト|メディア|ポータル|クラウド|EC)$")


def clean_name(name: str) -> str:
    name = nfkc(name).strip(" 　「」『』\"'“”・:：、。")
    for _ in range(3):
        name = _CORP_WORDS.sub("", name).strip(" 　")
    return "" if not name or len(name) < 2 or _GENERIC_NAME.match(name) else name


def name_aliases(title: str, name: str) -> list[str]:
    """見出しの先頭近くの「」の中の名前（サービス名）。会社の名前と別なら、言い換えとして確かめに使う"""
    head = _HEAD_NOISE.sub("", nfkc(title).strip())[:40]
    out = []
    for inner in re.findall(r"[「『]([^」』]{2,30})[」』]", head):
        alias = clean_name(inner)
        if alias and norm(alias) != norm(name):
            out.append(alias)
    return out[:2]


def extract_company(title: str, src: dict | None = None) -> str:
    """見出しから会社・サービスの名前（当てになる順: 「会社:題名」の発信元 → piyolog の型 → 末尾の「 - 会社」→ 先頭の「」→ 先頭の語）。
    取れなければ空（その見出しは使わない）。ここで取った名前は、公式のお知らせの本文にもあることを確かめてから使う"""
    src = src or {}
    text = _HEAD_NOISE.sub("", nfkc(title).strip())
    if sep := src.get("title_split"):
        head, _, _rest = text.partition(sep)
        return clean_name(re.sub(r"^[A-ZＡ-Ｚ]\s?[-－]\s?", "", head))  # 適時開示の市場の印（G－・P－ など）を外す
    if "「" in text and src.get("type") == "html":
        return clean_name(text.split("「", 1)[0].split("、")[0])  # 消費者庁の一覧「会社「商品」 - 対応」
    if m := _PIYO_NAME.match(text):
        inner = re.search(r"[「『]([^」』]{2,30})[」』]", m.group(1))
        return clean_name(inner.group(1) if inner else m.group(1))
    if m := _TAIL_NAME.search(text):
        if name := clean_name(m.group(1)):
            if not re.search(r"脆弱性|件|対応|修正|公開|注意|可能性", name):
                return name
    if m := _BRACKET_NAME.match(text):
        return clean_name(m.group(1))
    if m := _LATIN_NAME.match(text):
        if len(m.group(0)) >= 2 and not _GENERIC_NAME.match(m.group(0)):
            rest = text[m.end():]
            # 英字の名前に日本語が続く（NTTデータ・LINEヤフー）ときは、先頭の語まで読む
            if not rest or rest[0] in " 　、,，がでにへをのと「『（(":
                return clean_name(m.group(0))
    if m := _LEAD_NAME.match(text):
        lead = clean_name(m.group(1))
        after = text[m.end():]
        if after[:1] in "「『" and (not lead or _CATEGORY_LEAD.search(lead) or len(lead) <= 3):
            if inner := _BRACKET_NAME.match(after):
                return clean_name(inner.group(1))  # 「ネット印刷「ラクスル」」は、分類の語ではなく「」の名前
        return lead
    return ""


_NUM = r"\d[\d,，]*(?:\.\d+)?"
SCALE_RE = re.compile(
    rf"(?:最大|延べ|のべ|計|合計|およそ|約)*\s?((?:{_NUM}\s?億)?\s?(?:{_NUM}\s?万)?\s?(?:{_NUM})?)\s?(件|人|名|台|個|本|枚|世帯|アカウント|ID|口座|点|箱|袋|パック)"
)


def _to_int(expr: str) -> int:
    total = 0.0
    rest = expr.replace(",", "").replace("，", "").replace(" ", "")
    for unit, mul in (("億", 100_000_000), ("万", 10_000)):
        if unit in rest:
            head, rest = rest.split(unit, 1)
            total += float(head or 0) * mul
    if rest:
        total += float(rest)
    return int(total)


def parse_scale(text: str) -> tuple[int, str] | None:
    """文の中でいちばん大きい件数・台数（数, 書かれたままの表記）。無ければ None"""
    best: tuple[int, str] | None = None
    for m in SCALE_RE.finditer(nfkc(text)):
        expr = m.group(1).strip()
        if not expr or not re.search(r"\d", expr):
            continue
        try:
            value = _to_int(expr)
        except ValueError:
            continue
        if value > 0 and (best is None or value > best[0]):
            best = (value, m.group(0).strip())
    return best


def is_major_name(name: str, aliases: list[str] | None = None, cfg: dict | None = None) -> bool:
    """全国で売られている・使われている名前か（会社・サービスの名前だけで見る。見出しの中の別の会社の名前では当てない）"""
    cfg = cfg or CONFIG
    blob = " / ".join([name, *(aliases or [])])
    return any(public_interest.contains_term(n, blob) for n in cfg["major_names"])


def canonical(name: str, cfg: dict | None = None) -> tuple[str, list[str]]:
    """同じ会社の別の呼び名（無印良品・良品計画・MUJI）を1つの名前にまとめる。(代表の名前, 言い換え)"""
    cfg = cfg or CONFIG
    for group in cfg.get("name_groups") or []:
        if any(public_interest.contains_term(member, name) for member in group):
            return group[0], [g for g in group[1:]]
    return name, []


# --------------------------------------------------------------------------- #
# 2. 見つけるための発信元を読む
# --------------------------------------------------------------------------- #
_ITEM_RE = re.compile(r"<(item|entry)\b[^>]*>(.*?)</\1>", re.S)
_TAG_RE = {k: re.compile(rf"<(?:[a-z]+:)?{k}\b[^>]*>(.*?)</(?:[a-z]+:)?{k}>", re.S | re.I)
           for k in ("title", "link", "description", "summary", "pubDate", "date", "published", "updated")}
_ATOM_LINK_RE = re.compile(r"""<link\b[^>]*?href=["']([^"']+)["']""", re.I)
_ANCHOR_RE = re.compile(r"""<a\b[^>]*?href=["']([^"'#][^"']*)["'][^>]*>(.*?)</a>""", re.S | re.I)


def _field(block: str, key: str) -> str:
    m = _TAG_RE[key].search(block)
    if not m:
        return ""
    value = re.sub(r"^\s*<!\[CDATA\[|\]\]>\s*$", "", m.group(1).strip(), flags=re.S)
    value = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(value)))
    return re.sub(r"\s+", " ", value).strip()


def _decode(data: bytes) -> str:
    head = data[:300].decode("ascii", "ignore").lower()
    m = re.search(r"encoding=[\"']([a-z0-9_\-]+)", head)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "cp932", "euc_jp"]:
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", "replace")


def unwrap(url: str) -> str:
    """中継の URL（webapi.yanoshin.jp/rd.php?<本当の URL>）を本当の URL に戻す"""
    url = html.unescape(url or "").strip()
    if "rd.php?" in url:
        inner = url.split("rd.php?", 1)[1]
        if inner.startswith("https://"):
            return inner
    return url


def parse_source(src: dict, data: bytes) -> list[dict]:
    """発信元の一覧 → [{title, url, summary, published(datetime|None), source}]"""
    text = _decode(data)
    out: list[dict] = []
    if src.get("type") == "html":
        link_re = re.compile(src.get("link_re") or ".")
        seen = set()
        for href, inner in _ANCHOR_RE.findall(text):
            url = urllib.parse.urljoin(src["url"], html.unescape(href))
            title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
            if not link_re.search(url) or len(title) < 8 or url in seen:
                continue
            seen.add(url)
            out.append({"title": title, "url": url, "summary": "", "published": None, "source": src["slug"]})
    else:
        for _tag, block in _ITEM_RE.findall(text):
            title = _field(block, "title")
            link = _field(block, "link")
            if not link and (m := _ATOM_LINK_RE.search(block)):
                link = m.group(1)
            link = unwrap(link)
            if not title or not link.startswith("http"):
                continue
            when = None
            for key in ("pubDate", "date", "published", "updated"):
                if value := _field(block, key):
                    when = _when(value)
                    if when:
                        break
            out.append({"title": title, "url": link, "summary": (_field(block, "description") or _field(block, "summary"))[:500],
                        "published": when, "source": src["slug"]})
    return out[: int(src.get("max_items") or 80)]


def _when(value: str) -> datetime | None:
    from email.utils import parsedate_to_datetime  # noqa: PLC0415

    value = (value or "").strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return parse_time(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=JST)


def hit_key(kind: str, name: str) -> str:
    return f"{kind}:{norm(name)}"


def detect(items: list[dict], sources: dict[str, dict], cfg: dict | None = None, now: datetime | None = None) -> dict[str, dict]:
    """見出しの一覧 → 事故の候補（会社＋種類ごとに1つ。複数の発信元の見出しをまとめる）"""
    cfg = cfg or CONFIG
    now = now or datetime.now(UTC)
    oldest = now - timedelta(days=int(cfg["max_age_days"]))
    hits: dict[str, dict] = {}
    for item in items:
        src = sources.get(item["source"]) or {}
        kind = classify(item["title"], item.get("summary") or "", cfg)
        if src.get("kind") and kind is None and not cfg["_exclude_re"].search(nfkc(item["title"])):
            kind = src["kind"]  # 消費者庁のリコール情報は、題名に語が無くても回収の一覧
        if not kind:
            continue
        if item.get("published") and item["published"] < oldest:
            continue
        name = extract_company(item["title"], src)
        if not name:
            continue
        # 規模は見出しの数字を先に（要約には委託先全体の件数など別の数字が混ざる）
        scale = parse_scale(item["title"]) or parse_scale(item.get("summary") or "")
        raw_name = name
        name, group = canonical(name, cfg)
        key = hit_key(kind, name)
        hit = hits.setdefault(key, {"key": key, "kind": kind, "name": name, "aliases": [], "scale": 0, "scaleText": "",
                                    "title": item["title"][:200], "discovery": [], "majorOnly": True})
        for alias in [*group, *([raw_name] if raw_name != name else []), *name_aliases(item["title"], name)]:
            if alias not in hit["aliases"]:
                hit["aliases"].append(alias)
        if scale and scale[0] > hit["scale"]:
            hit["scale"], hit["scaleText"] = scale
        hit["majorOnly"] = hit["majorOnly"] and bool(src.get("major_only"))
        if not any(d["url"] == item["url"] for d in hit["discovery"]):
            hit["discovery"].append({"source": item["source"], "url": item["url"], "title": item["title"][:200],
                                     "publishedAt": iso(item.get("published")), "official": bool(src.get("official"))})
    return hits


def significant(hit: dict, cfg: dict | None = None) -> tuple[bool, str]:
    """記事にする大きさか。(はい/いいえ, 理由)。大きい＝件数が下限以上・全国で知られた名前・2つ以上の発信元が伝えた"""
    cfg = cfg or CONFIG
    major = is_major_name(hit["name"], hit.get("aliases"), cfg)
    outlets = {d["source"] for d in hit.get("discovery") or []}
    if hit.get("backfill"):
        return True, "取りこぼしの拾い直し"
    if hit.get("majorOnly") and not major:
        return False, "全国で知られた名前ではない（消費者庁の一覧の小さな回収）"
    if hit["kind"] == "breach" and hit.get("scale", 0) >= int(cfg["min_scale"]):
        return True, f"規模 {hit.get('scaleText')}"
    if major:
        return True, "全国で知られた名前"
    if len(outlets) >= 2 and (not hit.get("scale") or hit["scale"] >= int(cfg["min_scale_multi"])):
        return True, f"{len(outlets)}つの発信元が伝えた"
    if hit["kind"] == "breach" and hit.get("scale"):
        return False, f"規模が小さい（{hit.get('scaleText')}・下限 {cfg['min_scale']:,}）"
    return False, "規模が分からず、伝えた発信元も1つだけ"


# --------------------------------------------------------------------------- #
# 3. もう記事があるか
# --------------------------------------------------------------------------- #
def load_articles(days: int, now: datetime | None = None, articles_dir: Path | None = None) -> list[dict]:
    now = now or datetime.now(UTC)
    since = now - timedelta(days=days)
    rows = []
    for path in sorted((articles_dir or ARTICLES_DIR).glob("*.json")):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        at = parse_time(data.get("publishedAt") or data.get("generatedAt"))
        made = parse_time(data.get("generatedAt") or data.get("publishedAt"))
        if not at or max(at, made or at) < since:
            continue
        urls = [str(data.get("sourceUrl") or "")] + [str(s.get("url") or "") for s in data.get("sources") or [] if isinstance(s, dict)]
        rows.append({"slug": data.get("slug") or path.stem, "title": str(data.get("title") or ""), "seoTitle": str(data.get("seoTitle") or ""),
                     "urls": [u for u in urls if u], "publishedAt": at, "madeAt": made or at,
                     "sourcePublishedAt": parse_time(data.get("sourcePublishedAt")), "detectedAt": parse_time(data.get("detectedAt")),
                     "incident": data.get("incident") if isinstance(data.get("incident"), dict) else None})
    return rows


def _url_key(url: str) -> str:
    parts = urllib.parse.urlsplit((url or "").strip())
    return f"{parts.netloc.lower().removeprefix('www.')}{parts.path.rstrip('/')}"


SHARED_HOST_SUFFIXES = (".go.jp", ".lg.jp", "tdnet.info", "irdirect.jp", "eir-parts.net", "irpocket.com", "prtimes.jp", "amazonaws.com", "cloudfront.net")


def _site(url: str) -> str:
    """会社のサイトの単位（ホスト名）。官公庁の一覧・適時開示・IR の置き場など、何社もが載る共用のホストは空（同じ会社とみなさない）"""
    host = urllib.parse.urlsplit((url or "").strip()).netloc.lower().removeprefix("www.")
    return "" if host.endswith(SHARED_HOST_SUFFIXES) else host


def names_of(hit: dict) -> list[str]:
    return [n for n in dict.fromkeys([hit.get("name") or "", *(hit.get("aliases") or [])]) if n]


def covered(hit: dict, articles: list[dict], official_url: str = "", announced: datetime | None = None,
            cfg: dict | None = None) -> str | None:
    """同じ事故の記事がもうあれば、その slug。
    (1) 出典の URL が同じ (2) 題名に会社の名前と同じ種類の事故の語 (3) 同じ会社のサイトが出典で、題名に同じ種類の事故の語。
    (2)(3) は、公式のお知らせが記事を作った後に出たもの（第2報など）なら当てない（速報レーンが続報か新しい記事かを決める）"""
    cfg = cfg or CONFIG
    kind_re = cfg["types"][hit["kind"]]["_re"]
    key = _url_key(official_url) if official_url else ""
    site = _site(official_url) if official_url else ""
    for a in articles:
        if key and any(_url_key(u) == key for u in a["urls"]):
            return a["slug"]
    if hit.get("followup") and not key:
        return None  # 続きの知らせ（第2報など）は、公式のお知らせの URL と日付が分かってから比べる
    for a in articles:
        if announced and announced > a["madeAt"]:
            continue
        head = f"{a['title']} {a['seoTitle']}"
        if not kind_re.search(nfkc(head)):
            continue
        if any(public_interest.contains_term(n, head) for n in names_of(hit)):
            return a["slug"]
        if site and any(_site(u) == site for u in a["urls"][:1]):
            return a["slug"]
    return None


# --------------------------------------------------------------------------- #
# 4. 会社自身のお知らせ（公式の一次情報）を探す
# --------------------------------------------------------------------------- #
def official_candidate(url: str, cfg: dict | None = None) -> bool:
    """公式の一次情報として読んでよい URL か（https・会社/官公庁のドメイン・報道/配信/SNS/ブログ/見つけるための発信元ではない）"""
    cfg = cfg or CONFIG
    if not fast_lane.manual_official_url(url):
        return False
    host = urllib.parse.urlsplit(url).netloc.lower()
    return not any(fast_lane._host_in(host, bad) for bad in cfg["not_official_hosts"])


_LISTING_WORDS = {"jp", "ja", "ja-jp", "japan", "news", "newsrelease", "info", "information", "topics", "notice", "notices", "press",
                  "release", "company", "corporate", "corp", "ir", "announcement", "important", "oshirase", "index.html", "index.php", "top"}


def is_home(url: str) -> bool:
    """トップページ・お知らせの一覧（1つのお知らせのページではない）。ここからは「お詫び・不正アクセス・回収」のリンクを辿る"""
    parts = urllib.parse.urlsplit(url)
    if parts.query:
        return False
    segments = [seg.lower() for seg in parts.path.split("/") if seg]
    return len(segments) <= 2 and all(seg in _LISTING_WORDS for seg in segments)


_DATE_RE = re.compile(r"(20\d{2})\s?[年./]\s?(\d{1,2})\s?[月./]\s?(\d{1,2})\s?日?")
_WAREKI_RE = re.compile(r"令和\s?(\d{1,2}|元)\s?年\s?(\d{1,2})\s?月\s?(\d{1,2})\s?日")


def text_date(text: str, now: datetime) -> datetime | None:
    """お知らせの本文の最初のほうにある日付から読んだ発表の日（推定。今日より先・60日より前の日付は使わない）。その日の 0:00（日本時間）で返す"""
    head = nfkc(text or "")[:1500]
    found = []
    for m in _DATE_RE.finditer(head):
        found.append((m.start(), int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in _WAREKI_RE.finditer(head):
        year = 2018 + (1 if m.group(1) == "元" else int(m.group(1)))
        found.append((m.start(), year, int(m.group(2)), int(m.group(3))))
    best = None
    for _pos, year, month, day in found:
        try:
            when = datetime(year, month, day, tzinfo=JST)  # 日付だけ＝その日の始まり（日本時間）。速さを良く見せない側に倒す
        except ValueError:
            continue
        # お知らせは、中に書いた出来事の日より前には出せない。最初のほうにある日付のうち、今日までのいちばん新しい日を発表の日とみなす
        if now - timedelta(days=60) <= when <= now and (best is None or when > best):
            best = when
    return best


FIRST_PERSON_RE = re.compile(r"当社|弊社|当行|当金庫|当組合|当法人|当協会|当機構|当会|当院|当館|当店|当グループ|私ども|当市|当町|当県|本市|本県")
APOLOGY_RE = re.compile(r"お詫び申し上げ|おわび申し上げ|ご迷惑(?:と|・|、)?ご心配|ご心配(?:と|・|、)?ご迷惑|ご愛顧|平素より")
CUSTOMER_RE = re.compile(r"お客(?:様|さま)")
THIRD_PARTY_RE = re.compile(r"(?:と|を)(?:発表|公表)した|を明らかにした|明らかになった|と報じ|によると、|編集部|記者")


def first_party(page: dict, url: str = "") -> bool:
    """会社・団体が自分のこととして出したお知らせか（「当社」「弊社」と書いている。ほかの会社のブログ・ニュースの
    「〇〇は…と発表した」という書き方は公式のお知らせではない。官公庁・自治体のページはそのまま公式）"""
    host = urllib.parse.urlsplit(url or "").netloc.lower()
    if host.endswith((".go.jp", ".lg.jp")):
        return True
    text = nfkc(f"{page.get('title') or ''}\n{page.get('text') or ''}")
    own_voice = FIRST_PERSON_RE.search(text) or (APOLOGY_RE.search(text) and CUSTOMER_RE.search(text))
    return bool(own_voice) and not THIRD_PARTY_RE.search(text[:800])


def page_ok(page: dict, hit: dict, cfg: dict | None = None, same_site: bool = False, url: str = "") -> bool:
    """公式のお知らせとして使えるか: 本文に事故の語があり、会社の名前（言い換えを含む）があり、会社が自分のこととして書いている。
    same_site（その会社のトップから辿ったリンク・適時開示の項目）は名前と書き手の確認を省く（自社のお知らせは社名を「当社」と書くことが多い）"""
    cfg = cfg or CONFIG
    text = nfkc(f"{page.get('title') or ''}\n{page.get('text') or ''}")
    if len(text) < 300 or not cfg["types"][hit["kind"]]["_re"].search(text):
        return False
    if same_site:
        return True
    return any(public_interest.contains_term(n, text) for n in names_of(hit)) and first_party(page, url)


def url_date(url: str, now: datetime) -> datetime | None:
    """URL に入っている日付（…/2026_1104_02・…/261028.html・…/20261112-02.html）。お知らせを出した日であることが多い"""
    path = urllib.parse.urlsplit(url or "").path
    for m in re.finditer(r"(?<!\d)(20\d{2})[-_/.]?(0[1-9]|1[0-2])[-_/.]?(0[1-9]|[12]\d|3[01])|(?<!\d)(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)", path):
        year = int(m.group(1)) if m.group(1) else 2000 + int(m.group(4))
        month, day = (int(m.group(2)), int(m.group(3))) if m.group(1) else (int(m.group(5)), int(m.group(6)))
        try:
            when = datetime(year, month, day, tzinfo=JST)
        except ValueError:
            continue
        if now - timedelta(days=60) <= when <= now:
            return when
    return None


def announced_of(page: dict, now: datetime, url: str = "") -> tuple[datetime | None, str]:
    """発表の時刻と確かさ（time＝ページに時刻つきで書かれている / date＝日付だけ / ""＝分からない）。
    日付だけのときは、ページの公開日 → URL の日付 → 本文のいちばん上の日付 → 本文の最初のほうでいちばん新しい日付 の順"""
    import feeds  # noqa: PLC0415

    when = feeds.page_published(page)
    if when and now - timedelta(days=60) <= when <= now + timedelta(days=1):
        exact = bool(re.search(r"T\d{2}:\d{2}", str(page.get("published") or ""))) and (when.hour, when.minute) != (0, 0)
        if exact:
            return when, "time"
        day = when.astimezone(JST)
        return datetime(day.year, day.month, day.day, tzinfo=JST), "date"
    if when := url_date(url, now):
        return when, "date"
    body = f"{page.get('title') or ''}\n{page.get('text') or ''}"
    head = _DATE_RE.search(nfkc(page.get("text") or "")[:120])
    if head and (when := text_date(head.group(0), now)):
        return when, "date"  # いちばん上の日付（お知らせの頭に書く発表の日）
    when = text_date(body, now)
    return (when, "date") if when else (None, "")


def resolve_official(hit: dict, fetch_page, cfg: dict | None = None, now: datetime | None = None, max_fetch: int = 8) -> dict | None:
    """会社自身のお知らせを探す。見つかれば {url, via, announcedAt, precision, chars}。fetch_page(url) -> {text, links, title, published}。
    順番: 公式の発信元（適時開示・官公庁の一覧）の項目 → 取りこぼし一覧の official → 見つけた記事の中のリンク →
    会社のトップ/お知らせ一覧（home・記事の中のトップへのリンク）の「お詫び・不正アクセス・回収」のリンク"""
    cfg = cfg or CONFIG
    now = now or datetime.now(UTC)
    anchor_re = cfg["types"][hit["kind"]]["_anchor_re"]
    budget = [max_fetch]

    def get(url: str) -> dict | None:
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        try:
            return fetch_page(url)
        except Exception as error:  # noqa: BLE001 - 読めないページは飛ばして次を探す
            log(f"   [incident] 読めない: {url[:90]}（{str(error)[:80]}）")
            return None

    def accept(url: str, page: dict, via: str) -> dict:
        when, precision = announced_of(page, now, url)
        scale = parse_scale((page.get("text") or "")[:4000])
        return {"url": url, "via": via, "announcedAt": iso(when), "precision": precision, "chars": len(page.get("text") or ""),
                "title": re.sub(r"\s+", " ", str(page.get("title") or "")).strip()[:120],
                "scale": scale[0] if scale else 0, "scaleText": scale[1] if scale else ""}

    def try_direct(url: str, via: str, same_site: bool = False) -> dict | None:
        if not official_candidate(url, cfg) or is_home(url):
            return None
        page = get(url)
        if page and page_ok(page, hit, cfg, same_site=same_site, url=url):
            return accept(url, page, via)
        return None

    def try_home(home: str, via: str) -> dict | None:
        if not official_candidate(home, cfg):
            return None
        page = get(home)
        if not page:
            return None
        site = _site(home)
        for link in page.get("links") or []:
            url, text = str(link.get("url") or ""), nfkc(str(link.get("text") or ""))
            if url.startswith("http://") and _site(url) == site:
                url = "https://" + url[len("http://"):]  # 同じサイトの中の古い書き方のリンク
            if not anchor_re.search(text) or not url.startswith("https://") or url.rstrip("/") == home.rstrip("/"):
                continue
            other = _site(url)
            same = bool(site and other) and (other == site or other.endswith("." + site) or site.endswith("." + other))
            if found := try_direct(url, via, same_site=same):
                return found
        return None

    for d in hit.get("discovery") or []:
        if d.get("official") and (found := try_direct(d["url"], f"公式の発信元（{d['source']}）", same_site=True)):
            return found
    if hit.get("official") and (found := try_direct(hit["official"], "取りこぼし一覧の公式 URL")):
        return found
    homes: list[str] = [hit["home"]] if hit.get("home") else []
    for d in hit.get("discovery") or []:
        if d.get("official"):
            continue
        page = get(d["url"])
        if not page:
            continue
        links = [str(l.get("url") or "") for l in page.get("links") or [] if l.get("main") or True]
        direct = [u for u in dict.fromkeys(links) if official_candidate(u, cfg) and not is_home(u)]
        # 記事の本文の中のリンクを先に（メニュー・広告のリンクより前）。名前と事故の語で確かめるので、違うページは通らない
        direct.sort(key=lambda u: 0 if re.search(r"\.pdf$|news|info|notice|press|release|topics|important|oshirase|owabi", u, re.I) else 1)
        for url in direct[:5]:
            if found := try_direct(url, f"{d['source']} の記事の中のリンク"):
                return found
        homes += [u for u in dict.fromkeys(links) if official_candidate(u, cfg) and is_home(u)]
    for home in list(dict.fromkeys(homes))[:3]:
        if found := try_home(home, "会社のサイトのお知らせ"):
            return found
    return None


# --------------------------------------------------------------------------- #
# 5. 速報レーンに渡す形・記事の書き方
# --------------------------------------------------------------------------- #
PROMPT_NOTE = """

## 「自分は対象か」に答える記事の形（必ず守る。事故の見張り scripts/incident_watch.py・台帳 W44）
この記事を開く人は「自分は対象か・何をすればいいか」を確かめに来る。記事の型の中で、次の順に書く
（資料＝公式のお知らせにあることだけ。資料に無い項目は作らず、まだ発表されていないことは1回だけそう書く）:
1. 対象の条件の表: 対象になる人・製品（サービス名・会員の種類・入会/購入/利用の時期・型番やロット・件数）と、対象でないと書かれている人を、最初の章に Markdown の表で置く。
2. 連絡の届き方・窓口: 会社からの連絡の方法（メール・郵便・アプリなど）と時期、問い合わせ窓口（名前・電話番号・受付時間・URL は資料にあるものだけ）。
3. 今やること: 読者が今日できること（資料にあるもの。パスワードの変更・カードの明細の確認・不審なメールへの注意・使用の中止と回収の申し込みなど）。
4. 経緯: いつ何が起きて、いつ分かり、いつ発表したか（日付は資料のとおり）。
- 件数・台数・金額は、公式の資料に書かれた数字だけを、資料の言い方（最大・約・可能性がある）のまま書く。報道やほかのサイトの数字は書かない。
- 題名は「会社・サービスの名前＋何が起きたか＋対象の条件か今やること」。「自分は対象か」を調べる人が検索する言葉（会社名＋情報流出／リコール／回収／障害）を前に置く。
- 流出した「可能性」と「確認された」を混ぜない。原因・犯人・被害額を推測しない。"""


def prompt_note(incident: dict | None) -> str:
    return PROMPT_NOTE if incident else ""


def fast_id(key: str) -> str:
    return "incident-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def build_meta(entry: dict, cfg: dict | None = None, now: datetime | None = None) -> dict:
    """速報レーンに渡す fast_meta の1件（scripts/web_articles.py build_fast_items が incident を読む）"""
    cfg = cfg or CONFIG
    spec = cfg["types"][entry["kind"]]
    label = spec["label"]
    # 見つけた記事（報道）の件数は渡さない（数字は公式のお知らせからだけ書かせる）
    meta = {
        "id": fast_id(entry["key"]), "url": entry["officialUrl"],
        "title": (entry.get("officialTitle") or f"{entry['name']}の{label}に関するお知らせ")[:120], "sourceName": entry["name"], "lang": "ja",
        "detectedAt": entry.get("detectedAt") or iso(now or datetime.now(UTC)), "genre": spec["genre"],
        "incident": {"key": entry["key"], "kind": entry["kind"], "name": entry["name"],
                     "discoveredAt": entry.get("discoveredAt") or "", "backfill": bool(entry.get("backfill"))},
    }
    if entry.get("announcedAt"):
        # 日付だけ分かるときは、その日の 0:00（日本時間）を発表の時刻として渡す（48時間を超えた発表を「速報ではない」形にするため。
        # 本当の発表はそれより後なので、「発表から◯分」が実際より短く出ることはない）
        meta["publishedAt"] = entry["announcedAt"]
        meta["incident"]["dateOnly"] = entry.get("precision") != "time"
    return meta


def press_term(entry: dict, cfg: dict | None = None) -> str:
    cfg = cfg or CONFIG
    return f"{entry['name']} {cfg['types'][entry['kind']]['label']}"


def press_queue_item(entry: dict, cfg: dict | None = None, now: datetime | None = None) -> dict:
    """話題キュー（state/trend_queue.json）に足す1件。話題のレーンが、主要な報道機関の独立した2社以上が同じ事実を伝えているときだけ、
    報道と明記した短い記事にする（scripts/trend_lane.py の決まりそのまま。見つけた記事は公式のリンクを探すためだけに読まれる）"""
    import trends  # noqa: PLC0415

    now = now or datetime.now(UTC)
    term = press_term(entry, cfg)
    return {
        "id": trends.make_id(term, now), "kind": "trend", "url": (entry.get("discovery") or [{}])[0].get("url", ""),
        "title": term, "summary": f"事故の見張りが見つけた話題（{entry.get('title', '')[:80]}）。公式のお知らせは未確認。",
        "published_at": now.astimezone(JST).isoformat(), "source_name": "事故の見張り", "source_slug": "trends", "lang": "ja", "image": None,
        "genre": cfg["types"][entry["kind"]]["genre"] if cfg else "public", "traffic": PRESS_TRAFFIC, "incident": entry["key"],
        "sources": [{"title": d.get("title") or "", "url": d["url"], "source": d.get("source") or "", "published": d.get("publishedAt") or ""}
                    for d in entry.get("discovery") or [] if not d.get("official")][:4],
        "queued_at": now.astimezone(JST).isoformat(),
    }


# --------------------------------------------------------------------------- #
# 6. state（待ち・結果・時刻の記録）
# --------------------------------------------------------------------------- #
def load_state(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or STATE_PATH).read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("items", {})
    data.setdefault("seen", {})
    return data


def save_state(data: dict, now: datetime | None = None, path: Path | None = None) -> None:
    now = now or datetime.now(UTC)
    keep_items = now - timedelta(days=KEEP_DAYS)
    keep_seen = now - timedelta(days=SEEN_KEEP_DAYS)
    items = {k: v for k, v in data["items"].items() if (parse_time(v.get("detectedAt")) or now) >= keep_items}
    seen = {k: v for k, v in data["seen"].items() if (parse_time(v) or now) >= keep_seen}
    out = {"updated": iso(now), "items": dict(sorted(items.items())), "seen": dict(sorted(seen.items()))}
    target = path or STATE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", "utf-8")


def dispatched_today(state: dict, now: datetime) -> int:
    today = now.astimezone(JST).date()
    return sum(1 for e in state["items"].values()
               if (at := parse_time(e.get("firstDispatchedAt"))) and at.astimezone(JST).date() == today)


def settle(state: dict, acks: dict, articles: list[dict], live: dict, now: datetime, cfg: dict | None = None) -> list[str]:
    """速報レーンの結果（state/fast_lane.json）と記事・公開の記録から、待ちの項目の結果と時刻を埋める"""
    cfg = cfg or CONFIG
    notes: list[str] = []
    by_slug = {a["slug"]: a for a in articles}
    for entry in state["items"].values():
        if entry.get("status") in ("dispatched", "queued"):
            ack = (acks.get("items") or {}).get(fast_id(entry["key"]))
            if ack and (parse_time(ack.get("finishedAt")) or now) >= (parse_time(entry.get("dispatchedAt")) or now):
                outcome = ack.get("outcome")
                if outcome in ("created", "updated") and ack.get("slug"):
                    entry.update(status="published", slug=ack["slug"], updatedExisting=outcome == "updated", reason="")
                    notes.append(f"公開: {entry['name']} → {ack['slug']}{'（既存の記事に続報）' if outcome == 'updated' else ''}")
                elif outcome == "duplicate":
                    entry.update(status="covered", slug=ack.get("slug") or "", reason=f"速報レーンが重複と判定: {ack.get('reason', '')}"[:200])
                elif outcome == "skipped":
                    entry.update(status="failed", reason=f"速報レーンが見送り: {ack.get('reason', '')}"[:200])
                    notes.append(f"作れなかった: {entry['name']}（{entry['reason']}）")
                elif outcome == "capped":
                    entry.update(status="queued", reason="速報レーンの1日の上限")
                # retry は dispatched のまま（下の起こし直しに任せる）
        if entry.get("status") == "press":
            term = press_term(entry, cfg)
            for a in articles:
                if a["madeAt"] >= (parse_time(entry.get("detectedAt")) or now) - timedelta(hours=1) and public_interest.contains_term(entry["name"], a["title"]) \
                        and cfg["types"][entry["kind"]]["_re"].search(nfkc(a["title"])):
                    entry.update(status="published", slug=a["slug"], reason=f"報道の決まりで作った（{term}）")
                    notes.append(f"公開（報道の決まり）: {entry['name']} → {a['slug']}")
                    break
        if entry.get("status") == "published" and entry.get("slug"):
            a = by_slug.get(entry["slug"])
            if a and not entry.get("publishedAt"):
                entry["publishedAt"] = iso(a["madeAt"])
            if not entry.get("liveAt"):
                entry["liveAt"] = str(((live.get("live") or {}).get(entry["slug"]) or {}).get("liveAt") or "")
    return notes


# --------------------------------------------------------------------------- #
# 7. 見張りの本体
# --------------------------------------------------------------------------- #
def gather(cfg: dict, fetch_bytes) -> tuple[list[dict], dict[str, dict], list[str]]:
    items: list[dict] = []
    errors: list[str] = []
    sources = {s["slug"]: s for s in cfg["discovery"]}
    for src in cfg["discovery"]:
        try:
            data = fetch_bytes(src["url"])
            rows = parse_source(src, data) if data else []
        except Exception as error:  # noqa: BLE001 - 1つ読めなくてもほかで続ける
            rows = []
            errors.append(f"{src['slug']}: {str(error)[:80]}")
        if not rows:
            errors.append(f"{src['slug']}: 項目が読めない") if not any(e.startswith(src["slug"]) for e in errors) else None
        items.extend(rows)
    return items, sources, errors


def merge_backfill(backfill: dict[str, dict], hits: dict[str, dict]) -> dict[str, dict]:
    """取りこぼしの一覧と、この回に見つけた候補を合わせる（同じ会社は1つに。一覧の印・会社のサイト・公式の URL を残し、見つけた見出しを足す）"""
    out = dict(backfill)
    for key, hit in hits.items():
        if key not in out:
            out[key] = hit
            continue
        base = out[key]
        merged = {**hit, **{k: v for k, v in base.items() if v not in ("", [], 0, None)}}
        merged["discovery"] = base.get("discovery", []) + [d for d in hit.get("discovery", []) if d["url"] not in {x["url"] for x in base.get("discovery", [])}]
        merged["aliases"] = list(dict.fromkeys([*base.get("aliases", []), *hit.get("aliases", [])]))
        merged["scale"], merged["scaleText"], merged["title"] = hit.get("scale", 0), hit.get("scaleText", ""), hit.get("title") or base.get("title", "")
        merged["backfill"], merged["majorOnly"] = True, False
        out[key] = merged
    return out


def backfill_hits(cfg: dict) -> dict[str, dict]:
    hits = {}
    for b in cfg.get("backfill") or []:
        key = hit_key(b["kind"], b["name"])
        hits[key] = {"key": key, "kind": b["kind"], "name": b["name"], "aliases": list(b.get("aliases") or []), "scale": 0, "scaleText": "",
                     "title": f"{b['name']}（取りこぼしの拾い直し）", "home": b.get("home") or "", "official": b.get("official") or "",
                     "backfill": True, "majorOnly": False,
                     "discovery": ([{"source": "backfill", "url": b["discovery"], "title": "", "publishedAt": "", "official": False}]
                                   if b.get("discovery") else [])}
    return hits


FOLLOWUP_GAP_HOURS = 12
OUTAGE_SOURCE_FLOOR = 600  # scripts/web_articles.py の MIN_TEXT_CHARS と同じ


def source_floor(kind: str) -> int:
    """速報レーンが書く公式の資料の長さの下限（情報流出・回収は公共性の枠の下限、障害はふつうの下限）"""
    return public_interest.MIN_SOURCE_CHARS if kind in ("breach", "recall") else OUTAGE_SOURCE_FLOOR


def _new_entry(hit: dict, now: datetime, cfg: dict) -> dict:
    ok, why = significant(hit, cfg)
    first = min((t for d in hit["discovery"] if (t := parse_time(d.get("publishedAt")))), default=None)
    # 適時開示・官公庁の一覧の項目は、規模が見出しに無くても、公式の資料を読んでから大きさを決める
    need_scale = not ok and why.startswith("規模が分からず") and any(d.get("official") for d in hit["discovery"])
    return {**{k: v for k, v in hit.items() if k != "majorOnly"}, "detectedAt": iso(now), "discoveredAt": iso(first),
            "status": "new" if ok or need_scale else "skipped", "reason": "" if ok or need_scale else why,
            "needScale": need_scale, "tries": 0, "dispatches": 0}


def step(state: dict, hits: dict[str, dict], articles: list[dict], fetch_page, cfg: dict, now: datetime, max_resolve: int = 12) -> list[str]:
    """新しい候補を state に入れ、記事の有無 → 公式のお知らせ探し まで進める（速報レーンを起こす前まで）"""
    notes: list[str] = []
    resolved = 0
    for key, hit in hits.items():
        entry = state["items"].get(key)
        if entry is None:
            state["items"][key] = _new_entry(hit, now, cfg)
            continue
        fresh = [d for d in hit["discovery"] if not any(x["url"] == d["url"] for x in entry.get("discovery") or [])]
        if hit.get("backfill"):
            if entry.get("status") in ("skipped", "failed", "press"):
                entry.update(status="new", backfill=True, tries=0, home=hit.get("home") or entry.get("home", ""),
                             official=hit.get("official") or entry.get("official", ""), aliases=hit.get("aliases") or entry.get("aliases") or [])
            continue
        if entry.get("status") in ("covered", "published") and fresh:
            # もう記事がある会社の新しい見出し: 前の検知から時間がたっていれば「続きの知らせ」（第2報・件数の確定など）として別に確かめる。
            # 無印良品は第2報（11/4）で約109万件のカード番号が出た。公式のお知らせが記事より新しいときだけ速報レーンに回す
            base = parse_time(entry.get("detectedAt")) or now
            newest = max((t for d in fresh if (t := parse_time(d.get("publishedAt")))), default=now)
            if newest - base >= timedelta(hours=FOLLOWUP_GAP_HOURS):
                fkey = f"{key}#{newest.astimezone(JST):%Y%m%d}"
                if fkey not in state["items"]:
                    follow = _new_entry({**hit, "key": fkey, "discovery": fresh, "aliases": entry.get("aliases") or hit.get("aliases") or []}, now, cfg)
                    follow.update(followup=True, home=entry.get("home", ""), status="new", reason="", needScale=False)
                    state["items"][fkey] = follow
            continue
        entry.setdefault("discovery", []).extend(fresh)
        for alias in hit.get("aliases") or []:
            if alias not in entry.setdefault("aliases", []):
                entry["aliases"].append(alias)
        if hit.get("scale", 0) > entry.get("scale", 0):
            entry["scale"], entry["scaleText"] = hit["scale"], hit["scaleText"]
        if entry.get("status") == "skipped" and str(entry.get("reason", "")).startswith("規模"):
            # 小さい・分からないと見送ったものを、別の発信元も伝えた・規模が分かったときに拾い直す
            ok, _why = significant({**entry, "majorOnly": hit.get("majorOnly", False)}, cfg)
            if ok:
                entry.update(status="new", reason="")
    for key, entry in state["items"].items():
        if entry.get("status") not in ("new", "press"):
            continue
        label = cfg["types"][entry["kind"]]["label"]
        if entry["status"] == "new" and not entry.get("discoveredAt") and not entry.get("backfill") and resolved < max_resolve:
            # 日付の無い一覧（消費者庁のリコール情報）の項目: 項目のページの日付（対応開始日）を読む。古い・読めないものは拾わない
            resolved += 1
            when = None
            for d in entry.get("discovery") or []:
                try:
                    page = fetch_page(d["url"])
                except Exception:  # noqa: BLE001
                    continue
                when = text_date(f"{page.get('title') or ''}\n{page.get('text') or ''}", now)
                if when:
                    d["publishedAt"] = iso(when)
                    break
            if not when or now - when > timedelta(days=int(cfg["max_age_days"])):
                entry.update(status="skipped", reason="発表の日が分からない・古い（一覧の上に固定された項目など）")
                continue
            entry["discoveredAt"] = iso(when)
        if slug := covered(entry, articles, cfg=cfg):
            entry.update(status="covered", slug=slug, reason="同じ事故の記事がある")
            notes.append(f"記事あり: {entry['name']} → {slug}")
            continue
        if entry.get("tries", 0) >= int(cfg["official_tries"]) or resolved >= max_resolve:
            continue
        resolved += 1
        entry["tries"] = entry.get("tries", 0) + 1
        found = resolve_official(entry, fetch_page, cfg, now)
        if not found:
            if entry.get("followup") or entry.get("needScale"):
                entry.update(status="skipped", reason="公式のお知らせが見つからない（続きの知らせ・規模の分からない開示）")
            elif entry["status"] == "new":
                entry.update(status="press", reason="公式のお知らせが見つからない（報道の決まりで作れるか話題のレーンに回す）")
                notes.append(f"公式なし: {entry['name']}（{label}）→ 話題のレーンへ")
            continue
        announced = parse_time(found["announcedAt"])
        entry.update(officialUrl=found["url"], officialTitle=found.get("title") or "", announcedAt=found["announcedAt"],
                     precision=found["precision"], via=found["via"])
        floor = source_floor(entry["kind"])
        if found.get("chars", 0) < floor:
            # 速報レーンは、公式の資料がこの字数より短いと書かない（水増しになるため。scripts/public_interest.py MIN_SOURCE_CHARS・
            # scripts/web_articles.py MIN_TEXT_CHARS）。起こしても見送りになるだけなので、ここで止めて理由を残す
            entry.update(status="skipped", reason=f"公式のお知らせが短い（{found.get('chars', 0)}字。速報レーンの下限 {floor}字）")
            notes.append(f"公式が短い: {entry['name']}（{label}）{found.get('chars', 0)}字 → {found['url']}")
            continue
        if entry.get("needScale"):
            major = is_major_name(entry["name"], entry.get("aliases"), cfg)
            if not major and found.get("scale", 0) < int(cfg["min_scale"]):
                entry.update(status="skipped", reason=f"規模が小さい・分からない（公式の資料: {found.get('scaleText') or '件数なし'}）")
                continue
        if slug := covered(entry, articles, found["url"], announced, cfg):
            entry.update(status="covered", slug=slug, reason="同じ事故の記事がある（公式のお知らせで確認）")
            notes.append(f"記事あり: {entry['name']} → {slug}")
            continue
        first_seen = parse_time(entry.get("discoveredAt"))
        if not announced and not first_seen and not entry.get("backfill"):
            # 発表の日も、他社が伝えた日も分からない（官公庁の一覧の上に固定された古い項目など）。古い事故を今日の話として出さない
            entry.update(status="skipped", reason="発表の日が分からない")
            continue
        if entry.get("followup") and not announced:
            entry.update(status="skipped", reason="続きの知らせの日付が分からない（前の記事より新しいと確かめられない）")
            continue
        if announced and now - announced > timedelta(days=int(cfg["max_age_days"])):
            entry.update(status="skipped", reason=f"発表から{(now - announced).days}日（{cfg['max_age_days']}日より古い）")
            continue
        entry.update(status="queued", reason="")
        notes.append(f"公式あり: {entry['name']}（{label}）→ {found['url']}（{found['via']}）")
    return notes


def pick_dispatch(state: dict, cfg: dict, now: datetime) -> list[dict]:
    """いま速報レーンに渡す項目（大きい順・新しい順）。待ちの項目は、redispatch_minutes たって結果が無ければもう一度（max_dispatches まで）"""
    left = int(cfg["daily_max"]) - dispatched_today(state, now)
    wait = timedelta(minutes=int(cfg["redispatch_minutes"]))
    ready = []
    for entry in state["items"].values():
        if entry.get("status") == "queued":
            ready.append(entry)
        elif entry.get("status") == "dispatched" and now - (parse_time(entry.get("dispatchedAt")) or now) >= wait:
            if entry.get("dispatches", 0) >= int(cfg["max_dispatches"]):
                entry.update(status="failed", reason=f"速報レーンを{entry.get('dispatches')}回起こしても記事にならなかった")
            else:
                ready.append(entry)
    # 取りこぼしの拾い直し → 大きい順 → 先に見つけた順
    ready.sort(key=lambda e: (0 if e.get("backfill") else 1, -(e.get("scale") or 0), e.get("detectedAt") or ""))
    fresh = [e for e in ready if not e.get("firstDispatchedAt")]
    again = [e for e in ready if e.get("firstDispatchedAt")]
    return (again + fresh[: max(0, left)])[: int(cfg["per_dispatch"])]


def apply_press(state: dict, cfg: dict, now: datetime, processed: dict | None = None) -> int:
    """報道の決まりで作る話題（status=press）を話題キューに足す（もう入っていれば足さない。36時間たったら足さない）"""
    import trends  # noqa: PLC0415

    queue = trends.load_queue()
    have = {q.get("incident") for q in queue} | {trends._norm(q.get("title") or "") for q in queue}
    added = 0
    for entry in state["items"].values():
        if entry.get("status") != "press" or now - (parse_time(entry.get("detectedAt")) or now) > timedelta(hours=36):
            continue
        item = press_queue_item(entry, cfg, parse_time(entry.get("detectedAt")) or now)
        if entry["key"] in have or trends._norm(item["title"]) in have or item["id"] in (processed or {}):
            continue
        queue.append(item)
        have.add(entry["key"])
        added += 1
    if added:
        trends.save_queue(queue)
    return added


def enqueue_external(rows: list[dict], now: datetime | None = None, fetch_page=None, cfg: dict | None = None,
                     state_path: Path | None = None, articles: list[dict] | None = None) -> list[str]:
    """ほかの見張り（毎朝の見逃しチェックの「他社だけの話題」）が見つけた見出しを、同じ流れに入れる。
    rows: [{title, url, source（媒体の名前）, published(datetime|None)}]。事故の型（情報流出・回収・障害）の見出しだけ拾い、
    会社自身のお知らせが見つかれば速報レーン待ち（queued。次の見張りの回がすぐ起こす）、見つからなければ話題のレーンへ。
    戻り値は Issue に書く行（何を回したか・何を回せなかったか）"""
    cfg = cfg or CONFIG
    now = now or datetime.now(UTC)
    items = [{"title": r["title"], "url": r["url"], "summary": "", "published": r.get("published"), "source": r.get("source") or "他社"}
             for r in rows if r.get("title") and r.get("url")]
    hits = detect(items, {}, cfg, now)
    if not hits:
        return []
    state = load_state(state_path)
    before = {k: v.get("status") for k, v in state["items"].items()}
    step(state, hits, articles if articles is not None else load_articles(int(cfg["covered_days"]), now), fetch_page or _fetch_page, cfg, now)
    lines = []
    for key in hits:
        entry = state["items"].get(key) or {}
        status = entry.get("status")
        label = cfg["types"][entry.get("kind") or "breach"]["label"]
        head = f"{entry.get('name', key)}（{label}）"
        if before.get(key) == status and status not in ("queued", "press"):
            lines.append(f"- {head}: 対応済み（{status}{' → ' + entry['slug'] if entry.get('slug') else ''}）")
        elif status == "queued":
            lines.append(f"- {head}: **速報レーンに回しました** → {entry.get('officialUrl')}")
        elif status == "press":
            lines.append(f"- {head}: 会社自身のお知らせが見つからないので、話題のレーン（主要な報道機関2社以上・報道と明記）に回しました")
        elif status == "covered":
            lines.append(f"- {head}: 記事あり → {entry.get('slug')}")
        else:
            lines.append(f"- {head}: 回せませんでした（{entry.get('reason') or status}）")
    if state_path is None or state_path == STATE_PATH:
        apply_press(state, cfg, now)
    save_state(state, now, state_path)
    return lines


# --------------------------------------------------------------------------- #
# 8. 時間の記録（発表 → 他社の初報 → 検知 → 公開）
# --------------------------------------------------------------------------- #
def minutes(a: str, b: str) -> float | None:
    ta, tb = parse_time(a), parse_time(b)
    return round((tb - ta).total_seconds() / 60, 1) if ta and tb else None


def latency_rows(state: dict) -> list[dict]:
    rows = []
    for entry in state["items"].values():
        if entry.get("status") != "published":
            continue
        exact = entry.get("precision") == "time"
        end = entry.get("liveAt") or entry.get("publishedAt") or ""
        rows.append({
            "name": entry["name"], "kind": entry["kind"], "slug": entry.get("slug") or "", "backfill": bool(entry.get("backfill")),
            "announcedAt": entry.get("announcedAt") or "", "announcedExact": exact, "discoveredAt": entry.get("discoveredAt") or "",
            "detectedAt": entry.get("detectedAt") or "", "dispatchedAt": entry.get("firstDispatchedAt") or "", "publishedAt": end,
            # 発表の時刻が日付だけのときは「発表から何分」を出さない（うその速さを書かない）
            "announceToPublish": minutes(entry.get("announcedAt"), end) if exact else None,
            "pressToDetect": minutes(entry.get("discoveredAt"), entry.get("detectedAt")),
            "detectToPublish": minutes(entry.get("detectedAt"), end),
        })
    return sorted(rows, key=lambda r: r["detectedAt"], reverse=True)


def _fmt(value: str) -> str:
    dt = parse_time(value)
    return dt.astimezone(JST).strftime("%m/%d %H:%M") if dt else "不明"


def _min(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.0f}分" if abs(value) < 180 else f"{value / 60:.1f}時間"


def report_markdown(state: dict, cfg: dict | None = None) -> str:
    cfg = cfg or CONFIG
    rows = latency_rows(state)
    counts: dict[str, int] = {}
    for e in state["items"].values():
        counts[e.get("status", "?")] = counts.get(e.get("status", "?"), 0) + 1
    lines = ["### 事故の見張り（自分は対象か）の記録", "",
             "状態: " + " / ".join(f"{k} {v}" for k, v in sorted(counts.items())), "",
             "| 会社 | 種類 | 発表 | 他社の初報 | 検知 | 公開 | 発表→公開 | 初報→検知 | 検知→公開 | 記事 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows[:40]:
        announced = _fmt(r["announcedAt"]) + ("" if r["announcedExact"] or not r["announcedAt"] else "（日付のみ）")
        lines.append(f"| {r['name']}{'（拾い直し）' if r['backfill'] else ''} | {cfg['types'][r['kind']]['label']} | {announced} | {_fmt(r['discoveredAt'])} | "
                     f"{_fmt(r['detectedAt'])} | {_fmt(r['publishedAt'])} | {_min(r['announceToPublish'])} | {_min(r['pressToDetect'])} | "
                     f"{_min(r['detectToPublish'])} | {r['slug']} |")
    if not rows:
        lines.append("| （まだ公開した記事がありません） | | | | | | | | | |")
    lines += ["", "発表の時刻が日付しか分からないものは「発表→公開」を出しません（—）。「公開」は本番で開けた時刻（state/live_log.json）、無ければ記事を作った時刻です。"]
    waiting = [e for e in state["items"].values() if e.get("status") in ("queued", "dispatched", "press", "failed")]
    if waiting:
        lines += ["", "**まだ記事になっていないもの**"]
        for e in sorted(waiting, key=lambda e: e.get("detectedAt") or "", reverse=True)[:30]:
            lines.append(f"- {e['name']}（{cfg['types'][e['kind']]['label']}{' ' + e['scaleText'] if e.get('scaleText') else ''}）: {e['status']}"
                         f"{' / ' + e['reason'] if e.get('reason') else ''}{' / ' + e['officialUrl'] if e.get('officialUrl') else ''}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# 9. 入口
# --------------------------------------------------------------------------- #
def _fetch_bytes(url: str) -> bytes:
    import feeds  # noqa: PLC0415

    return feeds.fetch(url, timeout=20)[0]


def _fetch_page(url: str) -> dict:
    import feeds  # noqa: PLC0415

    if not feeds.robots_allows(url):
        raise RuntimeError("robots.txt で読めないページ")
    return feeds._fetch_direct(url, timeout=20)


def _summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def run(args) -> int:
    import release_watch  # noqa: PLC0415  速報レーンの起こし方（gh workflow run）と実行の確認は同じものを使う

    cfg = CONFIG
    now = datetime.now(UTC)
    state = load_state()
    articles = load_articles(int(cfg["covered_days"]), now)
    try:
        live = json.loads(LIVE_PATH.read_text("utf-8"))
    except (OSError, ValueError):
        live = {}
    notes = settle(state, fast_lane.load_acks(), articles, live, now, cfg)
    items, sources, errors = gather(cfg, _fetch_bytes)
    fresh = []
    for item in items:
        sid = hashlib.sha1(item["url"].encode("utf-8")).hexdigest()[:16]
        if sid not in state["seen"]:
            state["seen"][sid] = iso(now)
            fresh.append(item)
    hits = detect(fresh, sources, cfg, now)
    if args.backfill:
        hits = merge_backfill(backfill_hits(cfg), hits)
    log(f"[incident] 見出し {len(items)} 件（新しいもの {len(fresh)} 件）→ 事故の候補 {len(hits)} 件"
        + (f" / 読めなかった発信元: {' / '.join(errors)}" if errors else ""))
    notes += step(state, hits, articles, _fetch_page, cfg, now)
    batch = pick_dispatch(state, cfg, now)
    if batch and not args.dry_run and not args.no_dispatch:
        metas = [build_meta(e, cfg, now) for e in batch]
        runs = release_watch.fast_runs(metas[0]["url"])
        if any(r.get("status") != "completed" for r in runs):
            log(f"[incident] 同じ URL の速報レーンが待ち・実行中なので起こしません: {metas[0]['url']}")
        else:
            res = release_watch.gh(["workflow", "run", "auto_run.yml", "--ref", "main", "-f", "mode=web", "-f", "max_articles=1",
                                    "-f", f"fast_url={metas[0]['url']}", "-f", f"fast_meta={json.dumps(metas, ensure_ascii=False)}"])
            if res.returncode != 0:
                log(f"::warning::速報レーンを起こせませんでした: {res.stderr.strip()[:200]}")
            else:
                for e in batch:
                    e.update(status="dispatched", dispatchedAt=iso(now), dispatches=e.get("dispatches", 0) + 1)
                    e.setdefault("firstDispatchedAt", iso(now))
                    notes.append(f"速報レーンへ: {e['name']} → {e['officialUrl']}")
    elif batch:
        for e in batch:
            notes.append(f"（試し）速報レーンへ回す予定: {e['name']} → {e['officialUrl']}")
    pressed = 0
    if not args.dry_run:
        try:
            processed = json.loads((ROOT / "content" / "state.json").read_text("utf-8")).get("processed_web") or {}
        except (OSError, ValueError):
            processed = {}
        pressed = apply_press(state, cfg, now, processed)
        save_state(state, now)
    for note in notes:
        log(f"[incident] {note}")
    text = report_markdown(state, cfg)
    if notes:
        text += "\n**この回の動き**\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    if pressed:
        text += f"\n話題キューに {pressed} 件足しました（公式のお知らせが見つからない事故。報道の決まりで作れるか話題のレーンが確かめます）\n"
    if errors:
        text += "\n読めなかった発信元: " + " / ".join(errors) + "\n"
    _summary(text)
    if args.dry_run:
        print(text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--backfill", action="store_true")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--no-dispatch", action="store_true", help="見つけて state に入れるだけ（速報レーンは起こさない）")
    sub.add_parser("apply-press")
    p_rep = sub.add_parser("report")
    p_rep.add_argument("--markdown", action="store_true")
    args = parser.parse_args()
    if args.cmd == "run":
        return run(args)
    if args.cmd == "apply-press":
        state = load_state()
        print(f"[incident] 話題キューに {apply_press(state, CONFIG, datetime.now(UTC))} 件足しました")
        return 0
    state = load_state()
    print(report_markdown(state) if args.markdown else json.dumps(latency_rows(state), ensure_ascii=False, indent=2))
    return 0


CONFIG = load_config()

if __name__ == "__main__":
    sys.exit(main())
