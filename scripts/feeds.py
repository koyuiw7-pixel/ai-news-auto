#!/usr/bin/env python3
"""公式ブログ・ニュースルーム・プレスリリースの RSS/Atom から記事候補を集める（文章ソース）。

  python3 scripts/feeds.py            # 各フィードの取得件数を表示（API 不要）
  python3 scripts/feeds.py --days 7   # 対象期間を変える

標準ライブラリだけで動く（html.parser / xml.etree）。
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
TEXT_CAP = 12_000

# --------------------------------------------------------------------------- #
# フィード一覧
# --------------------------------------------------------------------------- #
# 2026-10-26 に urllib（UA 付き）で取得・XML 解析できることを確認したものだけを載せる。
#   ai_only=True … AI と無関係な発表も混ざるフィード。タイトル/概要に AI 系の語が無ければ除外
#   priority     … 小さいほど優先（同じ日の候補を並べる順）
# 本文取得の確認: blog.google / deepmind / huggingface / nvidia / microsoft は OK。
#   openai.com も Accept 系ヘッダ付きの urllib なら取得できた（curl の素の UA では 403 のことがある）。
#
# 確認して外したもの（2026-10-26）:
#   Anthropic: /news/rss.xml・/rss.xml・/feed.xml すべて 404（公式 RSS なし。YouTube 側で拾う）
#   Meta AI (ai.meta.com/blog/rss/, /feed/): 400 → 代わりに Meta Newsroom を ai_only で使う
#   Microsoft AI Blog (blogs.microsoft.com/ai/feed/): 410 Gone
#   PR TIMES テクノロジーカテゴリ (prtimes.jp/technology/index.rdf): 404 → 全体の index.rdf を ai_only で使う
#   PR TIMES キーワード検索 RSS: HTML が返る
#   Mistral / xAI / Perplexity / Sakana AI / Preferred Networks / SoftBank / NTT / LINEヤフー: RSS なし or 404/403
#   cloud.google.com AI ブログ RSS: XML でない / Gemini リリースノート: 日付だけの見出しで記事向きでない
#   重複のため不採用: openai.com/blog/rss.xml・ja-JP（news と同内容）、nvidianews（blogs.nvidia と同内容）、
#     azure.microsoft.com/blog（blogs.microsoft.com と同内容）、apple.com/newsroom 英語版（日本版を採用）、
#     japan.googleblog.com（旧 Blogger。blog.google/intl/ja-jp を採用）、blog.research.google（旧URL）
#   二次メディア（ITmedia AI+ 等）は一次情報ではないので対象外
FEEDS: list[dict] = [
    # --- 海外 AI 企業の公式 ---
    {"slug": "openai-news", "name": "OpenAI公式ブログ", "url": "https://openai.com/news/rss.xml", "lang": "en", "priority": 1},
    {"slug": "google-ai-blog", "name": "Google公式ブログ（AI）", "url": "https://blog.google/technology/ai/rss/", "lang": "en", "priority": 1},
    {"slug": "google-gemini-blog", "name": "Google公式ブログ（Gemini）", "url": "https://blog.google/products/gemini/rss/", "lang": "en", "priority": 1},
    {"slug": "google-deepmind-blog", "name": "Google DeepMind公式ブログ", "url": "https://deepmind.google/blog/rss.xml", "lang": "en", "priority": 1},
    {"slug": "google-developers-blog", "name": "Google Developers Blog", "url": "https://developers.googleblog.com/feeds/posts/default", "lang": "en", "priority": 2, "ai_only": True},
    {"slug": "google-research-blog", "name": "Google Research公式ブログ", "url": "https://research.google/blog/rss/", "lang": "en", "priority": 3},
    {"slug": "microsoft-blog", "name": "Microsoft公式ブログ", "url": "https://blogs.microsoft.com/feed/", "lang": "en", "priority": 2, "ai_only": True},
    {"slug": "microsoft-source", "name": "Microsoft Source（ニュースルーム）", "url": "https://news.microsoft.com/source/feed/", "lang": "en", "priority": 2, "ai_only": True},
    {"slug": "microsoft-research-blog", "name": "Microsoft Research Blog", "url": "https://www.microsoft.com/en-us/research/feed/", "lang": "en", "priority": 3},
    {"slug": "nvidia-blog", "name": "NVIDIA公式ブログ", "url": "https://blogs.nvidia.com/feed/", "lang": "en", "priority": 2},
    {"slug": "meta-newsroom", "name": "Metaニュースルーム", "url": "https://about.fb.com/news/feed/", "lang": "en", "priority": 2, "ai_only": True},
    {"slug": "hugging-face-blog", "name": "Hugging Face公式ブログ", "url": "https://huggingface.co/blog/feed.xml", "lang": "en", "priority": 3},
    {"slug": "aws-ml-blog", "name": "AWS Machine Learning Blog", "url": "https://aws.amazon.com/blogs/machine-learning/feed/", "lang": "en", "priority": 3},
    {"slug": "github-changelog-copilot", "name": "GitHub Changelog（Copilot）", "url": "https://github.blog/changelog/label/copilot/feed/", "lang": "en", "priority": 2},
    {"slug": "github-blog", "name": "GitHub公式ブログ", "url": "https://github.blog/feed/", "lang": "en", "priority": 3, "ai_only": True},
    # --- 日本の一次情報 ---
    {"slug": "google-japan-blog", "name": "Google Japan Blog", "url": "https://blog.google/intl/ja-jp/rss/", "lang": "ja", "priority": 1, "ai_only": True},
    {"slug": "microsoft-japan-news", "name": "日本マイクロソフト ニュースセンター", "url": "https://news.microsoft.com/ja-jp/feed/", "lang": "ja", "priority": 1, "ai_only": True},
    {"slug": "apple-newsroom-jp", "name": "Apple Newsroom（日本）", "url": "https://www.apple.com/jp/newsroom/rss-feed.rss", "lang": "ja", "priority": 2, "ai_only": True},
    {"slug": "nvidia-japan-blog", "name": "NVIDIA日本版ブログ", "url": "https://blogs.nvidia.co.jp/feed/", "lang": "ja", "priority": 2},
    {"slug": "aws-japan-blog", "name": "AWS ブログ（日本）", "url": "https://aws.amazon.com/jp/blogs/news/feed/", "lang": "ja", "priority": 3, "ai_only": True},
    {"slug": "prtimes", "name": "PR TIMES", "url": "https://prtimes.jp/index.rdf", "lang": "ja", "priority": 4, "ai_only": True, "title_only": True},
]
FEEDS_BY_SLUG = {f["slug"]: f for f in FEEDS}
# 公式フィードでも SNS 投稿へのリンクが混ざる（Microsoft Source → LinkedIn など）。一次記事でないので除外
BLOCKED_HOSTS = ("linkedin.com", "x.com", "twitter.com", "facebook.com", "instagram.com", "youtube.com", "youtu.be")

# AI 関連かどうかのざっくり判定（ai_only のフィードに使う）
AI_RE = re.compile(
    r"(?<![A-Za-z])(AI|A\.I\.|LLMs?|GPT[-\w]*|Gemini|Gemma|Copilot|Claude|ChatGPT|agents?|agentic|"
    r"machine learning|deep learning|neural|generative|model|inference|Llama|NVIDIA|GPU|robot\w*)(?![A-Za-z])"
    r"|人工知能|生成AI|機械学習|深層学習|大規模言語|言語モデル|エージェント|チャットボット|ロボット|推論",
    re.IGNORECASE,
)

ATOM = "{http://www.w3.org/2005/Atom}"
RSS1 = "{http://purl.org/rss/1.0/}"
DC = "{http://purl.org/dc/elements/1.1/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
MEDIA = "{http://search.yahoo.com/mrss/}"


def log(message: str) -> None:
    print(message, flush=True)


# --------------------------------------------------------------------------- #
# 取得
# --------------------------------------------------------------------------- #


def fetch(url: str, timeout: int = 25, accept: str = "*/*") -> tuple[bytes, str]:
    """(本文バイト列, 最終URL)。gzip 圧縮のまま返すサーバー（deepmind.google 等）にも対応。"""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "gzip, deflate", "Accept-Language": "ja,en;q=0.8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(5_000_000)
        encoding = (response.headers.get("Content-Encoding") or "").lower()
        final_url = response.geturl()
    if data[:2] == b"\x1f\x8b" or encoding == "gzip":
        data = gzip.decompress(data)
    elif encoding == "deflate":
        data = zlib.decompress(data, -zlib.MAX_WBITS)
    return data, final_url


def item_id(url: str) -> str:
    """URL から安定した ID（クエリの utm_* と末尾スラッシュは無視）"""
    parts = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.urlencode(
        [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if not k.lower().startswith("utm_")]
    )
    norm = urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", value or "")
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def parse_feed(feed: dict) -> list[dict]:
    """RSS 2.0 / Atom / RSS 1.0(RDF) を共通形式に。content は全文が入っていれば全文（HTML除去済み）。"""
    data, _ = fetch(feed["url"], accept="application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8")
    root = ET.fromstring(data)
    nodes = root.findall(".//item") or root.findall(f".//{ATOM}entry") or root.findall(f".//{RSS1}item")
    items = []
    for node in nodes:
        def first(*tags):
            for tag in tags:
                el = node.find(tag)
                if el is not None and (el.text or "").strip():
                    return el.text.strip()
            return ""

        title = strip_html(first("title", f"{ATOM}title", f"{RSS1}title"))
        link = first("link", f"{RSS1}link")
        if not link:
            for el in node.findall(f"{ATOM}link"):
                if el.get("rel", "alternate") == "alternate" and el.get("href"):
                    link = el.get("href")
                    break
        if not title or not link:
            continue
        published = _parse_date(first("pubDate", f"{DC}date", f"{ATOM}published", f"{ATOM}updated"))
        summary_raw = first("description", f"{ATOM}summary", f"{RSS1}description")
        content_raw = first(f"{CONTENT}encoded", f"{ATOM}content")
        image = None
        for el in list(node.findall(f"{MEDIA}content")) + list(node.findall(f"{MEDIA}thumbnail")) + list(node.findall("enclosure")):
            url = el.get("url") or ""
            kind = el.get("type") or el.get("medium") or "image"
            if url and "image" in kind:
                image = url
                break
        items.append(
            {
                "id": item_id(link),
                "url": link.strip(),
                "title": title,
                "summary": strip_html(summary_raw)[:600],
                "content": strip_html(content_raw or summary_raw)[:TEXT_CAP],
                "published_at": published,
                "source_name": feed["name"],
                "source_slug": feed["slug"],
                "lang": feed["lang"],
                "image": image,
                "priority": feed.get("priority", 5),
            }
        )
    return items


def is_ai_related(item: dict, title_only: bool = False) -> bool:
    text = item["title"] if title_only else f"{item['title']} {item['summary']}"
    return bool(AI_RE.search(text))


def _norm_title(title: str) -> str:
    return re.sub(r"\W+", "", title.lower())[:60]


def collect(lookback_days: int = 3, state: dict | None = None, feeds: list[dict] | None = None, report: dict | None = None) -> list[dict]:
    """期間内・未処理の候補を返す。優先度→新しい順で、同じ発信元が続かないよう交互に並べる。

    report を渡すと {slug: {"fetched": n, "kept": n, "error": str}} を書き込む。
    """
    state = state or {}
    done = set((state.get("processed_web") or {}).keys())
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    feeds = feeds or FEEDS
    report = report if report is not None else {}

    def load(feed):
        try:
            return feed, parse_feed(feed), ""
        except Exception as error:  # noqa: BLE001 - 1つ落ちても他は続ける
            return feed, [], f"{type(error).__name__}: {str(error)[:120]}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(load, feeds))

    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    per_source: dict[str, list[dict]] = {}
    for feed, items, error in results:
        kept = 0
        for item in items:
            if item["published_at"] is None or item["published_at"] < since:
                continue
            if item["id"] in done or item["id"] in seen_ids:
                continue
            host = urllib.parse.urlsplit(item["url"]).netloc.lower()
            if any(host == h or host.endswith("." + h) for h in BLOCKED_HOSTS):
                continue
            if feed.get("ai_only") and not is_ai_related(item, feed.get("title_only", False)):
                continue
            key = _norm_title(item["title"])
            if key in seen_titles:
                continue
            seen_ids.add(item["id"])
            seen_titles.add(key)
            per_source.setdefault(feed["slug"], []).append(item)
            kept += 1
        report[feed["slug"]] = {"fetched": len(items), "kept": kept, "error": error}

    # 発信元ごとに新しい順 → 優先度の高い発信元から1件ずつ交互に取り出す
    queues = sorted(
        (sorted(v, key=lambda i: i["published_at"], reverse=True) for v in per_source.values()),
        key=lambda q: (q[0]["priority"], -q[0]["published_at"].timestamp()),
    )
    ordered: list[dict] = []
    while any(queues):
        for queue in queues:
            if queue:
                ordered.append(queue.pop(0))
    return ordered


# --------------------------------------------------------------------------- #
# 本文の抽出（簡易リーダビリティ）
# --------------------------------------------------------------------------- #

SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "button", "template", "iframe", "select"}
BLOCK_TAGS = {"p", "div", "section", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "table", "blockquote", "pre", "figure", "figcaption", "article", "main", "dd", "dt"}
VOID_TAGS = {"br", "img", "meta", "link", "input", "hr", "source", "area", "base", "col", "embed", "param", "track", "wbr"}


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.skip_at: int | None = None  # 読み飛ばし中の要素の深さ
        self.buffers = {"body": [], "article": [], "main": []}
        self.in_article = 0
        self.in_main = 0
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key in {"og:image", "og:title", "og:description", "description", "twitter:image"} and attrs.get("content"):
                self.meta.setdefault(key, attrs["content"].strip())
            return
        if tag in VOID_TAGS:
            if tag == "br":
                self._emit("\n")
            return
        self.stack.append(tag)
        cls = (attrs.get("class") or "") + " " + (attrs.get("id") or "")
        hidden = attrs.get("aria-hidden") == "true" or re.search(r"\b(cookie|newsletter|share|related|breadcrumb|subscribe|social)\b", cls, re.I)
        if self.skip_at is None and (tag in SKIP_TAGS or (hidden and tag in {"div", "section", "ul"})):
            self.skip_at = len(self.stack) - 1
        if tag == "article":
            self.in_article += 1
        if tag == "main":
            self.in_main += 1
        if tag in BLOCK_TAGS:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag in VOID_TAGS or tag not in self.stack:
            return
        # 閉じ忘れのタグをまとめて閉じる
        while self.stack:
            top = self.stack.pop()
            if self.skip_at is not None and len(self.stack) <= self.skip_at:
                self.skip_at = None
            if top == "article":
                self.in_article = max(0, self.in_article - 1)
            if top == "main":
                self.in_main = max(0, self.in_main - 1)
            if top in BLOCK_TAGS:
                self._emit("\n")
            if top == tag:
                break

    def handle_data(self, data):
        if self.skip_at is None and data.strip():
            self._emit(data)

    def _emit(self, text):
        if self.skip_at is not None and text != "\n":
            return
        self.buffers["body"].append(text)
        if self.in_article:
            self.buffers["article"].append(text)
        if self.in_main:
            self.buffers["main"].append(text)


def _collapse(parts: list[str]) -> str:
    text = "".join(parts)
    lines = [re.sub(r"[ \t　\xa0]+", " ", line).strip() for line in text.split("\n")]
    # 短すぎる断片（メニュー残骸）を落としつつ段落を保つ
    kept = [line for line in lines if len(line) >= 2]
    return "\n".join(kept).strip()


def _decode(data: bytes) -> str:
    head = data[:4000].decode("ascii", "ignore")
    match = re.search(r"charset=[\"']?([\w-]+)", head, re.I)
    for enc in [match.group(1) if match else None, "utf-8", "cp932", "euc-jp"]:
        if not enc:
            continue
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", "ignore")


def fetch_article_text(url: str) -> dict:
    """{"text", "image", "title", "description", "final_url"}。取得失敗時は例外。"""
    data, final_url = fetch(url, accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
    parser = _Extractor()
    try:
        parser.feed(_decode(data))
        parser.close()
    except Exception:  # noqa: BLE001 - 壊れた HTML でもそこまでの結果を使う
        pass
    candidates = [_collapse(parser.buffers[k]) for k in ("article", "main", "body")]
    text = next((c for c in candidates if len(c) >= 500), max(candidates, key=len))
    image = parser.meta.get("og:image") or parser.meta.get("twitter:image")
    if image:
        image = urllib.parse.urljoin(final_url, html.unescape(image))
    return {
        "text": text[:TEXT_CAP],
        "image": image,
        "title": parser.meta.get("og:title", ""),
        "description": parser.meta.get("og:description") or parser.meta.get("description", ""),
        "final_url": final_url,
    }


# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--text", help="この URL の本文抽出結果を表示して終了")
    args = parser.parse_args()

    if args.text:
        result = fetch_article_text(args.text)
        print(json.dumps({**result, "text": result["text"][:1500], "chars": len(result["text"])}, ensure_ascii=False, indent=2))
        return 0

    report: dict = {}
    items = collect(args.days, {}, report=report)
    log(f"{'slug':28s} {'取得':>5s} {'期間内':>6s}  状態")
    for feed in FEEDS:
        r = report.get(feed["slug"], {})
        status = "NG " + r["error"] if r.get("error") else "OK"
        log(f"{feed['slug']:28s} {r.get('fetched', 0):5d} {r.get('kept', 0):6d}  {status}")
    log(f"\n直近 {args.days} 日の候補: {len(items)} 件")
    for item in items[:15]:
        log(f"  - [{item['source_slug']}] {item['published_at']:%m-%d %H:%M} {item['title'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
