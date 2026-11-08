#!/usr/bin/env python3
"""書く前の下調べ（2026-11-08 オーナー決定・台帳 A64）。

発表の写し書きにしないため、話題から公式・確かなページを 2〜5 本探して読み、事実の束（scripts/facts_bundle.py）に
「調べた公式情報」として出典 URL つきで入れる。記事はそこから使い方・手順・対象の判定・前との比較・注意点を足す。

- 探し方（無料）: Yahoo! JAPAN の検索結果のページを直接取る（鍵も料金も要らない。Jina は使わない）。
  1つの話題で検索は最大2回。結果のうち「確かなページ」だけを読む。
- 確かなページ: 元記事と同じ会社の公式ドメイン（source_links.OFFICIAL_GROUPS）・元記事が張っている会社のドメイン・
  名前の出た会社の公式ドメイン（KNOWN_OFFICIAL）・役所や公的機関（go.jp・lg.jp など）。報道機関・まとめ・知恵袋・ブログは読まない。
- 読んだページは source_links.excerpt で題名の言葉・数字のある行を抜き出す（1本 1,500 字まで）。
- 失敗しても例外にしない（取れたものだけ）。時間の上限 RESEARCH_BUDGET 秒。

  python3 scripts/research.py "ドコモ 顧客情報 流出 対象" [--url 元記事のURL]   # 試し（LLM は呼ばない）
"""

from __future__ import annotations

import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feeds  # noqa: E402
import source_links  # noqa: E402

JST = timezone(timedelta(hours=9))
SEARCH_URL = "https://search.yahoo.co.jp/search?p={q}&ei=UTF-8"
MAX_QUERIES = 2
MAX_PAGES = 3  # 元記事のリンク先（最大2本）と合わせて 2〜5 本
RESEARCH_BUDGET = 25  # 秒
FETCH_TIMEOUT = 8
RESEARCH_EXCERPT_CAP = 1500

# 名前が出たら、その会社の公式ドメインのページを「確かなページ」として読む
KNOWN_OFFICIAL = {
    r"ドコモ|docomo": {"docomo.ne.jp", "nttdocomo.co.jp"},
    r"au\b|KDDI": {"au.com", "kddi.com"},
    r"ソフトバンク|SoftBank": {"softbank.jp", "softbank.co.jp"},
    r"楽天": {"rakuten.co.jp", "rakuten-sec.co.jp", "rakuten-bank.co.jp", "rakuten-card.co.jp"},
    r"PayPay": {"paypay.ne.jp", "paypay-bank.co.jp", "paypay-sec.co.jp"},
    r"LINE": {"line.me"},
    r"メルカリ|メルペイ": {"mercari.com", "merpay.com"},
    r"Amazon|アマゾン": {"amazon.co.jp", "aboutamazon.jp"},
    r"ChatGPT|OpenAI|Sora|Codex": {"openai.com", "chatgpt.com"},
    r"Claude|Anthropic": {"anthropic.com", "claude.com", "claude.ai"},
    r"Gemini|Google|グーグル|YouTube": {"google.com", "blog.google", "gemini.google"},
    r"Copilot|Microsoft|マイクロソフト|Windows": {"microsoft.com"},
    r"Apple|iPhone|iOS|アップル|Mac\b": {"apple.com"},
    r"SBI証券": {"sbisec.co.jp"},
    r"マネックス": {"monex.co.jp"},
    r"ゆうちょ": {"jp-bank.japanpost.jp"},
    r"iDeCo|イデコ": {"ideco-koushiki.jp"},
    r"年金": {"nenkin.go.jp"},
    r"JR東日本|Suica": {"jreast.co.jp"},
    r"トヨタ": {"toyota.jp", "global.toyota"},
}
# 確かなページとみなさない場所（報道・まとめ・質問サイト・検索サービス自身）
NOT_RELIABLE_RE = re.compile(
    r"(?:^|\.)(?:yahoo\.co\.jp|yahoo\.com|yimg\.jp|lycorp\.co\.jp|privacy\.lycorp\.co\.jp|wikipedia\.org|note\.com|ameblo\.jp|"
    r"hatenablog\.com|hatena\.ne\.jp|livedoor\.jp|fc2\.com|prtimes\.jp|atpress\.ne\.jp|value-press\.com|chiebukuro|okwave\.jp|"
    r"twitter\.com|x\.com|facebook\.com|instagram\.com|youtube\.com|tiktok\.com|amazon\.co\.jp/dp)$"
)
GENERIC_WORDS = {
    "発表", "開始", "提供", "公開", "お知らせ", "について", "ついて", "サービス", "対象", "確認", "方法", "可能", "予定", "記事", "ニュース",
    "新た", "大幅", "全国", "一部", "最大", "記念", "スタート", "リリース", "キャンペーン", "プレスリリース", "株式会社", "本日", "今回",
}
# 役所・公的機関の表示名（source_links.SITE_NAMES に無いもの）
PUBLIC_NAMES = {
    "caa.go.jp": "消費者庁", "mlit.go.jp": "国土交通省", "jma.go.jp": "気象庁", "nenkin.go.jp": "日本年金機構", "cfa.go.jp": "こども家庭庁",
    "mext.go.jp": "文部科学省", "ppc.go.jp": "個人情報保護委員会", "npa.go.jp": "警察庁", "fdma.go.jp": "消防庁", "maff.go.jp": "農林水産省",
    "env.go.jp": "環境省", "moj.go.jp": "法務省", "mofa.go.jp": "外務省", "e-gov.go.jp": "e-Gov", "jftc.go.jp": "公正取引委員会",
    "kokusen.go.jp": "国民生活センター", "jpx.co.jp": "日本取引所グループ", "ideco-koushiki.jp": "iDeCo公式サイト",
}
# 起きたことの確認・対象の判定が知りたい話題（リコール・流出・障害）は「対象 確認方法」で探す
CHECK_TOPIC_RE = re.compile(r"リコール|回収|流出|漏えい|漏洩|不正アクセス|障害|不具合|詐欺|なりすまし|改修")
# ニュースの種類ごとの「調べる言葉」（1回目の検索。2回目は「よくある質問」）
INTENT_WORDS = {
    "security": "対象 確認方法",
    "pricing": "料金 プラン",
    "product": "使い方",
    "policy": "対象 条件",
    "money": "対象 条件 手続き",
}


