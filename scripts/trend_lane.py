#!/usr/bin/env python3
"""話題のレーン: 急上昇の言葉（Googleトレンド → state/trend_queue.json）から記事までの道（2026-11-13）。

オーナー 11/13「とにかく数字。それさえ出るなら結構なんでもいい」「注目する話題がとれていない」。
点検（out/strategy_20261110/audit_20261113_pipeline_ja.md）: 急上昇の言葉を7日で456語以上拾っていたのに、記事は0本だった
（報道を出典にできない決まり W31 で道ごと止めていた）。うそを出さない基準は変えずに、道を作る。

1つの言葉について、出典をこの順で探す（scripts/web_articles.py の話題のレーンが呼ぶ）:
  1. 公式のフィードの候補（会社・官公庁の発表）で、題名がその言葉に当たるもの → ふつうの記事と同じ作り方（公式が出典）
  2. 主要な報道機関の記事の中のリンクにある公式ページ（官公庁・自治体・登録済みの公式の発信元）で、本文にその言葉があるもの → 同じく公式が出典
  3. どちらも無いときだけ、主要な報道機関（public_interest.TREND_PRESS_OUTLETS）の独立した2社以上の記事を出典にした記事
     （「NHKなどが報じた」と報道であることを書く。pressReport の印。awaitingOfficial の印で、公式の発表が出たら更新する）
     2026-11-21: 話題の公式のページ（自治体・官公庁など。support_pages）を探して読み、窓口・やることの事実を足して 800字以上を目安にする

ここには通信しない部品（選ぶ・確かめる・指示文）と、主要な報道機関の RSS を読む小さな関数だけを置く。記事の生成・門は web_articles.py。
1日の本数は scripts/ramp.py の TREND_PER_RUN / TREND_DAILY_CAP（審査の期間の「暮らしとお金だけ・1日30本」の外。速報と同じ扱い）。
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import dedupe
import public_interest

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
JST = timezone(timedelta(hours=9))

# 主要な報道機関が自分で出している RSS（見出しと記事の URL。本文は記事ページから読む）。一覧に無い媒体は読まない
PRESS_FEEDS: list[tuple[str, str]] = [
    ("NHK", "https://www.nhk.or.jp/rss/news/cat0.xml"),
    ("NHK", "https://www.nhk.or.jp/rss/news/cat1.xml"),
    ("NHK", "https://www.nhk.or.jp/rss/news/cat3.xml"),
    ("NHK", "https://www.nhk.or.jp/rss/news/cat4.xml"),
    ("NHK", "https://www.nhk.or.jp/rss/news/cat5.xml"),
    ("NHK", "https://www.nhk.or.jp/rss/news/cat6.xml"),
    ("NHK", "https://www.nhk.or.jp/rss/news/cat7.xml"),
    ("朝日新聞", "https://www.asahi.com/rss/asahi/newsheadlines.rdf"),
    ("毎日新聞", "https://mainichi.jp/rss/etc/mainichi-flash.rss"),
    ("時事通信", "https://www.jiji.com/rss/ranking.rdf"),
    ("TBS NEWS DIG", "https://newsdig.tbs.co.jp/list/feed/rss"),
    ("日テレNEWS", "https://news.ntv.co.jp/rss/index.rdf"),
]
PRESS_MAX_AGE = timedelta(hours=48)
PRESS_MIN_CHARS = 400      # 1社の記事として数える本文の長さ
PRESS_SOURCE_CAP = 4000    # 1社あたり指示文に入れる文字数
PRESS_MAX_OUTLETS = 3
PRESS_BODY_MAX = 2000      # 報道が出典の記事の長さの上限の目安（1.5倍を超えたら形の確かめで落とす。2026-11-21 に 1400 → 2000。
                           # 公式の資料〔窓口・やること〕を足して 800字以上にするため。scripts/indexnow.py の SHORT_BODY）
OFFICIAL_MIN_CHARS = 600
COVERED_DAYS = 7           # 同じ言葉・同じ話題の記事がこの日数のうちにあれば作らない
CONSIDER_PER_SLOT = 4      # 1本の枠につき、この数の言葉まで出典を探す（1回の時間を守る）
REFRESH_PER_RUN = 2        # 公式の発表を待っている記事を、1回にこの数まで確かめる


# --------------------------------------------------------------------------- #
# 言葉と題名を当てる（英数字だけの語は語の区切りで。public_interest.contains_term）
# --------------------------------------------------------------------------- #
def norm(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or "")).lower()


def term_tokens(term: str) -> list[str]:
    """急上昇の言葉を当てる語に分ける（調べ方の語・1文字の語は外す。全部外れたら言葉まるごと）"""
    return public_interest.query_terms(term) or [unicodedata.normalize("NFKC", term or "").strip()]


def term_in(term: str, text: str) -> bool:
    """言葉の語が全部（3語以上なら1つ外れてよい）文に出てくるか"""
    tokens = [t for t in term_tokens(term) if t]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if public_interest._term_in(t, text))
    need = len(tokens) if len(tokens) <= 2 else len(tokens) - 1
    return hits >= need


# --------------------------------------------------------------------------- #
# 主要な報道機関の RSS
# --------------------------------------------------------------------------- #
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _when(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


ITEM_BLOCK_RE = re.compile(r"<item\b[^>]*>(.*?)</item>", re.S)
FIELD_RE = re.compile(r"<((?:dc:)?(?:title|link|pubDate|date))\b[^>]*>(.*?)</\1>", re.S)


def parse_press_feed(data: bytes, outlet: str) -> list[dict]:
    """RSS 2.0 / RDF の項目 → {title, url, source, published}。一覧に無いドメインの項目は捨てる"""
    rows: list[dict] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        # 形の崩れた XML（日テレNEWS の RDF など）は、項目ごとに文字として読む
        text = data.decode("utf-8", "replace")
        for block in ITEM_BLOCK_RE.findall(text):
            fields = {k.rsplit(":", 1)[-1]: html.unescape(re.sub(r"^<!\[CDATA\[|\]\]>$", "", v.strip())) for k, v in FIELD_RE.findall(block)}
            rows.append(fields)
    else:
        for el in root.iter():
            if _local(el.tag) != "item":
                continue
            fields = {_local(c.tag): (c.text or "").strip() for c in el}
            fields.setdefault("link", el.attrib.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about") or "")
            rows.append(fields)
    out = []
    for fields in rows:
        url = fields.get("link") or ""
        title = fields.get("title") or ""
        if not title or not public_interest.press_outlet(url):
            continue
        when = _when(fields.get("pubDate") or fields.get("date") or "")
        out.append({"title": title, "url": url, "source": outlet, "published": when.isoformat() if when else None})
    return out


def press_index(fetch, now: datetime | None = None, feeds: list[tuple[str, str]] | None = None) -> list[dict]:
    """主要な報道機関の新しい記事の見出しの索引（48時間以内）。fetch(url) -> bytes | None（失敗した発信元は飛ばす）"""
    now = now or datetime.now(timezone.utc)
    items, seen = [], set()
    for outlet, url in feeds if feeds is not None else PRESS_FEEDS:
        try:
            data = fetch(url)
        except Exception:  # noqa: BLE001 - 1つ読めなくてもほかで続ける
            data = None
        if not data:
            continue
        for item in parse_press_feed(data, outlet):
            when = _when(item.get("published") or "")
            if when and now - when > PRESS_MAX_AGE:
                continue
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            items.append(item)
    return items


def press_candidates(q: dict, index: list[dict], limit: int = 6) -> list[dict]:
    """その言葉を伝えている主要な報道機関の記事（直接の URL だけ）。急上昇の一覧に付いていた報道 → RSS の見出しが当たるもの の順。
    違う報道機関が先に並ぶようにする（独立した2社を早く確かめるため）"""
    term = q.get("title") or ""
    found: list[dict] = []
    for s in q.get("sources") or []:
        outlet = public_interest.press_outlet(str(s.get("url") or ""))
        if outlet:
            found.append({"title": s.get("title") or "", "url": s["url"], "source": outlet, "published": s.get("published")})
    for item in index:
        if term_in(term, item["title"]):
            found.append(dict(item))
    seen_url, by_outlet = set(), {}
    for item in found:
        if item["url"] in seen_url:
            continue
        seen_url.add(item["url"])
        by_outlet.setdefault(item["source"], []).append(item)
    ordered: list[dict] = []
    depth = 0
    while len(ordered) < limit and any(len(v) > depth for v in by_outlet.values()):
        for outlet in list(by_outlet):
            if len(by_outlet[outlet]) > depth and len(ordered) < limit:
                ordered.append(by_outlet[outlet][depth])
        depth += 1
    return ordered


def independent(fetched: list[dict], limit: int = PRESS_MAX_OUTLETS) -> list[dict]:
    """本文の読めた記事から、報道機関ごとに1本ずつ（独立した出典）。一覧に無い媒体・短すぎる本文は数えない"""
    out, seen = [], set()
    for s in fetched:
        outlet = public_interest.press_outlet(str(s.get("url") or ""))
        if not outlet or outlet in seen or len(s.get("text") or "") < PRESS_MIN_CHARS:
            continue
        seen.add(outlet)
        out.append({**s, "source": outlet})
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------- #
# 2社が同じ中心の事実を伝えているか（機械で確かめられる範囲。生成のあとは品質の門の事実確認が資料と照合する）
# --------------------------------------------------------------------------- #
NUMBER_RE = re.compile(r"\d[\d,.]*\s?(?:兆|億|万|千)?(?:円|人|名|件|社|台|本|%|％|ドル|歳|年|月|日|時|分|倍|点|勝|敗|号|位)")


def anchors(text: str) -> set[str]:
    """文の中の固有名詞と数（2社の記事が同じ出来事を書いているかを見る目印）"""
    text = unicodedata.normalize("NFKC", text or "")
    nums = {re.sub(r"[\s,]", "", m.group(0)) for m in NUMBER_RE.finditer(text)}
    return {e for e in dedupe.entities(text) if len(e) >= 3} | nums


def agreement(term: str, chosen: list[dict]) -> tuple[bool, str]:
    """独立した2社以上が、その言葉の同じ出来事を伝えているか。(可否, 理由)
    1) 2社以上の記事（見出しか本文の頭）にその言葉がある  2) その2社の本文に、共通の固有名詞・数が2つ以上ある"""
    on_topic = [s for s in chosen if term_in(term, f"{s.get('title') or ''} {(s.get('text') or '')[:1500]}")]
    if len({s["source"] for s in on_topic}) < public_interest.TREND_PRESS_MIN_OUTLETS:
        return False, f"この言葉を伝えている主要な報道機関が{len({s['source'] for s in on_topic})}社（2社以上が必要）"
    sets = [anchors(f"{s.get('title') or ''} {(s.get('text') or '')[:PRESS_SOURCE_CAP]}") for s in on_topic]
    best = max(len(a & b) for i, a in enumerate(sets) for b in sets[i + 1:])
    if best < 2:
        return False, "2社の記事に共通の固有名詞・数が足りない（同じ出来事と確かめられない）"
    return True, ""


def agreed(term: str, chosen: list[dict]) -> list[dict]:
    """その言葉を伝えている記事だけ（agreement が通ったあと、指示文と出典の欄に使う）"""
    return [s for s in chosen if term_in(term, f"{s.get('title') or ''} {(s.get('text') or '')[:1500]}")]


# --------------------------------------------------------------------------- #
# 公式のページ（報道の記事の中のリンクから）
# --------------------------------------------------------------------------- #
GOV_SUFFIXES = (".go.jp", ".lg.jp")
# 地方公共団体の都道府県型・地域型のドメイン（pref.〇〇.jp・city.〇〇.〇〇.jp など。JPRS が地方公共団体だけに割り当てる名前）。
# 2026-11-21: 前橋市（city.maebashi.gunma.jp）のように .lg.jp でない自治体の公式ページを読めていなかった
LOCAL_GOV_RE = re.compile(r"^(?:www\.)?(?:pref|city|town|vill)\.[a-z0-9-]+(?:\.[a-z0-9-]+)?\.jp$")
ORG_TYPE_JP_RE = re.compile(r"\.(?:co|ne|or|ac|ad|ed|gr)\.jp$")  # 属性型（会社・団体など）は地方公共団体の名前ではない


def local_gov_host(host: str) -> bool:
    """地方公共団体のドメインか（pref.gunma.jp・city.maebashi.gunma.jp。city.example.co.jp のような属性型は外す）"""
    host = (host or "").lower().split(":")[0]
    return bool(LOCAL_GOV_RE.match(host)) and not ORG_TYPE_JP_RE.search(host)


def link_only_sources(q: dict, limit: int = 2) -> list[dict]:
    """公式のリンクを探すためだけに読む記事（急上昇の一覧に付いていた、主要な報道機関の一覧に無い媒体の記事）。出典にはしない"""
    out = []
    for s in q.get("sources") or []:
        url = str(s.get("url") or "")
        host = urllib.parse.urlsplit(url).netloc.lower()
        if not url or host.endswith("news.google.com") or public_interest.press_outlet(url):
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def official_hosts(feeds_module, fast_rules: dict | None = None) -> set[str]:
    """登録済みの公式の発信元（官公庁・会社自身。配信・他社の告知・報道は除く）のドメイン。
    fast_rules（scripts/fast_lane_rules.json）を渡すと、速報レーンの発信元とレーダーの一次情報のドメインも足す"""
    hosts = set()
    for src in (fast_rules or {}).get("sources") or []:
        host = urllib.parse.urlsplit(str(src.get("url") or "")).netloc.lower().removeprefix("www.")
        if host and not public_interest.is_press_url(str(src.get("url") or "")):
            hosts.add(host)
    for h in ((fast_rules or {}).get("radar") or {}).get("primary_hosts") or []:
        if h.get("host"):
            hosts.add(str(h["host"]).lower().removeprefix("www."))
    for feed in list(getattr(feeds_module, "FEEDS", [])) + list(getattr(feeds_module, "BROAD_FEEDS", [])):
        if feed.get("kind") not in public_interest.PRIMARY_KINDS:
            continue
        host = urllib.parse.urlsplit(str(feed.get("url") or "")).netloc.lower().removeprefix("www.")
        if host:
            hosts.add(host)
    return hosts


def is_official_url(url: str, hosts: set[str]) -> bool:
    """公式の一次情報のページか（https・官公庁/自治体か登録済みの公式の発信元・トップページではない・報道ではない）"""
    try:
        parts = urllib.parse.urlsplit((url or "").strip())
    except ValueError:
        return False
    if parts.scheme != "https" or not parts.netloc or len(parts.path.strip("/")) < 2:
        return False
    if public_interest.is_press_url(url) or public_interest.press_outlet(url):
        return False
    host = parts.netloc.lower().split(":")[0].removeprefix("www.")
    if host.endswith(GOV_SUFFIXES) or local_gov_host(host):
        return True
    return any(host == h or host.endswith("." + h) for h in hosts)


def official_links(pages: list[dict], hosts: set[str], limit: int = 3) -> list[str]:
    """報道の記事ページのリンクのうち、公式のページ（重複なし・先に出たもの順）"""
    out: list[str] = []
    for page in pages:
        for link in page.get("links") or []:
            url = link.get("url") if isinstance(link, dict) else str(link)
            if url and url not in out and is_official_url(url, hosts):
                out.append(url)
                if len(out) >= limit:
                    return out
    return out


def official_page_ok(term: str, page: dict) -> bool:
    """読んだ公式のページが、その言葉の話か（本文が十分あり、題名か本文の頭にその言葉がある）"""
    text = page.get("text") or ""
    return len(text) >= OFFICIAL_MIN_CHARS and term_in(term, f"{page.get('title') or ''} {text[:4000]}")


def feed_candidate(term: str, pool: list[dict]) -> dict | None:
    """公式のフィードの候補のうち、題名がその言葉に当たるもの（新しい順）。発信元の名前だけで当たるものは数えない"""
    hits = [i for i in pool if public_interest.trend_hit(i.get("title") or "", [{"title": term}], i.get("source_name") or "")]
    hits.sort(key=lambda i: i.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return hits[0] if hits else None


# --------------------------------------------------------------------------- #
# 報道が出典の記事に添える「公式の資料」（2026-11-21 オーナー承認・AdSense の3回目の申請の準備）
# 報道の記事は、報道2社の共通の事実だけで書くと 300〜700字で終わっていた（11/20 の報道の記事17本が800字未満・検索に出ない）。
# 話題の公式のページ（自治体・官公庁・登録済みの公式の発信元）を探して読み、窓口・連絡先・やること・制度の説明の事実を足す。
# 出典（sources）は報道のまま（W31 の例外の形）。公式の資料は factSources に残し、品質の門の事実確認の資料にも入れる。
# --------------------------------------------------------------------------- #
SUPPORT_MAX = 2            # 1本の記事に添える公式の資料の数
SUPPORT_MIN_CHARS = 200    # 読んだ公式のページの本文の下限
SUPPORT_CAP = 2500         # 1ページあたり指示文・事実確認の資料に入れる字数
SUPPORT_LABEL = "公式の資料"


def support_queries(term: str) -> list[str]:
    """公式の資料を探す検索の言葉（調べ方の語〔今日・最新など〕は外した言葉＋「公式」/「問い合わせ」。2回まで）。
    1文字の語（「熊」）も検索には残す（当てる語の term_tokens は1文字の語を外す）"""
    words = [x for x in re.split(r"[\s　、,・/]+", unicodedata.normalize("NFKC", term or "").strip()) if x]
    subject = " ".join(x for x in words if x not in public_interest.QUERY_FILLER and x.lower() not in public_interest.QUERY_FILLER)
    return [f"{subject} 公式", f"{subject} 問い合わせ 窓口"] if subject else []


def support_ok(term: str, page: dict) -> bool:
    """読んだ公式のページが、その言葉の話か（本文が SUPPORT_MIN_CHARS 字以上・題名か本文の頭にその言葉がある）。
    今回の出来事の発表でなくてよい（窓口・やること・制度の説明のページ）。古い数字を今回のことにしない決まりは指示文に書く"""
    text = page.get("text") or ""
    return len(text) >= SUPPORT_MIN_CHARS and term_in(term, f"{page.get('title') or ''} {text[:6000]}")


def support_pages(term: str, hosts: set[str], *, pages: list[dict] | None = None, search=None, fetch=None,
                  skip: set[str] | None = None, limit: int = SUPPORT_MAX, deadline: float | None = None, log=None) -> list[dict]:
    """[{url, name, title, text}]。①すでに読んだ公式のページ（報道の中のリンク）→ ②検索（search(query) -> [url]）で見つけた公式のページ。
    公式のページ（is_official_url）で、その言葉の話のものだけ。fetch(url) -> {title, text, final_url}。失敗しても例外にしない"""
    import time  # noqa: PLC0415

    out: list[dict] = []
    seen = {u for u in (skip or set())}

    def add(url: str, page: dict) -> None:
        final = str(page.get("final_url") or url)
        if final in seen and url in seen:
            return
        seen.update({url, final})
        if not is_official_url(final, hosts) or not support_ok(term, page):
            return
        host = urllib.parse.urlsplit(final).netloc.lower().removeprefix("www.")
        title = re.sub(r"\s+", " ", str(page.get("title") or "")).strip()
        out.append({"url": final, "title": title[:80], "name": (title.split("｜")[-1].split("|")[-1].strip() or host)[:40],
                    "host": host, "text": str(page.get("text") or "")[:SUPPORT_CAP]})

    for row in pages or []:
        if len(out) >= limit:
            return out
        if row.get("url") and row.get("page"):
            add(str(row["url"]), row["page"])
    if search is None or fetch is None:
        return out
    for query in support_queries(term):
        if len(out) >= limit or (deadline and time.time() > deadline):
            break
        try:
            hits = search(query) or []
        except Exception as error:  # noqa: BLE001 - 検索できなくても記事は作る
            if log:
                log(f"   [support] 検索できません（{str(error)[:60]}）")
            continue
        picked = [u for u in hits if u not in seen and is_official_url(u, hosts)][:limit + 1]
        if log:
            log(f"   [support] 「{query}」→ 公式のページ {len(picked)} 本（結果 {len(hits)} 本）")
        for url in picked:
            if len(out) >= limit or (deadline and time.time() > deadline):
                break
            try:
                page = fetch(url) or {}
            except Exception as error:  # noqa: BLE001
                if log:
                    log(f"   [support] 読めません {url[:80]}（{str(error)[:60]}）")
                seen.add(url)
                continue
            add(url, page)
    return out


def support_block(pages: list[dict]) -> str:
    """指示文に入れる公式の資料の欄"""
    if not pages:
        return ""
    parts = [f"## 公式{n}: {p['name']}「{p['title']}」\nURL: {p['url']}\n<<<\n{p['text']}\n>>>" for n, p in enumerate(pages, 1)]
    return ("\n\n# 公式の資料（自治体・官公庁・会社の公式ページ。窓口・やること・制度の説明のために読んだもの）\n"
            + "\n\n".join(parts))


def support_source_text(pages: list[dict]) -> str:
    """品質の門の事実確認に渡す資料（報道の資料のあとに足す）"""
    return "\n\n".join(f"【{SUPPORT_LABEL}: {p['name']}】{p['title']}\n{p['url']}\n{p['text']}" for p in pages)


def support_fact_sources(pages: list[dict], now: datetime | None = None) -> list[dict]:
    """記事末の「出典と更新履歴」に出す確かめた資料（lib/articles.ts の FactSource の形）"""
    day = (now or datetime.now(JST)).astimezone(JST).strftime("%Y-%m-%d")
    return [{"label": SUPPORT_LABEL, "name": p["name"], "url": p["url"], "checkedAt": day} for p in pages]


# --------------------------------------------------------------------------- #
# 重複（直近7日）
# --------------------------------------------------------------------------- #
def covered_terms(days: int = COVERED_DAYS, articles_dir: Path | None = None, now: datetime | None = None) -> dict[str, str]:
    """直近 days 日の記事が扱った急上昇の言葉（trendKeyword / searchTrend）→ slug"""
    since = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    out: dict[str, str] = {}
    for path in sorted((articles_dir or ARTICLES_DIR).glob("*.json")):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        when = dedupe._article_time(data)
        if when is None or when < since:
            continue
        for key in ("trendKeyword", "searchTrend"):
            if data.get(key):
                out.setdefault(norm(str(data[key])), path.stem)
    return out


def awaiting_official(days: int = COVERED_DAYS, articles_dir: Path | None = None, now: datetime | None = None) -> list[tuple[Path, dict]]:
    """公式の発表を待っている報道の記事（awaitingOfficial の印。直近 days 日）"""
    since = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    out = []
    for path in sorted((articles_dir or ARTICLES_DIR).glob("*.json")):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        when = dedupe._article_time(data)
        if data.get("awaitingOfficial") and data.get("trendKeyword") and when and when >= since:
            out.append((path, data))
    return out


def mark_official_found(record: dict, url: str, now: datetime | None = None) -> dict:
    """公式の発表で更新した記事の印（待ちを外し、いつ・どのページで確かめたかを残す）"""
    record["awaitingOfficial"] = False
    record["officialSourceUrl"] = url
    record["officialConfirmedAt"] = (now or datetime.now(timezone.utc)).isoformat()
    return record


# --------------------------------------------------------------------------- #
# 1日の本数（processed_web の trendLane の印）
# --------------------------------------------------------------------------- #
def done_today(state: dict, now: datetime | None = None) -> int:
    today = (now or datetime.now(JST)).astimezone(JST).date()
    n = 0
    for rec in (state.get("processed_web") or {}).values():
        if not isinstance(rec, dict) or not rec.get("trendLane") or not rec.get("slug"):
            continue
        try:
            at = datetime.fromisoformat(str(rec.get("at") or ""))
        except ValueError:
            continue
        if (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(JST).date() == today:
            n += 1
    return n


# --------------------------------------------------------------------------- #
# 指示文と、できた記事の確かめ
# --------------------------------------------------------------------------- #
# 題名（どの出典の記事にも）: 検索される言葉＋読者が知りたいこと。形は毎回変える。本文に無い約束をしない。「｜」は使わない
TITLE_SHAPES = (
    "言葉＋いつ（例「〇〇、受付は12月1日から」）",
    "言葉＋いくら（例「〇〇は月額980円に　今の契約はどうなる」）",
    "言葉＋何をすればいいか（例「〇〇の対象か確かめる方法」）",
    "言葉＋何が起きたか（例「〇〇で通信障害　復旧の見通しは」）",
    "言葉＋だれに関係するか（例「〇〇、会社員の手取りはこう変わる」）",
)


def title_note(term: str, seed: str = "") -> str:
    """話題のレーンの題名の書き方（検索される言葉を先頭に・読者が知りたいこと・形を変える・本文に無いことを約束しない）"""
    start = sum(ord(c) for c in (seed or term)) % len(TITLE_SHAPES)
    shapes = [TITLE_SHAPES[(start + i) % len(TITLE_SHAPES)] for i in range(3)]
    return (
        "\n\n## 題名の書き方（話題のレーン。必ず守る）\n"
        f"- いま「{term}」が検索で急上昇しています。題名はこの言葉（中心の語）から始め、続けて読者がいちばん知りたいこと"
        "（いつ・いくら・何をすればいいか・何が起きたか）を書く。\n"
        f"- 形の例（資料に答えがあるものを1つ選ぶ。毎回同じ形にしない）: {' / '.join(shapes)}\n"
        "- 題名で言ったこと（日付・金額・やり方・対象）は、必ず本文で答える。資料に答えが無いことを題名で約束しない・問いにしない。\n"
        "- 「｜」（縦棒）は使わない。【速報】は付けない。大げさな言葉（衝撃・ついに・必見）で始めない。"
    )


# 報道が出典の記事の編集ルール（web_articles の TREND_SOURCE_NOTE に入れる。trends.EDITORIAL_RULES から「軸の話題だけ」の決まりを外したもの）
PRESS_RULES = """1. 冒頭で「何が報じられたか」を書く。きっかけ（発表・発売・料金改定・障害・制度変更・試合・放送など）を、渡された報道にある事実だけで説明する。
2. 次に「読者に関係すること」（いつ・いくら・何をすればいいか・次に何が起きるか）を、報道にある範囲で書く。
3. 事実は渡された報道（sources）の2社以上が共通して伝えている内容だけを使う。数値・日付・固有名詞は報道からそのまま取り、
   「〇〇（媒体名）によると」と出典を示す。報道の間で食い違う点は食い違いとして書く。報道に無い情報を推測で補わない。
4. 個人について推測しない。人物の意図・内心・私生活・責任の所在を憶測で書かない。私人の名前は書かない。
5. 煽らない。「衝撃」「ヤバい」「〇〇終了」「知らないと損」などの釣り見出し・不安を煽る表現は使わない。
6. 投資・お金の話題では売買の推奨をしない。相場の先行きを断定しない。"""

RELEVANT_NOTE = """

# この話題を記事にするか（話題のレーンの決まり。上の is_relevant の決まりより優先する）
この言葉は、いま日本で検索が急上昇している話題です。スポーツ・エンタメ・政策・海外の話題など、分野を理由に対象外にしないでください。
- is_relevant を false にするのは次のときだけ: 資料で中心の事実を確かめられない／確かめようのないうわさ・憶測が中心／
  私人（公人でない人）や事件の被害者にかかわる話／訃報／アダルト・ギャンブル（競馬などの予想を含む）／選挙・政党の話。
- そのときは skip_reason に理由を具体的に書く。資料で確かめられない所が一部だけなら、その所を書かずに記事にする。
- 私人の名前は書かない。人物の内心・私生活・責任の所在を推測しない。"""

PRESS_NOTE = """

# 出典は報道です（話題のレーンの決まり。必ず守る）
この話題は、公式の発表（会社・官公庁のページ）がまだ見つかっていません。資料は主要な報道機関 {outlets} の記事です。
- リードの1文目と本文の最初の段落で「{lead}などが報じた」「{lead}によると」のように、報道が出典であることを書く。公式の発表として断定しない。
- 今回の出来事の事実（何が・いつ・どこで・どのくらい）は、資料の2社以上の報道が共通して伝えていることだけ。1社だけが伝えていること・見立て・関係者の話は書かない。
  報道の間で食い違う点は、食い違いとして「{lead}は〜、△△は〜と伝えている」と書く。