def subject_words(title: str, limit: int = 3) -> list[str]:
    """題名から検索に使う言葉（固有名詞らしい長い言葉を前に）"""
    words = []
    for w in source_links.WORD_RE.findall(title or ""):
        if w in GENERIC_WORDS or w.lower() in source_links.STOP_WORDS or w in words:
            continue
        words.append(w)
    words.sort(key=lambda w: (not re.match(r"[A-Za-zァ-ヶ]", w), -len(w)))
    return words[:limit]


def queries(title: str, news_type: str = "", money: bool = False) -> list[str]:
    words = subject_words(title)
    if not words:
        return []
    subject = " ".join(words)
    if CHECK_TOPIC_RE.search(title or ""):
        intent = INTENT_WORDS["security"]
    else:
        intent = INTENT_WORDS.get("money" if money and news_type not in INTENT_WORDS else news_type, "使い方")
    return [f"{subject} {intent}", f"{subject} よくある質問"][:MAX_QUERIES]


def reliable_domains(source_url: str, title: str, page: dict | None = None, text: str = "") -> set[str]:
    """読んでよい公式のドメイン（base_domain の形）。公的機関（go.jp など）は is_reliable が別に認める"""
    out = set(source_links.official_domains(source_url)) if source_url else set()
    for pattern, domains in KNOWN_OFFICIAL.items():
        if re.search(pattern, f"{title} {(text or '')[:600]}", re.I):
            out |= domains
    # 元記事（発表の配信サービスを含む）が張っている会社のサイト（ソーシャル・ログインなどは除く）
    for link in (page or {}).get("links") or []:
        url = link.get("url") or ""
        if url.startswith("http") and not source_links.SKIP_RE.search(url):
            h = source_links.host(url)
            if h and not NOT_RELIABLE_RE.search(h):
                out.add(source_links.base_domain(h))
    return {d for d in out if d and not NOT_RELIABLE_RE.search(d)}


def is_reliable(url: str, domains: set[str]) -> bool:
    h = source_links.host(url)
    if not h or NOT_RELIABLE_RE.search(h) or source_links.SKIP_RE.search(url):
        return False
    try:
        import public_interest  # noqa: PLC0415 - 報道機関のページは出典にしない（台帳 W31）

        if public_interest.is_press_url(url):
            return False
    except Exception:  # noqa: BLE001
        pass
    return source_links.is_public(url) or source_links.base_domain(h) in domains or any(h.endswith("." + d) for d in domains)


NEWS_PATH_RE = re.compile(r"/(?:news|press|pr|release|releases|newsrelease|topics|campaigns?|cp|event)s?(?:/|$)|/\d{4}/\d{2}/", re.I)
GUIDE_RE = re.compile(r"help|support|faq|guide|qa|howto|how-to|manual|procedure|tetsuzuki|使い方|手続|よくある|ヘルプ|案内|/docs?/|/info/|pric|plan|fee|ryokin|料金", re.I)


def rank(urls: list[str]) -> list[str]:
    """使い方・ヘルプ・料金・手続きのページを先に、ほかの発表・キャンペーンのページを後に（同じ点数は検索の順）"""
    def score(u: str) -> int:
        return (2 if GUIDE_RE.search(u) else 0) + (1 if source_links.is_public(u) else 0) - (2 if NEWS_PATH_RE.search(u) else 0)
    return [u for _, u in sorted(enumerate(urls), key=lambda x: (-score(x[1]), x[0]))]


def same_as_source(got: dict, title: str, source_text: str) -> bool:
    """元記事そのもの（別の URL で配られた同じ発表）か"""
    head = re.sub(r"\s+", "", title or "")[:18]
    if head and head in re.sub(r"\s+", "", got.get("title") or ""):
        return True
    lines = [ln.strip() for ln in (got.get("text") or "").split("\n") if len(ln.strip()) >= 30][:20]
    src = source_text or ""
    return bool(lines) and sum(1 for ln in lines if ln[:30] in src) >= max(3, len(lines) // 2)


def search_links(query: str, timeout: int = FETCH_TIMEOUT) -> list[str]:
    """Yahoo! JAPAN の検索結果の URL（上から順）。取れなければ空"""
    url = SEARCH_URL.format(q=urllib.parse.quote(query))
    data, _ = feeds.fetch(url, timeout=timeout, accept="text/html")
    html = feeds._decode(data)
    out = []
    for href in re.findall(r'href="(https?://[^"#]+)"', html):
        href = href.replace("&amp;", "&")
        h = source_links.host(href)
        if not h or NOT_RELIABLE_RE.search(h) or href in out:
            continue
        out.append(href)
    return out


def site_label(url: str, item: dict, source_url: str) -> str:
    """出典の表示名。名前の分かるドメインはその名前（国税庁・Google公式ヘルプ…）、元記事と同じ会社は元記事の発信元、ほかは「公式サイト（ドメイン）」"""
    h = source_links.host(url)
    for key in (h, source_links.base_domain(h)):
        if key in source_links.SITE_NAMES:
            return source_links.SITE_NAMES[key]
        if key in PUBLIC_NAMES:
            return PUBLIC_NAMES[key]
    if source_url and source_links.base_domain(h) in source_links.official_domains(source_url) and item.get("source_name"):
        return f"{item['source_name']}公式"
    return f"公式サイト（{source_links.base_domain(h)}）"


def research(item: dict, text: str = "", page: dict | None = None, *, news_type: str = "", money: bool = False,
             max_pages: int = MAX_PAGES, skip: set[str] | None = None, searcher=None, fetcher=None, log=None,
             now: datetime | None = None) -> list[dict]:
    """話題から公式・確かなページを探して読む。戻り値は source_links.follow と同じ形
    [{"url", "name", "title", "excerpt", "checkedAt", "public", "research": True}]"""
    if max_pages <= 0:
        return []
    title = item.get("title") or ""
    source_url = item.get("url") or ""
    searcher = searcher or search_links
    fetcher = fetcher or source_links._fetch_page
    domains = reliable_domains(source_url, title, page, text)
    seen = {source_links._norm(u) for u in (skip or set())} | {source_links._norm(source_url)}
    today = (now or datetime.now(JST)).astimezone(JST).strftime("%Y-%m-%d")
    keywords = set(subject_words(title, 6))
    started = time.time()
    out: list[dict] = []
    for q in queries(title, news_type, money):
        if len(out) >= max_pages or time.time() - started > RESEARCH_BUDGET:
            break
        try:
            hits = searcher(q)
        except Exception as error:  # noqa: BLE001 - 検索できなくても記事は作る
            if log:
                log(f"   [research] 検索できません「{q}」（{str(error)[:60]}）")
            continue
        picked = rank([u for u in hits if is_reliable(u, domains) and source_links._norm(u) not in seen])[:max_pages - len(out) + 1]
        if log:
            log(f"   [research] 「{q}」→ 確かなページ {len(picked)} 本（結果 {len(hits)} 本）")
        for url in picked:
            if len(out) >= max_pages or time.time() - started > RESEARCH_BUDGET:
                break
            seen.add(source_links._norm(url))
            try:
                got = fetcher(url, FETCH_TIMEOUT)
            except Exception as error:  # noqa: BLE001
                if log:
                    log(f"   [research] 読めません {url[:80]}（{str(error)[:60]}）")
                continue
            if same_as_source(got, title, text):
                continue
            body = source_links.excerpt(got.get("text") or "", title, keywords, cap=RESEARCH_EXCERPT_CAP)
            if len(body) < 120 or not (keywords & source_links._words(body) or source_links.shared_words(keywords, body)):
                continue  # 話題と関係の薄いページは入れない
            out.append({
                "url": got.get("final_url") or url,
                "name": site_label(url, item, source_url),
                "title": (got.get("title") or "").strip()[:80],
                "excerpt": body,
                "checkedAt": today,
                "public": source_links.is_public(url),
                "research": True,
            })
            if log:
                log(f"   [research] {url[:90]}（{len(body)}字を抜き出し）")
    return out


def main() -> int:
    args = sys.argv[1:]
    url = ""
    if "--url" in args:
        i = args.index("--url")
        url = args[i + 1]
        args = args[:i] + args[i + 2:]
    title = " ".join(args)
    for got in research({"title": title, "url": url}, log=print):
        print(f"\n## {got['name']}「{got['title']}」 {got['url']}\n{got['excerpt'][:600]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