- 資料に無い事実・数・日付・発言・背景は書かない。分からないことは「公式の発表はまだ確認できていない」と書く。
- 報道の文を書き写さない（引用は30字以内を「」で）。自分の言葉でまとめる。
{support}
- 長さ: 本文は900〜1,600字を目安にする。ただし水増ししない（同じことのくり返し・一般論・だれにでも当てはまる注意・資料に無い背景で長くしない）。
  材料は、報道にある日時・場所・数字・経緯と、公式の資料にある窓口・やること・制度の説明。
- 章は3〜5つ。中身に合わせた見出しにする（決まり文句の見出しにしない）。入れる中身: 何が報じられたか／詳しい経緯と数字／
  読者に関係すること・何をすればいいか／「## サイソクの見方」／まだ分かっていないこと（最後）。
- 「## サイソクの見方」は1〜3文。報道と公式の資料の事実から言えること（前との違い・見落としやすい点・だれに関係が大きいか・判断の目安）だけ。
  資料に無い予測・見込み（「〜だろう」「〜でしょう」「見込まれる」「期待される」「可能性がある」「注目される」）は書かない。
- 題名は確定した事実のように言い切らない（「〜と報道」「〜か」「NHKなど」のいずれかを入れる）。【速報】は付けない。
- verdict は null、faq は空にする。"""

PRESS_SUPPORT_NOTE = """- 下の「公式の資料」（自治体・官公庁・会社の公式ページ）にある事実は、「〇〇（公式サイト）によると」と出典を示して書いてよい
  （窓口・電話番号・受付時間・URL・呼びかけ・やること・制度の説明・これまでの件数）。URL・電話番号は資料にあるものだけ書く。
- 公式の資料は、今回の出来事の発表とは限らない。今回の出来事の事実は報道のとおりに書き、公式の資料の古い日付・数字を今回のことのように書かない。
- 「読者に関係すること・何をすればいいか」の章に、公式の資料の窓口・確かめ方・URL を入れる。"""

PRESS_NO_SUPPORT_NOTE = """- 公式の資料（窓口・連絡先のページ）は見つかっていない。窓口・電話番号・URL は書かない（作らない）。読者に関係することは報道にある範囲で書く。"""

# 書き足し・「サイソクの見方」の章の追加（scripts/own_view.py の ensure）に足す決まり（報道が出典の記事。2026-11-21）
PRESS_EXPAND_NOTE = """# この記事は報道が出典です（必ず守る）
- 資料のうち【公式の資料: …】以外は主要な報道機関の記事。今回の出来事の事実は、2社以上の報道が共通して伝えていることだけを「〇〇によると」と出典を示して書く。1社だけが伝えていることは足さない。
- 【公式の資料: …】の事実（窓口・連絡先・URL・やること・制度の説明）は「〇〇（公式サイト）によると」と書いてよい。古い日付・数字を今回の出来事のことのように書かない。
- リードと本文の最初の段落の「〇〇などが報じた」「〇〇によると」は消さない。「サイソクの見方」に予測・見込み（だろう・見込まれる・期待される・可能性がある）を書かない。"""

PRESS_DISCLAIMER = (
    "本記事は複数の報道（{outlets}）をもとにAIが要約して自動生成したものです。公式の発表はまだ確認できていません。"
    "発表が出たら内容を更新します。正確な情報は元の報道と、今後の公式発表をご確認ください。"
)
PRESS_LABEL = "報道ベース・公式発表は未確認"
TITLE_HEDGE_RE = re.compile(r"報道|報じ|か$|か[　 、]|NHKなど|とみられ|見通し|方針|検討|伝え")


def press_note(chosen: list[dict], support: list[dict] | None = None) -> str:
    """報道が出典の記事の指示（support は support_pages の公式の資料。あれば指示のあとに資料の欄を付ける）"""
    names = list(dict.fromkeys(s["source"] for s in chosen))
    note = PRESS_NOTE.format(outlets="・".join(names), lead=names[0], support=PRESS_SUPPORT_NOTE if support else PRESS_NO_SUPPORT_NOTE)
    return note + support_block(support or [])


def press_fields(record: dict, term: str, chosen: list[dict], now: datetime | None = None) -> dict:
    """報道が出典の記事の印と出典の欄（公開前の門 public_interest.trend_press_ok が見る）"""
    names = list(dict.fromkeys(s["source"] for s in chosen))
    record.update({
        "channel": "話題のニュース", "channelSlug": "trends", "trendKeyword": term,
        "pressReport": True, "awaitingOfficial": True, "factStatus": PRESS_LABEL,
        "pressCheckedAt": (now or datetime.now(timezone.utc)).isoformat(),
        "sources": [{"title": s.get("title", ""), "url": s["url"], "source": s["source"]} for s in chosen],
        "sourceUrl": chosen[0]["url"], "sourceName": "・".join(names[:2]) + (" ほか" if len(names) > 2 else ""),
        "disclaimer": PRESS_DISCLAIMER.format(outlets="・".join(names)),
        "verdict": None,
    })
    record.pop("faq", None)
    record.pop("todayActions", None)
    return record


def press_record_problems(record: dict) -> list[str]:
    """報道が出典の記事の形の確かめ（うそにつながるものだけ）: 報道と書いているか・題名で言い切っていないか・長すぎないか・「｜」"""
    problems = []
    title = str(record.get("title") or "")
    lede_body = f"{record.get('lede') or ''}\n{record.get('body') or ''}"
    head = lede_body[:400]
    if not public_interest.PRESS_ATTRIBUTION_RE.search(head):
        problems.append("リードか本文の最初の段落に、報道が出典であること（「〇〇などが報じた」「〇〇によると」）が書かれていない")
    if not TITLE_HEDGE_RE.search(title):
        problems.append("題名が報道の内容を確定した事実のように言い切っている（「〜と報道」「NHKなど」「〜か」のいずれかを入れる）")
    if "｜" in title or "|" in title:
        problems.append("題名に「｜」がある（使わない）")
    if "【速報】" in title:
        problems.append("題名に【速報】がある（報道が出典の記事には付けない）")
    if len(str(record.get("body") or "")) > PRESS_BODY_MAX * 1.5:
        problems.append(f"本文が長すぎる（{len(str(record.get('body') or ''))}字。報道が出典の記事は{PRESS_BODY_MAX}字ほどまで）")
    if not public_interest.trend_press_ok(record):
        problems.append("出典が主要な報道機関の独立した2社以上になっていない（W31 の例外の形ではない）")
    return problems


def title_problems(record: dict, term: str) -> list[str]:
    """話題のレーンの題名の確かめ（公式が出典の記事にも）: 「｜」を使わない・急上昇の言葉の語が題名にある"""
    title = str(record.get("title") or "")
    problems = []
    if "｜" in title or "|" in title:
        problems.append("題名に「｜」がある（使わない）")
    if not any(public_interest._term_in(t, title) for t in term_tokens(term)):
        problems.append(f"題名に、検索されている言葉「{term}」の語が入っていない")
    return problems
